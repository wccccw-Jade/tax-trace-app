"""Read-only generated tax views and completeness over the original packet and saved work."""
from datetime import date
from decimal import Decimal
import re
import calendar
from sqlalchemy import select
from backend.persistence.models import Record,FilingSnapshot
from backend.domain.history import snapshot,compare
from backend.domain.filing import available,replay_as_of
from backend.domain.policy import standards

VIEWS={
 'tax':('Tax computation',('F1040.','Sch1.','Sch2.','Sch3.','F6251.','F8959.','F8960.','F540NR.')),
 'depreciation':('Depreciation by asset',('F4562','FTB3885A','F4797')),
 'rentals':('Rentals & passive losses',('SchE.','F8582','F4797')),
 'k1':('K-1 income',('SchE.28','SchE.32','F7203','ScheduleS','SchB.1.7','SchB.1.8')),
 'basis':('Basis by year',('F7203','F8606')),
 'retirement':('Retirement & foreign items',('F8606','F8938','SchB.1.6','SchB.7','SchB.8','F1040.4','F8889','Sch3.1')),
 'deductions':('Deductions & credits',('SchA.','F8283','F8812','F8863','F2441','F8867','F8995')),
 'payments':('Payments & agency records',('F1040.25','F1040.26','F1040.31','F1040.33','F1040.37','F1040.38','F540NR.7','F540NR.97','F2210','FTB5805','Sch3.10','Sch3.11')),
 'state':('California split',('SchCA540NR','F540NR','ScheduleS','FTB3885A')),
 'carryovers':('Carryovers',('SchD.6','SchD.14','F8582','F8606.14','F7203.15')),
 'prior':('Prior preparer vs our work',()),
}


def as_of(db,packet):
    return replay_as_of(db,packet) or packet.data['return_versions'][-1]['computed_at']


def visible_records(db,packet):
    records={r.ref:r for r in db.scalars(select(Record).where(Record.packet_id==packet.digest))}
    at=as_of(db,packet)
    return {ref:r for ref,r in records.items() if available(packet,ref,at,records) or r.kind in {'assignment','outside_filing','time_entry','notification_seen','quality_finding','firm_policy','retention_hold'}}


def state_split(packet):
    def text(doc):return '\n'.join(p['printed_content'] for p in packet.resolve(doc)['pages'])
    w2=Decimal(re.search(r'Box 16 ([\d,.]+)',text('D09')).group(1).replace(',',''))
    stub=Decimal(re.search(r'CA taxable wages ([\d,.]+)',text('D73')).group(1).replace(',','').rstrip('.'))
    old=Decimal(str(packet.resolve('v3:SchCA540NR.1.E')['value']))
    other=Decimal(re.search(r'Box 16 ([\d,.]+)',text('D08')).group(1).replace(',',''))
    return {'status':'needs_decision','claim_ref':'v3:SchCA540NR.1.E','engine_ca_wages':str(old),
        'halvorsen_w2_ca':str(w2),'halvorsen_paystub_ca':str(stub),'difference_to_reconcile':str(w2-stub),
        'corvane_w2_ca':str(other),'candidate_ca_wages':str(other+stub),
        'evidence':['doc:D08#page1','doc:D09#page1','doc:D73#page1','ev-1081'],
        'note':'The July 18 paystub covers July 1–15 and reports CA wages near the July 15 move. Annual payroll kept California through September. Reconcile work dates, transition-day pay and California HSA treatment before finalizing. This candidate is not an approved correction. Do not apply a blanket residency-day fraction to all wages.'}


def dated(value,at):
    if isinstance(value,list):
        return [dated(v,at) for v in value if not isinstance(v,dict) or not (v.get('date') or v.get('as_of')) or str(v.get('date') or v.get('as_of'))<=at]
    if isinstance(value,dict):return {k:dated(v,at) for k,v in value.items()}
    return value


