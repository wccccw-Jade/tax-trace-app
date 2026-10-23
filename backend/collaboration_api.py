"""Client-facing questions and evidence; internal, independently reviewed decisions."""
import base64
import binascii
import hashlib
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.dependencies import packet, identity, staff, imported, respond
from backend.persistence.db import session
from backend.persistence.models import Record, Edge, AuditEvent, Adjustment
from backend.domain.workpaper import (get_record, now, require_preparation, evidence_refs,
    mark_preparer, current_values, contributor_ids, fingerprint, adjustments_for,
    estimated_effect, category_for, reopen_affected_approvals, requires_partner)
from backend.workpaper_api import apply_adjustment_review
from backend.storage import attachments

router=APIRouter(prefix='/api/collaboration')


class RevisionWrite(BaseModel):
    expected_revision:int=Field(ge=1)


class QuestionWrite(RevisionWrite):
    recipient:str
    prompt:str=Field(min_length=1,max_length=5000)

    @field_validator('prompt')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Enter a question for the client')
        return v.strip()


class FileWrite(BaseModel):
    filename:str=Field(min_length=1,max_length=200)
    content_base64:str=Field(max_length=7_000_000)


class AnswerWrite(RevisionWrite):
    text:str=Field(min_length=1,max_length=10000)
    files:list[FileWrite]=Field(default_factory=list,max_length=3)

    @field_validator('text')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Enter your answer')
        return v.strip()


class DecisionWrite(RevisionWrite):
    question:str=Field(min_length=1,max_length=5000)
    alternatives:list[str]=Field(min_length=2,max_length=10)
    choice:str=Field(min_length=1,max_length=2000)
    authority:str=Field(min_length=1,max_length=5000)
    rationale:str=Field(min_length=1,max_length=10000)
    outcome:Literal['accepted','needs_evidence']='accepted'
    evidence:list[str]=Field(min_length=1,max_length=30)
    proposed_value:Decimal|None=Field(default=None,allow_inf_nan=False,max_digits=18,decimal_places=2)
    cost_basis:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False,max_digits=18,decimal_places=2)
    acquired_on:date|None=None

    @field_validator('question','choice','authority','rationale')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Decision, authority and rationale must not be blank')
        return v.strip()

    @field_validator('alternatives')
    @classmethod
    def distinct_options(cls,v):
        v=list(dict.fromkeys(x.strip() for x in v if x.strip()))
        if len(v)<2:
            raise ValueError('Record at least two distinct alternatives')
        return v


class DecisionReview(RevisionWrite):
    expected_claim_revision:int=Field(ge=1)
    decision:Literal['approved','rejected']
    note:str=Field(min_length=1,max_length=5000)

    @field_validator('note')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('A review conclusion is required')
        return v.strip()


def node(db,kind,payload):
    row=Record(packet_id=packet().digest,ref=kind+':'+uuid4().hex,kind=kind,payload=payload)
    db.add(row)
    db.flush()
    return row


def link(db,source,target,kind='supports'):
    existing=db.scalar(select(Edge.id).where(Edge.packet_id==packet().digest,Edge.source==source,Edge.target==target,Edge.kind==kind))
    if existing is None:
        db.add(Edge(packet_id=packet().digest,source=source,target=target,kind=kind,resolved=True))


def question_access(db,ref,actor,revision=None,lock=False):
    question=get_record(db,packet(),ref,revision,lock)
    if question.kind!='question' or (actor['role']=='client' and question.payload['recipient']!=actor['id']):
        raise HTTPException(404,'Question not found')
    return question


def question_view(db,row,client=False):
    p=row.payload
    answers=list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='client_answer',Record.payload['question_ref'].as_string()==row.ref).order_by(Record.id)))
    # Explicit projection: clients never receive internal claim payloads or decision notes.
    return {'ref':row.ref,'revision':row.revision,'prompt':p['prompt'],'recipient':p['recipient'],
        'claim_ref':p['claim_ref'],'claim_label':p['claim_label'],'status':p['status'],'at':p['at'],
        'answers':[{'ref':a.ref,'text':a.payload['text'],'actor_id':a.payload['actor_id'],'at':a.payload['at'],
                    'files':a.payload['files']} for a in answers]}


