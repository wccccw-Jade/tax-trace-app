"""Story B: partner sign-off, source changes and an evidence-bound second review."""
from decimal import Decimal
import pytest
from test_story_a import story, identity, claim, propose, verify, review

REF='v3:SchC.1'


def propose_business(client):
    state=claim(client,REF)
    response=client.post('/api/workpaper/adjustments',params={'ref':REF},json={
        'expected_revision':state['revision'],'proposed_value':'151300',
        'reason':'The books already include the Paywell payment. Remove the duplicated $12,400 reported again on D21.',
        'evidence':['D14','D15','D21']})
    assert response.status_code==200,response.text
    return response.json()


def check_business(client):
    state=claim(client,REF)
    result=client.post('/api/workpaper/verify',params={'ref':REF},json={
        'expected_revision':state['revision'],'method':'agreed_to_source_document',
        'note':'D14 revenue already includes the Atlas deposits reconciled on D15. D21 reports the same Paywell payment, not extra receipts.',
        'evidence':['D14','D15','D21']})
    assert result.status_code==200,result.text
    return result.json()


def decide(client,state):
    change=next(a for a in state['adjustments'] if a['status'] in {'proposed','reopened'})
    return client.post(f"/api/workpaper/adjustments/{change['id']}/review",json={
        'expected_revision':state['revision'],'decision':'approved',
        'note':'Independently reconciled D14, D15 and D21; the same payment is included only once.'})


@pytest.mark.postgres
def test_business_bridge_partner_reopening_and_reapproval(story):
    client,_=story
    identity(client,'st-01')
    initial=client.get('/api/workpaper/business-income').json()
    assert {k:Decimal(v) for k,v in initial['books'].items()}=={'income':151300,'expenses':61466,'profit':89834}
    assert initial['engine_receipts']=='163700' and Decimal(initial['recommended_receipts'])==151300
    assert sum(Decimal(r['value']) for r in initial['bridge'])==Decimal(initial['approved_profit'])==81854
    state=propose_business(client)
    assert state['adjustments'][0]['requires_partner']
    assert state['adjustments'][0]['effect']['tax_change']=={'federal':'-4402','california':'-384'}
    assert client.get('/api/workpaper/business-income').json()['preview_profit']=='69454'
    state=check_business(client)
    assert decide(client,state).status_code==403  # self-review
    identity(client,'st-02')
    assert decide(client,state).status_code==403  # partner required
    identity(client,'st-03')
    approved=decide(client,state)
    assert approved.status_code==200,approved.text
    assert approved.json()['adjustments'][0]['approval_current']
    summary=client.get('/api/workpaper/summary').json()
    assert summary['summary']['federal']['total_tax']=='77560'
    assert summary['summary']['california']['total_tax']=='18490'
    lines={l['key']:l for l in summary['changed_lines']}
    assert lines['SchC.31']['value']=='69454' and lines['SchC.31']['basis']=='recomputed'
    assert lines['F1040.24']['basis']=='affected'
    assert lines['F1040.13']['basis']=='affected'  # qualified business income deduction
    assert lines['SchSE.12']['basis']=='affected'
    bridge=client.get('/api/workpaper/business-income').json()
    assert bridge['approved_profit']=='69454'
    assert sum(Decimal(r['value']) for r in bridge['bridge'])==69454
    # An unrelated approved correction must survive the business evidence change.
    identity(client,'st-01')
    interest=verify(client,propose(client))
    identity(client,'st-02')
    assert review(client,interest).status_code==200
    identity(client,'st-01')
    doc=client.get('/api/trace?ref=D15').json()
    response=client.put('/api/workpaper/documents/D15',json={'expected_revision':doc['revision'],
        'disposition':'supporting','reason':'Rechecked the deposit reconciliation; document supports the books total.'})
    assert response.status_code==200,response.text
    assert response.json()['reopened_claims']==[REF]
    state=claim(client,REF)  # new request: durable reopened status and preserved review
    change=state['adjustments'][0]
    assert change['status']=='reopened' and change['reviews'][0]['decision']=='approved'
    assert not change['reviews'][0]['current'] and not state['verifications'][0]['current']
    assert change['reopen_events'][0]['source_ref']=='D15'
    assert change['reopen_events'][0]['source_revision']==2
    assert 'D15' in change['reopen_events'][0]['reason']
    assert state['approved_value']=='163700' and state['review_value']=='151300'
    statuses=client.get('/api/workpaper/status').json()
    assert statuses[REF]['status']=='reopened' and statuses['v3:SchB.1.2']['status']=='approved'
    summary=client.get('/api/workpaper/summary').json()
    assert summary['approved_adjustments']==1 and summary['reopened_adjustments']==1
    assert summary['summary']['federal']['total_tax']=='81322'  # E1 only
    identity(client,'st-03')
    assert decide(client,state).status_code==409  # must check changed evidence
    identity(client,'st-01')
    state=check_business(client)
    identity(client,'st-03')
    response=decide(client,state)
    assert response.status_code==200,response.text
    change=response.json()['adjustments'][0]
    assert change['status']=='approved'
    assert [r['current'] for r in change['reviews']]==[False,True]
    assert len(change['reopen_events'])==1
    summary=client.get('/api/workpaper/summary').json()
    assert summary['approved_adjustments']==2 and summary['reopened_adjustments']==0
    assert summary['tax_change']=={'federal':'-5042','california':'-511'}  # E4 counted once
    assert client.get('/api/trace?ref='+REF).json()['value']['value']==163700
    identity(client,'cu-01')
    assert client.get('/api/workpaper/business-income').status_code==403


@pytest.mark.postgres
def test_source_anchor_change_reopens_approval(story):
    client,_=story
    identity(client,'st-01')
    state=propose_business(client)
    state=check_business(client)
    identity(client,'st-03')
    assert decide(client,state).status_code==200
    identity(client,'st-01')
    source=client.get('/api/trace?ref=ev-0103').json()
    text=source['page']['printed_content']
    # A manual evidence-location revision must invalidate sign-off just like a disposition.
    response=client.put('/api/locators/ev-0103',json={'expected_revision':source['revision'],'start':0,'end':len(text)})
    assert response.status_code==200,response.text
    assert response.json()['reopened_claims']==[REF]
    state=claim(client,REF)
    assert state['adjustments'][0]['status']=='reopened'
    assert not state['verifications'][0]['current']
    assert client.get('/api/workpaper/summary').json()['approved_adjustments']==0
