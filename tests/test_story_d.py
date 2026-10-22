"""Story D comparisons, per-user cursors, independent previews and prior-year review."""
from decimal import Decimal
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from backend.persistence.models import Adjustment,LastSeen
from backend.domain.history import variance_values
from test_story_a import story,identity,claim,propose,verify,review


def test_variance_thresholds_and_zero_prior():
    assert not variance_values(10000,11000)['flagged']  # exactly 10% and $1,000
    assert variance_values(10000,11001)['flagged']
    assert not variance_values(100000,101001)['flagged']  # dollar test alone is insufficient
    assert not variance_values(0,1000)['flagged']
    assert variance_values(0,1001)=={'delta':'1001','percent_change':None,'flagged':True,'comparison':'new_activity'}
    assert variance_values(-10000,-12000)['percent_change']=='20.00'


@pytest.mark.postgres
def test_versions_source_changes_and_approved_workpaper(story,packet):
    client,_=story
    identity(client,'st-01')
    response=client.get('/api/history/compare?before=v2&after=v3')
    assert response.status_code==200,response.text
    result=response.json()
    rows={r['key']:r for r in result['rows']}
    assert Decimal(rows['F1040.24']['delta'])==4492
    assert result['before']['summary']['federal']['total_tax']==77470
    assert result['after']['summary']['federal']['total_tax']==81962
    first=client.get('/api/history/compare?before=v1&after=v2').json()
    changes={r['key']:r for r in first['rows']}
    assert changes['F8949.A.M14']['change']=='removed'
    assert changes['F8949.D.M14']['change']=='added'
    assert 'sources' in changes['F8949.D.M1']['fields']
    assert changes['F8949.D.M1']['delta']=='0.0'
    state=propose(client)
    pending=client.get('/api/history/compare?before=v3&after=workpaper').json()
    assert pending['rows']==[] and pending['pending'][0]['status']=='proposed'
    state=verify(client,state)
    identity(client,'st-02')
    assert review(client,state).status_code==200
    current=client.get('/api/history/compare?before=v3&after=workpaper').json()
    rows={r['key']:r for r in current['rows']}
    assert Decimal(rows['SchB.1.2']['after']['value'])==0
    assert rows['F1040.2b']['after']['basis']=='recomputed'
    assert rows['F1040.11']['after']['basis']=='affected'
    assert rows['F1040.11']['delta']=='0'  # amount is retained but basis changes
    assert current['after']['summary']['federal']['total_tax']=='81322'
    assert client.get('/api/trace?ref=v3:SchB.1.2').json()['value']['value']==1840
    assert client.get('/api/history/compare?before=not-a-version').status_code==422
    identity(client,'cu-01')
    assert client.get('/api/history/compare').status_code==403


@pytest.mark.postgres
def test_activity_seen_cursors_are_per_user_and_acknowledge_only_displayed_changes(story):
    client,engine=story
    identity(client,'st-01')
    initial=client.get('/api/history/activity').json()
    assert initial['first_visit'] and initial['unseen_count']==0
    state=propose(client)
    shown=client.get('/api/history/activity').json()
    assert shown['unseen_count']==1 and 'v3:SchB.1.2' in shown['changed_claims']
    # New work arrives after the displayed cursor. Acknowledging the old view must not hide it.
    verify(client,state)
    marked=client.post('/api/history/seen',json={'expected_revision':shown['seen_revision'],'through_cursor':shown['through_cursor']})
    assert marked.status_code==200,marked.text
    assert marked.json()['unseen_count']==1
    fresh=client.get('/api/history/activity').json()
    assert not fresh['first_visit'] and fresh['seen_revision']==1
    assert client.post('/api/history/seen',json={'expected_revision':0,'through_cursor':fresh['through_cursor']}).status_code==409
    identity(client,'st-02')
    other=client.get('/api/history/activity').json()
    assert other['first_visit'] and other['unseen_count']==2
    assert client.post('/api/history/seen',json={'expected_revision':0,'through_cursor':other['through_cursor']}).status_code==200
    identity(client,'st-01')
    assert client.get('/api/history/activity').json()['unseen_count']==1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LastSeen))==2
    identity(client,'cu-01')
    assert client.get('/api/history/activity').status_code==403
    assert client.post('/api/history/seen',json={'expected_revision':0,'through_cursor':0}).status_code==403


