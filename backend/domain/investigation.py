"""Day-0 fixture investigation dispositions. Judgment items remain decisions, not invented fixes."""
from decimal import Decimal
import re


def investigate(packet):
    p=packet.data
    v=p['return_versions'][-1]
    lines={l['key']:l for l in v['lines']}
    docs={d['id']:d for d in p['documents']}
    def text(d):
        return '\n'.join(page['printed_content'] for page in docs[d]['pages'])
    extractions={e['id']:e for e in p['extracted_values']}
    used={extractions[s]['document_id'] for l in v['lines'] if l['form']=='F8949' and re.search(r'\.M\d+$',l['key']) for s in l['sources'] if s in extractions}
    k23=text('D40')
    income=int(re.search(r'income ([\d,]+)',k23).group(1).replace(',',''))
    distribution=int(re.search(r'distributions ([\d,]+)',k23).group(1).replace(',',''))
    basis=p['prior_years']['basis_records']['scorp_lindqvist_family_woodworks'][0]['ending_stock_basis']+income-distribution+p['prior_years']['return_2024']['K1_1120S']['box1']-p['prior_years']['return_2024']['K1_1120S']['box16D']
    transcript=p['tax_agency_records']['irs_account_transcript_2025'][0]
    wages=extractions['ev-0016']['value']+extractions['ev-0035']['value']
    prior=Decimal(str(p['prior_years']['return_2024']['lines']['F1040.24']))
    safe=round(prior*Decimal('1.1'))
    return [
        {'lead':'Meridian summary/detail mismatch','status':'confirmed_discrepancy','evidence':['doc:D31#page1','doc:D31#page32'],
         'conclusion':'Page 32 contains M18, proceeds 250 and basis 310: a missing short-term loss of 60. Add an evidence-backed manual lot in Story A; no extracted value exists for it.'},
        {'lead':'Corrected brokerage statement','status':'reconciled' if used=={'D31'} else 'needs_decision','evidence':['D30','D31'],
         'conclusion':f'v3 Meridian lot sources use {", ".join(sorted(used))}. The replacement is used; the supplemental unextracted lot remains a separate discrepancy.'},
        {'lead':'Duplicate W-2 upload','status':'reconciled' if wages==lines['F1040.1a']['value'] else 'confirmed_discrepancy','evidence':['D09','D10','msg-02','v3:F1040.1a'],
         'conclusion':f'D09 and D10 represent one W-2. The distinct employer wage sum is {wages:g}, agreeing with the current return; the phone image was not counted twice.'},
        {'lead':'Crypto C6 basis and acquisition date','status':'needs_decision','evidence':['msg-07','D34','D35'],
         'conclusion':'Client states purchase in March 2021 for about 3,050 and cites a bank statement. This is evidence to assess, not confirmed cost basis. Record a decision on the support and holding period in Story C.'},
        {'lead':'Handwritten donation receipt','status':'needs_decision','evidence':['D64','msg-08','ev-1049'],
         'conclusion':'Printed first digit is ambiguous; extraction is 1,500 and later client confirmation is also 1,500. No amount discrepancy proved. Record substantiation and confirmation; confidence alone is not an error.'},
        {'lead':'S-corporation historical basis','status':'reconciled' if basis==lines['F7203.1']['value'] else 'confirmed_discrepancy','evidence':['D40','py:/basis_records/scorp_lindqvist_family_woodworks/0','py:/return_2024/K1_1120S','v3:F7203.1'],
         'conclusion':f'21,300 + {income:,} - {distribution:,} + 16,900 - 30,000 = {basis:,} opening 2025 basis, agreeing with v3. Preserve the source worksheet assumption; prior-year history is not silently rewritten.'},
        {'lead':'California-source wages','status':'needs_decision','evidence':['D08','D09','D73','v3:SchCA540NR.1.E'],
         'conclusion':'D73 supports 22,469 Halvorsen CA taxable wages near the move, versus annual W-2 CA wages of 111,300. Do not allocate all annual wages or use a blanket day fraction. Preparer must reconcile work dates and HSA treatment before finalizing the split.'},
        {'lead':'California AMT','status':'needs_decision','evidence':['D12','v3:F6251.2i'],
         'conclusion':'The engine explicitly did not compute California AMT. Keep a blocking unresolved calculation requiring a conclusion; do not manufacture a zero.'},
        {'lead':'Questionnaire says no investment sales','status':'needs_decision','evidence':['qa-14','D28','D31','D34','D74'],
         'conclusion':'Broker documents prove sales despite the organizer answer. Preserve the original answer and obtain/document a reconciled response; this is a completeness conflict, not a second tax adjustment.'},
        {'lead':'Underpayment penalty','status':'reconciled','evidence':['py:/return_2024/lines/F1040.24','v3:F2210.8','v3:F2210.AI'],
         'conclusion':f'Prior-year safe harbor rounds to {safe:,}, agreeing with F2210.8. The supplied annualized scenario changes the penalty by zero. Unchanged 164 is not itself a defect; reassess payment timing after the confirmed IRS payment correction.'},
        {'lead':'Mixed business use and Spotify','status':'confirmed_discrepancy','evidence':['call-01','D15','v3:SchC.25','v3:SchC.27a.1'],
         'conclusion':'Client statement supports phone 70%, internet 50%, Spotify personal. Proposed utilities 2,172 instead of 3,480 and software 6,634 instead of 6,850. These proposals still require verification of the statement.'},
        {'lead':'Home-office variance','status':'reconciled','evidence':['D24','v3:SchC.30','D07'],
         'conclusion':'Current measurements are 220 Sacramento and 260 Austin; the engine uses simplified average 240. This explains a change from prior-year 300. A prior-year correction is not inferred.'},
        {'lead':'Outside filings and prior open matters','status':'needs_decision','evidence':['D01','D07','D27','D38','D39'],
         'conclusion':'FBAR and contractor 1099s are outside engagement and require responsibility/communication. Prior preparer left a 2023 Form 3520 question unresolved. Oregon and Arizona composite statements need disposition; Ada files separately. Do not imply any outside filing was completed.'},
        {'lead':'Dependent identity rejection','status':'replay_only','evidence':['D71','msg-10','agency:/efile/0'],
         'conclusion':'Later correction evidence supports the scripted July rejection/resubmission. Preserve submitted and corrected identities separately when replay is built; no current mutation is applied.'},
        {'lead':'Unextracted documents','status':'needs_decision','evidence':['D07','D69','D70','D72'],
         'conclusion':'D07 and agency records can be cited manually despite no extraction. D70 records a resolved prior CP2000; D72 is future notice material. Extraction status does not establish verification or document completeness.'},
    ]
