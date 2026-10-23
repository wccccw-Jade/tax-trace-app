"""Day 7–8: generated views, team coordination, firm controls and frozen quality review."""
from datetime import date
from decimal import Decimal
from uuid import uuid4
import json
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.dependencies import packet,staff,imported,respond,tokens
from backend.persistence.db import session
from backend.persistence.models import Record,PacketImport,AuditEvent,FilingSnapshot,Adjustment
from backend.domain.security import actors,redact
from backend.domain.workpaper import now,get_record,requires_partner,reopen_change
from backend.domain.policy import standards,tax_policy
from backend.domain.breadth import VIEWS,OUTSIDE,generated,visible_records,as_of,completeness,retention
from backend.domain.filing import available,digest

router=APIRouter(prefix='/api/workspace')


def admin(actor):
    if actor['role']!='firm_administrator':raise HTTPException(403,'Firm administrator access required')


def coordinator(actor):
    if actor['role'] not in {'preparer','reviewer','partner','firm_administrator'}:raise HTTPException(403,'Coordination access required')


def saved(db,ref):
    return db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.ref==ref))


def write(db,actor,ref,kind,revision,payload,action):
    # Lock the packet for first-write serialization as well as existing-row revisions.
    db.scalar(select(PacketImport).where(PacketImport.id==packet().digest).with_for_update())
    row=db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.ref==ref).with_for_update().execution_options(populate_existing=True))
    if (row.revision if row else 0)!=revision:
        raise HTTPException(409,{'message':'Another session changed this record. Reload the latest version before saving.',
            'ref':ref,'revision':row.revision if row else 0,'changed_by':row.payload.get('actor_id') if row else None,'at':row.payload.get('at') if row else None,'current':redact({k:v for k,v in row.payload.items() if k!='history'},tokens()) if row and not actor.get('sensitive_data_clearance') else {k:v for k,v in row.payload.items() if k!='history'} if row else None})
    if any(isinstance(v,str) and not v.strip() for v in payload.values()):raise HTTPException(422,'Record a substantive explanation and nonempty fields')
    payload={**payload,'actor_id':actor['id'],'at':now()}
    if row:
        prior={k:v for k,v in row.payload.items() if k!='history'}
        row.payload={**payload,'history':[*row.payload.get('history',[]),{'revision':row.revision,**prior}]}
        row.revision+=1
    else:
        row=Record(packet_id=packet().digest,ref=ref,kind=kind,payload=payload)
        db.add(row)
    db.add(AuditEvent(actor_id=actor['id'],action=action,subject=ref));db.flush()
    if kind=='firm_policy':db.info.pop('standards:'+packet().digest,None)
    return row


class Revision(BaseModel):
    expected_revision:int=Field(ge=0)


class Assignment(Revision):
    subject:str=Field(min_length=1,max_length=200)
    assignee:str
    due:date
    note:str=Field(min_length=1,max_length=3000)
    status:str=Field(default='open',pattern='^(open|done)$')


class Policy(Revision):
    verification_types:list[str]=Field(min_length=1,max_length=20)
    variance_percent:Decimal=Field(ge=0,le=1000,allow_inf_nan=False)
    variance_amount:Decimal=Field(ge=0,allow_inf_nan=False,max_digits=12,decimal_places=2)
    partner_threshold:Decimal=Field(ge=0,allow_inf_nan=False,max_digits=12,decimal_places=2)
    retention_years:int=Field(ge=1,le=100)
    required_steps:list[str]=Field(min_length=1,max_length=40)
    note:str=Field(min_length=1,max_length=3000)
    @field_validator('verification_types','required_steps')
    @classmethod
    def names(cls,items):
        if any(not s.strip() or len(s)>200 for s in items):raise ValueError('Names must be nonempty and under 200 characters')
        return list(dict.fromkeys(s.strip() for s in items))


class Outside(Revision):
    owner:str=Field(min_length=1,max_length=200)
    status:str=Field(pattern='^(open|communicated|completed|outside_scope)$')
    note:str=Field(min_length=1,max_length=3000)


class Area(Revision):
    status:str=Field(pattern='^(open|reviewed|not_applicable)$')
    note:str=Field(min_length=1,max_length=3000)


