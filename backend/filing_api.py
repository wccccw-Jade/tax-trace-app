"""Simulated filing, exact-draft approvals, immutable copies and post-filing records."""
from copy import deepcopy
from datetime import date
import hashlib
import re
from decimal import Decimal,ROUND_HALF_UP
import base64
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.dependencies import packet,staff,identity,imported,respond
from backend.persistence.db import session
from backend.persistence.models import Record,AuditEvent,FilingSnapshot,Verification,Adjustment,AdjustmentReview,Edge
from backend.domain.filing import branch,state,current_lines,available,canonical,digest,resolution_fingerprint,START,AUTO_STEPS,change_fingerprint
from backend.domain.workpaper import now,require_preparation,get_record,evidence_refs,evidence_graph,category_for,estimated_effect,contributor_ids,scope_records
from backend.domain.formulas import D
from backend.storage import attachments

router=APIRouter(prefix='/api/filing')


class Revision(BaseModel):
    expected_revision:int=Field(ge=1)


class Explained(Revision):
    note:str=Field(min_length=1,max_length=10000)
    evidence:list[str]=Field(min_length=1,max_length=30)
    @field_validator('note')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Record a substantive explanation')
        return v.strip()


class StepWrite(Explained):
    name:str


class ResolutionWrite(Explained):
    target:str
    authority:str=Field(min_length=1,max_length=5000)
    conclusion:str=Field(min_length=1,max_length=5000)
    resolved_amount:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False,max_digits=18,decimal_places=2)
    reasoned_none:bool=False
    @field_validator('authority','conclusion')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():
            raise ValueError('Authority and conclusion are required')
        return v.strip()


class ReviewWrite(Revision):
    decision:str=Field(pattern='^(approved|rejected)$')
    note:str=Field(min_length=1,max_length=5000)


class SignWrite(Revision):
    fingerprint:str
    kind:str=Field(pattern='^(reviewer|partner|final_computation)$')
    note:str=Field(min_length=1,max_length=10000)


class AuthorizeWrite(Revision):
    fingerprint:str
    authorize:bool


class SubmitWrite(Revision):
    fingerprint:str
    supersedes:str|None=None


class NoteWrite(Revision):
    text:str=Field(min_length=1,max_length=5000)
    blocking:bool=True


class ChangeWrite(Explained):
    key:str
    proposed_value:Decimal|None=Field(default=None,allow_inf_nan=False,max_digits=18,decimal_places=2)
    authority:str=Field(min_length=1,max_length=5000)


class BranchWrite(BaseModel):
    parent_snapshot:str


def node(db,kind,payload):
    r=Record(packet_id=packet().digest,ref=kind+':'+uuid4().hex,kind=kind,payload=payload)
    db.add(r)
    db.flush()
    return r


def event(db,actor,action,subject):
    db.add(AuditEvent(actor_id=actor['id'],action=action,subject=subject))


def prep(actor,row):
    require_preparation(actor)
    active=actor.get('active_from')
    if active and active>row.payload['as_of'][:10]:
        raise HTTPException(403,'This staff member was not active at this replay date')


def refs(db,row,evidence):
    result=evidence_refs(packet(),evidence,db)
    records,_=evidence_graph(db,packet())
    if not all(available(packet(),r,row.payload['as_of'],records) for r in result):
        raise HTTPException(422,'Evidence has not arrived at this replay date')
    return result


def submissions(db,branch_ref):
    return list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='filing_submission',Record.payload['branch_ref'].as_string()==branch_ref).order_by(Record.id)))


def snapshot_record(db,identifier):
    s=db.get(FilingSnapshot,identifier)
    if not s or s.packet_id!=packet().digest:
        raise HTTPException(404,'Frozen copy not found')
    if digest(s.content)!=s.digest:
        raise HTTPException(409,'Frozen copy checksum does not match')
    return s


def accepted(db,identifier):
    return db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.kind=='filing_submission',Record.payload['snapshot_id'].as_string()==identifier,
        Record.payload['federal'].as_string()=='accepted',Record.payload['california'].as_string()=='accepted'))


