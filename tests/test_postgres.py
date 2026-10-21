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