@router.get('/questions')
def questions(ref:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
    if actor['role']!='client':staff(actor,db)
    imported(db)
    query=select(Record).where(Record.packet_id==packet().digest,Record.kind=='question').order_by(Record.id.desc())
    if actor['role']=='client':
        query=query.where(Record.payload['recipient'].as_string()==actor['id'])
    if ref:
        query=query.where(Record.payload['claim_ref'].as_string()==ref)
    return respond([question_view(db,r) for r in db.scalars(query)],actor,db,'client-questions')


@router.post('/questions')
def ask(ref:str,body:QuestionWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    claim=get_record(db,packet(),ref,body.expected_revision,True)
    if claim.kind!='claim' or claim.payload['version']!='v3':
        raise HTTPException(422,'Ask from a current-return claim')
    from backend.domain.security import actor_by_id
    from backend.domain.breadth import as_of
    recipient=actor_by_id(packet(),body.recipient)
    if not recipient or recipient['role'] not in {'client','preparer','reviewer','partner'}:
        raise HTTPException(422,'Select a client or tax-team colleague')
    if recipient.get('active_from','0000')>as_of(db,packet())[:10]:
        raise HTTPException(422,'This colleague is not active at the current replay date')
    q=node(db,'question',{'claim_ref':ref,'claim_label':claim.payload['label'],'prompt':body.prompt,
        'recipient':body.recipient,'actor_id':actor['id'],'at':now(),'status':'open'})
    # Asking is review activity, not evidence preparation. Answers get evidence edges when received.
    claim.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='question_asked',subject=q.ref))
    db.commit()
    return respond(question_view(db,q),actor,db,q.ref)


@router.post('/questions/{question_ref}/answers')
def answer(question_ref:str,body:AnswerWrite,actor=Depends(identity),db:Session=Depends(session)):
    if actor['role']!='client':
        staff(actor,db)
        require_preparation(actor)
    imported(db)
    q=question_access(db,question_ref,actor,body.expected_revision,True)
    if q.payload['recipient']!=actor['id']:
        raise HTTPException(403,'Only the assigned recipient can answer')
    if q.payload['status']=='resolved':
        raise HTTPException(409,'This question is resolved; ask the firm to open a follow-up')
    decoded=[]
    for file in body.files:
        name=PurePath(file.filename.replace('\\','/')).name
        if not name or any(ord(c)<32 for c in name):
            raise HTTPException(422,'Use a valid filename')
        try:
            data=base64.b64decode(file.content_base64,validate=True)
        except (ValueError,binascii.Error):
            raise HTTPException(422,'Invalid attachment encoding')
        if not data or len(data)>5*1024*1024:
            raise HTTPException(422,'Each attachment must contain 1 byte to 5 MB')
        decoded.append((name,data))
    claim=get_record(db,packet(),q.payload['claim_ref'],lock=True)
    written=[]
    try:
        a=node(db,'client_answer',{'question_ref':q.ref,'text':body.text,'actor_id':actor['id'],'at':now(),'files':[],'preparers':[actor['id']] if actor['role']!='client' else []})
        files=[]
        for name,data in decoded:
            key=attachments.put(data)
            written.append(key)
            file=node(db,'attachment',{'question_ref':q.ref,'answer_ref':a.ref,'filename':name,'storage_key':key,
                'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'actor_id':actor['id'],'at':now()})
            files.append({'ref':file.ref,'filename':name,'size':len(data),'sha256':file.payload['sha256']})
            link(db,a.ref,file.ref)
        a.payload={**a.payload,'files':files}
        q.payload={**q.payload,'status':'answered'}
        q.revision+=1
        link(db,claim.ref,a.ref)
        link(db,a.ref,q.ref,'answers')
        claim.revision+=1
        db.add(AuditEvent(actor_id=actor['id'],action='client_answered',subject=a.ref))
        reopen_affected_approvals(db,packet(),a,actor['id'])
        db.commit()
    except Exception:
        db.rollback()
        for key in written:
            attachments.remove(key)
        raise
    result=question_view(db,q)
    # Client gets their thread, not internal approval identifiers.
    return respond(result,actor,db,q.ref)


@router.post('/questions/{question_ref}/resolve')
def resolve_question(question_ref:str,body:RevisionWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    q=question_access(db,question_ref,actor,body.expected_revision,True)
    if q.payload['status']!='answered':
        raise HTTPException(409,'Receive a client answer before resolving the question')
    q.payload={**q.payload,'status':'resolved','resolved_by':actor['id'],'resolved_at':now()}
    # Resolving the task does not alter the immutable client answer or its evidence.
    q.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='question_resolved',subject=q.ref))
    db.commit()
    return respond(question_view(db,q),actor,db,q.ref)


@router.get('/attachments/{attachment_ref}')
def download(attachment_ref:str,actor=Depends(identity),db:Session=Depends(session)):
    row=get_record(db,packet(),attachment_ref)
    if row.kind!='attachment':
        raise HTTPException(404,'Attachment not found')
    question_access(db,row.payload['question_ref'],actor)
    if actor['role']!='client' and not actor.get('sensitive_data_clearance'):
        raise HTTPException(403,'Sensitive-data clearance is required to download original attachments')
    try:
        data=attachments.read(row.payload['storage_key'])
    except FileNotFoundError:
        raise HTTPException(404,'Attachment file is unavailable')
    db.add(AuditEvent(actor_id=actor['id'],action='attachment_downloaded',subject=row.ref))
    db.commit()
    return Response(data,media_type='application/octet-stream',headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.payload['filename']),
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})


