"""Day 7–8 acceptance checks in isolated PostgreSQL schemas, with no live approvals."""
import json
from copy import deepcopy
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.api import app
from backend.persistence.models import Record,FilingSnapshot
from backend.domain.filing import digest
from backend.domain.breadth import state_split
from test_story_a import story,identity,claim,propose,verify,review
from test_story_b import propose_business,check_business,decide


def policy_body(data,**changes):
    p=data['standards']
    return {'expected_revision':data['revision'],'verification_types':p['verification_types'],
        'variance_percent':p['variance_review']['flag_if_change_over_percent'],'variance_amount':p['variance_review']['and_over_amount'],
        'partner_threshold':p['partner_threshold'],'retention_years':p['retention_years'],'required_steps':p['required_steps'],
        'note':'Acceptance-test policy change; isolated schema only.',**changes}


def test_generated_views_temporal_search_and_completeness(story,packet):
    client,_=story;identity(client,'st-01')
    views=client.get('/api/workspace/views').json()
    assert len(views)==11
    for view in views:
        response=client.get('/api/workspace/views/'+view['id'])
        assert response.status_code==200,response.text
        assert response.json()['sections'] or response.json()['rows']
    check=state_split(packet)
    assert check['halvorsen_paystub_ca']=='22469.00'
    assert check['difference_to_reconcile']=='88831.00'
    assert check['candidate_ca_wages']=='129569.00'
    assert check['status']=='needs_decision'
    complete=client.get('/api/workspace/completeness').json()
    assert complete['documents_total']==72 and complete['documents_done']==0
    assert complete['outside_done']==0 and len(complete['outside'])==6
    assert not complete['all_accounted_for']
    assert client.get('/api/workspace/search',params={'q':'D71'}).json()['items']==[]
    assert client.get('/api/workspace/search',params={'q':'Subaru'}).json()['items']
    identity(client,'st-01');assert client.post('/api/filing/start').status_code==200
    assert client.get('/api/trace',params={'ref':'agency:/irs_account_transcript_2025/1'}).status_code==404
    identity(client,'st-04')
    assert client.get('/api/workspace/search',params={'q':'666-41-2287'}).json()['items']==[]
    masked=client.get('/api/workspace/views/retirement')
    assert '666-41-2287' not in masked.text
    identity(client,'cu-01')
    for path in ['/views','/team','/search?q=Subaru','/standards','/completeness','/quality']:
        assert client.get('/api/workspace'+path).status_code==403


def test_two_sessions_assign_notify_time_outside(story):
    first,_=story;identity(first,'st-05')
    body={'expected_revision':0,'subject':'v3:SchC.1','assignee':'st-01','due':'2026-10-01','note':'Reconcile the included payment-platform receipts.','status':'open'}
    response=first.put('/api/workspace/assignments',json=body)
    assert response.status_code==200,response.text
    version=response.json()['revision']
    with TestClient(app) as second:
        identity(second,'st-02')
        assert second.put('/api/workspace/assignments',json={**body,'expected_revision':version,'note':'Independent session updated the hand-off.'}).status_code==200
    conflict=first.put('/api/workspace/assignments',json={**body,'expected_revision':version})
    assert conflict.status_code==409
    assert conflict.json()['detail']['changed_by']=='st-02'
    assert conflict.json()['detail']['current']['note']=='Independent session updated the hand-off.'
    assert first.get('/api/workspace/team').json()['assignments'][0]['revision']==2
    identity(first,'st-01')
    items=first.get('/api/workspace/notifications').json()['items']
    assigned=next(i for i in items if i['id'].startswith('assignment:'))
    assert not assigned['seen']
    assert first.post('/api/workspace/notifications/seen',json={'notification_id':assigned['id']}).status_code==200
    assert next(i for i in first.get('/api/workspace/notifications').json()['items'] if i['id']==assigned['id'])['seen']
    r=first.post('/api/workspace/time',json={'area':'business','hours':'1.25','date':'2026-07-10','note':'Reviewed books and source receipts.'})
    assert r.status_code==200,r.text
    budget=next(b for b in first.get('/api/workspace/team').json()['budgets'] if b['area']=='business')
    assert budget['actual']=='1.25'
    r=first.put('/api/workspace/outside/fbar',json={'expected_revision':0,'owner':'Client','status':'communicated','note':'Client notified they are responsible for the FBAR and asked to confirm filing.'})
    assert r.status_code==200,r.text
    complete=first.get('/api/workspace/completeness').json()
    assert complete['outside_done']==1 and complete['documents_done']==0
    assert first.put('/api/workspace/outside/fbar',json={'expected_revision':1,'owner':'Client','status':'completed','note':'   '}).status_code==422


