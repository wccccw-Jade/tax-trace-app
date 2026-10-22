"""Story-A routes. Every mutation locks/checks the subject revision and commits its audit event."""
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from backend.dependencies import packet, staff, respond, imported
from backend.persistence.db import session
from backend.persistence.models import Record, Edge, AuditEvent, Verification, Adjustment, AdjustmentReview
from backend.domain.workpaper import (now, require_preparation, get_record, evidence_refs, mark_preparer,
    fingerprint, contributor_ids, adjustments_for, current_values, category_for, estimated_effect, workflow, projected_summary)

router=APIRouter(prefix='/api/workpaper')

class EvidenceWrite(BaseModel):
    expected_revision:int=Field(ge=1)
    evidence:list[str]=Field(min_length=1,max_length=30)

class VerificationWrite(EvidenceWrite):
    method:str
    note:str=Field(min_length=1,max_length=5000)
    @field_validator('note')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('A verification note is required')
        return v.strip()

class ProposalWrite(EvidenceWrite):
    proposed_value:Decimal=Field(allow_inf_nan=False,max_digits=18,decimal_places=2)
    reason:str=Field(min_length=1,max_length=5000)
    @field_validator('reason')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('A correction reason is required')
        return v.strip()

class ReviewWrite(BaseModel):
    expected_revision:int=Field(ge=1)
    decision:Literal['approved','rejected']
    note:str=Field(min_length=1,max_length=5000)
    @field_validator('note')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('A review note is required')
        return v.strip()

class DispositionWrite(BaseModel):
    expected_revision:int=Field(ge=1)
    disposition:Literal['used','duplicate','superseded','supporting','outside_scope','unextracted_reviewed','unresolved']
    reason:str=Field(min_length=1,max_length=5000)
    duplicate_of:str|None=None
    @field_validator('reason')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('A disposition reason is required')
        return v.strip()

@router.get('/claim')
def claim(ref:str,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    record=get_record(db,packet(),ref)
    if record.kind!='claim':
        raise HTTPException(422,'Choose a return line')
    return respond(workflow(db,packet(),record),actor,db,ref)

@router.get('/status')
def statuses(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    rows=list(db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet().digest).order_by(Adjustment.id.desc())))
    result={}
    for change,record in rows:
        if record.ref in result:
            continue
        reviews=list(db.scalars(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==change.id)))
        current=all(review.fingerprint==fingerprint(db,packet(),record,change.proposed_value,review.evidence) for review in reviews)
        result[record.ref]={'status':'stale' if change.status=='approved' and not current else change.status,'proposed_value':change.proposed_value}
    return respond(result,actor,db,'workpaper-status')

