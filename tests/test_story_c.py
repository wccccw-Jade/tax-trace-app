"""Story C: real PostgreSQL, private client evidence, reviewed judgment and reversible bulk work."""
import base64
import hashlib
from decimal import Decimal
import pytest
from backend.config import settings
from test_story_a import story, identity, claim

VEHICLE='v3:F8283.A1.vehicle'
CRYPTO='v3:F8949.H.C6'


@pytest.fixture
def files_dir(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'attachment_dir',tmp_path/'attachments')
    return settings.attachment_dir


def ask(client,ref=VEHICLE,recipient='cu-01'):
    response=client.post('/api/collaboration/questions',params={'ref':ref},json={
        'expected_revision':claim(client,ref)['revision'],'recipient':recipient,
        'prompt':'Please provide any additional supporting correspondence and explain what it establishes.'})
    assert response.status_code==200,response.text
    return response.json()


def answer(client,q,data=b'Invented case-study supporting correspondence.'):
    response=client.post('/api/collaboration/questions/'+q['ref']+'/answers',json={
        'expected_revision':q['revision'],'text':'Here is the additional support requested. Please assess it with the existing documents.',
        'files':[{'filename':'../support.txt','content_base64':base64.b64encode(data).decode()}]})
    assert response.status_code==200,response.text
    return response.json()


def decision(client,ref,evidence,crypto=False):
    body={'expected_revision':claim(client,ref)['revision'],'question':'Which treatment is supported?',
        'alternatives':['Use the documented support','Retain the engine pending more evidence'],
        'choice':'Use the documented support','authority':'IRS 2025 Form 8283 instructions; vehicle gross-proceeds rule.' if not crypto else 'IRS digital asset recordkeeping requirements; basis and acquisition date.',
        'rationale':'Reviewed the linked documents and client support; recorded the limits and treatment explicitly.',
        'evidence':evidence}
    if crypto:
        body.update(cost_basis='3050',acquired_on='2021-03-15')
    else:
        body.update(proposed_value='2900')
    response=client.post('/api/collaboration/decisions',params={'ref':ref},json=body)
    assert response.status_code==200,response.text
    return response.json()


def verify_value(client,ref,evidence):
    response=client.post('/api/workpaper/verify',params={'ref':ref},json={
        'expected_revision':claim(client,ref)['revision'],'method':'agreed_to_source_document',
        'note':'Compared the underlying documents and client answer against the proposed treatment, including the limits of that support.',
        'evidence':evidence})
    assert response.status_code==200,response.text
    return response.json()


def review_decision(client,d,ref):
    current=client.get('/api/collaboration/decisions',params={'ref':ref}).json()[0]
    return client.post('/api/collaboration/decisions/'+d['ref']+'/review',json={
        'expected_revision':current['revision'],'expected_claim_revision':current['claim_revision'],
        'decision':'approved','note':'Independently reviewed the authority, support and proposed treatment.'})