def decision_view(db,row):
    p=row.payload
    claim=get_record(db,packet(),p['claim_ref'])
    change=db.get(Adjustment,p['adjustment_id']) if p.get('adjustment_id') else None
    value=change.proposed_value if change else p['value']
    current=fingerprint(db,packet(),claim,value,p['evidence'])
    reviews=[{**r,'current':r['fingerprint']==current} for r in p.get('reviews',[])]
    status=p['status']
    if status=='approved' and (not reviews or not reviews[-1]['current'] or (change and change.status!='approved')):
        status='stale'
    if status=='approved' and p.get('outcome')=='needs_evidence':
        status='needs_evidence'
    return {'ref':row.ref,'revision':row.revision,**p,'status':status,'reviews':reviews,
        'claim_revision':claim.revision,'requires_partner':requires_partner(change,db,packet()) if change else False}


@router.get('/decisions')
def decisions(ref:str,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    rows=db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='decision',Record.payload['claim_ref'].as_string()==ref).order_by(Record.id.desc()))
    return respond([decision_view(db,r) for r in rows],actor,db,ref)


@router.post('/decisions')
def decide(ref:str,body:DecisionWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    claim=get_record(db,packet(),ref,body.expected_revision,True)
    if claim.kind!='claim' or claim.payload.get('version')!='v3' or not isinstance(claim.payload.get('value'),(int,float)):
        raise HTTPException(422,'Record a judgment on a numeric current-return claim')
    if body.choice not in body.alternatives:
        raise HTTPException(422,'The chosen treatment must be one of the alternatives')
    refs=evidence_refs(packet(),body.evidence,db)
    if ref=='v3:SchCA540NR.1.E' and not any(r in refs for r in ('D73','doc:D73#page1','ev-1081')):
        raise HTTPException(422,'The wage allocation decision must cite D73 and reconcile work dates and HSA treatment')
    pending,approved,engine,value=current_values(db,claim,packet())
    if pending:
        raise HTTPException(409,'Resolve the existing proposal before recording a decision')
    if db.scalar(select(Record.id).where(Record.packet_id==packet().digest,Record.kind=='decision',Record.payload['claim_ref'].as_string()==ref,Record.payload['status'].as_string()=='proposed')):
        raise HTTPException(409,'Review the existing decision first')
    if body.outcome=='needs_evidence' and any(v is not None for v in (body.proposed_value,body.cost_basis,body.acquired_on)):
        raise HTTPException(422,'A decision awaiting evidence preserves the current claim; leave correction fields blank')
    proposed=body.proposed_value
    treatment=None
    if body.cost_basis is not None or body.acquired_on is not None:
        if ref!='v3:F8949.H.C6' or body.cost_basis is None or body.acquired_on is None:
            raise HTTPException(422,'For C6, record both cost basis and acquisition date')
        sold=date.fromisoformat(packet().resolve('ev-0881')['value'])
        if body.acquired_on>sold:
            raise HTTPException(422,'Acquisition must be on or before the sale date')
        proceeds=Decimal(str(packet().resolve('ev-0882')['value']))
        computed=proceeds-body.cost_basis
        if proposed is not None and proposed!=computed:
            raise HTTPException(422,'C6 gain must equal proceeds minus the documented basis')
        proposed=computed
        long_term=(sold-body.acquired_on).days>365
        treatment={'cost_basis':str(body.cost_basis),'acquired_on':body.acquired_on.isoformat(),
            'holding_period':'long-term' if long_term else 'short-term','target_total':'F8949.K.total' if long_term else 'F8949.H.total',
            'engine_total':'F8949.H.total'}
    change=None
    if proposed is not None and (proposed!=Decimal(value) or treatment):
        if claim.payload.get('inputs') and ref!='v3:SchCA540NR.1.E':
            raise HTTPException(422,'Record the correction on the source line, not a derived total')
        category=category_for(packet(),claim)
        effect=estimated_effect(packet(),claim,proposed,category)
        if treatment:
            rates=packet().data['return_versions'][-1]['tax_effect_rates']
            target='ltcg' if treatment['holding_period']=='long-term' else 'stcg'
            effect['tax_change']={j:str((proposed*Decimal(str(rates[target][j+'_per_dollar']))-Decimal(engine)*Decimal(str(rates['stcg'][j+'_per_dollar']))).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) for j in ('federal','california')}
            effect['balance_change']=effect['tax_change']
            effect['treatment']=treatment
            effect['note']='Rate estimate: remove the engine short-term gain and add the chosen gain at its holding-period rate. Box totals and Schedule D remain affected, not recomputed.'
        change=Adjustment(record_id=claim.id,actor_id=actor['id'],original_value=engine,proposed_value=str(proposed),category=category,
            reason=body.rationale,evidence=refs,effect=effect,status='proposed',at=now())
        db.add(change)
        db.flush()
    decision=node(db,'decision',{'claim_ref':ref,'question':body.question,'alternatives':body.alternatives,'choice':body.choice,
        'authority':body.authority,'rationale':body.rationale,'outcome':body.outcome,'evidence':refs,'actor_id':actor['id'],'at':now(),'status':'proposed',
        'adjustment_id':change.id if change else None,'value':str(proposed) if change else value,'treatment':treatment,'reviews':[]})
    for evidence in refs:
        link(db,decision.ref,evidence)
    link(db,decision.ref,ref,'subject')
    mark_preparer(claim,actor)
    claim.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='decision_recorded',subject=decision.ref))
    db.commit()
    return respond(decision_view(db,decision),actor,db,ref)


