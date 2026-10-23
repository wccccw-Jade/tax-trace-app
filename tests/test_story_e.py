"""Story E: true blockers, exact-draft approval, frozen rejected/accepted copies and branches."""
import hashlib
import json
from io import BytesIO
from zipfile import ZipFile
from decimal import Decimal
import pytest
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from backend.persistence.models import Record,FilingSnapshot
from backend.domain.filing import branch,state,current_lines,resolution_fingerprint,AUTO_STEPS
from backend.domain.workpaper import evidence_graph
from test_story_a import story,identity,claim
from test_story_b import propose_business,check_business,decide as approve_business
from test_story_c import decision,verify_value,review_decision

ROOT='filing:original'


def view(client,ref=ROOT):
    r=client.get('/api/filing',params={'ref':ref})
    assert r.status_code==200,r.text
    return r.json()


def start(client):
    identity(client,'st-01')
    r=client.post('/api/filing/start')
    assert r.status_code==200,r.text
    return view(client)


def test_only_prepare_full_scope(client,engine,packet):
    """Synthetic test setup, not a product action: explicitly reviewed support for every remaining item.

    No UI/API can mark the whole return ready. Full-scope proofs below are created only inside the
    isolated test schema to reach later state transitions without hundreds of manual form entries.
    E3 and E4 still use their real proposal/verification/independent-review endpoints.
    """
    identity(client,'st-01')
    with Session(engine) as db,db.begin():
        for r in db.scalars(select(Record).where(Record.kind=='document')):
            if r.ref not in {'D71','D72'}:
                r.payload={**r.payload,'disposition':'used','disposition_reason':'SYNTHETIC TEST SETUP — scope accounted for.','disposition_actor':'st-01','preparers':['st-01']}
                r.revision+=1
    change=check_business(client) if claim(client,'v3:SchC.1')['adjustments'] else None
    if not change:
        propose_business(client)
        change=check_business(client)
    identity(client,'st-03')
    assert approve_business(client,change).status_code==200
    identity(client,'st-01')
    d=decision(client,'v3:F8283.A1.vehicle',['doc:D66#page1','call-01'])
    verify_value(client,'v3:F8283.A1.vehicle',['doc:D66#page1','call-01'])
    identity(client,'st-02')
    assert review_decision(client,d,'v3:F8283.A1.vehicle').status_code==200
    with Session(engine) as db,db.begin():
        row=branch(db,packet,ROOT)
        lines,_,_=current_lines(db,packet,row)
        records,_=evidence_graph(db,packet)
        current=state(db,packet,row)
        targets=[(c['ref'],c['value']) for c in current['claims'] if not c['done']]
        targets.extend((i['ref'],i['value']) for i in current['issues'])
        for i,(target,value) in enumerate(targets):
            evidence=['doc:D01#page1']
            fp=resolution_fingerprint(records,target,value,evidence)
            db.add(Record(packet_id=packet.digest,ref='synthetic-proof:'+str(i),kind='filing_resolution',payload={
                'branch_ref':ROOT,'target':target,'value':value,'evidence':evidence,'fingerprint':fp,
                'authority':'Synthetic acceptance-test setup; not a tax conclusion.','conclusion':'Synthetic reviewed test disposition.',
                'rationale':'Only to exercise later filing state transitions in an isolated test schema.','actor_id':'st-01','at':'2026-07-10T18:00:00Z',
                'resolved_amount':None,'reasoned_none':target=='diagnostic:CA_AMT_NOT_COMPUTED',
                'review':{'decision':'approved','actor_id':'st-02','fingerprint':fp},'review_history':[]}))
        # Explicit synthetic coverage for Day 7–8 scope gates, isolated to this test schema.
        from backend.domain.breadth import OUTSIDE,VIEWS
        for item in OUTSIDE:
            if not db.scalar(select(Record).where(Record.ref=='outside:'+item['id'])):
                db.add(Record(packet_id=packet.digest,ref='outside:'+item['id'],kind='outside_filing',payload={'owner':'Synthetic test owner','status':'communicated','note':'SYNTHETIC TEST SETUP — responsibility communicated.','actor_id':'st-01'}))
        for key in [*VIEWS,'business','sales']:
            if not db.scalar(select(Record).where(Record.ref=='area:'+key)):
                db.add(Record(packet_id=packet.digest,ref='area:'+key,kind='area_review',payload={'status':'reviewed','note':'SYNTHETIC TEST SETUP — area considered.','actor_id':'st-01'}))
        steps={s:{'actor_id':'st-01','evidence':['D01'],'note':'Synthetic test-only completed step.','at':'2026-07-10T18:00:00Z'} for s in packet.data['firm']['starter_standards']['required_steps'] if s not in AUTO_STEPS}
        row.payload={**row.payload,'steps':steps}
        row.revision+=1
    identity(client,'st-01')
    current=view(client)
    assert current['technical_ready'],current['blockers'][:8]
    return current