@pytest.mark.postgres
def test_vehicle_client_answer_attachment_and_independent_decision(story,files_dir):
    client,_=story
    identity(client,'st-01')
    assert client.post('/api/workpaper/adjustments?ref='+VEHICLE,json={'expected_revision':claim(client,VEHICLE)['revision'],'proposed_value':'2900','reason':'Skip authority','evidence':['D66']}).status_code==422
    q=ask(client)
    identity(client,'cu-02')
    assert client.get('/api/collaboration/questions').json()==[]
    assert client.post('/api/collaboration/questions/'+q['ref']+'/answers',json={'expected_revision':1,'text':'Not assigned.'}).status_code==404
    identity(client,'cu-01')
    public=client.get('/api/collaboration/questions').json()[0]
    assert public['prompt']==q['prompt'] and 'internal_note' not in public
    data=b'Invented charity correspondence: vehicle sold for 2,900; no later change.'
    answered=answer(client,q,data)
    a=answered['answers'][0]
    attachment=a['files'][0]
    assert attachment['filename']=='support.txt'
    assert attachment['sha256']==hashlib.sha256(data).hexdigest()
    assert client.get('/api/collaboration/attachments/'+attachment['ref']).content==data
    assert len(list(files_dir.iterdir()))==1
    assert client.post('/api/collaboration/decisions?ref='+VEHICLE,json={}).status_code==403
    identity(client,'cu-02')
    assert client.get('/api/collaboration/attachments/'+attachment['ref']).status_code==404
    identity(client,'st-04')
    assert client.get('/api/collaboration/attachments/'+attachment['ref']).status_code==403
    identity(client,'st-01')
    assert client.get('/api/collaboration/attachments/'+attachment['ref']).content==data
    resolved=client.post('/api/collaboration/questions/'+q['ref']+'/resolve',json={'expected_revision':answered['revision']})
    assert resolved.status_code==200,resolved.text
    evidence=['doc:D66#page1','call-01',a['ref'],attachment['ref']]
    d=decision(client,VEHICLE,evidence)
    assert d['status']=='proposed' and not d['requires_partner']
    assert review_decision(client,d,VEHICLE).status_code==403
    identity(client,'st-02')
    assert review_decision(client,d,VEHICLE).status_code==409
    identity(client,'st-01')
    state=verify_value(client,VEHICLE,evidence)
    assert state['adjustments'][0]['decision_ref']==d['ref']
    # Generic adjustment approval cannot bypass the authority/decision review.
    identity(client,'st-02')
    assert client.post('/api/workpaper/adjustments/'+str(d['adjustment_id'])+'/review',json={
        'expected_revision':state['revision'],'decision':'approved','note':'Bypass attempt'}).status_code==409
    approved=review_decision(client,d,VEHICLE)
    assert approved.status_code==200,approved.text
    assert approved.json()['status']=='approved'
    assert claim(client,VEHICLE)['approved_value']=='2900'
    summary=client.get('/api/workpaper/summary').json()
    assert summary['tax_change']=={'federal':'806','california':'149'}
    assert client.get('/api/trace?ref='+VEHICLE).json()['value']['value']==6000
    trace=client.get('/api/trace',params={'ref':a['ref']}).json()
    assert trace['kind']=='client_answer' and any(e['target']==a['ref'] for e in trace['edges'])
    identity(client,'cu-01')
    assert 'authority' not in str(client.get('/api/collaboration/questions').json())
    assert client.get('/api/collaboration/decisions?ref='+VEHICLE).status_code==403


@pytest.mark.postgres
def test_crypto_judgment_basis_holding_period_partner_and_reopening(story,files_dir):
    client,_=story
    identity(client,'st-01')
    q=ask(client,CRYPTO,'cu-02')
    identity(client,'cu-02')
    answered=answer(client,q,b'Invented additional record: CryptoNorth 03/15/2021 3,050; assess linkage to C6.')
    a=answered['answers'][0]
    identity(client,'st-01')
    evidence=['msg-07','D34','D35',a['ref']]
    d=decision(client,CRYPTO,evidence,True)
    assert d['treatment']['holding_period']=='long-term'
    assert d['requires_partner'] and d['value']=='2275.0'
    state=verify_value(client,CRYPTO,evidence)
    change=state['adjustments'][0]
    assert change['effect']['tax_change']=={'federal':'-1312','california':'-104'}
    identity(client,'st-02')
    assert review_decision(client,d,CRYPTO).status_code==403
    identity(client,'st-03')
    result=review_decision(client,d,CRYPTO)
    assert result.status_code==200,result.text
    assert result.json()['status']=='approved'
    summary=client.get('/api/workpaper/summary').json()
    assert summary['classification_changes'][0]['target_total']=='F8949.K.total'
    lines={l['key']:l for l in summary['changed_lines']}
    assert lines['F8949.K.total']['basis']=='affected' and lines['F8949.H.total']['basis']=='affected'
    assert Decimal(claim(client,CRYPTO)['approved_value'])==2275
    identity(client,'st-01')
    # Closing an answered task does not change the underlying client evidence.
    assert client.post('/api/collaboration/questions/'+q['ref']+'/resolve',json={'expected_revision':answered['revision']}).status_code==200
    assert client.get('/api/collaboration/decisions?ref='+CRYPTO).json()[0]['status']=='approved'
    source=client.get('/api/trace?ref=D35').json()
    response=client.put('/api/workpaper/documents/D35',json={'expected_revision':source['revision'],'disposition':'supporting','reason':'Reassess linkage of the transfer record to the older purchase.'})
    assert response.status_code==200 and response.json()['reopened_claims']==[CRYPTO]
    assert client.get('/api/collaboration/decisions?ref='+CRYPTO).json()[0]['status']=='stale'
    verify_value(client,CRYPTO,evidence)
    identity(client,'st-03')
    approved=review_decision(client,d,CRYPTO)
    assert approved.status_code==200,approved.text
    assert [r['current'] for r in approved.json()['reviews']]==[False,True]
    assert client.get('/api/workpaper/summary').json()['tax_change']['federal']=='-1312'


