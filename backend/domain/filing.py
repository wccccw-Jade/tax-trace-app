"""Computed readiness and immutable-content assembly for simulated filing."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from sqlalchemy import select
from fastapi import HTTPException
from backend.persistence.models import Record,Verification,Adjustment,AdjustmentReview,FilingSnapshot
from backend.domain.workpaper import fingerprint,evidence_graph,contributor_ids,approval_is_current,scope_records
from backend.domain.history import snapshot
from backend.domain.formulas import D,FORMULAS,check_registry
from backend.domain.audit import run_audit

START='2026-07-10T20:05:00Z'
AUTO_STEPS={'Reviewer sign-off','Partner sign-off','Client approval and e-file authorization'}


def canonical(value):
    # PostgreSQL JSONB normalizes signed numeric zero. Use the same representation
    # before hashing so an unchanged persisted snapshot verifies after a reload.
    def normalized(v):
        if isinstance(v,dict):
            return {k:normalized(x) for k,x in v.items()}
        if isinstance(v,list):
            return [normalized(x) for x in v]
        if isinstance(v,float) and v==0:
            return 0
        return v
    return json.dumps(normalized(value),sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def branch(db,packet,ref='filing:original',revision=None,lock=False):
    query=select(Record).where(Record.packet_id==packet.digest,Record.ref==ref,Record.kind=='filing_branch')
    row=db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404,'Open the filing workspace first')
    if revision is not None and row.revision!=revision:
        raise HTTPException(409,'The filing draft changed; reload before saving')
    return row


def available(packet,ref,as_of,records=None):
    value=records.get(ref).payload if records and ref in records else packet.resolve(ref)
    if value is None:
        return False
    if ref.startswith('agency:/notices/'):
        return ref!='agency:/notices/1' or as_of>='2028-01-26T15:00:00Z'
    if ref=='agency:/efile':
        return as_of>='2026-07-13T17:04:00Z'
    if isinstance(value,dict):
        arrived=value.get('received_at') or value.get('sent_at') or (value.get('date') if ref.startswith('agency:') else value.get('at') if ref.startswith('timeline:') else None)
        if arrived and arrived>as_of:
            return False
        if value.get('document_id'):
            return available(packet,value['document_id'],as_of,records)
        if value.get('document') and str(value['document']).startswith('D'):
            return available(packet,value['document'],as_of,records)
    return True


def change_fingerprint(db,packet,change):
    from types import SimpleNamespace
    sources=scope_records(db,packet,SimpleNamespace(ref='_branch_change'),change['evidence'])
    return digest({'key':change['key'],'value':change['after'],'sources':sorted((r.ref,r.revision) for r in sources),'evidence':sorted(change['evidence'])})


def current_lines(db,packet,row):
    if row.payload.get('parent_snapshot'):
        parent=db.get(FilingSnapshot,row.payload['parent_snapshot'])
        lines=deepcopy(parent.content['lines'])
        summary=deepcopy(parent.content['summary'])
        household=deepcopy(parent.content['household'])
    else:
        projected=snapshot(db,packet,'workpaper')
        lines={k:{**l,'value':str(l['value']) if isinstance(l['value'],Decimal) else l['value']} for k,l in projected['lines'].items()}
        summary=deepcopy(projected['summary'])
        household=deepcopy(packet.data['household'])
    overrides={}
    amt_resolution=None
    if not row.payload.get('parent_snapshot'):
        records,_=evidence_graph(db,packet)
        for resolution in records.values():
            p=resolution.payload
            if resolution.kind=='filing_resolution' and p['branch_ref']==row.ref and p['target']=='diagnostic:CA_AMT_NOT_COMPUTED' and (p.get('review') or {}).get('decision')=='approved':
                if p['fingerprint']==resolution_fingerprint(records,p['target'],None,p['evidence']):
                    amt_resolution=resolution
        if amt_resolution:
            amount=D(amt_resolution.payload.get('resolved_amount') or 0)
            lines['F540NR.61']={**lines['F540NR.61'],'value':str(amount),'basis':'recomputed' if amount else 'engine','review_basis':'accepted_by_judgment'}
            summary['california']['total_tax']=str(D(summary['california']['total_tax'])+amount)
            if amount:
                for k in ['F540NR.64','F540NR.97']:
                    if k in lines:
                        lines[k]={**lines[k],'basis':'affected'}
        else:
            lines['F540NR.61']={**lines['F540NR.61'],'basis':'unresolved'}
    for change in row.payload.get('changes',[]):
        if change['status']!='approved' or change.get('fingerprint')!=change_fingerprint(db,packet,change):
            continue
        if change['kind']=='identity':
            person=next(p for p in household['people'] if p['id']=='theo')
            person['ssn']=change['after']
        else:
            overrides[change['key']]=D(change['after'])
            for j in ('federal','california'):
                summary[j]['total_tax']=str(D(summary[j]['total_tax'])+D(change['effect']['tax_change'][j]))
                if change['category']=='payment' and lines[change['key']]['jurisdiction']==j:
                    summary[j]['payments']=str(D(summary[j]['payments'])+D(change['after'])-D(change['before']))
    changed=set(overrides)
    values={k:D(l['value']) for k,l in lines.items() if isinstance(l['value'],(int,float,Decimal)) or isinstance(l['value'],str) and l['value'].replace('.','',1).lstrip('-').isdigit()}
    values.update(overrides)
    supported={f['key'] for f in check_registry(packet.data['return_versions'][-1]) if f['status']=='passed'}
    visited=set()
    def evaluate(key):
        if key in visited:
            return
        visited.add(key)
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
        more={k for k,l in lines.items() if any(i in affected for i in l['inputs'])}
        if more<=affected:
            break
        affected.update(more)
    for key in affected:
        lines[key]={**lines[key],'value':str(values[key]) if key in changed else lines[key]['value'],'basis':'recomputed' if key in changed else 'affected'}
    for j in summary:
        summary[j]['balance_due']=str(D(summary[j]['total_tax'])-D(summary[j]['payments']))
    return lines,summary,household


def state(db,packet,row):
    records,links=evidence_graph(db,packet)
    lines,summary,household=current_lines(db,packet,row)
    is_amendment=bool(row.payload.get('parent_snapshot'))
    graph=(records,links)
    verifications=list(db.scalars(select(Verification).join(Record,Record.id==Verification.record_id).where(Record.packet_id==packet.digest)))
    checks={}
    preparers=set()
    for check in verifications:
        checks.setdefault(check.record_id,[]).append(check)
        if not check.reversed_at:
            preparers.add(check.actor_id)
    for r in records.values():
        if r.kind in {'claim','document','extraction'}:
            preparers.update(r.payload.get('preparers',[]))
            if r.payload.get('disposition_actor'):
                preparers.add(r.payload['disposition_actor'])
            if r.payload.get('locator',{}).get('actor'):
                preparers.add(r.payload['locator']['actor'])
    resolutions={}
    for r in records.values():
        if r.kind=='filing_resolution' and r.payload['branch_ref']==row.ref:
            p=r.payload
            if p.get('review') and p['review']['decision']=='approved':
                resolutions.setdefault(p['target'],[]).append(r)
    def resolution(target,value=None):
        for r in resolutions.get(target,[]):
            p=r.payload
            evidence=p['evidence']
            if not all(available(packet,ref,row.payload['as_of'],records) for ref in evidence):
                continue
            signature=resolution_fingerprint(records,target,value,evidence)
            if signature==p['fingerprint'] and p['review']['fingerprint']==signature:
                return r.ref
        return None
    claim_rows=[]
    statuses={}
    supported={f['key'] for f in check_registry(packet.data['return_versions'][-1]) if f['status']=='passed'}
    decisions=[r for r in records.values() if r.kind=='decision' and r.payload['status']=='approved' and r.payload.get('outcome','accepted')=='accepted']
    proof_details=[]
    def done(key,visiting=None):
        if key in statuses:
            return statuses[key]
        visiting=set(visiting or ())
        if key in visiting:
            return False
        visiting.add(key)
        line=lines[key]
        ref='v3:'+key
        record=records[ref]
        value=line['value']
        proof=resolution(ref,value)
        if key=='F540NR.61' and line.get('review_basis')=='accepted_by_judgment':
            proof=resolution('diagnostic:CA_AMT_NOT_COMPUTED',None)
        if is_amendment:
            changes=[c for c in row.payload.get('changes',[]) if c.get('key')==key and c['status'] in {'proposed','approved'}]
            valid=not changes or all(c['status']=='approved' for c in changes)
            statuses[key]=valid
            return valid
        if not proof:
            for check in checks.get(record.id,[]):
                if check.reversed_at:
                    continue
                refs=check.evidence
                located=all(r not in records or records[r].kind!='extraction' or records[r].payload.get('locator',{}).get('resolved') for r in refs)
                if located and all(available(packet,r,row.payload['as_of'],records) for r in refs) and check.fingerprint==fingerprint(db,packet,record,value,refs,graph):
                    proof='verification:'+str(check.id)
                    break
        if not proof:
            for decision in decisions:
                p=decision.payload
                if p['claim_ref']==ref and p['reviews'] and p['reviews'][-1]['fingerprint']==fingerprint(db,packet,record,value,p['evidence'],graph):
                    proof=decision.ref
                    break
        inherited=not proof and key in supported and all(done(term,visiting) for term,_ in FORMULAS[key])
        statuses[key]=bool(proof or inherited)
        if proof:
            proof_details.append({'claim':ref,'proof':proof})
        return statuses[key]
    for key,line in lines.items():
        good=done(key)
        claim_rows.append({'ref':'v3:'+key,'label':line['label'],'value':line['value'],'basis':line['basis'],'done':good,
            'reason':'Reviewed or inherited through checked arithmetic' if good else 'Needs current verification or independently approved judgment; unchecked arithmetic does not inherit readiness'})
    documents=[]
    if not is_amendment:
        for r in records.values():
            if r.kind=='document' and available(packet,r.ref,row.payload['as_of'],records):
                p=r.payload
                good=p.get('disposition')!='unresolved' and (p.get('disposition')=='used' or bool(p.get('disposition_reason','').strip()))
                documents.append({'ref':r.ref,'title':p['title'],'done':good})
    issues=[]
    if not is_amendment:
        for finding in run_audit(packet)['findings']:
            ref='v3:'+finding['claim']
            line=lines.get(finding['claim'])
            fixed=line is not None and D(line['value'])==D(finding['proposed']) if line and isinstance(line['value'],(int,float,Decimal,str)) else False
            # A missing manual lot (E12) requires an explicit disposition; absence is never zero.
            accepted=resolution('finding:'+finding['id'],line['value'] if line else None)
            if not fixed and not accepted:
                issues.append({'ref':'finding:'+finding['id'],'label':finding['title'],'value':line['value'] if line else None})
        for diagnostic in packet.data['return_versions'][-1]['diagnostics']:
            if diagnostic['severity']=='warning' and not resolution('diagnostic:'+diagnostic['code'],None):
                issues.append({'ref':'diagnostic:'+diagnostic['code'],'label':diagnostic['message'],'value':None})
    open_questions=[r.ref for r in records.values() if r.kind=='question' and r.payload['status']!='resolved'] if not is_amendment else []
    notes=[{'ref':r.ref,'revision':r.revision,**r.payload} for r in records.values() if r.kind=='filing_note' and r.payload['branch_ref']==row.ref]
    branch_changes=[{**c,'status':'stale' if c['status']=='approved' and c.get('fingerprint')!=change_fingerprint(db,packet,c) else c['status']} for c in row.payload.get('changes',[])]
    preparers.update(c['actor_id'] for c in branch_changes)
    preparers.update(r.payload['actor_id'] for r in records.values() if r.kind=='filing_resolution' and r.payload['branch_ref']==row.ref)
    preparers.update(s['actor_id'] for s in row.payload.get('steps',{}).values())
    required=[s for s in packet.data['firm']['starter_standards']['required_steps'] if s not in AUTO_STEPS]
    steps=[{'name':name,'done':name in row.payload.get('steps',{})} for name in required]
    pending_adjustments=[]
    if not is_amendment:
        for a,r in db.execute(select(Adjustment,Record).join(Record,Record.id==Adjustment.record_id).where(Record.packet_id==packet.digest,Adjustment.status.in_(['proposed','reopened','approved']))):
            if a.status!='approved' or not approval_is_current(db,packet,r,a):
                pending_adjustments.append(r.ref)
    technical=[]
    technical.extend({'kind':'claim',**c} for c in claim_rows if not c['done'])
    technical.extend({'kind':'document',**d} for d in documents if not d['done'])
    technical.extend({'kind':'issue',**i} for i in issues)
    technical.extend({'kind':'step','ref':s['name'],'label':s['name']} for s in steps if not s['done'])
    technical.extend({'kind':'question','ref':r,'label':'Unresolved client question'} for r in open_questions)
    technical.extend({'kind':'note','ref':n['ref'],'label':n['text']} for n in notes if n['blocking'] and not n['closed'])
    technical.extend({'kind':'proposal','ref':r,'label':'Correction awaiting current independent review'} for r in pending_adjustments)
    if is_amendment and not any(c['status']=='approved' for c in branch_changes):
        technical.append({'kind':'branch_change','ref':'new_amendment_change','label':'Record and independently approve an amendment correction'})
    technical.extend({'kind':'branch_change','ref':c['id'],'label':'Branch correction awaiting independent review'} for c in branch_changes if c['status'] in {'proposed','stale'})
    source_revisions=sorted((r.ref,r.revision) for r in records.values() if r.kind in {'document','extraction','client_evidence','client_answer','attachment','household','decision','filing_resolution'} and available(packet,r.ref,row.payload['as_of'],records)) if not is_amendment else []
    if is_amendment:
        from types import SimpleNamespace
        changed_sources={r.ref:r for c in branch_changes for r in scope_records(db,packet,SimpleNamespace(ref='_branch_change'),c['evidence'])}
        source_revisions=sorted((r.ref,r.revision) for r in changed_sources.values())
    fp=digest({'lines':lines,'summary':summary,'household':household,'changes':branch_changes,'steps':row.payload.get('steps',{}),
        'sources':source_revisions,'proofs':proof_details,'blockers':technical,'policy':packet.data['firm']['starter_standards'],'parent':row.payload.get('parent_snapshot')})
    signoffs=[r for r in records.values() if r.kind=='filing_signoff' and r.payload['branch_ref']==row.ref]
    current_signoffs={r.payload['kind']:r for r in signoffs if r.payload['fingerprint']==fp}
    approvals=[r for r in records.values() if r.kind=='filing_authorization' and r.payload['branch_ref']==row.ref]
    approved_clients={r.payload['actor_id'] for r in approvals if r.payload['fingerprint']==fp}
    missing=[]
    for name in ['reviewer','partner','final_computation']:
        if name not in current_signoffs:
            missing.append({'kind':'signoff','ref':name,'label':name.replace('_',' ')+' approval missing or stale'})
    for client in packet.data['firm']['client_users']:
        if client['id'] not in approved_clients:
            missing.append({'kind':'authorization','ref':client['id'],'label':client['name']+' approval and e-file authorization missing or stale'})
    contributors=[]
    for a,r in db.execute(select(Adjustment,Record).join(Record,Record.id==Adjustment.record_id).where(Record.packet_id==packet.digest,Adjustment.status=='approved')):
        if approval_is_current(db,packet,r,a):
            contributors.append({'ref':r.ref,'tax_change':a.effect['tax_change'],'basis':a.effect['basis']})
    contributors.extend({'ref':c['key'],'tax_change':c['effect']['tax_change'],'basis':c['effect'].get('basis','exact')} for c in branch_changes if c['status']=='approved')
    if not is_amendment:
        amt_proof=resolution('diagnostic:CA_AMT_NOT_COMPUTED',None)
        if amt_proof and D(records[amt_proof].payload.get('resolved_amount') or 0):
            contributors.append({'ref':'v3:F540NR.61','tax_change':{'federal':'0','california':str(D(records[amt_proof].payload['resolved_amount']))},'basis':'recorded AMT judgment amount'})
    contributors.sort(key=lambda c:max(abs(D(v)) for v in c['tax_change'].values()),reverse=True)
    estimate_details={'largest_contributors':contributors[:10],'limits':'Rates measured at engine v3; thresholds, SE tax/QBI interactions and affected downstream lines are not recomputed.'}
    return {'branch_ref':row.ref,'revision':row.revision,'kind':row.payload['kind'],'as_of':row.payload['as_of'],'parent_snapshot':row.payload.get('parent_snapshot'),
        'fingerprint':fp,'summary':summary,'estimate_details':estimate_details,'claims':claim_rows,'documents':documents,'issues':issues,'steps':steps,'notes':notes,'changes':branch_changes,
        'technical_ready':not technical,'ready':not technical and not missing,'blockers':technical+missing,
        'counts':{'claims':len(claim_rows),'claims_done':sum(c['done'] for c in claim_rows),'documents':len(documents),'documents_done':sum(d['done'] for d in documents),'blockers':len(technical)+len(missing)},
        'preparers':sorted(preparers),'signoffs':[{'ref':r.ref,**r.payload,'current':r.payload['fingerprint']==fp} for r in signoffs],
        'authorizations':[{'ref':r.ref,**r.payload,'current':r.payload['fingerprint']==fp} for r in approvals],
        'limit':'Simulated filing only. Registered arithmetic is exact; affected lines retain engine values. The tax summary is an estimate and requires explicit partner acceptance. No return is transmitted.'}


def resolution_fingerprint(records,target,value,evidence):
    return digest({'target':target,'value':value,'evidence':[(ref,records[ref].revision if ref in records else None) for ref in evidence]})


def replay_as_of(db,packet):
    values=[r.payload['as_of'] for r in db.scalars(select(Record).where(Record.packet_id==packet.digest,Record.kind=='filing_branch'))]
    return max(values) if values else None