@router.put('/areas/{key}')
def review_area(key:str,body:Area,actor=Depends(staff),db:Session=Depends(session)):
    from backend.domain.workpaper import require_preparation
    require_preparation(actor);imported(db)
    if key not in {*VIEWS,'business','sales'}:raise HTTPException(404,'Tax area not found')
    r=write(db,actor,'area:'+key,'area_review',body.expected_revision,body.model_dump(exclude={'expected_revision'}),'area_considered')
    db.commit();return {'revision':r.revision}


class TimeWrite(BaseModel):
    area:str
    hours:Decimal=Field(gt=0,le=24,allow_inf_nan=False,max_digits=5,decimal_places=2)
    date:date
    note:str=Field(min_length=1,max_length=3000)


class Hold(Revision):
    active:bool
    reason:str=Field(min_length=1,max_length=3000)


class QualityWrite(BaseModel):
    snapshot_id:str
    claim_key:str|None=None
    conclusion:str=Field(min_length=1,max_length=5000)
    severity:str=Field(pattern='^(observation|follow_up|material)$')


@router.get('/views')
def views(actor=Depends(staff)):
    return [{'id':key,'title':v[0]} for key,v in VIEWS.items()]


@router.get('/views/{view}')
def view(view:str,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    if view not in VIEWS:raise HTTPException(404,'View not found')
    return respond(generated(db,packet(),view),actor,db,'generated-view:'+view)


@router.get('/search')
def search(q:str=Query(min_length=2,max_length=100),actor=Depends(staff),db:Session=Depends(session)):
    imported(db);items=[]
    for r in visible_records(db,packet()).values():
        if r.kind not in {'claim','document','client_evidence','client_answer','question','decision','filing_note','outside_filing'}:continue
        if r.kind=='claim' and r.payload['version']!='v3':continue
        payload=r.payload if actor.get('sensitive_data_clearance') else redact(r.payload,tokens())
        text=json.dumps(payload,ensure_ascii=False,default=str)
        if q.casefold() not in (r.ref+' '+text).casefold():continue
        at=text.casefold().find(q.casefold());snippet=text[max(0,at-45):max(0,at)+160]
        items.append({'ref':r.ref,'kind':r.kind,'title':payload.get('title') or payload.get('label') or payload.get('text') or payload.get('question') or r.ref,'snippet':snippet})
        if len(items)==100:break
    return respond({'items':items,'limit':100,'as_of':as_of(db,packet())},actor,db,'workspace-search')


@router.get('/completeness')
def complete(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    return respond(completeness(db,packet()),actor,db,'completeness')


@router.put('/outside/{key}')
def outside(key:str,body:Outside,actor=Depends(staff),db:Session=Depends(session)):
    coordinator(actor);imported(db)
    if key not in {i['id'] for i in OUTSIDE}:raise HTTPException(404,'Outside filing not found')
    row=write(db,actor,'outside:'+key,'outside_filing',body.expected_revision,body.model_dump(exclude={'expected_revision'}),'outside_filing_updated')
    db.commit();return respond({'ref':row.ref,'revision':row.revision,**row.payload},actor,db,row.ref)


@router.get('/team')
def team(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    assignments=[{'ref':r.ref,'revision':r.revision,**r.payload} for r in db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='assignment'))]
    entries=[{'ref':r.ref,**r.payload} for r in db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='time_entry'))]
    budgets=packet().data['firm']['budget_hours']
    return respond({'assignments':assignments,'default_roles':packet().data['firm']['assignment_at_start'],'as_of':as_of(db,packet()),
        'deadlines':[{**d,'overdue':d['date']<as_of(db,packet())[:10]} for d in packet().data['firm']['deadlines']],
        'budgets':[{'area':k,'budget':v,'actual':str(sum((Decimal(e['hours']) for e in entries if e['area']==k),Decimal(0)))} for k,v in budgets.items()],
        'time_entries':entries},actor,db,'team-workspace')