@router.get('/summary')
def summary(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    return respond(projected_summary(db,packet()),actor,db,'workpaper-summary')

@router.post('/verify')
def verify(ref:str,body:VerificationWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    record=get_record(db,packet(),ref,body.expected_revision,lock=True)
    if record.kind!='claim' or record.payload.get('version')!='v3':
        raise HTTPException(422,'Verification is available on current v3 claims')
    methods=packet().data['firm']['starter_standards']['verification_types']
    if body.method not in methods:
        raise HTTPException(422,'Unknown firm verification method')
    pending,approved,engine,applied=current_values(db,record)
    value=pending.proposed_value if pending else applied
    try:
        Decimal(value)
    except Exception:
        raise HTTPException(422,'This story supports numeric return-line verification')
    refs=evidence_refs(packet(),body.evidence)
    refs=list(dict.fromkeys([*refs,*(pending.evidence if pending else approved.evidence if approved else [])]))
    mark_preparer(record,actor)
    record.revision+=1
    db.add(Verification(record_id=record.id,actor_id=actor['id'],method=body.method,note=body.note,evidence=refs,
                        value=value,subject_revision=record.revision,fingerprint=fingerprint(db,packet(),record,value,refs),at=now()))
    db.add(AuditEvent(actor_id=actor['id'],action='verification_recorded',subject=record.ref))
    db.commit()
    return respond(workflow(db,packet(),record),actor,db,ref)

@router.post('/adjustments')
def propose(ref:str,body:ProposalWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    record=get_record(db,packet(),ref,body.expected_revision,lock=True)
    if record.kind!='claim' or record.payload.get('version')!='v3' or not isinstance(record.payload.get('value'),(int,float)) or isinstance(record.payload.get('value'),bool):
        raise HTTPException(422,'Choose a numeric current-return claim')
    if record.payload.get('inputs'):
        raise HTTPException(422,'Adjust the source line, not a derived total, to avoid double-counting tax effects')
    if any(a.status=='proposed' for a in adjustments_for(db,record)):
        raise HTTPException(409,'A proposal is already awaiting review')
    _,_,_,applied=current_values(db,record)
    if body.proposed_value==Decimal(applied):
        raise HTTPException(422,'Proposed value must differ from the approved value')
    refs=evidence_refs(packet(),body.evidence)
    category=category_for(packet(),record)
    effect=estimated_effect(packet(),record,body.proposed_value,category)
    change=Adjustment(record_id=record.id,actor_id=actor['id'],original_value=str(record.payload['value']),proposed_value=str(body.proposed_value),category=category,reason=body.reason,evidence=refs,effect=effect,status='proposed',at=now())
    db.add(change)
    mark_preparer(record,actor)
    record.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='adjustment_proposed',subject=record.ref))
    db.commit()
    return respond(workflow(db,packet(),record),actor,db,ref)

@router.post('/adjustments/{adjustment_id}/review')
def review(adjustment_id:int,body:ReviewWrite,actor=Depends(staff),db:Session=Depends(session)):
    change=db.get(Adjustment,adjustment_id)
    if not change:
        raise HTTPException(404,'Adjustment not found')
    subject=db.get(Record,change.record_id)
    if subject.packet_id!=packet().digest:
        raise HTTPException(404,'Adjustment not found in this engagement')
    record=get_record(db,packet(),subject.ref,body.expected_revision,lock=True)
    db.refresh(change)
    if change.status!='proposed':
        raise HTTPException(409,'Adjustment is no longer awaiting review')
    if actor['id'] in contributor_ids(db,packet(),record,change.evidence) or actor['id']==change.actor_id:
        raise HTTPException(403,'You prepared this claim or its evidence and cannot review your own work')
    if actor['role'] not in {'reviewer','partner'}:
        raise HTTPException(403,'Independent reviewer or partner access required')
    material=max(abs(Decimal(v)) for v in change.effect['tax_change'].values())>1000
    if material and actor['role']!='partner' and body.decision=='approved':
        raise HTTPException(403,'Tax effect exceeds $1,000; independent partner approval required')
    refs=change.evidence
    if body.decision=='approved':
        valid=[]
        for check in db.scalars(select(Verification).where(Verification.record_id==record.id)):
            evidence=list(dict.fromkeys([*check.evidence,*change.evidence]))
            if check.fingerprint==fingerprint(db,packet(),record,change.proposed_value,evidence):
                valid.append(check)
        if not valid:
            raise HTTPException(409,'Record a current verification of the proposed value before approval')
        refs=list(dict.fromkeys([*refs,*valid[-1].evidence]))
        for old in adjustments_for(db,record):
            if old.status=='approved':
                old.status='superseded'
    change.status=body.decision
    db.add(AdjustmentReview(adjustment_id=change.id,actor_id=actor['id'],decision=body.decision,note=body.note,evidence=refs,
                            fingerprint=fingerprint(db,packet(),record,change.proposed_value,refs),at=now()))
    record.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='adjustment_'+body.decision,subject=record.ref))
    db.commit()
    return respond(workflow(db,packet(),record),actor,db,record.ref)

@router.put('/documents/{document_id}')
def disposition(document_id:str,body:DispositionWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    record=get_record(db,packet(),document_id,body.expected_revision,lock=True)
    if record.kind!='document':
        raise HTTPException(422,'Choose a document')
    if body.disposition=='duplicate':
        other=get_record(db,packet(),body.duplicate_of or '')
        if other.id==record.id or other.kind!='document':
            raise HTTPException(422,'Select a different original document')
    old={k:record.payload.get(k) for k in ('disposition','disposition_reason','duplicate_of')}
    history=record.payload.get('disposition_history',[])
    history=[*history,{'before':old,'actor':actor['id'],'at':now()}]
    record.payload={**record.payload,'disposition':body.disposition,'disposition_reason':body.reason,
                    'duplicate_of':body.duplicate_of if body.disposition=='duplicate' else None,
                    'disposition_actor':actor['id'],'disposition_at':now(),'disposition_history':history}
    mark_preparer(record,actor)
    record.revision+=1
    db.execute(delete(Edge).where(Edge.packet_id==packet().digest,Edge.source==document_id,Edge.kind=='duplicate'))
    if body.disposition=='duplicate':
        db.add(Edge(packet_id=packet().digest,source=document_id,target=body.duplicate_of,kind='duplicate',resolved=True))
    db.add(AuditEvent(actor_id=actor['id'],action='document_disposition',subject=document_id))
    db.commit()
    return respond({'ref':record.ref,'revision':record.revision,'payload':record.payload},actor,db,record.ref)
