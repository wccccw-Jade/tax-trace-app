"""Atomic bulk verification of checked rows, with append-only reversal history."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.dependencies import packet, staff, respond, imported
from backend.persistence.db import session
from backend.persistence.models import Record, Verification, AuditEvent
from backend.domain.sales import sales_checks
from backend.domain.workpaper import get_record, require_preparation, mark_preparer, now, projected_summary

router=APIRouter(prefix='/api/sales')


class BulkWrite(BaseModel):
    selection_token:str
    refs:list[str]=Field(min_length=1,max_length=300)
    note:str=Field(min_length=1,max_length=5000)

    @field_validator('note')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Describe the source checks covered by this verification')
        return v.strip()


class UndoWrite(BaseModel):
    expected_revision:int=Field(ge=1)


def operation_view(row):
    return {'ref':row.ref,'revision':row.revision,**row.payload}


@router.get('')
def sales(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    result=sales_checks(db,packet())
    operations=db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='bulk_operation').order_by(Record.id.desc()))
    result['operations']=[operation_view(r) for r in operations]
    summary=projected_summary(db,packet())
    changed={l['key']:l for l in summary['changed_lines']}
    result['classification_changes']=summary['classification_changes']
    result['totals']=[{'ref':'v3:'+l['key'],'label':l['label'],'value':changed.get(l['key'],{}).get('value',l['value']),'basis':changed.get(l['key'],{}).get('basis','engine')} for l in packet().data['return_versions'][-1]['lines'] if l['form']=='F8949' and l['key'].endswith('.total')]
    return respond(result,actor,db,'sales-checks')


@router.post('/verify')
def bulk_verify(body:BulkWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    selected=set(body.refs)
    # Lock the subjects before rebuilding the selection from current evidence.
    records=list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.ref.in_(selected)).order_by(Record.id).with_for_update()))
    checks=sales_checks(db,packet())
    if body.selection_token!=checks['selection_token']:
        raise HTTPException(409,'Sales or evidence changed; reload the checked selection')
    allowed={r['ref']:r for r in checks['rows'] if r['eligible']}
    if not selected<=allowed.keys() or len(records)!=len(selected):
        raise HTTPException(422,'Select only rows with passed source checks and no existing verification')
    operation='bulk:'+uuid4().hex
    revisions={}
    for record in records:
        row=allowed[record.ref]
        mark_preparer(record,actor)
        record.revision+=1
        revisions[record.ref]=record.revision
        db.add(Verification(record_id=record.id,actor_id=actor['id'],method='agreed_to_source_document',note=body.note,
            evidence=row['evidence'],value=str(record.payload['value']),subject_revision=record.revision,
            fingerprint=row['fingerprint'],at=now(),operation_id=operation))
        db.add(AuditEvent(actor_id=actor['id'],action='bulk_claim_verified',subject=record.ref))
    op=Record(packet_id=packet().digest,ref=operation,kind='bulk_operation',payload={
        'actor_id':actor['id'],'at':now(),'status':'applied','note':body.note,'claim_revisions':revisions,'count':len(records)})
    db.add(op)
    db.add(AuditEvent(actor_id=actor['id'],action='bulk_verified',subject=operation))
    db.commit()
    return respond(operation_view(op),actor,db,operation)


@router.post('/operations/{operation_ref}/undo')
def undo(operation_ref:str,body:UndoWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    op=get_record(db,packet(),operation_ref,body.expected_revision,True)
    if op.kind!='bulk_operation':
        raise HTTPException(404,'Verification operation not found')
    if op.payload['status']!='applied':
        raise HTTPException(409,'This operation has already been reversed')
    if actor['id']!=op.payload['actor_id'] and actor['role'] not in {'reviewer','partner'}:
        raise HTTPException(403,'Only the author or a reviewer can reverse this operation')
    subjects=list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.ref.in_(op.payload['claim_revisions'])).order_by(Record.id).with_for_update()))
    if any(r.revision!=op.payload['claim_revisions'][r.ref] for r in subjects):
        raise HTTPException(409,'A selected claim changed after verification; review it before undoing this batch')
    at=now()
    checks=list(db.scalars(select(Verification).where(Verification.operation_id==op.ref)))
    for check in checks:
        check.reversed_at=at
        check.reversed_by=actor['id']
    for record in subjects:
        record.revision+=1
        db.add(AuditEvent(actor_id=actor['id'],action='bulk_verification_reversed',subject=record.ref))
    op.payload={**op.payload,'status':'reversed','reversed_at':at,'reversed_by':actor['id']}
    op.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='bulk_undo',subject=op.ref))
    db.commit()
    return respond(operation_view(op),actor,db,op.ref)