@pytest.mark.postgres
def test_supplied_and_user_whatifs_are_read_only_until_proposed(story,packet):
    client,engine=story
    identity(client,'st-01')
    options=client.get('/api/history/what-if').json()
    assert options['scenarios']==packet.data['what_if']['alternatives']
    assert len(options['scenarios'])==5
    assert all(s['base_version']=='v3' for s in options['scenarios'])
    zero=next(s for s in options['scenarios'] if s['id']=='penalty_annualized')
    assert zero['changed_lines']==[] and zero['federal']['total_tax_change']==0
    before=client.get('/api/history/activity').json()['through_cursor']
    body={'ref':'v3:SchB.1.2','base':'v3','proposed_value':'0'}
    result=client.post('/api/history/what-if',json=body)
    assert result.status_code==200,result.text
    preview=result.json()
    assert preview['effect']['tax_change']=={'federal':'-640','california':'-127'}
    assert preview['summary']['federal']['total_tax']=='81322' and preview['can_propose']
    wage_base=next(l['value'] for l in packet.data['return_versions'][-1]['lines'] if l['key']=='F1040.1a')
    wage=client.post('/api/history/what-if',json={'ref':'v3:F1040.1a','proposed_value':wage_base+1000,'category':'wages'})
    assert wage.status_code==200,wage.text
    assert wage.json()['effect']['basis']=='estimated'
    assert wage.json()['effect']['tax_change']=={'federal':'310','california':'99'}
    expense=client.post('/api/history/what-if',json={'ref':'v3:SchC.25','proposed_value':'2172'}).json()
    assert expense['effect']['tax_change']=={'federal':'464','california':'41'}
    payment=client.post('/api/history/what-if',json={'ref':'v3:F1040.26','base':'v3','proposed_value':13000,'category':'payment'}).json()
    assert payment['effect']['tax_change']=={'federal':'0','california':'0'}
    base_payment=next(l['value'] for l in packet.data['return_versions'][-1]['lines'] if l['key']=='F1040.26')
    assert Decimal(payment['summary']['federal']['payments'])==77742+13000-base_payment
    assert payment['effect']['basis']=='exact'
    state_only=client.post('/api/history/what-if',json={'ref':'v3:F540NR.17','proposed_value':'482096','category':'ordinary_income'}).json()
    assert state_only['effect']['tax_change']=={'federal':'0','california':'99'}
    derived=client.post('/api/history/what-if',json={'ref':'v3:F1040.2b','proposed_value':5000}).json()
    assert not derived['can_propose']
    assert client.post('/api/history/what-if',json={**body,'category':'made-up'}).status_code==422
    assert client.post('/api/history/what-if',json={**body,'proposed_value':'NaN'}).status_code==422
    assert client.get('/api/history/activity').json()['through_cursor']==before
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Adjustment))==0
    # Explicit promotion uses existing revision/evidence/review controls, not a new approval path.
    converted=client.post('/api/workpaper/adjustments?ref='+body['ref'],json={
        'expected_revision':preview['revision'],'proposed_value':preview['proposed_value'],
        'reason':'Promote the explored duplicate-interest correction.','evidence':['D28','D29']})
    assert converted.status_code==200,converted.text
    assert converted.json()['approved_value']=='1840'
    assert client.get('/api/workpaper/summary').json()['approved_adjustments']==0
    state=verify(client,converted.json())
    identity(client,'st-02')
    assert review(client,state).status_code==200
    approved_preview=client.post('/api/history/what-if',json={**body,'base':'workpaper','proposed_value':'100'}).json()
    assert approved_preview['base_value']=='0'
    assert approved_preview['effect']['tax_change']=={'federal':'34','california':'7'}
    assert approved_preview['summary']['federal']['total_tax']=='81356'
    identity(client,'cu-01')
    assert client.get('/api/history/what-if').status_code==403
    assert client.post('/api/history/what-if',json=body).status_code==403


@pytest.mark.postgres
def test_variance_explanation_tracks_compared_values_and_stales_after_approval(story):
    client,_=story
    identity(client,'st-01')
    result=client.get('/api/history/variance')
    assert result.status_code==200,result.text
    data=result.json()
    rows={r['key']:r for r in data['rows']}
    interest=rows['F1040.2b']
    assert interest['prior_value']==2310 and interest['current_value']==6450 and interest['flagged']
    assert 'SchB.1.2' not in rows
    assert any(r['key']=='CA540.13' for r in data['not_compared'])
    zero=next(r for r in data['rows'] if r['comparison']=='new_activity')
    assert zero['percent_change'] is None
    revision=client.get('/api/trace?ref=v3:F1040.2b').json()['revision']
    body={'expected_revision':revision,'fingerprint':interest['fingerprint'],'note':'Higher investment balances and additional sources explain the increased interest; reconcile the duplicate separately.'}
    response=client.post('/api/history/variance?ref=v3:F1040.2b',json=body)
    assert response.status_code==200,response.text
    assert next(r for r in client.get('/api/history/variance').json()['rows'] if r['key']=='F1040.2b')['explained']
    state=verify(client,propose(client))
    identity(client,'st-02')
    assert review(client,state).status_code==200
    new=next(r for r in client.get('/api/history/variance').json()['rows'] if r['key']=='F1040.2b')
    assert Decimal(new['current_value'])==4610 and not new['explained']
    assert not new['explanations'][0]['current']
    assert client.post('/api/history/variance?ref=v3:F1040.2b',json=body).status_code==409
    identity(client,'st-05')
    assert client.post('/api/history/variance?ref=v3:F1040.2b',json=body).status_code==403
    identity(client,'cu-01')
    assert client.get('/api/history/variance').status_code==403