@router.put('/assignments')
def assign(body:Assignment,actor=Depends(staff),db:Session=Depends(session)):
    coordinator(actor);imported(db)
    person=next((p for p in actors(packet()) if p['id']==body.assignee and p['role']!='client'),None)
    if not person:raise HTTPException(422,'Choose a staff assignee')
    if person.get('active_from','0000')>body.due.isoformat():raise HTTPException(422,'Assignee is not active by this deadline')
    if body.subject not in {'engagement:preparer','engagement:reviewer','engagement:partner'}:
        subject=saved(db,body.subject)
        if not subject or subject.ref not in visible_records(db,packet()):raise HTTPException(422,'Choose an available record or engagement role')
    row=write(db,actor,'assignment:'+body.subject,'assignment',body.expected_revision,{**body.model_dump(mode='json',exclude={'expected_revision'})},'assignment_updated')
    db.commit();return respond({'ref':row.ref,'revision':row.revision,**row.payload},actor,db,row.ref)


@router.post('/time')
def time(body:TimeWrite,actor=Depends(staff),db:Session=Depends(session)):
    coordinator(actor);imported(db)
    if body.area not in packet().data['firm']['budget_hours']:raise HTTPException(422,'Choose a budget area')
    row=write(db,actor,'time:'+uuid4().hex,'time_entry',0,body.model_dump(mode='json'),'time_recorded')
    db.commit();return {'ref':row.ref,'revision':row.revision}


@router.get('/notifications')
def notifications(actor=Depends(staff),db:Session=Depends(session)):
    imported(db);records=visible_records(db,packet());items=[]
    for r in records.values():
        if r.kind=='assignment' and r.payload['assignee']==actor['id'] and r.payload['status']=='open':
            items.append({'id':r.ref+':'+str(r.revision),'title':'Assigned: '+r.payload['subject'],'text':r.payload['note']+' · due '+r.payload['due'],'target':'team'})
        if r.kind=='question' and r.payload.get('status')!='resolved':
            items.append({'id':r.ref+':'+str(r.revision),'title':'Client question '+r.payload.get('status','open'),'text':r.payload.get('prompt',r.ref),'target':'questions'})
    for d in packet().data['firm']['deadlines']:
        if d['date']<as_of(db,packet())[:10]:items.append({'id':'deadline:'+d['what'],'title':'Past due in replay: '+d['what'],'text':d['date']+' · Confirm completion or responsibility in Team & deadlines.','target':'team'})
    from backend.domain.history import MUTATIONS
    for e in db.scalars(select(AuditEvent).where(AuditEvent.actor_id!=actor['id'],AuditEvent.action.in_(MUTATIONS)).order_by(AuditEvent.id.desc()).limit(20)):
        target='team' if e.action in {'assignment_updated','time_recorded'} else 'completeness' if e.action in {'outside_filing_updated','area_considered'} else 'firm' if e.action in {'standards_updated','retention_hold_updated'} else 'questions' if e.action in {'question_asked','client_answered'} else 'history'
        items.append({'id':'activity:'+str(e.id),'title':e.action.replace('_',' ')+' · '+e.actor_id,'text':e.subject+' · '+e.at,'target':target})
    acknowledged={r.payload['notification_id'] for r in records.values() if r.kind=='notification_seen' and r.payload['actor_id']==actor['id']}
    return respond({'items':[{**i,'seen':i['id'] in acknowledged} for i in items],'as_of':as_of(db,packet())},actor,db,'notifications')


class Acknowledge(BaseModel):
    notification_id:str=Field(min_length=1,max_length=500)