def test_standards_selective_reopening_and_authorization(story):
    client,engine=story;identity(client,'st-01')
    verify(client,propose(client))
    identity(client,'st-02');assert review(client,claim(client)).status_code==200
    identity(client,'st-01');propose_business(client);change=check_business(client)
    identity(client,'st-03');assert decide(client,change).status_code==200
    identity(client,'st-01');assert client.post('/api/filing/start').status_code==200
    before=client.get('/api/filing').json()['fingerprint']
    p=client.get('/api/workspace/standards').json()
    assert client.put('/api/workspace/standards',json=policy_body(p,retention_years=8)).status_code==403
    identity(client,'st-05')
    r=client.put('/api/workspace/standards',json=policy_body(p,retention_years=8))
    assert r.status_code==200 and r.json()['reopened']==[]
    assert client.get('/api/filing').json()['fingerprint']==before
    p=client.get('/api/workspace/standards').json()
    r=client.put('/api/workspace/standards',json=policy_body(p,partner_threshold=100))
    assert r.status_code==200,r.text
    assert r.json()['reopened']==['v3:SchB.1.2']
    assert client.get('/api/filing').json()['fingerprint']!=before
    identity(client,'st-01')
    assert claim(client)['adjustments'][0]['status']=='reopened'
    assert claim(client,'v3:SchC.1')['adjustments'][0]['status']=='approved'
    identity(client,'st-05')
    assert len(client.get('/api/workspace/standards').json()['history'])==1
    assert client.put('/api/workspace/standards',json=policy_body(p)).status_code==409
    assert client.get('/api/access-log').status_code==200


def test_quality_frozen_only_retention_holds_and_active_date(story,packet):
    client,engine=story
    # Minimal synthetic frozen record in this isolated schema; never imported into the live workspace.
    content={'as_of':'2026-07-10T20:05:00Z','lines':{'F1040.24':{'label':'Synthetic frozen total','value':100,'basis':'engine'}},'summary':{},'limit':'Synthetic test snapshot'}
    frozen_digest=digest(content)
    with Session(engine) as db,db.begin():
        db.add(FilingSnapshot(id='synthetic-frozen',packet_id=packet.digest,branch_ref='filing:original',content=content,digest=frozen_digest,actor_id='st-01',at='2026-07-10T20:05:00Z'))
    identity(client,'st-06')
    assert client.get('/api/workspace/quality').status_code==403
    assert client.post('/api/workspace/quality',json={'snapshot_id':'synthetic-frozen','conclusion':'A finding before activation must be blocked.','severity':'observation'}).status_code==403
    identity(client,'st-01');assert client.post('/api/filing/start').status_code==200
    with Session(engine) as db,db.begin():
        row=db.scalar(select(Record).where(Record.ref=='filing:original'))
        row.payload={**row.payload,'as_of':'2027-01-15T15:00:00Z'}
    identity(client,'st-06')
    assert client.get('/api/workspace/quality').json()['snapshots'][0]['sha256']==frozen_digest
    r=client.post('/api/workspace/quality',json={'snapshot_id':'synthetic-frozen','claim_key':'F1040.24','conclusion':'Review the frozen total and retain support for follow-up.','severity':'follow_up'})
    assert r.status_code==200,r.text
    assert len(client.get('/api/workspace/quality').json()['findings'])==1
    assert client.post('/api/workspace/time',json={'area':'business','hours':'1','date':'2027-01-15','note':'Not authorized.'}).status_code==403
    with Session(engine) as db:
        s=db.get(FilingSnapshot,'synthetic-frozen')
        assert s.digest==frozen_digest and s.content==content
    identity(client,'st-05')
    retained=client.get('/api/workspace/retention').json()
    assert not retained['deletion_enabled'] and retained['records'][0]['eligible_on']=='2033-07-10'
    r=client.put('/api/workspace/retention/synthetic-frozen',json={'expected_revision':0,'active':True,'reason':'Keep support for examination.'})
    assert r.status_code==200,r.text
    assert client.get('/api/workspace/retention').json()['records'][0]['hold']
    assert client.delete('/api/workspace/retention/synthetic-frozen').status_code==405


def test_new_required_step_and_removed_verification_method(story):
    client,_=story;identity(client,'st-01')
    verify(client,propose(client))
    identity(client,'st-02');assert review(client,claim(client)).status_code==200
    identity(client,'st-01');assert client.post('/api/filing/start').status_code==200
    identity(client,'st-05');p=client.get('/api/workspace/standards').json()
    body=policy_body(p,verification_types=['recalculated'],required_steps=p['standards']['required_steps']+['Review state wage allocation'])
    r=client.put('/api/workspace/standards',json=body)
    assert r.status_code==200,r.text
    assert r.json()['reopened']==['v3:SchB.1.2']
    data=client.get('/api/filing').json()
    assert any(b['ref']=='Review state wage allocation' for b in data['blockers'])
    assert any(b['ref']=='check:CA_WAGES_D73' for b in data['blockers'])
    identity(client,'st-01')
    assert claim(client)['verification_methods']==['recalculated']
    assert not any(v['current'] for v in claim(client)['verifications'])


