"""Story D: comparisons, independent scenario previews, variance and acknowledged activity."""
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from backend.dependencies import packet, staff, imported, respond
from backend.persistence.db import session
from backend.persistence.models import LastSeen, Record, AuditEvent
from backend.domain.history import compare, activity, variances, snapshot, numeric
from backend.domain.workpaper import get_record, require_preparation, now, category_for, estimated_effect, projected_summary, current_values
from backend.domain.formulas import D, tax_effect
from backend.domain.audit import run_audit

router=APIRouter(prefix='/api/history')


class SeenWrite(BaseModel):
    expected_revision:int=Field(ge=0)
    through_cursor:int=Field(ge=0)


class VarianceWrite(BaseModel):
    expected_revision:int=Field(ge=1)
    fingerprint:str
    note:str=Field(min_length=1,max_length=5000)

    @field_validator('note')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Explain the prior-year change')
        return value.strip()


class WhatIfWrite(BaseModel):
    ref:str
    proposed_value:Decimal=Field(allow_inf_nan=False,max_digits=18,decimal_places=2)
    category:str|None=None
    base:str='workpaper'


@router.get('/compare')
def comparison(before:str='v2',after:str='v3',actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    return respond(compare(db,packet(),before,after),actor,db,'version-comparison')


@router.get('/activity')
def changed(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    return respond(activity(db,packet(),actor['id']),actor,db,'changed-since-seen')


@router.post('/seen')
def mark_seen(body:SeenWrite,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    result=activity(db,packet(),actor['id'])
    if body.through_cursor>result['through_cursor'] or body.through_cursor<result['seen_cursor']:
        raise HTTPException(409,'Reload activity before marking it seen')
    row=db.scalar(select(LastSeen).where(LastSeen.packet_id==packet().digest,LastSeen.actor_id==actor['id']).with_for_update())
    if row:
        if row.revision!=body.expected_revision:
            raise HTTPException(409,'Your seen marker changed in another session; reload activity')
        row.cursor=body.through_cursor
        row.revision+=1
        row.at=now()
    else:
        if body.expected_revision!=0:
            raise HTTPException(409,'Reload your activity marker')
        created=db.execute(insert(LastSeen).values(packet_id=packet().digest,actor_id=actor['id'],cursor=body.through_cursor,revision=1,at=now()).on_conflict_do_nothing().returning(LastSeen.actor_id)).scalar_one_or_none()
        if not created:
            raise HTTPException(409,'Your seen marker changed in another session; reload activity')
    db.add(AuditEvent(actor_id=actor['id'],action='activity_seen',subject='activity'))
    db.commit()
    return respond(activity(db,packet(),actor['id']),actor,db,'changed-since-seen')


@router.get('/variance')
def prior_year(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    return respond(variances(db,packet()),actor,db,'prior-year-variance')


@router.post('/variance')
def explain(ref:str,body:VarianceWrite,actor=Depends(staff),db:Session=Depends(session)):
    require_preparation(actor)
    imported(db)
    claim=get_record(db,packet(),ref,body.expected_revision,True)
    row=next((r for r in variances(db,packet())['rows'] if r['ref']==ref),None)
    if row is None:
        raise HTTPException(422,'This line has no comparable numeric prior-year value')
    if row['fingerprint']!=body.fingerprint:
        raise HTTPException(409,'The compared amounts or calculation basis changed; reload the variance')
    note=Record(packet_id=packet().digest,ref='variance:'+uuid4().hex,kind='variance_note',payload={
        'key':row['key'],'claim_ref':ref,'prior_value':str(row['prior_value']),'current_value':str(row['current_value']),
        'basis':row['basis'],'fingerprint':row['fingerprint'],'note':body.note,'actor_id':actor['id'],'at':now()})
    db.add(note)
    db.add(AuditEvent(actor_id=actor['id'],action='variance_explained',subject=claim.ref))
    db.commit()
    return respond({'ref':note.ref,**note.payload},actor,db,ref)


def category_map():
    result={f['claim']:f['category'] for f in run_audit(packet())['findings']}
    result.update({f'SchB.1.{i}':'interest' for i in range(1,9)})
    result.update({'SchB.2':'interest','SchB.4':'interest','F1040.2b':'interest','F8949.H.C6':'stcg'})
    return result


@router.get('/what-if')
def what_if_options(actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    defaults=category_map()
    projection=projected_summary(db,packet())
    changes={l['key']:l for l in projection['changed_lines']}
    treatments={c['ref']:c for c in projection['classification_changes']}
    rows=list(db.scalars(select(Record).where(Record.packet_id==packet().digest,Record.kind=='claim')))
    claims=[]
    for record in rows:
        p=record.payload
        if p['version']!='v3':
            continue
        ref=record.ref
        category=defaults.get(p['key'])
        if ref in treatments:
            category='ltcg' if treatments[ref]['holding_period']=='long-term' else 'stcg'
        claims.append({'ref':ref,'key':p['key'],'label':p['label'],'engine_value':p['value'],
            'approved_value':changes.get(p['key'],{}).get('value',p['value']),
            'basis':changes.get(p['key'],{}).get('basis','engine'),'numeric':numeric(p['value']),
            'default_category':category,'sources':p['sources']})
    return respond({'claims':claims,'categories':[*packet().data['return_versions'][-1]['tax_effect_rates'],'payment','credit'],
        'scenarios':packet().data['what_if']['alternatives'],
        'scenario_basis':'Each supplied alternative belongs to v3 only. They are independent snapshots; never combine them or add their effects to approved workpaper changes.'},actor,db,'what-if-options')


@router.post('/what-if')
def preview(body:WhatIfWrite,actor=Depends(staff),db:Session=Depends(session)):
    imported(db)
    if body.base not in {'v3','workpaper'}:
        raise HTTPException(422,'User what-ifs use engine v3 or the current approved workpaper')
    record=get_record(db,packet(),body.ref)
    if record.kind!='claim' or record.payload.get('version')!='v3' or not numeric(record.payload.get('value')):
        raise HTTPException(422,'Rate previews need a numeric current-return claim. Use a judgment for text, dates or yes/no choices.')
    base=snapshot(db,packet(),body.base)
    line=base['lines'][record.payload['key']]
    value=D(line['value'])
    try:
        configured=category_for(packet(),record)
    except HTTPException:
        configured=None
    category=body.category or configured
    if category not in {*packet().data['return_versions'][-1]['tax_effect_rates'],'payment','credit'}:
        raise HTTPException(422,'Choose a tax-effect category; this claim has no configured rate mapping')
    # For configured lines, preserve expense signs, mileage units and fixture sourcing overrides.
    # Subtracting two estimates measured at v3 also preserves their dollar rounding.
    if configured==category and not (record.ref=='v3:F8949.H.C6' and body.base=='workpaper'):
        new=estimated_effect(packet(),record,body.proposed_value,category)
        old=estimated_effect(packet(),record,value,category)
        effect={**new,'tax_change':{j:str(D(new['tax_change'][j])-D(old['tax_change'][j])) for j in ('federal','california')},
            'balance_change':{j:str(D(new['balance_change'][j])-D(old['balance_change'][j])) for j in ('federal','california')}}
        mapping='Configured claim mapping; effect is the difference between two estimates measured at v3.'
    else:
        delta=body.proposed_value-value
        rates=packet().data['return_versions'][-1]['tax_effect_rates']
        result=tax_effect(delta,category,rates)
        taxes={j:'0' for j in ('federal','california')}
        balances=dict(taxes)
        if category in {'payment','credit'}:
            j=record.payload['jurisdiction']
            taxes[j]=result['tax_change']
            balances[j]=result['balance_change'] if category=='payment' else result['tax_change']
        else:
            taxes={j:result[j] for j in taxes}
            if record.payload['jurisdiction']=='california':
                taxes['federal']='0'
            balances=dict(taxes)
        effect={'basis':result['basis'],'kind':category if category in {'payment','credit'} else 'tax','tax_change':taxes,'balance_change':balances}
        mapping='Selected rate applied to the amount change as an increase in that tax base. This is an assumption, not a validated claim calculation.'
    summary={j:{k:str(v) for k,v in base['summary'][j].items()} for j in ('federal','california')}
    for j in summary:
        summary[j]['total_tax']=str(D(summary[j]['total_tax'])+D(effect['tax_change'][j]))
        if category=='payment' and j==record.payload['jurisdiction']:
            summary[j]['payments']=str(D(summary[j]['payments'])+body.proposed_value-value)
        summary[j]['balance_due']=str(D(summary[j]['total_tax'])-D(summary[j]['payments']))
    pending,_,_,approved_value=current_values(db,record,packet())
    requires_judgment=record.ref in {'v3:F8283.A1.vehicle','v3:F8949.H.C6'}
    return respond({'ref':record.ref,'revision':record.revision,'base':body.base,'base_value':str(value),'proposed_value':str(body.proposed_value),
        'category':category,'effect':effect,'summary':summary,'mapping':mapping,'basis':line['basis'],
        'can_propose':configured==category and not record.payload.get('inputs') and not requires_judgment and not pending and D(approved_value)!=body.proposed_value,
        'requires_judgment':requires_judgment,
        'limit':'Preview only. No claim, proposal, approval or seen marker is saved. Rates do not recompute thresholds, interactions or downstream return lines. A proposal is measured against engine v3 and still requires evidence, verification and independent review.'},actor,db,record.ref)
