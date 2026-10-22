"""Story A: persisted evidence, proposals, independent review and honest projections."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from backend.persistence.models import Record, Edge, Verification, Adjustment, AdjustmentReview
from backend.domain.formulas import D, FORMULAS, check_registry, tax_effect


def now():
    return datetime.now(timezone.utc).isoformat()


def require_preparation(actor):
    if actor['role'] not in {'preparer','reviewer','partner'}:
        raise HTTPException(403,'Preparation access required')


def get_record(db, packet, ref, revision=None, lock=False):
    query=select(Record).where(Record.packet_id==packet.digest,Record.ref==ref)
    if lock:
        query=query.with_for_update()
    record=db.scalar(query)
    if not record:
        raise HTTPException(404,'Workpaper record not found')
    if revision is not None and record.revision!=revision:
        raise HTTPException(409,'Record changed; reload before saving')
    return record


def evidence_refs(packet, refs):
    refs=list(dict.fromkeys(ref.strip() for ref in refs if ref.strip()))
    if not refs:
        raise HTTPException(422,'At least one evidence reference is required')
    missing=[ref for ref in refs if packet.resolve(ref) is None]
    if missing:
        raise HTTPException(422,'Unresolved evidence reference: '+', '.join(missing))
    return refs


def mark_preparer(record, actor):
    record.payload={**record.payload,'preparers':sorted(set(record.payload.get('preparers',[]))|{actor['id']})}


def scope_records(db, packet, record, evidence):
    records={r.ref:r for r in db.scalars(select(Record).where(Record.packet_id==packet.digest))}
    links={}
    for edge in db.scalars(select(Edge).where(Edge.packet_id==packet.digest)):
        links.setdefault(edge.source,[]).append(edge.target)
    pending=[record.ref,*evidence]
    seen=set()
    while pending:
        ref=pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        pending.extend(links.get(ref,[]))
    return [records[ref] for ref in sorted(seen) if ref in records]


def fingerprint(db, packet, record, value, evidence):
    # Approval changes the subject revision without changing its reviewed value.
    # Source revisions, by contrast, invalidate evidence-bound verification.
    refs=[(r.ref,r.revision) for r in scope_records(db,packet,record,evidence) if r.id!=record.id]
    body={'claim':record.ref,'value':str(D(value)),'evidence':sorted(evidence),'sources':refs}
    return hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()


def contributor_ids(db, packet, record, evidence):
    ids=set()
    for r in scope_records(db,packet,record,evidence):
        ids.update(r.payload.get('preparers',[]))
        if r.payload.get('disposition_actor'):
            ids.add(r.payload['disposition_actor'])
        if r.payload.get('locator',{}).get('actor'):
            ids.add(r.payload['locator']['actor'])
    return ids


def adjustments_for(db, record):
    return list(db.scalars(select(Adjustment).where(Adjustment.record_id==record.id).order_by(Adjustment.id.desc())))


def current_values(db, record):
    adjustments=adjustments_for(db,record)
    pending=next((a for a in adjustments if a.status=='proposed'),None)
    approved=next((a for a in adjustments if a.status=='approved'),None)
    engine=str(record.payload['value'])
    return pending,approved,engine,approved.proposed_value if approved else engine


def category_for(packet, record):
    key=record.payload['key']
    if key.startswith('SchB.1.') or key in {'SchB.2','SchB.4','F1040.2b'}:
        return 'interest'
    from backend.domain.audit import run_audit
    # Classification is fixture metadata, not a category supplied by the browser.
    for finding in run_audit(packet)['findings']:
        if finding['claim']==key:
            return finding['category']
    raise HTTPException(422,'Tax-effect category is not configured for this line yet')


def estimated_effect(packet, record, proposed, category):
    delta=D(proposed)-D(record.payload['value'])
    key=record.payload['key']
    rates=packet.data['return_versions'][-1]['tax_effect_rates']
    jurisdiction=record.payload['jurisdiction']
    if category in {'payment','credit'}:
        exact=tax_effect(delta,category,rates)
        changes={'federal':'0','california':'0'}
        changes[jurisdiction]=exact['tax_change'] if category=='credit' else exact['balance_change']
        return {'basis':'exact','kind':category,'tax_change':changes if category=='credit' else {'federal':'0','california':'0'},'balance_change':changes}
    if category=='schc_profit' and key not in {'SchC.1','SchC.5','SchC.7','SchC.29','SchC.31'}:
        delta=-delta
        if key=='SchC.44a':
            delta*=D(packet.data['engine_reference']['parameters']['mileage_rate'])
    result=tax_effect(delta,category,rates)
    if key in {'F8949.B.N1','F8949.B.N3'}:
        result['california']=tax_effect(D(proposed)-D(record.payload['value']),'ca_source_income',rates)['california']
    changes={j:result[j] for j in ('federal','california')}
    return {'basis':'estimated','kind':'tax','tax_change':changes,'balance_change':changes,'note':'Measured at v3; thresholds and interactions are not recomputed.'}


def workflow(db, packet, record):
    pending,approved,engine,applied=current_values(db,record)
    value=pending.proposed_value if pending else applied
    refs=pending.evidence if pending else approved.evidence if approved else []
    checks=[]
    for v in db.scalars(select(Verification).where(Verification.record_id==record.id).order_by(Verification.id.desc())):
        scope=list(dict.fromkeys([*v.evidence,*refs]))
        current=v.fingerprint==fingerprint(db,packet,record,value,scope)
        checks.append({'id':v.id,'actor_id':v.actor_id,'method':v.method,'note':v.note,'evidence':v.evidence,'value':v.value,'at':v.at,'current':current,'subject_revision':v.subject_revision})
    changes=[]
    for a in adjustments_for(db,record):
        reviews=[]
        for review in db.scalars(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==a.id).order_by(AdjustmentReview.id)):
            reviews.append({'actor_id':review.actor_id,'decision':review.decision,'note':review.note,'at':review.at,
                            'current':review.fingerprint==fingerprint(db,packet,record,a.proposed_value,review.evidence)})
        changes.append({'id':a.id,'actor_id':a.actor_id,'original_value':a.original_value,'proposed_value':a.proposed_value,'reason':a.reason,'category':a.category,'evidence':a.evidence,'effect':a.effect,'status':a.status,'at':a.at,'reviews':reviews})
    try:
        category=category_for(packet,record)
    except HTTPException:
        category=None
    return {'ref':record.ref,'revision':record.revision,'engine_value':engine,'approved_value':applied,'review_value':value,
            'verification_methods':packet.data['firm']['starter_standards']['verification_types'],
            'verifications':checks,'adjustments':changes,'preparers':sorted(contributor_ids(db,packet,record,refs)),
            'category':category}


def projected_summary(db, packet):
    base=packet.data['return_versions'][-1]
    rows=list(db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet.digest,Adjustment.status=='approved')))
    summary={j:dict(base['summary'][j]) for j in ('federal','california')}
    deltas={j:D(0) for j in summary}
    payment_delta={j:D(0) for j in summary}
    overrides={}
    for a,r in rows:
        overrides[r.payload['key']]=D(a.proposed_value)
        for j in summary:
            deltas[j]+=D(a.effect['tax_change'][j])
        if a.category=='payment':
            payment_delta[r.payload['jurisdiction']]+=D(a.proposed_value)-D(r.payload['value'])
    for j in summary:
        summary[j]['total_tax']=str(D(summary[j]['total_tax'])+deltas[j])
        summary[j]['payments']=str(D(summary[j]['payments'])+payment_delta[j])
        summary[j]['balance_due']=str(D(summary[j]['total_tax'])-D(summary[j]['payments']))
    lines={l['key']:l for l in base['lines']}
    values={key:D(line['value']) for key,line in lines.items() if isinstance(line['value'],(int,float)) and not isinstance(line['value'],bool)}
    values.update(overrides)
    changed=set(overrides)
    supported={r['key'] for r in check_registry(base) if r['status']=='passed'}
    # Registry evaluation follows dependencies, never blindly sums engine inputs.
    seen=set()
    def evaluate(key):
        if key in seen:
            return
        seen.add(key)
        if key not in supported or key in overrides:
            return
        for term,_ in FORMULAS[key]:
            evaluate(term)
        if any(term in changed for term,_ in FORMULAS[key]):
            values[key]=sum((values[t]*sign for t,sign in FORMULAS[key]),D(0))
            changed.add(key)
    for key in supported:
        evaluate(key)
    affected=set(changed)
    while True:
        more={key for key,line in lines.items() if any(i in affected for i in line['inputs'])}
        if more<=affected:
            break
        affected.update(more)
    return {'version':'v3','summary':summary,'approved_adjustments':len(rows),'tax_change':{j:str(deltas[j]) for j in summary},
            'basis':'Estimated tax summary over v3; only approved adjustments included. No filing readiness implied.',
            'changed_lines':[{'key':key,'engine_value':lines[key]['value'],'value':str(values[key]) if key in changed else lines[key]['value'],
                              'basis':'recomputed' if key in changed else 'affected'} for key in sorted(affected)]}