def test_colleague_evidence_and_area_coverage_are_real_work(story):
    client,_=story;identity(client,'st-01')
    initial=claim(client)
    question=client.post('/api/collaboration/questions',params={'ref':'v3:SchB.1.2'},json={'expected_revision':initial['revision'],'recipient':'st-02','prompt':'Please explain whether the bank sweep is already in the composite statement.'})
    assert question.status_code==200,question.text
    q=question.json()
    identity(client,'cu-01')
    assert client.get('/api/collaboration/questions').json()==[]
    identity(client,'st-02')
    answered=client.post('/api/collaboration/questions/'+q['ref']+'/answers',json={'expected_revision':q['revision'],'text':'The standalone and composite statements identify the same sweep account.','files':[]})
    assert answered.status_code==200,answered.text
    answer_ref=answered.json()['answers'][0]['ref']
    identity(client,'st-01')
    proposed=propose(client,evidence=['D28','D29',answer_ref])
    verified=verify(client,proposed)
    identity(client,'st-02')
    assert review(client,claim(client)).status_code==403  # supplied material evidence
    identity(client,'st-01')
    before=client.get('/api/workspace/completeness').json()
    assert before['areas_done']==0 and len(before['areas'])==13
    r=client.put('/api/workspace/areas/state',json={'expected_revision':0,'status':'reviewed','note':'Reviewed the D73 wage discrepancy. The claim still needs a supported resolution.'})
    assert r.status_code==200,r.text
    after=client.get('/api/workspace/completeness').json()
    assert after['areas_done']==1 and not after['all_accounted_for']
    assert client.post('/api/filing/start').status_code==200
    filing=client.get('/api/filing').json()
    assert any(b['kind']=='outside' for b in filing['blockers'])
    assert any(b['kind']=='area' for b in filing['blockers'])
    assert any(b['ref']=='check:CA_WAGES_D73' for b in filing['blockers'])
    identity(client,'st-05')
    assert client.put('/api/workspace/areas/state',json={'expected_revision':1,'status':'reviewed','note':'Administrator may not sign tax work.'}).status_code==403


def test_state_wage_judgment_correction_is_explicit_and_partner_reviewed(story):
    client,_=story;identity(client,'st-01')
    ref='v3:SchCA540NR.1.E';evidence=['doc:D08#page1','doc:D09#page1','doc:D73#page1']
    original=claim(client,ref)
    body={'expected_revision':original['revision'],'question':'Which CA wages are supported after reconciliation?',
        'alternatives':['Retain annual allocation','Use reconciled work-location allocation'],'choice':'Use reconciled work-location allocation',
        'authority':'Synthetic acceptance-test allocation, not a tax conclusion for the live return.',
        'rationale':'Synthetic test assumes work dates and HSA treatment were independently reconciled to exercise the supported judgment path.',
        'evidence':['D08','D09'],'outcome':'accepted','proposed_value':'129569'}
    assert client.post('/api/collaboration/decisions',params={'ref':ref},json=body).status_code==422
    r=client.post('/api/collaboration/decisions',params={'ref':ref},json={**body,'evidence':evidence})
    assert r.status_code==200,r.text
    current=claim(client,ref)
    assert current['approved_value']=='218400'
    correction=current['adjustments'][0]
    assert correction['effect']['tax_change']=={'federal':'0','california':'-5685'}
    assert correction['requires_partner']
    checked=client.post('/api/workpaper/verify',params={'ref':ref},json={'expected_revision':current['revision'],'method':'recalculated','note':'Synthetic test reconciliation of the candidate; not a live tax conclusion.','evidence':evidence})
    assert checked.status_code==200,checked.text
    identity(client,'st-02')
    d=client.get('/api/collaboration/decisions',params={'ref':ref}).json()[0]
    review_body={'expected_revision':d['revision'],'expected_claim_revision':d['claim_revision'],'decision':'approved','note':'Independent test review of the supported allocation.'}
    assert client.post('/api/collaboration/decisions/'+d['ref']+'/review',json=review_body).status_code==403
    identity(client,'st-03')
    assert client.post('/api/collaboration/decisions/'+d['ref']+'/review',json=review_body).status_code==200
    assert claim(client,ref)['approved_value']=='129569'
    assert client.post('/api/filing/start').status_code==200
    assert not any(b['ref']=='check:CA_WAGES_D73' for b in client.get('/api/filing').json()['blockers'])