def generated(db,packet,view):
    title,prefixes=VIEWS[view]
    current=snapshot(db,packet,'workpaper')
    rows=[{'ref':'v3:'+k,**l} for k,l in current['lines'].items() if prefixes and k.startswith(prefixes)]
    sections=[]
    def section(title,value,refs):sections.append({'title':title,'value':value,'refs':refs})
    if view=='depreciation':
        for a in packet.data['return_versions'][-1]['assets']:
            section(a['description'],a,['v3:asset:'+a['asset_id'],*a.get('sources',[])])
    if view=='basis':
        prior=packet.data['prior_years']
        start=Decimal(str(prior['basis_records']['scorp_lindqvist_family_woodworks'][0]['ending_stock_basis']))
        text=' '.join(p['printed_content'] for p in packet.resolve('D40')['pages'])
        income=Decimal(re.search(r'income ([\d,]+)',text).group(1).replace(',',''))
        distributions=Decimal(re.search(r'distributions ([\d,]+)',text).group(1).replace(',',''))
        end23=start+income-distributions
        k24=prior['return_2024']['K1_1120S'];end24=end23+Decimal(str(k24['box1']))-Decimal(str(k24['box16D']))
        k25={l['key']:l['value'] for l in packet.data['return_versions'][-1]['lines'] if l['key'].startswith('F7203')}
        section('S-corporation basis reconciliation by year',[
            {'year':2022,'ending_basis':str(start),'basis':'Prior preparer worksheet'},
            {'year':2023,'beginning_basis':str(start),'income':str(income),'distributions':str(distributions),'ending_basis':str(end23),'basis':'D40 closes the missing prior-file year'},
            {'year':2024,'beginning_basis':str(end23),'income':k24['box1'],'distributions':k24['box16D'],'ending_basis':str(end24),'basis':'Prior return K-1 amounts'},
            {'year':2025,'beginning_basis':k25['F7203.1'],'increases':k25['F7203.4'],'distributions':k25['F7203.6'],'ending_basis':k25['F7203.15'],'excess_distributions':k25['F7203.excess'],'basis':'Engine v3 Form 7203; verify treatment separately'}
        ],['py:/basis_records','D39','D40','v3:F7203.1'])
        for key,value in packet.data['prior_years']['basis_records'].items():section(key.replace('_',' '),value,['py:/basis_records/'+key])
        section('Missing prior-year amounts stay unknown','Null basis amounts are missing evidence, not zero. Use the current Form 7203 lines and D40 to reconcile the history.',['D39','D40'])
    if view=='payments':
        at=as_of(db,packet)
        for i,v in enumerate(packet.data['tax_agency_records']['irs_account_transcript_2025']):
            if v['as_of']<=at[:10]:section('IRS account transcript as of '+v['as_of'],v,['agency:/irs_account_transcript_2025/'+str(i)])
        section('California payment account',dated(packet.data['tax_agency_records']['ftb_account'],at[:10]),['agency:/ftb_account'])
        section('Payment discrepancies','Federal estimates: engine 13,000 vs transcript 12,000. California: review the payment designated for 2024 before including it in 2025.',['v3:F1040.26','v3:F540NR.72','D68'])
    if view=='state':section('D73 wage allocation check',state_split(packet),state_split(packet)['evidence'])
    if view in {'carryovers','rentals'}:section('Carryovers into 2025',packet.data['prior_years']['carryovers_into_2025'],['py:/carryovers_into_2025','D06','D07'])
    if view=='carryovers':
        section('Engine v3 carryovers out of 2025 — not recomputed after adjustments',packet.data['return_versions'][-1]['carryovers_out'],['v3'])
        records=visible_records(db,packet)
        for r in records.values():
            if r.kind=='post_filing' and r.payload.get('action')=='rollforward':section('Saved 2026 roll-forward',r.payload['details'],[])
    if view=='prior':
        section('Prior preparer notes and open items',packet.data['prior_years']['prior_preparer_workpaper'],['D07'])
        comparison=compare(db,packet,'v3','workpaper')
        section('Our changes to the inherited engine draft',comparison,[])
        rows=[{'ref':'v3:'+k,**l} for k,l in current['lines'].items() if l['basis']!='engine']
    return {'id':view,'title':title,'as_of':as_of(db,packet),'rows':rows,'sections':sections,
        'note':'Generated from engine v3 and approved workpaper corrections. Pending changes are excluded. Limits and phase-outs are displayed as supplied; this is not a tax-engine recomputation.'}


