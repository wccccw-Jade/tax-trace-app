from functools import lru_cache
from pathlib import Path
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from backend.config import settings, ROOT
from backend.domain.packet import Packet
from backend.domain.security import actors, actor_by_id, sensitive_tokens, redact, STAFF_ROLES
from backend.persistence.db import session
from backend.persistence.models import PacketImport, Record, Edge, DemoSession, AuditEvent

app = FastAPI(title='Miraflores workpaper — local demo', version='0.1.0')

@lru_cache
def packet():
    return Packet.read(settings.packet_path)

@lru_cache
def tokens():
    return sensitive_tokens(packet())

def identity(request: Request, db: Session = Depends(session)):
    token = request.cookies.get('demo_session')
    current = db.get(DemoSession, token) if token else None
    actor = actor_by_id(packet(), current.actor_id) if current else None
    if not actor:
        raise HTTPException(401, 'Choose a demo identity first.')
    return actor

def staff(actor=Depends(identity)):
    if actor['role'] not in STAFF_ROLES:
        raise HTTPException(403, 'Internal workpaper: staff access required.')
    return actor

def respond(value, actor, db, subject):
    if actor.get('sensitive_data_clearance', False):
        # Log all authorized internal payload views conservatively, with no sensitive payload in the event.
        db.add(AuditEvent(actor_id=actor['id'], action='unmasked_view', subject=subject))
        db.commit()
        return value
    return redact(value, tokens())

def imported(db):
    result = db.get(PacketImport, packet().digest)
    if not result:
        raise HTTPException(503, 'Run migrations and packet import first; see README.')
    return result

@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={'detail':'PostgreSQL is unavailable or migrations are missing. See README setup.'})

@app.get('/api/health')
def health():
    return {'status':'ok', 'stage':'day-0-1', 'demo':True}

@app.get('/api/ready')
def ready(db: Session = Depends(session)):
    db.execute(text('SELECT 1'))
    imported(db)
    return {'database':'ready', 'packet':'imported'}

@app.get('/api/actors')
def list_actors():
    return [{'id':a['id'], 'name':a['name'], 'role':a['role'], 'sensitive_data_clearance':a.get('sensitive_data_clearance',False)} for a in actors(packet())]

class Switch(BaseModel):
    actor_id: str

@app.post('/api/session')
def switch(body: Switch, response: Response, request: Request, db: Session = Depends(session)):
    actor = actor_by_id(packet(), body.actor_id)
    if not actor:
        raise HTTPException(400, 'Unknown demo identity')
    old = request.cookies.get('demo_session')
    old_session = db.get(DemoSession, old) if old else None
    if old_session:
        db.delete(old_session)
    token = secrets.token_hex(32)
    db.add(DemoSession(token=token, actor_id=actor['id']))
    db.add(AuditEvent(actor_id=actor['id'], action='demo_role_selected', subject='session'))
    db.commit()
    response.set_cookie('demo_session', token, httponly=True, samesite='strict')
    return {'id': actor['id'], 'name': actor['name'], 'role': actor['role'], 'demo':True}

@app.get('/api/session')
def get_session(actor=Depends(identity)):
    return {'id':actor['id'], 'name':actor['name'], 'role':actor['role']}

@app.get('/api/summary')
def summary(actor=Depends(identity), db: Session = Depends(session)):
    imported(db)
    v = packet().data['return_versions'][-1]
    return {'name':packet().data['packet']['name'], 'version':v['version'], 'summary':v['summary'], 'basis':'Unreviewed engine output'}

@app.get('/api/audit')
def audit(actor=Depends(staff), db: Session = Depends(session)):
    return respond(imported(db).report, actor, db, 'audit-report')

@app.get('/api/records')
def records(kind: str = 'document', version: str = 'v3', actor=Depends(staff), db: Session = Depends(session)):
    imported(db)
    query = select(Record).where(Record.packet_id == packet().digest, Record.kind == kind)
    rows = db.scalars(query).all()
    if kind == 'claim':
        rows = [r for r in rows if r.payload['version']==version]
    return respond([{'ref':r.ref, 'revision':r.revision, 'payload':r.payload} for r in rows], actor, db, 'records:'+kind)

@app.get('/api/trace')
def trace(ref: str, version: str = 'v3', actor=Depends(staff), db: Session = Depends(session)):
    imported(db)
    record = db.scalar(select(Record).where(Record.packet_id==packet().digest, Record.ref==ref))
    value = record.payload if record else packet().resolve(ref, version)
    if value is None:
        raise HTTPException(404, 'Reference not found')
    edges = db.scalars(select(Edge).where(Edge.packet_id==packet().digest, (Edge.source==ref) | (Edge.target==ref))).all()
    page = None
    if record and record.kind == 'extraction':
        page = packet().resolve(f"doc:{value['document_id']}#page{value['page']}")
    return respond({'ref':ref, 'value':value, 'page':page, 'edges':[{'source':e.source,'target':e.target,'kind':e.kind,'resolved':e.resolved} for e in edges]}, actor, db, ref)

@app.get('/api/access-log')
def access_log(actor=Depends(staff), db: Session = Depends(session)):
    if actor['role'] != 'firm_administrator':
        raise HTTPException(403, 'Administrator access required')
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)).all()
    return [{'actor_id':r.actor_id,'action':r.action,'subject':r.subject,'at':r.at} for r in rows]



class ManualAnchor(BaseModel):
    expected_revision: int
    start: int
    end: int

@app.put('/api/locators/{extraction_id}')
def manual_anchor(extraction_id: str, body: ManualAnchor, actor=Depends(staff), db: Session = Depends(session)):
    if actor['role'] not in {'preparer','reviewer','partner'}:
        raise HTTPException(403, 'Preparation access required')
    imported(db)
    record = db.scalar(select(Record).where(Record.packet_id==packet().digest, Record.ref==extraction_id, Record.kind=='extraction').with_for_update())
    if not record:
        raise HTTPException(404, 'Extraction not found')
    if record.revision != body.expected_revision:
        raise HTTPException(409, 'Record changed; reload before saving')
    page = packet().resolve(f"doc:{record.payload['document_id']}#page{record.payload['page']}")
    printed = page['printed_content']
    if not (0 <= body.start < body.end <= len(printed)):
        raise HTTPException(422, 'Anchor must select a nonempty passage in the source page')
    if not actor.get('sensitive_data_clearance') and redact(printed, tokens()) != printed:
        raise HTTPException(403, 'Manual anchoring on a sensitive page requires clearance')
    record.payload = {**record.payload, 'locator': {'resolved':True, 'layer':'manual', 'start':body.start, 'end':body.end,
                                                 'quote':printed[body.start:body.end], 'actor':actor['id']}}
    record.revision += 1
    db.add(AuditEvent(actor_id=actor['id'], action='manual_anchor', subject=extraction_id))
    db.commit()
    return respond({'ref':record.ref, 'revision':record.revision, 'payload':record.payload}, actor, db, extraction_id)


# Only build output is served; never mount the repository or original fixture.
if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='frontend')
