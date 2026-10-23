"""Read-only comparisons and source-aware, per-person activity over the saved workpaper."""
import hashlib
import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from backend.persistence.models import Record, AuditEvent, Adjustment, LastSeen
from backend.domain.workpaper import projected_summary, evidence_graph

MUTATIONS={
    'area_considered','assignment_updated','outside_filing_updated','time_recorded','standards_updated','retention_hold_updated','quality_finding_recorded',
    'manual_anchor','verification_recorded','adjustment_proposed','adjustment_approved','adjustment_rejected',
    'document_disposition','approval_reopened','question_asked','client_answered','question_resolved',
    'decision_recorded','decision_approved','decision_rejected','bulk_claim_verified','bulk_verified',
    'bulk_verification_reversed','bulk_undo','variance_explained',
    'filing_workspace_started','filing_step_recorded','filing_resolution_recorded','filing_resolution_reviewed',
    'filing_note_opened','filing_note_closed','filing_signed','filing_client_authorized','filing_submitted',
    'filing_response_replayed','filing_branch_change_proposed','filing_branch_change_reviewed','amendment_started',
    'post_filing_payments','post_filing_rollforward','post_filing_notice',
}


def numeric(value):
    return isinstance(value,(int,float,Decimal)) and not isinstance(value,bool)


def snapshot(db,packet,version):
    versions={v['version']:v for v in packet.data['return_versions']}
    if version not in {*versions,'workpaper'}:
        raise HTTPException(422,'Choose v1, v2, v3 or the approved workpaper')
    base=versions['v3' if version=='workpaper' else version]
    lines={l['key']:{**l,'basis':'engine','ref':base['version']+':'+l['key']} for l in base['lines']}
    summary=base['summary']
    if version=='workpaper':
        projection=projected_summary(db,packet)
        summary=projection['summary']
        for changed in projection['changed_lines']:
            key=changed['key']
            lines[key]={**lines[key],'value':Decimal(changed['value']) if changed['basis']=='recomputed' else lines[key]['value'],'basis':changed['basis']}
        for c in projection['classification_changes']:
            lines[c['ref'].split(':',1)[1]]['treatment']=c
    return {'id':version,'computed_at':base['computed_at'],'trigger':base['trigger'] if version!='workpaper' else 'Current approved corrections over engine v3. Pending and reopened corrections are excluded.',
        'lines':lines,'summary':summary,'documents_used':base['documents_used'],'documents_superseded':base['documents_superseded']}


def compare(db,packet,before='v2',after='v3'):
    left=snapshot(db,packet,before)
    right=snapshot(db,packet,after)
    rows=[]
    fields=['value','sources','inputs','rule','label','basis','treatment']
    for key in sorted(left['lines'].keys()|right['lines'].keys()):
        a,b=left['lines'].get(key),right['lines'].get(key)
        differences=fields if not a or not b else [f for f in fields if a.get(f)!=b.get(f)]
        if not differences:
            continue
        delta=str(Decimal(str(b['value']))-Decimal(str(a['value']))) if a and b and numeric(a['value']) and numeric(b['value']) else None
        rows.append({'key':key,'label':(b or a)['label'],'change':'added' if not a else 'removed' if not b else 'changed',
            'fields':differences,'before':a,'after':b,'delta':delta})
    proposals=[]
    if 'workpaper' in {before,after}:
        for change,record in db.execute(select(Adjustment,Record).join(Record,Adjustment.record_id==Record.id).where(Record.packet_id==packet.digest,Adjustment.status.in_(['proposed','reopened'])).order_by(Adjustment.id.desc())):
            proposals.append({'ref':record.ref,'status':change.status,'proposed_value':change.proposed_value,'reason':change.reason})
    return {'before':{k:v for k,v in left.items() if k!='lines'},'after':{k:v for k,v in right.items() if k!='lines'},
        'rows':rows,'counts':{kind:sum(r['change']==kind for r in rows) for kind in ['added','removed','changed']},
        'pending':proposals,'basis':'Computed directly from line values, sources, inputs and rules; includes changes to evidence even when the amount is unchanged. Workpaper tax summaries are estimates.'}