OUTSIDE=[
 {'id':'fbar','label':'FinCEN 114 (FBAR)','owner':'Client','due':'2026-10-15','support':['D07'],'note':'Outside engagement; confirm client responsibility and completion.'},
 {'id':'1099','label':'2025 contractor Forms 1099-NEC','owner':'Client','due':'2026-02-02','support':['v3:SchC.J'],'note':'Already late at the case-study start; record communication and responsibility.'},
 {'id':'ada','label':'Ada’s separate 2025 Form 1040','owner':'Ada','due':None,'support':[],'note':'Return not supplied. Do not invent its contents.'},
 {'id':'scorp','label':'Woodworks Form 1120-S and Oregon composite','owner':'Willamette CPA Group','due':None,'support':['D39','D40'],'note':'Only K-1s supplied; underlying return is missing.'},
 {'id':'partnership','label':'Ridgeline Form 1065 and Arizona composite','owner':'Fund administrator','due':None,'support':['D37','D38'],'note':'Only K-1 and state supplement supplied; underlying return is missing.'},
 {'id':'3520','label':'Prior-year foreign inheritance / Form 3520 follow-up','owner':'Unassigned','due':None,'support':['D07'],'note':'Prior preparer left this open. Record scope, owner and client communication.'},
]


def completeness(db,packet):
    records=visible_records(db,packet)
    docs=[{'ref':r.ref,'title':r.payload['title'],'status':r.payload.get('disposition','unresolved'),
        'done':r.payload.get('disposition','unresolved')!='unresolved' and (r.payload.get('disposition')=='used' or bool(r.payload.get('disposition_reason')))} for r in records.values() if r.kind=='document']
    outside=[]
    for item in OUTSIDE:
        r=records.get('outside:'+item['id'])
        outside.append({**item,'ref':'outside:'+item['id'],'revision':r.revision if r else 0,'saved':r.payload if r else None,'done':bool(r and r.payload.get('status') in {'communicated','completed','outside_scope'})})
    areas=[]
    for key,title in [(k,v[0]) for k,v in VIEWS.items()]+[('business','Business books to tax'),('sales','Investment sales')]:
        r=records.get('area:'+key)
        areas.append({'id':key,'title':title,'revision':r.revision if r else 0,'saved':r.payload if r else None,'done':bool(r and r.payload['status'] in {'reviewed','not_applicable'})})
    return {'areas':areas,'areas_done':sum(a['done'] for a in areas),'documents':docs,'documents_done':sum(d['done'] for d in docs),'documents_total':len(docs),'packet_documents':len(packet.data['documents']),
        'outside':outside,'outside_done':sum(r['done'] for r in outside),'all_accounted_for':all(d['done'] for d in docs) and all(r['done'] for r in outside) and all(a['done'] for a in areas)}


def retention(db,packet):
    years=standards(db,packet)['retention_years'];at=as_of(db,packet)[:10]
    holds={r.payload['snapshot_id']:r for r in db.scalars(select(Record).where(Record.packet_id==packet.digest,Record.kind=='retention_hold'))}
    result=[]
    for s in db.scalars(select(FilingSnapshot).where(FilingSnapshot.packet_id==packet.digest)):
        submitted=s.content.get('as_of',s.at)[:10]
        start=date.fromisoformat(submitted);eligibility=start.replace(year=start.year+years,day=min(start.day,calendar.monthrange(start.year+years,start.month)[1]))
        hold=holds.get(s.id)
        active=bool(hold and hold.payload['active'])
        result.append({'snapshot_id':s.id,'filed_date':submitted,'eligible_on':eligibility.isoformat(),'hold':active,'hold_reason':hold.payload.get('reason') if hold else None,
            'hold_revision':hold.revision if hold else 0,'eligible':at>=eligibility.isoformat() and not active})
    return {'years':years,'as_of':at,'records':result,'deletion_enabled':False,'note':'Retention eligibility only. Records and frozen snapshots are never deleted. Holds prevent eligibility.'}