# This is a setup helper, not a pytest test.
test_only_prepare_full_scope.__test__=False


def sign_and_authorize(client,ref=ROOT):
    for actor,kind in [('st-02','reviewer'),('st-03','partner'),('st-03','final_computation')]:
        identity(client,actor)
        current=view(client,ref)
        r=client.post('/api/filing/signoffs',params={'ref':ref},json={'expected_revision':current['revision'],'fingerprint':current['fingerprint'],'kind':kind,
            'note':'Independently reviewed this exact revision; accept estimated computation for simulated filing, including largest contributors and affected-line limitations.'})
        assert r.status_code==200,r.text
    for actor in ['cu-01','cu-02']:
        identity(client,actor)
        current=view(client,ref)
        assert current['can_authorize']
        r=client.post('/api/filing/authorize',params={'ref':ref},json={'expected_revision':current['revision'],'fingerprint':current['fingerprint'],'authorize':True})
        assert r.status_code==200,r.text
    identity(client,'st-01')
    return view(client,ref)


def submit(client,current,supersedes=None):
    r=client.post('/api/filing/submit',params={'ref':current['branch_ref']},json={'expected_revision':current['revision'],'fingerprint':current['fingerprint'],'supersedes':supersedes})
    assert r.status_code==200,r.text
    return r.json()


def replay(client,attempt):
    r=client.post('/api/filing/submissions/'+attempt['ref']+'/replay',json={'expected_revision':attempt['revision']})
    assert r.status_code==200,r.text
    return r.json()


@pytest.mark.postgres
def test_readiness_blocks_and_explicit_disposition_separates_preparer_from_reviewer(story):
    client,_=story
    current=start(client)
    assert not current['ready'] and current['counts']['claims_done']<current['counts']['claims']
    assert any(b['kind']=='document' for b in current['blockers'])
    assert any(b['ref']=='diagnostic:CA_AMT_NOT_COMPUTED' for b in current['blockers'])
    assert client.get('/api/trace?ref=D71').status_code==404
    assert client.get('/api/trace?ref=D72').status_code==404
    visible_notices=client.get('/api/trace?ref=agency:/notices').json()['value']
    assert all(n['id']!='N-2025-L566' for n in visible_notices)
    bad={'expected_revision':current['revision'],'fingerprint':current['fingerprint']}
    assert client.post('/api/filing/submit?ref='+ROOT,json=bad).status_code==409
    assert client.post('/api/filing/signoffs?ref='+ROOT,json={**bad,'kind':'final_computation','note':'Skip blockers'}).status_code==409
    resolution={'expected_revision':current['revision'],'target':'diagnostic:CA_AMT_NOT_COMPUTED','authority':'Test authority must be assessed by a professional.','conclusion':'Explicit modeled conclusion.','note':'Reasoned test disposition.','evidence':['doc:D12#page1']}
    assert client.post('/api/filing/resolutions?ref='+ROOT,json=resolution).status_code==422
    r=client.post('/api/filing/resolutions?ref='+ROOT,json={**resolution,'reasoned_none':True})
    assert r.status_code==200,r.text
    record=r.json()
    review={'expected_revision':record['revision'],'decision':'approved','note':'Independently assessed the stated conclusion and cited support.'}
    assert client.post('/api/filing/resolutions/'+record['ref']+'/review',json=review).status_code==403
    identity(client,'st-02')
    assert client.post('/api/filing/resolutions/'+record['ref']+'/review',json=review).status_code==200
    assert not any(b['ref']=='diagnostic:CA_AMT_NOT_COMPUTED' for b in view(client)['blockers'])
    identity(client,'cu-01')
    public=view(client)
    assert 'blockers' not in public and 'signoffs' not in public and not public['can_authorize']
    assert client.post('/api/filing/authorize?ref='+ROOT,json={**bad,'authorize':True}).status_code==409


