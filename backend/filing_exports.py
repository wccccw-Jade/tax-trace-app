"""Downloads are generated only from immutable accepted copies."""
import base64
import hashlib
from html import escape
from io import BytesIO
import json
from zipfile import ZipFile,ZIP_DEFLATED
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.dependencies import identity,staff,packet
from backend.persistence.db import session
from backend.persistence.models import Record,AuditEvent
from backend.domain.filing import canonical
from backend.filing_api import snapshot_record,accepted,branch

router=APIRouter(prefix='/api/filing')


def page(title,body):
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>'+escape(title)+'</title><style>body{max-width:1100px;margin:40px auto;padding:0 22px;font:15px/1.6 system-ui;color:#243b2b}table{border-collapse:collapse;width:100%}th,td{border:1px solid #d6dfd1;padding:9px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{padding:18px;background:#fff3d7}h1{font-size:26px}small{color:#52664a}</style>'
        '<h1>'+escape(title)+'</h1>'+body+'</html>')


def frozen_copy(s):
    c=s.content
    body='<p class="notice">'+escape(c['limit'])+'</p><p>Frozen copy: '+escape(s.id)+'<br>SHA-256: '+s.digest+'</p>'
    body+='<h2>As submitted summary</h2><table><tr><th>Jurisdiction</th><th>Total tax (estimated)</th><th>Payments</th><th>Balance due</th></tr>'
    for j in ['federal','california']:
        summary=c['summary'][j]
        body+='<tr><td>'+j+'</td>'+''.join('<td>'+escape(str(summary[k]))+'</td>' for k in ['total_tax','payments','balance_due'])+'</tr>'
    body+='</table><h2>Household as submitted</h2><table><tr><th>Name</th><th>Taxpayer identification</th></tr>'
    for person in c['household']['people']:
        body+='<tr><td>'+escape(str(person['name']))+'</td><td>'+escape(person['ssn'])+'</td></tr>'
    body+='</table><h2>Claim values and computation basis</h2><table><tr><th>Line</th><th>Description</th><th>Value</th><th>Basis</th></tr>'
    for key,l in c['lines'].items():
        body+='<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in [key,l['label'],l['value'],l['basis']])+'</tr>'
    return page('Simulated client copy — tax year 2025',body+'</table>')


@router.get('/snapshots/{snapshot_id}/client-copy')
def client_copy(snapshot_id:str,actor=Depends(identity),db:Session=Depends(session)):
    s=snapshot_record(db,snapshot_id)
    if not accepted(db,s.id):
        raise HTTPException(409,'Client copies are generated from copies accepted by both agencies')
    if actor['role']!='client' and not actor.get('sensitive_data_clearance'):
        raise HTTPException(403,'Clearance is required to download a complete copy')
    db.add(AuditEvent(actor_id=actor['id'],action='client_copy_exported',subject=s.branch_ref))
    db.commit()
    return Response(frozen_copy(s),media_type='text/html',headers={'Content-Disposition':'attachment; filename="simulated-client-copy.html"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.get('/snapshots/{snapshot_id}/examination-bundle')
def bundle(snapshot_id:str,actor=Depends(staff),db:Session=Depends(session)):
    if not actor.get('sensitive_data_clearance'):
        raise HTTPException(403,'Sensitive-data clearance required for the complete examination record')
    s=snapshot_record(db,snapshot_id)
    if not accepted(db,s.id):
        raise HTTPException(409,'Choose an accepted frozen copy')
    row=branch(db,packet(),s.branch_ref)
    notice=db.scalar(select(Record).where(Record.packet_id==packet().digest,Record.kind=='post_filing',Record.payload['branch_ref'].as_string()==row.ref,Record.payload['action'].as_string()=='notice'))
    if not notice:
        raise HTTPException(409,'Replay receipt of the examination notice first')
    c=s.content
    files={}
    def add_json(name,value):
        files[name]=canonical(value).encode()
    add_json('snapshot.json',{'id':s.id,'sha256':s.digest,'parent_id':s.parent_id,'content':c})
    add_json('claims.json',c['lines'])
    add_json('checks.json',c['verifications'])
    add_json('adjustments.json',c['adjustments'])
    add_json('decisions.json',{ref:r for ref,r in c['evidence'].items() if r['kind'] in ['decision','filing_resolution']})
    add_json('signoffs.json',{'staff':c['signoffs'],'clients':c['authorizations'],'steps':c['steps']})
    add_json('evidence.json',{'records':c['evidence'],'edges':c['evidence_edges']})
    add_json('audit-events.json',c['audit_events'])
    add_json('notice.json',notice.payload['details'])
    files['client-copy.html']=frozen_copy(s).encode()
    docs=[]
    for ref,r in c['evidence'].items():
        if r['kind']=='document':
            p=r['payload']
            name='simulated-documents/'+ref+'.html'
            body='<p class="notice">Simulated document text from the frozen record.</p>'
            for source in p['pages']:
                body+='<h2>Page '+str(source['page'])+'</h2><pre>'+escape(source['printed_content'])+'</pre>'
            files[name]=page(p['title'],body).encode()
            docs.append('<li><a href="'+name+'">'+escape(ref+' — '+p['title'])+'</a></li>')
    for ref,a in c['attachments'].items():
        data=base64.b64decode(a['content_base64'])
        if hashlib.sha256(data).hexdigest()!=a['sha256']:
            raise HTTPException(409,'Frozen attachment checksum mismatch')
        files['attachments/'+ref.replace(':','_')+'.bin']=data
    index='<p class="notice">'+escape(c['limit'])+'</p><p>Snapshot '+escape(s.id)+' · '+s.digest+'</p>'
    index+='<p>The donation and gross-receipts support already existed at submission. No evidence is fabricated for the notice.</p><ul>'
    for name in ['client-copy.html','snapshot.json','claims.json','checks.json','adjustments.json','decisions.json','signoffs.json','evidence.json','audit-events.json','notice.json','manifest.json']:
        index+='<li><a href="'+name+'">'+name+'</a></li>'
    files['index.html']=page('Examination bundle — Letter 566',index+'</ul><h2>Frozen simulated sources</h2><ul>'+''.join(docs)+'</ul>').encode()
    manifest={'snapshot_id':s.id,'snapshot_sha256':s.digest,'packet_sha256':c['packet_hash'],
        'basis':'Checksums cover every other archive entry. The manifest does not hash itself.',
        'entries':[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())]}
    add_json('manifest.json',manifest)
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            archive.writestr(name,data)
    db.add(AuditEvent(actor_id=actor['id'],action='examination_bundle_exported',subject=s.branch_ref))
    db.commit()
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="simulated-examination-bundle.zip"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
