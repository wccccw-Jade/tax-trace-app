"""Match individual sales to printed broker rows before offering bulk verification."""
import hashlib
import json
import re
from decimal import Decimal
from sqlalchemy import select
from backend.persistence.models import Record, Verification, Adjustment
from backend.domain.workpaper import evidence_graph, fingerprint

NUMBER=r'[\d,]+\.\d{2}'
LOT=re.compile(r'\b(?P<lot>[NMX]\d+)\s+(?P<description>.*?)\s+[\d.]+\s+sh\s+acquired\s+(?P<acquired>\d{4}-\d{2}-\d{2})\s+sold\s+(?P<sold>\d{4}-\d{2}-\d{2})\s+proceeds\s+(?P<proceeds>'+NUMBER+r')\s+basis\s+(?P<basis>'+NUMBER+r'|\(not reported\))(?P<tail>[^;]*)')


def sales_checks(db,packet):
    graph=evidence_graph(db,packet)
    records,_=graph
    printed={}
    for doc_id in ['D28','D31','D74']:
        doc=records[doc_id]
        for page in doc.payload['pages']:
            for match in LOT.finditer(page['printed_content']):
                printed[(doc_id,match['lot'])]={**match.groupdict(),'page':page['page']}
    verifications={}
    for check in db.scalars(select(Verification).join(Record,Record.id==Verification.record_id).where(Record.packet_id==packet.digest,Verification.reversed_at.is_(None)).order_by(Verification.id)):
        verifications[check.record_id]=check
    proposals={a.record_id for a in db.scalars(select(Adjustment).join(Record,Record.id==Adjustment.record_id).where(Record.packet_id==packet.digest,Adjustment.status.in_(['proposed','reopened','approved'])))}
    rows=[]
    for record in records.values():
        p=record.payload
        if record.kind!='claim' or p.get('version')!='v3' or p.get('form')!='F8949' or p['key'].endswith('.total'):
            continue
        lot=p['key'].split('.')[-1]
        fields=[records[r] for r in p['sources'] if r in records and records[r].kind=='extraction']
        docs={f.payload['document_id'] for f in fields}
        broker=bool(re.fullmatch(r'[NMX]\d+',lot))
        reasons=[]
        evidence=p['sources']
        if not broker:
            reasons.append('Crypto or basis rollforward requires individual review')
        else:
            if len(docs)!=1 or not docs<={'D28','D31','D74'}:
                reasons.append('Sources are missing, mixed, or not the current broker statement')
            if any(records[d].payload.get('disposition') in {'duplicate','superseded','outside_scope'} for d in docs):
                reasons.append('Document disposition excludes this source')
            source=printed.get((next(iter(docs)),lot)) if len(docs)==1 else None
            if not source:
                reasons.append('No matching printed broker row')
            else:
                required={}
                for field in fields:
                    suffix=field.payload['field'].split('_',1)[-1]
                    suffix={'desc':'description','acq':'acquired'}.get(suffix,suffix)
                    required[suffix]=field.payload['value']
                for name in ['description','acquired','sold','proceeds','basis']:
                    raw=required.get(name)
                    expected=source[name]
                    if name in {'proceeds','basis'}:
                        if raw is None or expected=='(not reported)' or Decimal(str(raw))!=Decimal(expected.replace(',','')):
                            reasons.append('Missing or mismatched '+name)
                    elif raw is None or str(raw)!=expected:
                        reasons.append('Printed/extracted '+name+' mismatch')
                wash=re.search(r'wash sale loss disallowed ('+NUMBER+r')',source['tail'])
                if wash and Decimal(wash[1].replace(',',''))!=0:
                    reasons.append('Wash-sale exception')
                if required.get('wash') not in (None,0,0.0):
                    reasons.append('Wash-sale exception')
                if source['basis']!='(not reported)':
                    proceeds=Decimal(source['proceeds'].replace(',',''))
                    basis=Decimal(source['basis'].replace(',',''))
                    if basis<=0:
                        reasons.append('Zero basis requires individual review')
                    if (proceeds-basis).quantize(Decimal('.01'))!=Decimal(str(p['value'])).quantize(Decimal('.01')):
                        reasons.append('Gain differs from proceeds less basis; check adjustments')
                evidence=list(dict.fromkeys([*evidence,f"doc:{next(iter(docs))}#page{source['page']}"]))
            if any(not f.payload.get('locator',{}).get('resolved') for f in fields):
                reasons.append('Unresolved source anchor')
            if record.id in proposals:
                reasons.append('Correction has its own review workflow')
        reasons=list(dict.fromkeys(reasons))
        fp=fingerprint(db,packet,record,p['value'],evidence,graph)
        check=verifications.get(record.id)
        verified=bool(check and check.fingerprint==fingerprint(db,packet,record,p['value'],check.evidence,graph))
        rows.append({'ref':record.ref,'revision':record.revision,'label':p['label'],'value':str(p['value']),
            'box':p['key'].split('.')[1],'lot':lot,'broker':broker,'check':'passed' if not reasons else 'exception',
            'reasons':reasons,'eligible':not reasons and not verified,'verified':verified,
            'evidence':evidence,'fingerprint':fp})
    token=hashlib.sha256(json.dumps([(r['ref'],r['revision'],r['fingerprint'],r['eligible']) for r in rows],sort_keys=True).encode()).hexdigest()
    return {'rows':rows,'selection_token':token,'counts':{'total':len(rows),'broker':sum(r['broker'] for r in rows),
        'passed':sum(r['check']=='passed' for r in rows),'eligible':sum(r['eligible'] for r in rows),
        'exceptions':sum(r['check']=='exception' for r in rows),'verified':sum(r['verified'] for r in rows)}}