@pytest.mark.postgres
def test_checked_sales_bulk_verify_and_undo_preserves_history(story):
    client,_=story
    identity(client,'st-01')
    sales=client.get('/api/sales')
    assert sales.status_code==200,sales.text
    data=sales.json()
    assert data['counts']['total']==295 and data['counts']['broker']==282
    eligible=[r['ref'] for r in data['rows'] if r['eligible']]
    assert 0<len(eligible)<282
    rows={r['ref']:r for r in data['rows']}
    for ref in ['v3:F8949.B.N1','v3:F8949.A.N2','v3:F8949.D.X4',CRYPTO]:
        assert not rows[ref]['eligible'] and rows[ref]['reasons']
    bad={'selection_token':data['selection_token'],'refs':[CRYPTO],'note':'Attempt all rows.'}
    assert client.post('/api/sales/verify',json=bad).status_code==422
    assert client.post('/api/sales/verify',json={**bad,'selection_token':'old','refs':eligible}).status_code==409
    response=client.post('/api/sales/verify',json={**bad,'refs':eligible,'note':'Agreed each selected description, dates, proceeds and basis to the printed current broker statement; gain arithmetic agrees and exceptions are excluded.'})
    assert response.status_code==200,response.text
    op=response.json()
    assert op['count']==len(eligible) and op['status']=='applied'
    after=client.get('/api/sales').json()
    assert after['counts']['eligible']==0 and after['counts']['verified']==len(eligible)
    chosen=claim(client,eligible[0])
    assert chosen['verifications'][0]['current'] and chosen['verifications'][0]['operation_id']==op['ref']
    assert not claim(client,CRYPTO)['verifications']
    assert client.post('/api/sales/verify',json={**bad,'refs':eligible}).status_code==409
    response=client.post('/api/sales/operations/'+op['ref']+'/undo',json={'expected_revision':op['revision']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='reversed'
    after=client.get('/api/sales').json()
    assert after['counts']['eligible']==len(eligible) and after['counts']['verified']==0
    check=claim(client,eligible[0])['verifications'][0]
    assert check['reversed_at'] and check['reversed_by']=='st-01' and not check['current']
    assert client.post('/api/sales/operations/'+op['ref']+'/undo',json={'expected_revision':response.json()['revision']}).status_code==409
    identity(client,'cu-01')
    assert client.get('/api/sales').status_code==403
    assert client.post('/api/sales/verify',json=bad).status_code==403


@pytest.mark.postgres
def test_reviewed_request_for_more_evidence_does_not_resolve_crypto(story):
    client,_=story
    identity(client,'st-01')
    body={'expected_revision':claim(client,CRYPTO)['revision'],'question':'Can the claimed purchase be supported?',
        'alternatives':['Request stronger support','Accept the claimed basis'],
        'choice':'Request stronger support','authority':'IRS digital asset recordkeeping requirements.',
        'rationale':'The client statement alone does not establish linkage to the sold units.',
        'outcome':'needs_evidence','evidence':['msg-07','D34','D35']}
    assert client.post('/api/collaboration/decisions?ref='+CRYPTO,json={**body,'authority':'  '}).status_code==422
    assert client.post('/api/collaboration/decisions?ref='+CRYPTO,json={**body,'proposed_value':'2275'}).status_code==422
    response=client.post('/api/collaboration/decisions?ref='+CRYPTO,json=body)
    assert response.status_code==200,response.text
    d=response.json()
    assert d['adjustment_id'] is None
    identity(client,'st-02')
    reviewed=review_decision(client,d,CRYPTO)
    assert reviewed.status_code==200,reviewed.text
    assert reviewed.json()['status']=='needs_evidence'
    assert client.get('/api/workpaper/status').json()[CRYPTO]['status']=='needs_evidence'
    assert claim(client,CRYPTO)['approved_value']=='5325.0'
    assert client.get('/api/workpaper/summary').json()['approved_adjustments']==0
