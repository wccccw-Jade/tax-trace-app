from functools import lru_cache
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from backend.config import settings
from backend.domain.packet import Packet
from backend.domain.security import actor_by_id, sensitive_tokens, redact, STAFF_ROLES
from backend.persistence.db import session
from backend.persistence.models import DemoSession, AuditEvent, PacketImport

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

def staff(actor=Depends(identity), db: Session = Depends(session)):
    if actor['role'] not in STAFF_ROLES:
        raise HTTPException(403, 'Internal workpaper: staff access required.')
    from backend.domain.breadth import as_of
    current=as_of(db,packet())
    if actor.get('active_from','0000')>current[:10]:
        raise HTTPException(403,'This staff member is not active at the current replay date.')
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

