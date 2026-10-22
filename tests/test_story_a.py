"""Story A acceptance checks against a real, isolated PostgreSQL schema."""
import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from backend.api import app
from backend.persistence.db import session
from backend.persistence.models import Base, Record
from backend.importer import import_packet, refresh_derived

@pytest.fixture
def story(packet):
    url=os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run Story A PostgreSQL checks')
    schema='test_story_a_'+uuid4().hex
    root=create_engine(url)
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    def database():
        with Session(engine) as db:
            yield db
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db,db.begin():
            import_packet(db,packet)
        app.dependency_overrides[session]=database
        with TestClient(app) as client:
            yield client,engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()


def identity(client,actor):
    assert client.post('/api/session',json={'actor_id':actor}).status_code==200


def claim(client,ref='v3:SchB.1.2'):
    response=client.get('/api/workpaper/claim',params={'ref':ref})
    assert response.status_code==200,response.text
    return response.json()


def propose(client,ref='v3:SchB.1.2',value='0',evidence=None):
    state=claim(client,ref)
    response=client.post('/api/workpaper/adjustments',params={'ref':ref},json={'expected_revision':state['revision'],'proposed_value':value,'reason':'Remove duplicate bank-sweep interest already included in D28.','evidence':evidence or ['D28','D29']})
    assert response.status_code==200,response.text
    return response.json()


def verify(client,state,ref='v3:SchB.1.2'):
    response=client.post('/api/workpaper/verify',params={'ref':ref},json={'expected_revision':state['revision'],'method':'agreed_to_source_document','note':'Compared both documents; same bank sweep account and amount. Proposed zero avoids a duplicate inclusion.','evidence':next((a['evidence'] for a in state['adjustments'] if a['status']=='proposed'),['D28','D29'])})
    assert response.status_code==200,response.text
    return response.json()


def review(client,state,decision='approved'):
    pending=next(a for a in state['adjustments'] if a['status']=='proposed')
    return client.post(f"/api/workpaper/adjustments/{pending['id']}/review",json={'expected_revision':state['revision'],'decision':decision,'note':'Independently checked the sources and the documented correction.'})

@pytest.mark.postgres
def test_story_a_trace_propose_verify_independent_review_and_reload(story,packet):
    client,engine=story
    identity(client,'st-01')
    # Document disposition is separate from the return correction.
    original=client.get('/api/trace?ref=D29').json()
    disposition=client.put('/api/workpaper/documents/D29',json={'expected_revision':original['revision'],'disposition':'duplicate','reason':'Same sweep interest as D28, same account.','duplicate_of':'D28'})
    assert disposition.status_code==200,disposition.text
    assert disposition.json()['payload']['duplicate_of']=='D28'
    baseline=client.get('/api/workpaper/summary').json()
    assert baseline['approved_adjustments']==0
    state=propose(client)
    assert state['engine_value']=='1840' and state['approved_value']=='1840'
    assert state['review_value']=='0'
    pending=state['adjustments'][0]
    assert pending['original_value']=='1840'
    assert pending['effect']['tax_change']=={'federal':'-640','california':'-127'}
    assert client.get('/api/workpaper/summary').json()['approved_adjustments']==0
    # Persisted proposal is visible to a different actor, but cannot be approved without verification.
    identity(client,'st-02')
    state=claim(client)
    assert review(client,state).status_code==409
    identity(client,'st-01')
    state=verify(client,state)
    assert state['verifications'][0]['current']
    blocked=review(client,state)
    assert blocked.status_code==403 and 'own work' in blocked.json()['detail']
    identity(client,'st-02')
    state=claim(client)
    response=review(client,state)
    assert response.status_code==200,response.text
    state=response.json()
    assert state['approved_value']=='0'
    assert state['adjustments'][0]['reviews'][0]['actor_id']=='st-02'
    assert state['verifications'][0]['current']
    summary=client.get('/api/workpaper/summary').json()
    assert summary['approved_adjustments']==1
    assert summary['summary']['federal']['total_tax']=='81322'
    assert summary['summary']['california']['total_tax']=='18747'
    changed={line['key']:line for line in summary['changed_lines']}
    assert changed['SchB.2']['value']=='4610' and changed['SchB.2']['basis']=='recomputed'
    assert changed['F1040.9']['basis']=='affected'
    # Original engine values are never overwritten. Derived refresh does not erase human work.
    with Session(engine) as db,db.begin():
        refresh_derived(db,packet)
    assert client.get('/api/trace?ref=v3:SchB.1.2').json()['value']['value']==1840
    assert claim(client)['approved_value']=='0'
    assert client.get('/api/workpaper/status').json()['v3:SchB.1.2']['status']=='approved'
    identity(client,'cu-01')
    assert client.get('/api/summary').json()['summary']['federal']['total_tax']=='81322'
    assert client.get('/api/workpaper/claim?ref=v3:SchB.1.2').status_code==403
    assert client.get('/api/workpaper/summary').status_code==403

@pytest.mark.postgres
def test_review_separation_rejection_and_stale_sources(story):
    client,_=story
    # A reviewer who prepares a correction cannot approve it either.
    identity(client,'st-02')
    state=verify(client,propose(client))
    assert review(client,state).status_code==403
    identity(client,'st-03')
    rejected=review(client,claim(client),'rejected')
    assert rejected.status_code==200,rejected.text
    assert rejected.json()['approved_value']=='1840'
    assert rejected.json()['adjustments'][0]['status']=='rejected'
    assert client.get('/api/workpaper/summary').json()['approved_adjustments']==0
    identity(client,'st-01')
    state=verify(client,propose(client))
    # Change cited evidence after verification. The old verification is stale and blocks approval.
    doc=client.get('/api/trace?ref=D29').json()
    assert client.put('/api/workpaper/documents/D29',json={'expected_revision':doc['revision'],'disposition':'supporting','reason':'Reassessing source treatment.'}).status_code==200
    state=claim(client)
    assert not state['verifications'][0]['current']
    identity(client,'st-03')
    assert review(client,state).status_code==409

@pytest.mark.postgres
def test_mutations_validate_roles_evidence_revisions_and_partner_threshold(story):
    client,_=story
    identity(client,'st-01')
    state=claim(client)
    bad={'expected_revision':state['revision'],'proposed_value':'0','reason':'Remove duplicate.','evidence':['does-not-exist']}
    assert client.post('/api/workpaper/adjustments?ref=v3:SchB.1.2',json=bad).status_code==422
    assert client.post('/api/workpaper/adjustments?ref=v3:SchB.1.2',json={**bad,'reason':'   '}).status_code==422
    assert client.post('/api/workpaper/adjustments?ref=v3:SchB.1.2',json={**bad,'evidence':['D29'],'proposed_value':'NaN'}).status_code==422
    state=propose(client)
    assert client.post('/api/workpaper/adjustments?ref=v3:SchB.1.2',json={**bad,'evidence':['D29']}).status_code==409
    identity(client,'st-05')
    assert client.post('/api/workpaper/verify?ref=v3:SchB.1.2',json={'expected_revision':state['revision'],'method':'recalculated','note':'Check','evidence':['D29']}).status_code==403
    identity(client,'st-01')
    state=propose(client,'v3:SchC.1','151300',['D14','D15','D21'])
    state=verify(client,state,'v3:SchC.1')
    identity(client,'st-02')
    assert review(client,state).status_code==403  # material tax adjustment requires partner
    identity(client,'st-03')
    assert review(client,state).status_code==200