def immutable_draft(db,row):
    attempts=submissions(db,row.ref)
    if attempts and attempts[-1].payload['federal']!='rejected':
        raise HTTPException(409,'This draft is submitted. Replay its response or create an amendment from its accepted copy.')


@router.post('/start')
def start(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    row=db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.ref=='filing:original'))
    if not row:
        require_preparation(actor)
        row=Record(packet_id=packet().digest,ref='filing:original',kind='filing_branch',payload={'kind':'original','as_of':START,'steps':{},'changes':[],'parent_snapshot':None})
        db.add(row)
        db.flush()
        event(db,actor,'filing_workspace_started',row.ref)
        db.commit()
    return respond({'ref':row.ref,'revision':row.revision},actor,db,row.ref)


@router.get('')
def dashboard(ref:str='filing:original',actor=Depends(identity),db:Session=Depends(session)):
    imported(db)
    row=branch(db,packet(),ref)
    current=state(db,packet(),row)
    attempts=[{'ref':r.ref,'revision':r.revision,**r.payload} for r in submissions(db,row.ref)]
    branches=list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='filing_branch').order_by(Record.id)))
    if actor['role']=='client':
        return {'branch_ref':ref,'revision':row.revision,'fingerprint':current['fingerprint'],'summary':current['summary'],
            'can_authorize':current['technical_ready'] and all(any(s['kind']==kind and s['current'] for s in current['signoffs']) for kind in ['reviewer','partner','final_computation']),
            'authorized':any(a['actor_id']==actor['id'] and a['current'] for a in current['authorizations']),
            'branches':[{'ref':b.ref,'kind':b.payload['kind']} for b in branches],
            'accepted_copies':[{'snapshot_id':a['snapshot_id'],'branch_ref':ref} for a in attempts if a['federal']=='accepted' and a['california']=='accepted'],
            'limit':current['limit']}
    resolutions=[{'ref':r.ref,'revision':r.revision,**r.payload} for r in db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='filing_resolution',Record.payload['branch_ref'].as_string()==ref).order_by(Record.id.desc()))]
    post=[{'ref':r.ref,**r.payload} for r in db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='post_filing',Record.payload['branch_ref'].as_string()==ref).order_by(Record.id))]
    return respond({**current,'branches':[{'ref':b.ref,'kind':b.payload['kind']} for b in branches],'submissions':attempts,'resolutions':resolutions,'post_filing':post,
        'extension':packet().data['what_if']['extension']},actor,db,row.ref)


