"""Story A: persisted evidence, proposals, independent review and honest projections."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select, func
from backend.persistence.models import Record, Edge, Verification, Adjustment, AdjustmentReview
from backend.domain.formulas import D, FORMULAS, check_registry, tax_effect
from backend.domain.policy import standards


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


def evidence_refs(packet, refs, db=None):
    refs=list(dict.fromkeys(ref.strip() for ref in refs if ref.strip()))
    if not refs:
        raise HTTPException(422,'At least one evidence reference is required')
    saved=set(db.scalars(select(Record.ref).where(Record.packet_id==packet.digest,Record.ref.in_(refs),Record.kind.in_(['client_answer','attachment'])))) if db else set()
    missing=[ref for ref in refs if packet.resolve(ref) is None and ref not in saved]
    if missing:
        raise HTTPException(422,'Unresolved evidence reference: '+', '.join(missing))
    if db:
        from backend.domain.filing import replay_as_of,available
        as_of=replay_as_of(db,packet)
        if as_of and any(not available(packet,r,as_of) for r in refs):
            raise HTTPException(422,'Evidence has not arrived in the filing replay')
    return refs


def mark_preparer(record, actor):
    record.payload={**record.payload,'preparers':sorted(set(record.payload.get('preparers',[]))|{actor['id']})}


def evidence_graph(db, packet):
    records={r.ref:r for r in db.scalars(select(Record).where(Record.packet_id==packet.digest))}
    links={}
    for edge in db.scalars(select(Edge).where(Edge.packet_id==packet.digest)):
        if edge.kind not in {'answers','subject'}:
            links.setdefault(edge.source,[]).append(edge.target)
    return records,links


def scope_records(db, packet, record, evidence, graph=None):
    records,links=graph or evidence_graph(db,packet)
    pending=[record.ref,*evidence]
    seen=set()
    while pending:
        ref=pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        pending.extend(links.get(ref,[]))
    return [records[ref] for ref in sorted(seen) if ref in records]


def fingerprint(db, packet, record, value, evidence, graph=None):
    # Approval changes the subject revision without changing its reviewed value.
    # Source revisions, by contrast, invalidate evidence-bound verification.
    refs=[(r.ref,r.revision) for r in scope_records(db,packet,record,evidence,graph) if r.id!=record.id]
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


def current_values(db, record, packet=None):
    adjustments=adjustments_for(db,record)
    pending=next((a for a in adjustments if a.status in {'proposed','reopened'}),None)
    approved=next((a for a in adjustments if a.status=='approved' and (packet is None or approval_is_current(db,packet,record,a))),None)
    engine=str(record.payload['value'])
    return pending,approved,engine,approved.proposed_value if approved else engine


def category_for(packet, record):
    key=record.payload['key']
    if key=='SchCA540NR.1.E':
        return 'ca_source_income'
    if key=='F8949.H.C6':
        return 'stcg'
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
    if key=='SchCA540NR.1.E':changes['federal']='0'
    return {'basis':'estimated','kind':'tax','tax_change':changes,'balance_change':changes,'note':'Measured at v3; thresholds and interactions are not recomputed.'}



def requires_partner(change,db=None,packet=None):
    threshold=standards(db,packet)['partner_threshold'] if db is not None else 1000
    return max(abs(D(value)) for value in change.effect['tax_change'].values())>D(threshold)


def approval_is_current(db, packet, record, change):
    review=db.scalar(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==change.id,
        AdjustmentReview.decision=='approved').order_by(AdjustmentReview.id.desc()))
    if not review or review.fingerprint!=fingerprint(db,packet,record,change.proposed_value,review.evidence):return False
    from backend.domain.security import actor_by_id
    if requires_partner(change,db,packet) and actor_by_id(packet,review.actor_id)['role']!='partner':return False
    methods=standards(db,packet)['verification_types']
    checks=list(db.scalars(select(Verification).where(Verification.record_id==record.id)))
    return any(not v.reversed_at and v.method in methods and v.fingerprint==fingerprint(db,packet,record,change.proposed_value,list(dict.fromkeys([*v.evidence,*review.evidence])) ) for v in checks)


def reopen_change(db, packet, record, change, actor_id, source_ref, source_revision, reason):
    change.status='reopened'
    event={'adjustment_id':change.id,'source_ref':source_ref,'source_revision':source_revision,
           'reason':reason,'actor_id':actor_id,'at':now()}
    record.payload={**record.payload,'review_events':[*record.payload.get('review_events',[]),event]}
    record.revision+=1
    from backend.persistence.models import AuditEvent
    db.add(AuditEvent(actor_id=actor_id,action='approval_reopened',subject=record.ref))
    return record.ref


def reopen_affected_approvals(db, packet, source, actor_id):
    """Run in the same transaction as an evidence change; preserve prior reviews."""
    db.flush()
    changes=list(db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id)
        .where(Record.packet_id==packet.digest,Adjustment.status=='approved')))
    reopened=[]
    for change,record in changes:
        review=db.scalar(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==change.id,
            AdjustmentReview.decision=='approved').order_by(AdjustmentReview.id.desc()))
        refs=review.evidence if review else change.evidence
        if source.ref not in {r.ref for r in scope_records(db,packet,record,refs)}:
            continue
        if not approval_is_current(db,packet,record,change):
            label=source.payload.get('title',source.payload.get('label',source.ref))
            reason=f"{source.ref} ({label}) changed to revision {source.revision}. Its earlier approval no longer covers the current evidence."
            reopened.append(reopen_change(db,packet,record,change,actor_id,source.ref,source.revision,reason))
    db.flush()
    return reopened

def workflow(db, packet, record):
    pending,approved,engine,applied=current_values(db,record,packet)
    value=pending.proposed_value if pending else applied
    refs=pending.evidence if pending else approved.evidence if approved else []
    checks=[]
    for v in db.scalars(select(Verification).where(Verification.record_id==record.id).order_by(Verification.id.desc())):
        scope=list(dict.fromkeys([*v.evidence,*refs]))
        current=not v.reversed_at and v.method in standards(db,packet)['verification_types'] and v.fingerprint==fingerprint(db,packet,record,value,scope)
        checks.append({'id':v.id,'actor_id':v.actor_id,'method':v.method,'note':v.note,'evidence':v.evidence,'value':v.value,'at':v.at,'current':current,'subject_revision':v.subject_revision,'operation_id':v.operation_id,'reversed_at':v.reversed_at,'reversed_by':v.reversed_by})
    changes=[]
    for a in adjustments_for(db,record):
        reviews=[]
        for review in db.scalars(select(AdjustmentReview).where(AdjustmentReview.adjustment_id==a.id).order_by(AdjustmentReview.id)):
            reviews.append({'actor_id':review.actor_id,'decision':review.decision,'note':review.note,'at':review.at,
                            'current':review.fingerprint==fingerprint(db,packet,record,a.proposed_value,review.evidence)})
        decision_ref=db.scalar(select(Record.ref).where(Record.packet_id==packet.digest,Record.kind=='decision',Record.payload['adjustment_id'].as_integer()==a.id))
        changes.append({'decision_ref':decision_ref,'id':a.id,'actor_id':a.actor_id,'original_value':a.original_value,'proposed_value':a.proposed_value,'reason':a.reason,'category':a.category,'evidence':a.evidence,'effect':a.effect,'status':a.status,'at':a.at,'reviews':reviews,'requires_partner':requires_partner(a,db,packet),
                        'approval_current':approval_is_current(db,packet,record,a) if a.status=='approved' else False,
                        'reopen_events':[e for e in record.payload.get('review_events',[]) if e['adjustment_id']==a.id]})
    try:
        category=category_for(packet,record)
    except HTTPException:
        category=None
    return {'ref':record.ref,'revision':record.revision,'engine_value':engine,'approved_value':applied,'review_value':value,
            'verification_methods':standards(db,packet)['verification_types'],'partner_threshold':standards(db,packet)['partner_threshold'],
            'verifications':checks,'adjustments':changes,'preparers':sorted(contributor_ids(db,packet,record,refs)),
            'category':category}


def projected_summary(db, packet):
    base=packet.data['return_versions'][-1]
    rows=list(db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet.digest,Adjustment.status=='approved')))
    summary={j:dict(base['summary'][j]) for j in ('federal','california')}
    deltas={j:D(0) for j in summary}
    payment_delta={j:D(0) for j in summary}
    reopened_count=db.scalar(select(func.count()).select_from(Adjustment).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet.digest,Adjustment.status=='reopened'))
    current=[(a,r) for a,r in rows if approval_is_current(db,packet,r,a)]
    stale_count=len(rows)-len(current)
    rows=current
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
    classification_changes=[{'ref':r.ref,**a.effect['treatment']} for a,r in rows if a.effect.get('treatment')]
    affected=set(changed)|{c['target_total'] for c in classification_changes}
    while True:
        more={key for key,line in lines.items() if any(i in affected for i in line['inputs'])}
        if more<=affected:
            break
        affected.update(more)
    return {'version':'v3','summary':summary,'approved_adjustments':len(rows),'reopened_adjustments':reopened_count+stale_count,'tax_change':{j:str(deltas[j]) for j in summary},
            'basis':'Estimated tax summary over v3; only current approved adjustments included; reopened corrections are excluded. No filing readiness implied.',
            'classification_changes':classification_changes,
            'changed_lines':[{'key':key,'engine_value':lines[key]['value'],'value':str(values[key]) if key in changed else lines[key]['value'],
                              'basis':'recomputed' if key in changed else 'affected'} for key in sorted(affected)]}