def activity(db,packet,actor_id):
    graph=evidence_graph(db,packet)
    records,links=graph
    seen=db.get(LastSeen,(packet.digest,actor_id))
    cursor=seen.cursor if seen else 0
    reverse={}
    for source,targets in links.items():
        for target in targets:
            reverse.setdefault(target,[]).append(source)
    events=list(db.scalars(select(AuditEvent).where(AuditEvent.action.in_(MUTATIONS)).order_by(AuditEvent.id)))
    items=[]
    for event in events:
        record=records.get(event.subject)
        if not record:
            continue
        pending=[record.ref]
        visited=set()
        claims=set()
        while pending:
            ref=pending.pop()
            if ref in visited:
                continue
            visited.add(ref)
            r=records.get(ref)
            if r and r.kind=='claim' and r.payload.get('version')=='v3':
                claims.add(ref)
            if r and r.payload.get('claim_ref'):
                claims.add(r.payload['claim_ref'])
            pending.extend(reverse.get(ref,[]))
        items.append({'id':event.id,'actor_id':event.actor_id,'action':event.action,'subject':event.subject,
            'at':event.at,'claims':sorted(claims),'new':event.id>cursor})
    return {'actor_id':actor_id,'first_visit':seen is None,'seen_cursor':cursor,'seen_revision':seen.revision if seen else 0,
        'through_cursor':max((i['id'] for i in items),default=0),'unseen_count':sum(i['new'] for i in items),
        'changed_claims':sorted({ref for i in items if i['new'] for ref in i['claims']}),'items':list(reversed(items))}


def variance_values(prior,current,percent_limit=10,amount_limit=1000):
    old,new=Decimal(str(prior)),Decimal(str(current))
    delta=new-old
    pct=abs(delta)/abs(old)*100 if old else None
    flagged=abs(delta)>Decimal(str(amount_limit)) and (pct is None or pct>Decimal(str(percent_limit)))
    return {'delta':str(delta),'percent_change':str(pct.quantize(Decimal('.01'))) if pct is not None else None,
        'flagged':flagged,'comparison':'new_activity' if old==0 and new!=0 else 'both_zero' if old==0 else 'percentage'}


def variances(db,packet):
    prior=packet.data['prior_years']['return_2024']
    current=snapshot(db,packet,'workpaper')['lines']
    from backend.domain.policy import standards
    thresholds=standards(db,packet)['variance_review']
    percent=thresholds['flag_if_change_over_percent']
    amount=thresholds['and_over_amount']
    notes={}
    for note in db.scalars(select(Record).where(Record.packet_id==packet.digest,Record.kind=='variance_note').order_by(Record.id.desc())):
        notes.setdefault(note.payload['key'],[]).append({'ref':note.ref,**note.payload})
    rows=[]
    not_compared=[]
    for key,old in prior['lines'].items():
        # Payer row positions are not stable identities between tax years.
        if key=='SchC.44a':
            not_compared.append({'key':key,'reason':'Quantity in miles; the firm’s dollar variance threshold does not apply. Review mileage separately.'})
            continue
        if key.startswith(('SchB.1.','SchB.5.')):
            not_compared.append({'key':key,'reason':'Payer positions differ between years; reconcile by payer before comparing.'})
            continue
        if key not in current:
            not_compared.append({'key':key,'reason':'No matching current line. Missing is not zero; resident CA540 and part-year F540NR are not equated automatically.'})
            continue
        line=current[key]
        if not numeric(old) or not numeric(line['value']):
            not_compared.append({'key':key,'reason':'Not a numeric comparison.'})
            continue
        source=prior['line_sources'].get(key)
        prior_ref='py:/return_2024/lines/'+key
        body={'key':key,'prior':str(Decimal(str(old))),'current':str(Decimal(str(line['value']))),'basis':line['basis'],'percent':percent,'amount':amount}
        fp=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        history=[{**n,'current':n['fingerprint']==fp} for n in notes.get(key,[])]
        rows.append({'key':key,'label':line['label'],'ref':'v3:'+key,'prior_ref':prior_ref,'prior_source':source,
            'prior_value':old,'current_value':line['value'],'basis':line['basis'],**variance_values(old,line['value'],percent,amount),
            'fingerprint':fp,'explanations':history,'explained':any(n['current'] for n in history),
            'prior_note':prior.get('notes',{}).get(key)})
    rows.sort(key=lambda r:(not r['flagged'],-abs(Decimal(r['delta'])),r['key']))
    return {'prior_year':2024,'current_year':2025,'rows':rows,'not_compared':not_compared,
        'threshold':{'percent':percent,'amount':amount,'rule':'Flag only when the absolute change exceeds both limits. From zero: percentage is undefined; flag a new amount over the dollar limit.'},
        'basis':'Current approved workpaper values; affected lines retain engine values and need final computation. A variance is a review prompt, not an error or approval.',
        'counts':{'compared':len(rows),'flagged':sum(r['flagged'] for r in rows),'unexplained':sum(r['flagged'] and not r['explained'] for r in rows)}}