@router.post('/steps')
def step(ref:str,body:StepWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    if body.name not in packet().data['firm']['starter_standards']['required_steps'] or body.name in AUTO_STEPS:
        raise HTTPException(422,'Choose a preparer required step; sign-offs and authorization are computed separately')
    evidence=refs(db,row,body.evidence)
    history=[*row.payload.get('step_history',[]),{'name':body.name,'before':row.payload['steps'].get(body.name),'at':now()}]
    row.payload={**row.payload,'steps':{**row.payload['steps'],body.name:{'note':body.note,'evidence':evidence,'actor_id':actor['id'],'at':now()}},'step_history':history}
    row.revision+=1
    event(db,actor,'filing_step_recorded',row.ref)
    db.commit()
    return respond({'revision':row.revision},actor,db,row.ref)


@router.post('/resolutions')
def resolve(ref:str,body:ResolutionWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    current=state(db,packet(),row)
    target=next((b for b in current['blockers'] if b['ref']==body.target and b['kind'] in {'claim','issue'}),None)
    if body.target=='diagnostic:CA_AMT_NOT_COMPUTED' and body.resolved_amount is None and not body.reasoned_none:
        raise HTTPException(422,'State a California AMT amount or an explicit reasoned none, with authority and rationale')
    if not target:
        raise HTTPException(422,'Choose a currently open claim or diagnostic/finding disposition')
    evidence=refs(db,row,body.evidence)
    records,_=evidence_graph(db,packet())
    for r in evidence:
        if r in records and records[r].kind=='extraction' and not records[r].payload.get('locator',{}).get('resolved'):
            raise HTTPException(422,'Resolve this source anchor or cite a reviewed page explicitly')
    fp=resolution_fingerprint(records,body.target,target.get('value'),evidence)
    resolution=node(db,'filing_resolution',{'branch_ref':ref,'target':body.target,'value':target.get('value'),'evidence':evidence,'fingerprint':fp,
        'authority':body.authority,'resolved_amount':str(body.resolved_amount) if body.resolved_amount is not None else None,'reasoned_none':body.reasoned_none,'conclusion':body.conclusion,'rationale':body.note,'actor_id':actor['id'],'at':now(),'review':None,'review_history':[]})
    row.revision+=1
    event(db,actor,'filing_resolution_recorded',resolution.ref)
    db.commit()
    return respond({'ref':resolution.ref,'revision':resolution.revision,'branch_revision':row.revision},actor,db,ref)


@router.post('/resolutions/{resolution_ref}/review')
def review_resolution(resolution_ref:str,body:ReviewWrite,actor=Depends(staff),db:Session=Depends(session)):
    record=get_record(db,packet(),resolution_ref,body.expected_revision,True)
    if record.kind!='filing_resolution':
        raise HTTPException(404,'Disposition not found')
    row=branch(db,packet(),record.payload['branch_ref'],lock=True)
    prep(actor,row)
    immutable_draft(db,row)
    p=record.payload
    from types import SimpleNamespace
    contributors=contributor_ids(db,packet(),SimpleNamespace(ref='_resolution'),p['evidence'])
    if actor['role'] not in {'reviewer','partner'} or actor['id']==p['actor_id'] or actor['id'] in contributors:
        raise HTTPException(403,'Independent reviewer or partner required')
    if p.get('resolved_amount') and D(p['resolved_amount'])>1000 and actor['role']!='partner' and body.decision=='approved':
        raise HTTPException(403,'This material California tax disposition requires partner approval')
    if not body.note.strip():
        raise HTTPException(422,'Record a review conclusion')
    if p.get('review'):
        raise HTTPException(409,'This disposition has already been reviewed; record a fresh disposition for changed evidence')
    records,_=evidence_graph(db,packet())
    value=p['value']
    if p['target'].startswith('v3:'):
        lines,_,_=current_lines(db,packet(),row)
        value=lines[p['target'].split(':',1)[1]]['value']
    signature=resolution_fingerprint(records,p['target'],value,p['evidence'])
    if signature!=p['fingerprint']:
        raise HTTPException(409,'Covered values or evidence changed; record a fresh disposition')
    review={'actor_id':actor['id'],'decision':body.decision,'note':body.note.strip(),'fingerprint':signature,'at':now()}
    record.payload={**p,'review':review,'review_history':[*p['review_history'],review]}
    record.revision+=1
    row.revision+=1
    event(db,actor,'filing_resolution_reviewed',record.ref)
    db.commit()
    return respond({'ref':record.ref,'revision':record.revision},actor,db,row.ref)


@router.post('/notes')
def note(ref:str,body:NoteWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    if not body.text.strip():
        raise HTTPException(422,'Enter a review note')
    r=node(db,'filing_note',{'branch_ref':ref,'text':body.text,'blocking':body.blocking,'closed':False,'actor_id':actor['id'],'at':now()})
    row.revision+=1
    event(db,actor,'filing_note_opened',r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':r.revision},actor,db,ref)


@router.post('/notes/{note_ref}/close')
def close_note(note_ref:str,body:Revision,actor=Depends(staff),db:Session=Depends(session)):
    r=get_record(db,packet(),note_ref,body.expected_revision,True)
    if r.kind!='filing_note':
        raise HTTPException(404,'Review note not found')
    row=branch(db,packet(),r.payload['branch_ref'],lock=True)
    prep(actor,row)
    immutable_draft(db,row)
    r.payload={**r.payload,'closed':True,'closed_by':actor['id'],'closed_at':now()}
    r.revision+=1
    row.revision+=1
    event(db,actor,'filing_note_closed',r.ref)
    db.commit()
    return {'revision':r.revision}


@router.post('/signoffs')
def sign(ref:str,body:SignWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    current=state(db,packet(),row)
    if not current['technical_ready']:
        raise HTTPException(409,'Resolve the technical blockers before signing off')
    if body.fingerprint!=current['fingerprint']:
        raise HTTPException(409,'The covered draft changed; reload before signing')
    role='reviewer' if body.kind=='reviewer' else 'partner'
    if actor['role'] not in ({'reviewer','partner'} if role=='reviewer' else {'partner'}) or actor['id'] in current['preparers']:
        raise HTTPException(403,'Independent '+role+' required; substantive preparers cannot sign off their own draft')
    if not body.note.strip():
        raise HTTPException(422,'Record the scope and conclusion of the sign-off')
    r=node(db,'filing_signoff',{'branch_ref':ref,'kind':body.kind,'fingerprint':current['fingerprint'],'note':body.note,'actor_id':actor['id'],'at':now(),
        'summary':current['summary'],'estimate_details':current['estimate_details'],'affected_lines':[c['ref'] for c in current['claims'] if c['basis']=='affected'],
        'decision':'accept estimated computation for simulated filing' if body.kind=='final_computation' else 'independent review'})
    row.revision+=1
    event(db,actor,'filing_signed',r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':row.revision},actor,db,ref)


@router.post('/authorize')
def authorize(ref:str,body:AuthorizeWrite,actor=Depends(identity),db:Session=Depends(session)):
    if actor['role']!='client' or not body.authorize:
        raise HTTPException(403,'Client approval and explicit simulated e-file authorization required')
    row=branch(db,packet(),ref,body.expected_revision,True)
    immutable_draft(db,row)
    current=state(db,packet(),row)
    if not current['technical_ready'] or any(not any(s['kind']==kind and s['current'] for s in current['signoffs']) for kind in ['reviewer','partner','final_computation']):
        raise HTTPException(409,'The team must complete review and the computation decision before client authorization')
    if body.fingerprint!=current['fingerprint']:
        raise HTTPException(409,'Amounts or evidence changed; review the new draft before authorizing')
    r=node(db,'filing_authorization',{'branch_ref':ref,'actor_id':actor['id'],'fingerprint':current['fingerprint'],'summary':current['summary'],'at':now(),
        'consent':'Approve this exact simulated return and authorize its simulated federal and California submission.'})
    row.revision+=1
    event(db,actor,'filing_client_authorized',r.ref)
    db.commit()
    return {'authorized':True,'revision':row.revision}


def frozen_content(db,row,current):
    lines,summary,household=current_lines(db,packet(),row)
    records,_=evidence_graph(db,packet())
    if row.payload.get('parent_snapshot'):
        evidence=deepcopy(snapshot_record(db,row.payload['parent_snapshot']).content['evidence'])
    else:
        evidence={r.ref:{'ref':r.ref,'kind':r.kind,'revision':r.revision,'payload':r.payload} for r in records.values()
            if r.kind in {'document','page','extraction','client_evidence','question','client_answer','attachment','household','decision','filing_resolution'} and available(packet(),r.ref,row.payload['as_of'],records)}
    if row.payload.get('parent_snapshot'):
        for change in row.payload['changes']:
            if change['status']=='approved':
                from types import SimpleNamespace
                for source in scope_records(db,packet(),SimpleNamespace(ref='_branch'),change['evidence']):
                    evidence[source.ref]={'ref':source.ref,'kind':source.kind,'revision':source.revision,'payload':source.payload}
    files=deepcopy(snapshot_record(db,row.payload['parent_snapshot']).content['attachments']) if row.payload.get('parent_snapshot') else {}
    for ref,r in evidence.items():
        if r['kind']=='attachment' and ref not in files:
            content=attachments.read(r['payload']['storage_key'])
            if hashlib.sha256(content).hexdigest()!=r['payload']['sha256']:
                raise HTTPException(409,'Attachment checksum changed before freezing')
            files[ref]={'filename':r['payload']['filename'],'content_base64':base64.b64encode(content).decode(),'sha256':r['payload']['sha256']}
    for line in lines.values():
        for source in line['sources']:
            if source not in evidence and available(packet(),source,row.payload['as_of'],records):
                evidence[source]={'ref':source,'kind':'reference','revision':None,'payload':packet().resolve(source)}
    checks=[{key:getattr(c,key) for key in ['id','record_id','actor_id','method','note','evidence','value','subject_revision','fingerprint','at','operation_id','reversed_at','reversed_by']}
        for c in db.scalars(select(Verification).join(Record,Record.id==Verification.record_id).where(Record.packet_id==packet().digest))]
    adjustments=[{key:getattr(a,key) for key in ['id','record_id','actor_id','original_value','proposed_value','reason','evidence','effect','status','at']}
        for a in db.scalars(select(Adjustment).join(Record,Record.id==Adjustment.record_id).where(Record.packet_id==packet().digest))]
    by_id={r.id:r.ref for r in records.values()}
    for check in checks:
        check['record_ref']=by_id.get(check['record_id'])
    for change in adjustments:
        change['record_ref']=by_id.get(change['record_id'])
        change['reviews']=[{k:getattr(r,k) for k in ['id','actor_id','decision','note','evidence','fingerprint','at']} for r in db.scalars(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==change['id']).order_by(AdjustmentReview.id))]
    from backend.domain.history import MUTATIONS
    audit=[{k:getattr(e,k) for k in ['id','actor_id','action','subject','at']} for e in db.scalars(select(AuditEvent).where(AuditEvent.action.in_(MUTATIONS)).order_by(AuditEvent.id))]
    included=set(evidence)|{'v3:'+key for key in lines}
    edges=[{k:getattr(e,k) for k in ['source','target','kind','resolved']} for e in db.scalars(select(Edge).where(Edge.packet_id==packet().digest)) if e.source in included and e.target in included]
    return {'packet_hash':packet().digest,'branch_ref':row.ref,'kind':row.payload['kind'],'as_of':row.payload['as_of'],'fingerprint':current['fingerprint'],
        'lines':lines,'summary':summary,'household':household,'evidence':evidence,'attachments':files,'verifications':checks,'adjustments':adjustments,
        'changes':row.payload['changes'],'evidence_edges':edges,'audit_events':audit,'step_history':row.payload.get('step_history',[]),'steps':row.payload['steps'],'signoffs':current['signoffs'],'authorizations':current['authorizations'],
        'standards':packet().data['firm']['starter_standards'],'carryovers':packet().data['return_versions'][-1]['carryovers_out'],
        'carryover_basis':'Engine v3 carryovers; review after workpaper adjustments. They are not silently recomputed.',
        'limit':current['limit'],'frozen_at':now()}


@router.post('/submit')
def submit(ref:str,body:SubmitWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    if not actor.get('sensitive_data_clearance'):
        raise HTTPException(403,'Clearance required to freeze the complete return')
    immutable_draft(db,row)
    current=state(db,packet(),row)
    if not current['ready'] or body.fingerprint!=current['fingerprint']:
        raise HTTPException(409,'Readiness, approvals or the draft fingerprint changed; reload the blockers')
    attempts=submissions(db,ref)
    if attempts:
        previous=attempts[-1]
        if body.supersedes!=previous.ref or previous.payload['federal']!='rejected' or previous.payload['fingerprint']==current['fingerprint']:
            raise HTTPException(409,'A corrected submission must reference the rejected attempt and contain a new approved revision')
    elif body.supersedes:
        raise HTTPException(422,'This branch has no rejected attempt to replace')
    content=frozen_content(db,row,current)
    identifier='snapshot:'+uuid4().hex
    snap=FilingSnapshot(id=identifier,packet_id=packet().digest,branch_ref=ref,parent_id=attempts[-1].payload['snapshot_id'] if attempts else row.payload.get('parent_snapshot'),
        content=content,digest=digest(content),actor_id=actor['id'],at=now())
    db.add(snap)
    r=node(db,'filing_submission',{'branch_ref':ref,'snapshot_id':identifier,'snapshot_hash':snap.digest,'fingerprint':current['fingerprint'],
        'supersedes':body.supersedes,'federal':'transmitted','california':'held','events':[],'at':now(),'simulation':True})
    row.revision+=1
    event(db,actor,'filing_submitted',r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':r.revision,**r.payload},actor,db,ref)


@router.post('/submissions/{submission_ref}/replay')
def replay(submission_ref:str,body:Revision,actor=Depends(staff),db:Session=Depends(session)):
    r=get_record(db,packet(),submission_ref,body.expected_revision,True)
    if r.kind!='filing_submission':
        raise HTTPException(404,'Submission not found')
    row=branch(db,packet(),r.payload['branch_ref'],lock=True)
    prep(actor,row)
    p=r.payload
    attempts=submissions(db,row.ref)
    if attempts[-1].ref!=r.ref:
        raise HTTPException(409,'Replay the latest attempt; earlier attempt history is frozen')
    script=packet().data['tax_agency_records']['efile']
    if p['federal']=='transmitted':
        if row.payload['kind']=='original' and not p['supersedes']:
            events=[script[0],script[1]]
            updated={**p,'federal':'rejected','california':'not_transmitted','events':[*p['events'],*events]}
            as_of='2026-07-13T19:02:00Z'
        else:
            if row.payload['kind']=='original' and not any(c['kind']=='identity' and c['status']=='approved' for c in row.payload['changes']):
                raise HTTPException(409,'Record and independently approve the corrected dependent identity first')
            result=script[2] if row.payload['kind']=='original' else {'date':row.payload['as_of'],'jurisdiction':'federal','status':'accepted','submission_id':'SIM-AMEND-'+uuid4().hex,'simulation':True}
            updated={**p,'federal':'accepted','california':'transmitted','events':[*p['events'],result]}
            as_of=max(row.payload['as_of'],result['date'])
    elif p['federal']=='accepted' and p['california']=='transmitted':
        result=script[3] if row.payload['kind']=='original' else {'date':row.payload['as_of'],'jurisdiction':'california','status':'accepted','submission_id':'SIM-AMEND-'+uuid4().hex,'simulation':True}
        updated={**p,'california':'accepted','events':[*p['events'],result]}
        as_of=max(row.payload['as_of'],result['date'])
    else:
        raise HTTPException(409,'No further agency response is available for this attempt')
    r.payload=updated
    r.revision+=1
    row.payload={**row.payload,'as_of':as_of}
    row.revision+=1
    event(db,actor,'filing_response_replayed',r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':r.revision,**r.payload},actor,db,row.ref)


@router.post('/changes')
def change(ref:str,body:ChangeWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    if not actor.get('sensitive_data_clearance'):
        raise HTTPException(403,'Clearance required to prepare this branch correction')
    if not body.authority.strip():
        raise HTTPException(422,'Record authority for the branch correction')
    evidence=refs(db,row,body.evidence)
    lines,_,household=current_lines(db,packet(),row)
    if body.key=='household:theo':
        if row.payload['as_of']<'2026-07-13T19:02:00Z' or 'D71' not in evidence:
            raise HTTPException(422,'The corrected Social Security card must have arrived and be cited')
        original=next(p['ssn'] for p in household['people'] if p['id']=='theo')
        corrected=re.search(r'\d{3}-\d{2}-\d{4}',packet().resolve('D71')['pages'][0]['printed_content'])[0]
        if original==corrected:
            raise HTTPException(422,'This identity already matches the card')
        item={'kind':'identity','key':body.key,'before':original,'after':corrected,'effect':{'tax_change':{'federal':'0','california':'0'}},'category':'identity'}
    else:
        if not row.payload.get('parent_snapshot'):
            raise HTTPException(422,'Prepare ordinary return corrections in the claim workflow; branch amount changes belong to an amendment')
        if body.key not in lines or lines[body.key]['inputs'] or body.proposed_value is None:
            raise HTTPException(422,'Choose a numeric source claim and a proposed amount')
        record=get_record(db,packet(),'v3:'+body.key)
        category=category_for(packet(),record)
        from types import SimpleNamespace
        baseline=snapshot_record(db,row.payload['parent_snapshot']).content['lines'][body.key]['value']
        if body.proposed_value==D(baseline):
            raise HTTPException(422,'Proposed amount must differ from the accepted parent')
        source=SimpleNamespace(payload={**record.payload,'value':baseline})
        effect=estimated_effect(packet(),source,body.proposed_value,category)
        item={'kind':'amount','key':body.key,'before':str(baseline),'after':str(body.proposed_value),'category':category,'effect':effect}
    if any(c['key']==body.key and c['status']=='proposed' for c in row.payload['changes']):
        raise HTTPException(409,'Review the existing proposed correction first')
    item={**item,'id':uuid4().hex,'status':'proposed','evidence':evidence,'authority':body.authority,'reason':body.note,'actor_id':actor['id'],'at':now(),'reviews':[]}
    item['fingerprint']=change_fingerprint(db,packet(),item)
    row.payload={**row.payload,'changes':[*row.payload['changes'],item]}
    row.revision+=1
    event(db,actor,'filing_branch_change_proposed',row.ref)
    db.commit()
    return respond({'revision':row.revision,'change':item},actor,db,ref)


@router.post('/changes/{change_id}/review')
def review_change(change_id:str,ref:str,body:ReviewWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    immutable_draft(db,row)
    changes=deepcopy(row.payload['changes'])
    item=next((c for c in changes if c['id']==change_id),None)
    if not item or item['status']!='proposed':
        raise HTTPException(409,'Correction is no longer awaiting review')
    from types import SimpleNamespace
    contributors=contributor_ids(db,packet(),SimpleNamespace(ref='_branch'),item['evidence'])
    if actor['role'] not in {'reviewer','partner'} or actor['id']==item['actor_id'] or actor['id'] in contributors:
        raise HTTPException(403,'Independent reviewer or partner required')
    if max(abs(D(v)) for v in item['effect']['tax_change'].values())>1000 and actor['role']!='partner' and body.decision=='approved':
        raise HTTPException(403,'This material correction requires partner approval')
    refs(db,row,item['evidence'])
    if body.decision=='approved' and item.get('fingerprint')!=change_fingerprint(db,packet(),item):
        raise HTTPException(409,'Evidence changed after proposal; reject it and record a fresh correction')
    if not body.note.strip():
        raise HTTPException(422,'Record the independent review conclusion')
    if body.decision=='approved':
        for old in changes:
            if old['key']==item['key'] and old['status']=='approved':
                old['status']='superseded'
    item['status']=body.decision
    item['reviews'].append({'actor_id':actor['id'],'decision':body.decision,'note':body.note,'at':now()})
    row.payload={**row.payload,'changes':changes}
    row.revision+=1
    event(db,actor,'filing_branch_change_reviewed',row.ref)
    db.commit()
    return respond({'revision':row.revision,'change':item},actor,db,ref)


@router.post('/amendments')
def amendment(body:BranchWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    parent=snapshot_record(db,body.parent_snapshot)
    if not accepted(db,parent.id):
        raise HTTPException(409,'An amendment must branch from a copy accepted by both agencies')
    original=branch(db,packet(),parent.branch_ref)
    r=node(db,'filing_branch',{'kind':'amendment','parent_snapshot':parent.id,'as_of':original.payload['as_of'],'changes':[],
        'steps':deepcopy(parent.content['steps']),'step_history':[]})
    event(db,actor,'amendment_started',r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':r.revision},actor,db,r.ref)


@router.get('/snapshots/{snapshot_id}')
def frozen(snapshot_id:str,actor=Depends(staff),db:Session=Depends(session)):
    s=snapshot_record(db,snapshot_id)
    return respond({'id':s.id,'hash':s.digest,'parent':s.parent_id,'content':s.content},actor,db,s.id)


class PostWrite(Revision):
    action:str=Field(pattern='^(payments|rollforward|notice)$')


@router.post('/post-filing')
def post_filing(ref:str,body:PostWrite,actor=Depends(staff),db:Session=Depends(session)):
    row=branch(db,packet(),ref,body.expected_revision,True)
    prep(actor,row)
    attempts=submissions(db,ref)
    if not attempts or not accepted(db,attempts[-1].payload['snapshot_id']):
        raise HTTPException(409,'Both agencies must accept a frozen copy before post-filing work')
    s=snapshot_record(db,attempts[-1].payload['snapshot_id'])
    if db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.kind=='post_filing',Record.payload['branch_ref'].as_string()==ref,Record.payload['action'].as_string()==body.action)):
        raise HTTPException(409,'This post-filing event has already been recorded')
    if body.action=='payments':
        federal=s.content['summary']['federal']
        principal=max(D(federal['balance_due']),D(0))
        due=date(2026,4,15);paid=date(2026,7,20)
        days=(paid-due).days
        months=(paid.year-due.year)*12+paid.month-due.month+(paid.day>due.day)
        rates=packet().data['post_filing_rates']
        interest=(principal*D(rates['irs_underpayment_interest_rate_annual'])*D(days)/365).quantize(D('.01'),rounding=ROUND_HALF_UP)
        penalty=(principal*min(D('.25'),D(rates['irs_failure_to_pay_penalty_per_month'])*months)).quantize(D('.01'),rounding=ROUND_HALF_UP)
        original_penalty=D(federal.get('penalty',0))
        ca_balance=D(s.content['summary']['california']['balance_due'])
        ca_principal=max(ca_balance,D(0))
        ca_date=date(2026,8,21)
        ca_days=(ca_date-due).days
        ca_months=(ca_date.year-due.year)*12+ca_date.month-due.month+(ca_date.day>due.day)
        ca_interest=(ca_principal*D(rates['ftb_interest_rate_annual'])*D(ca_days)/365).quantize(D('.01'),rounding=ROUND_HALF_UP)
        ca_penalty=(ca_principal*(D('.05')+D('.005')*ca_months)).quantize(D('.01'),rounding=ROUND_HALF_UP)
        details={'snapshot_id':s.id,'federal':{'principal':str(principal),'form2210_penalty':str(original_penalty),'days':days,'months':months,'interest':str(interest),
            'failure_to_pay':str(penalty),'modeled_total':str(principal+original_penalty+interest+penalty),'paid_at':'2026-07-20T14:00:00Z'},
            'california':{'refund':str(max(-ca_balance,D(0))),'balance_due':str(ca_principal),'interest':str(ca_interest),'late_penalty':str(ca_penalty),
                'modeled_liability':str(ca_principal+ca_interest+ca_penalty),'status':'refund' if ca_balance<0 else 'balance_due_requires_payment' if ca_balance>0 else 'settled',
                'as_of':'2026-08-21T14:00:00Z'},
            'basis':'Fixture-rate model using the frozen balance: simple daily interest, whole or partial monthly failure-to-pay periods. Form 2210 is shown separately. This is not a recomputed agency account.'}
        as_of='2026-08-21T14:00:00Z'
    elif body.action=='rollforward':
        reference=packet().data['planning_reference_2026']
        federal=(D(s.content['summary']['federal']['total_tax'])*D('1.10')).quantize(D('.01'),rounding=ROUND_HALF_UP)
        ca=(D(s.content['summary']['california']['total_tax'])*D('1.10')).quantize(D('.01'),rounding=ROUND_HALF_UP)
        details={'snapshot_id':s.id,'tax_year':2026,'carryovers':s.content['carryovers'],'carryover_basis':s.content['carryover_basis'],
            'federal_prior_tax_benchmark':str(federal),'federal_installments':[{'date':d,'amount':str((federal/4).quantize(D('.01')))} for d in reference['federal_estimate_due_dates']],
            'california_prior_tax_benchmark':str(ca),'california_installments':[{'date':d,'amount':str((ca*D(rate)).quantize(D('.01')))} for d,rate in zip(reference['california_estimate_due_dates'],reference['california_installment_percentages'])],
            'known_changes':reference['known_2026_changes_for_this_household'],'basis':'Planning benchmark only, using 110% of the frozen estimated 2025 tax. Current-year 90% alternative and withholding are not known. Engine carryovers require review after corrections; California-source-only scope remains a planning input.'}
        as_of='2027-01-15T15:00:00Z'
    else:
        details={'snapshot_id':s.id,'notice':packet().data['tax_agency_records']['notices'][1],
            'basis':'The examination bundle is assembled from the accepted frozen evidence, not newly invented support.'}
        as_of='2028-01-26T15:00:00Z'
    r=node(db,'post_filing',{'branch_ref':ref,'action':body.action,'details':details,'actor_id':actor['id'],'at':now()})
    row.payload={**row.payload,'as_of':max(row.payload['as_of'],as_of)}
    row.revision+=1
    event(db,actor,'post_filing_'+body.action,r.ref)
    db.commit()
    return respond({'ref':r.ref,'revision':row.revision,**r.payload},actor,db,ref)
