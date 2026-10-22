"""Integration test uses an isolated schema in an explicitly supplied PostgreSQL test DB."""
import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from backend.persistence.models import Base, Record, Edge, AuditEvent
from backend.importer import import_packet

@pytest.mark.postgres
def test_real_postgres_import_is_idempotent(packet):
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run PostgreSQL integration checks')
    schema = 'test_' + uuid4().hex
    root = create_engine(url)
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db, db.begin():
            assert import_packet(db,packet)['created']
        with Session(engine) as db, db.begin():
            assert not import_packet(db,packet)['created']
            assert db.scalar(select(func.count()).select_from(Record).where(Record.kind=='extraction'))==3012
            assert db.scalar(select(func.count()).select_from(Edge))==11280
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()

@pytest.mark.postgres
def test_manual_anchor_permissions_conflicts_and_refresh(packet):
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.persistence.db import session
    from backend.importer import refresh_derived
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run PostgreSQL API checks')
    schema = 'test_' + uuid4().hex
    root = create_engine(url)
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options':f'-csearch_path={schema}'})
    def database():
        with Session(engine) as db:
            yield db
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db, db.begin():
            import_packet(db,packet)
        app.dependency_overrides[session] = database
        with TestClient(app) as client:
            assert client.post('/api/session',json={'actor_id':'st-01'}).status_code==200
            before = client.get('/api/trace?ref=ev-0960').json()
            page = before['page']['printed_content']
            start = page.index('18,450.00')
            revision = before['revision']
            body={'expected_revision':revision,'start':start,'end':start+len('18,450.00')}
            assert client.put('/api/locators/ev-0960',json={**body,'start':-1}).status_code==422
            saved = client.put('/api/locators/ev-0960',json=body)
            assert saved.status_code==200
            anchor = saved.json()['payload']['locator']
            assert anchor['quote']=='18,450.00' and anchor['actor']=='st-01' and anchor['at']
            assert client.put('/api/locators/ev-0960',json=body).status_code==409
            # A new DB session and derived-data refresh must preserve manual evidence.
            with Session(engine) as db, db.begin():
                refresh_derived(db,packet)
            after=client.get('/api/trace?ref=ev-0960').json()
            assert after['value']['locator']==anchor
            assert after['revision']==revision+1
            fields=client.get('/api/records?kind=extraction&document_id=D36').json()
            assert len(fields)==4
            client.post('/api/session',json={'actor_id':'st-04'})
            masked=client.get('/api/trace?ref=household:ngozi').json()
            assert masked['value']['ssn']=='[masked]'
            assert client.put('/api/locators/ev-0960',json={**body,'expected_revision':revision+1}).status_code==403
            client.post('/api/session',json={'actor_id':'st-05'})
            assert client.put('/api/locators/ev-0960',json={**body,'expected_revision':revision+1}).status_code==403
            assert any(row['action']=='manual_anchor' for row in client.get('/api/access-log').json())
            client.post('/api/session',json={'actor_id':'cu-01'})
            assert client.get('/api/summary').status_code==200
            assert client.get('/api/records').status_code==403
            assert client.get('/api/audit').status_code==403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()