@router.post('/notifications/seen')
def acknowledge(body:Acknowledge,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    ref='notice_seen:'+digest([actor['id'],body.notification_id])
    if not saved(db,ref):write(db,actor,ref,'notification_seen',0,body.model_dump(),'notification_seen')
    db.commit();return {'saved':True}


@router.get('/standards')
def policy(actor=Depends(staff),db:Session=Depends(session)):
    imported(db);row=saved(db,'firm:policy')
    return respond({'revision':row.revision if row else 0,'standards':standards(db,packet()),'history':row.payload.get('history',[]) if row else [],'last_change':{k:v for k,v in row.payload.items() if k!='history'} if row else None},actor,db,'firm-standards')


@router.put('/standards')
def edit_policy(body:Policy,actor=Depends(staff),db:Session=Depends(session)):
    admin(actor);imported(db)
    old=standards(db,packet());new={**old,'verification_types':body.verification_types,
        'variance_review':{**old['variance_review'],'flag_if_change_over_percent':float(body.variance_percent),'and_over_amount':float(body.variance_amount)},
        'partner_threshold':float(body.partner_threshold),'retention_years':body.retention_years,'required_steps':body.required_steps}
    new['rules']=[f"Any adjustment with a tax effect over {body.partner_threshold} (federal or state) requires partner sign-off." if r.startswith('Any adjustment') else f"Retention eligibility begins {body.retention_years} years after filing; holds apply and deletion is disabled in this prototype." if r.startswith('Records are retained') or r.startswith('Retention eligibility') else r for r in old.get('rules',[])]
    mandatory={'Reviewer sign-off','Partner sign-off','Client approval and e-file authorization'}
    if not mandatory.issubset(new['required_steps']):raise HTTPException(422,'Independent reviewer, partner and client authorization steps must remain required')
    row=write(db,actor,'firm:policy','firm_policy',body.expected_revision,{'standards':new,'note':body.note},'standards_updated')
    reopened=[]
    changed_tax_policy=any(old[k]!=new[k] for k in ('verification_types','variance_review','required_steps','partner_threshold'))
    # Only adjustments crossing into a stricter partner requirement lose reviewer approval.
    for a,r in db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet().digest,Adjustment.status=='approved')):
        from backend.domain.workpaper import approval_is_current
        if changed_tax_policy and not approval_is_current(db,packet(),r,a):reopened.append(reopen_change(db,packet(),r,a,actor['id'],row.ref,row.revision,'Firm tax-review standards changed; verify the permitted method and any partner requirement before fresh review.'))
    db.commit();return respond({'revision':row.revision,'standards':new,'reopened':reopened},actor,db,row.ref)


@router.get('/retention')
def retention_view(actor=Depends(staff),db:Session=Depends(session)):
    admin(actor);imported(db);return respond(retention(db,packet()),actor,db,'retention')


@router.put('/retention/{snapshot_id}')
def retention_hold(snapshot_id:str,body:Hold,actor=Depends(staff),db:Session=Depends(session)):
    admin(actor);imported(db)
    s=db.get(FilingSnapshot,snapshot_id)
    if not s or s.packet_id!=packet().digest:raise HTTPException(404,'Frozen copy not found')
    r=write(db,actor,'hold:'+snapshot_id,'retention_hold',body.expected_revision,{'snapshot_id':snapshot_id,'active':body.active,'reason':body.reason},'retention_hold_updated')
    db.commit();return {'revision':r.revision}


@router.get('/quality')
def quality(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    if actor['role'] not in {'quality_reviewer','partner'}:raise HTTPException(403,'Quality reviewer or partner access required')
    copies=[{'id':s.id,'sha256':s.digest,'parent_id':s.parent_id,'branch_ref':s.branch_ref,'at':s.at} for s in db.scalars(select(FilingSnapshot).where(FilingSnapshot.packet_id==packet().digest))]
    findings=[{'ref':r.ref,**r.payload} for r in db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='quality_finding'))]
    return respond({'snapshots':copies,'findings':findings,'as_of':as_of(db,packet()),'note':'Inspect immutable submitted copies. Findings are separate records and never alter the frozen return.'},actor,db,'quality-review')


@router.post('/quality')
def quality_finding(body:QualityWrite,actor=Depends(staff),db:Session=Depends(session)):
    if actor['role']!='quality_reviewer':raise HTTPException(403,'Quality reviewer access required')
    imported(db);s=db.get(FilingSnapshot,body.snapshot_id)
    if not s or s.packet_id!=packet().digest:raise HTTPException(404,'Frozen copy not found')
    if body.claim_key and body.claim_key not in s.content['lines']:raise HTTPException(422,'Choose a claim from this frozen copy')
    r=write(db,actor,'quality:'+uuid4().hex,'quality_finding',0,body.model_dump(),'quality_finding_recorded')
    db.commit();return {'ref':r.ref}