@pytest.mark.postgres
def test_frozen_rejection_correction_acceptance_bundle_and_amendment(story,packet):
    client,engine=story
    start(client)
    test_only_prepare_full_scope(client,engine,packet)
    ready=sign_and_authorize(client)
    assert ready['ready']
    first=submit(client,ready)
    original_response=client.get('/api/filing/snapshots/'+first['snapshot_id'])
    assert original_response.status_code==200,original_response.text
    original=original_response.json()
    assert original['content']['household']['people'][-1]['ssn']=='666-74-3309'
    assert Decimal(original['content']['lines']['SchC.1']['value'])==151300
    assert Decimal(original['content']['lines']['F8283.A1.vehicle']['value'])==2900
    assert original['content']['lines']['F1040.11']['basis']=='affected'
    rejected=replay(client,first)
    assert rejected['federal']=='rejected' and rejected['california']=='not_transmitted'
    assert rejected['events'][0]['errors'][0]['code']=='R0000-504-02'
    assert client.get('/api/trace?ref=D71').status_code==200
    assert client.get('/api/trace?ref=D72').status_code==404
    assert client.get('/api/trace?ref=agency:/efile/2').status_code==404
    current=view(client)
    assert not current['ready'] and any(not s['current'] for s in current['signoffs'])
    doc=client.get('/api/trace?ref=D71').json()
    assert client.put('/api/workpaper/documents/D71',json={'expected_revision':doc['revision'],'disposition':'used','reason':'Corrected card received after rejection.'}).status_code==200
    current=view(client)
    r=client.post('/api/filing/changes?ref='+ROOT,json={'expected_revision':current['revision'],'key':'household:theo','authority':'Received Social Security card D71.','note':'Correct the transcription using the card, retaining the rejected identity.','evidence':['D71','msg-10']})
    assert r.status_code==200,r.text
    proposed=r.json()['change']
    identity(client,'st-02')
    current=view(client)
    assert client.post('/api/filing/changes/'+proposed['id']+'/review?ref='+ROOT,json={'expected_revision':current['revision'],'decision':'approved','note':'Independently compared the corrected card and rejected identity.'}).status_code==200
    identity(client,'st-01')
    assert view(client)['technical_ready'],view(client)['blockers'][:5]
    corrected_ready=sign_and_authorize(client)
    second=submit(client,corrected_ready,rejected['ref'])
    assert second['snapshot_id']!=first['snapshot_id'] and second['supersedes']==first['ref']
    accepted_fed=replay(client,second)
    assert accepted_fed['federal']=='accepted' and accepted_fed['california']=='transmitted'
    accepted_both=replay(client,accepted_fed)
    assert accepted_both['california']=='accepted'
    frozen=client.get('/api/filing/snapshots/'+second['snapshot_id']).json()
    assert frozen['parent']==first['snapshot_id']
    assert frozen['content']['household']['people'][-1]['ssn']=='666-74-3390'
    assert client.get('/api/filing/snapshots/'+first['snapshot_id']).json()['hash']==original['hash']
    assert client.get('/api/filing/snapshots/'+first['snapshot_id']).json()['content']==original['content']
    assert client.get('/api/trace?ref=household:theo').json()['value']['ssn']=='666-74-3309'
    identity(client,'cu-01')
    copy=client.get('/api/filing/snapshots/'+second['snapshot_id']+'/client-copy')
    assert copy.status_code==200 and second['snapshot_id'] in copy.text and 'affected' in copy.text
    assert client.get('/api/filing/snapshots/'+second['snapshot_id']+'/examination-bundle').status_code==403
    identity(client,'st-04')
    assert client.get('/api/filing/snapshots/'+second['snapshot_id']+'/client-copy').status_code==403
    identity(client,'st-01')
    for action in ['payments','rollforward','notice']:
        current=view(client)
        r=client.post('/api/filing/post-filing?ref='+ROOT,json={'expected_revision':current['revision'],'action':action})
        assert r.status_code==200,r.text
        details=r.json()['details']
        assert details['snapshot_id']==second['snapshot_id']
        if action=='payments':
            assert Decimal(details['federal']['principal'])==max(Decimal(frozen['content']['summary']['federal']['balance_due']),0)
            assert details['federal']['months']==4
        if action=='rollforward':
            assert details['tax_year']==2026 and len(details['federal_installments'])==4
    assert client.get('/api/trace?ref=D72').status_code==200
    bundle=client.get('/api/filing/snapshots/'+second['snapshot_id']+'/examination-bundle')
    assert bundle.status_code==200,bundle.text[:100] if bundle.headers.get('content-type')!='application/zip' else ''
    with ZipFile(BytesIO(bundle.content)) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['snapshot_sha256']==frozen['hash']
        assert 'simulated-documents/D66.html' in archive.namelist()
        assert 'simulated-documents/D15.html' in archive.namelist()
        corrections=json.loads(archive.read('adjustments.json'))
        receipts=next(c for c in corrections if c['record_ref']=='v3:SchC.1')
        assert receipts['reviews'][0]['actor_id']=='st-03'
        assert 'audit-events.json' in archive.namelist()
        assert 'simulated-documents/D72.html' not in archive.namelist()  # it arrived after the frozen filing
        for entry in manifest['entries']:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest()==entry['sha256']
    amendment=client.post('/api/filing/amendments',json={'parent_snapshot':second['snapshot_id']})
    assert amendment.status_code==200,amendment.text
    ref=amendment.json()['ref']
    current=view(client,ref)
    assert not current['technical_ready']
    r=client.post('/api/filing/changes',params={'ref':ref},json={'expected_revision':current['revision'],'key':'SchB.1.2','proposed_value':'0','authority':'Synthetic test correction with cited statements.','note':'Remove duplicate sweep interest on a separate amendment branch.','evidence':['D28','D29']})
    assert r.status_code==200,r.text
    item=r.json()['change']
    identity(client,'st-02')
    current=view(client,ref)
    assert client.post('/api/filing/changes/'+item['id']+'/review',params={'ref':ref},json={'expected_revision':current['revision'],'decision':'approved','note':'Independently checked duplicate sweep support.'}).status_code==200
    # Evidence changed after amendment review: the approval must go stale, while
    # the accepted parent remains byte-for-byte unchanged.
    identity(client,'st-01')
    doc=client.get('/api/trace?ref=D29').json()
    assert client.put('/api/workpaper/documents/D29',json={'expected_revision':doc['revision'],'disposition':'supporting','reason':'Reassessed the sweep statement relationship for the amendment.'}).status_code==200
    stale=view(client,ref)
    assert not stale['technical_ready'] and stale['changes'][-1]['status']=='stale'
    replacement=client.post('/api/filing/changes',params={'ref':ref},json={'expected_revision':stale['revision'],'key':'SchB.1.2','proposed_value':'0','authority':'Reviewed current sweep statements.','note':'Fresh proposal against current evidence revisions.','evidence':['D28','D29']})
    assert replacement.status_code==200,replacement.text
    identity(client,'st-02')
    current=view(client,ref)
    assert client.post('/api/filing/changes/'+replacement.json()['change']['id']+'/review',params={'ref':ref},json={'expected_revision':current['revision'],'decision':'approved','note':'Rechecked the revised evidence.'}).status_code==200
    current=sign_and_authorize(client,ref)
    amended=submit(client,current)
    amended=replay(client,amended)
    amended=replay(client,amended)
    assert amended['california']=='accepted'
    child=client.get('/api/filing/snapshots/'+amended['snapshot_id']).json()
    assert child['parent']==second['snapshot_id'] and child['content']['kind']=='amendment'
    assert Decimal(child['content']['lines']['SchB.1.2']['value'])==0
    assert client.get('/api/filing/snapshots/'+second['snapshot_id']).json()['content']==frozen['content']
    # The migration installs this same database guard in production. The shared test fixture
    # builds tables directly, so install the guard explicitly in this isolated test schema.
    with engine.begin() as conn:
        conn.execute(text("CREATE FUNCTION prevent_filing_snapshot_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Filing snapshots are immutable'; END; $$"))
        conn.execute(text('CREATE TRIGGER immutable_filing_snapshot BEFORE UPDATE OR DELETE ON filing_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_filing_snapshot_change()'))
    with pytest.raises(DBAPIError),engine.begin() as conn:
        conn.execute(text('UPDATE filing_snapshots SET digest=:digest WHERE id=:id'),{'digest':'changed','id':first['snapshot_id']})
    with pytest.raises(DBAPIError),engine.begin() as conn:
        conn.execute(text('DELETE FROM filing_snapshots WHERE id=:id'),{'id':first['snapshot_id']})