@router.post('/decisions/{decision_ref}/review')
def review_decision(decision_ref:str,body:DecisionReview,actor=Depends(staff),db:Session=Depends(session)):
    row=get_record(db,packet(),decision_ref,body.expected_revision,True)
    if row.kind!='decision':
        raise HTTPException(404,'Decision not found')
    p=row.payload
    claim=get_record(db,packet(),p['claim_ref'],body.expected_claim_revision,True)
    state=decision_view(db,row)
    if state['status'] not in {'proposed','stale'}:
        raise HTTPException(409,'Decision is no longer awaiting review')
    if actor['role'] not in {'reviewer','partner'} or actor['id'] in contributor_ids(db,packet(),claim,p['evidence']) or actor['id']==p['actor_id']:
        raise HTTPException(403,'Independent reviewer or partner required; you cannot review work you prepared')
    change=db.get(Adjustment,p['adjustment_id']) if p.get('adjustment_id') else None
    if change:
        apply_adjustment_review(db,packet(),claim,change,actor,body.decision,body.note)
    else:
        # A judgment without a numeric adjustment preserves the current return value.
        _,_,_,current=current_values(db,claim,packet())
        if current!=p['value']:
            raise HTTPException(409,'The claim value changed; record a new decision on the current value')
        claim.revision+=1
    review={'actor_id':actor['id'],'decision':body.decision,'note':body.note,'at':now(),
        'fingerprint':fingerprint(db,packet(),claim,p['value'],p['evidence'])}
    row.payload={**p,'status':body.decision,'reviews':[*p['reviews'],review]}
    row.revision+=1
    db.add(AuditEvent(actor_id=actor['id'],action='decision_'+body.decision,subject=row.ref))
    db.commit()
    return respond(decision_view(db,row),actor,db,claim.ref)