@pytest.mark.postgres
def test_readiness_inherits_only_registered_arithmetic(story,packet):
    client,engine=story
    start(client)
    with Session(engine) as db,db.begin():
        records,_=evidence_graph(db,packet)
        for i in range(1,9):
            target='v3:SchB.1.'+str(i)
            value=records[target].payload['value']
            evidence=['doc:D28#page1']
            fp=resolution_fingerprint(records,target,value,evidence)
            db.add(Record(packet_id=packet.digest,ref='synthetic-interest:'+str(i),kind='filing_resolution',payload={
                'branch_ref':ROOT,'target':target,'value':value,'evidence':evidence,'fingerprint':fp,
                'authority':'Synthetic isolated-test proof.','conclusion':'Synthetic test support.','rationale':'Not a product shortcut.',
                'actor_id':'st-01','review':{'decision':'approved','actor_id':'st-02','fingerprint':fp},'review_history':[]}))
    current=view(client)
    claims={c['ref']:c for c in current['claims']}
    assert claims['v3:SchB.2']['done'] and claims['v3:F1040.2b']['done']
    assert not claims['v3:F1040.11']['done']  # unchecked computation never inherits readiness
    assert not current['ready']


@pytest.mark.postgres
def test_open_notes_block_filing_and_do_not_erase_prior_approvals(story,packet):
    client,engine=story
    start(client)
    test_only_prepare_full_scope(client,engine,packet)
    ready=sign_and_authorize(client)
    note=client.post('/api/filing/notes?ref='+ROOT,json={'expected_revision':ready['revision'],'text':'Confirm final disclosure before filing.','blocking':True})
    assert note.status_code==200,note.text
    current=view(client)
    assert not current['ready'] and any(b['kind']=='note' for b in current['blockers'])
    assert all(not a['current'] for a in current['authorizations'])
    assert client.post('/api/filing/submit?ref='+ROOT,json={'expected_revision':ready['revision'],'fingerprint':ready['fingerprint']}).status_code==409
    close=client.post('/api/filing/notes/'+note.json()['ref']+'/close',json={'expected_revision':note.json()['revision']})
    assert close.status_code==200,close.text
    assert view(client)['ready']  # resolving an administrative note restores the unchanged covered draft
