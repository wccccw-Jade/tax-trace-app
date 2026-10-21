"""Fixture audit: findings are derived from source text/records, not engine diagnostics."""
import re
from decimal import Decimal
from backend.domain.formulas import check_registry, tax_effect
from backend.domain.locators import packet_locators

D = lambda x: Decimal(str(x))


def amount(text, pattern):
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError(f'Cannot locate source amount for {pattern}')
    return D(match.group(1).replace(',', '').rstrip('.'))


def run_audit(packet):
    p = packet.data
    v = p['return_versions'][-1]
    lines = {l['key']: l for l in v['lines']}
    docs = {d['id']: d for d in p['documents']}
    def text(doc):
        return '\n'.join(page['printed_content'] for page in docs[doc]['pages'])
    findings = []
    def finding(code, title, key, expected, refs, category):
        observed = D(lines[key]['value'])
        expected = D(expected)
        if observed == expected:
            return
        delta = expected - observed
        findings.append({'id': code, 'title': title, 'claim': key, 'observed': str(observed),
                         'proposed': str(expected), 'delta': str(delta), 'evidence': refs,
                         'category': category, 'tax_effect': tax_effect(delta, category, v['tax_effect_rates']),
                         'status': 'confirmed_discrepancy', 'review_status': 'not_reviewed'})
    # Duplicate interest: match the bank-sweep relationship and account, not equal amounts alone.
    a, b = text('D28'), text('D29')
    account_a = re.search(r'account ending (\d+)', a).group(1)
    account_b = re.search(r'account ending (\d+)', b).group(1)
    if account_a == account_b and 'bank sweep' in a.lower() and 'bank sweep' in b.lower():
        finding('E1', 'Duplicate Northlake sweep interest', 'SchB.1.2', 0, ['doc:D28#page1', 'doc:D29#page1'], 'interest')
    sek = amount(text('D36'), r'Interest credited [^:]+: SEK ([\d,]+\.\d{2})')
    rate = D(packet.resolve('ref:fx.SEK.2025_average'))
    finding('E2', 'Prior-year exchange rate used for 2025 interest', 'SchB.1.6', round(sek / rate), ['ev-0960', 'ref:fx.SEK.2025_average'], 'interest')
    sold = amount(text('D66'), r'4c gross proceeds from sale ([\d,.]+)')
    finding('E3', 'Vehicle gift exceeds charity sale proceeds', 'F8283.A1.vehicle', sold, ['doc:D66#page1', 'call-01'], 'itemized')
    books = amount(text('D14'), r'Total income ([\d,.]+)')
    if '12,400.00 arrived through Paywell' in text('D15'):
        finding('E4', '1099-K receipts already included in books', 'SchC.1', books, ['doc:D14#page1', 'doc:D15#page3', 'D21'], 'schc_profit')
    for code, key, basis, page in [('E5','F8949.B.N1','19,100.00',2),('E6','F8949.B.N3','19,100.00',2),('E7','F8949.E.N4','9,420.00',2)]:
        # Supplemental statement is source of adjusted basis; engine lot labels disclose proceeds.
        if basis not in text('D11'):
            continue
        proceeds = amount(lines[key]['label'], r'proceeds ([\d,.]+)')
        finding(code, 'RSU adjusted basis omitted', key, proceeds-D(basis.replace(',','')), [f'doc:D11#page{page}', 'D28'], 'stcg' if '.B.' in key else 'ltcg')
        if findings[-1]['id'] == code and '.B.' in key:
            findings[-1]['tax_effect']['california'] = tax_effect(findings[-1]['delta'], 'ca_source_income', v['tax_effect_rates'])['california']
            findings[-1]['california_basis'] = 'Sale during California residency; ca_source_income rate'
    pages = docs['D23']['pages']
    unique = {page['printed_content'][page['printed_content'].index('Mileage log'):] for page in pages}
    mileage = sum((amount(t, r'Page total ([\d,]+) miles') for t in unique), D(0))
    finding('E8', 'Duplicate mileage log page counted twice', 'SchC.44a', mileage, ['doc:D23#page2', 'doc:D23#page3'], 'schc_profit')
    # Mileage quantity is not dollars: estimate from the deduction change, not the miles.
    if findings[-1]['id'] == 'E8':
        rate_miles = D(p['engine_reference']['parameters']['mileage_rate'])
        profit_delta = -D(findings[-1]['delta']) * rate_miles
        findings[-1]['tax_effect'] = tax_effect(profit_delta, 'schc_profit', v['tax_effect_rates'])
        findings[-1]['effect_input'] = {'profit_delta': str(profit_delta), 'rate_per_mile': str(rate_miles)}
    payoff = amount(text('D56'), r'interest 11/01/2025-11/20/2025 ([\d,.]+)')
    if 'includes prepaid interest' in text('D55') and 'Interest is reported on the 2025 Form 1098' in text('D56'):
        finding('E9', 'Payoff interest already included in Form 1098', 'SchA.8a', D(lines['SchA.8a']['value'])-payoff, ['D55','D56'], 'itemized')
    federal = sum((D(t['amount']) for t in p['tax_agency_records']['irs_account_transcript_2025'][0]['transactions'] if t['code']=='670'), D(0))
    finding('E10', 'Federal estimates do not agree to IRS transcript', 'F1040.26', federal, ['agency:/irs_account_transcript_2025/0'], 'payment')
    ca = sum((D(t['amount']) for t in p['tax_agency_records']['ftb_account']['tax_year_2025_payments']), D(0))
    finding('E11', '2024-designated payment counted toward 2025 California', 'F540NR.72', ca, ['D68','agency:/ftb_account'], 'payment')
    locators = packet_locators(packet)
    edges = packet.edges()
    return {'packet_hash': packet.digest, 'counts': {'documents': len(p['documents']), 'extractions': len(p['extracted_values']),
            'versions': len(p['return_versions']), 'claims': sum(len(v['lines']) for v in p['return_versions']), 'edges': len(edges)},
            'locators': {'resolved': sum(x['resolved'] for x in locators.values()), 'total': len(locators)},
            'unresolved_references': [e for e in edges if not e['resolved']],
            'formula_checks': {v['version']: check_registry(v) for v in p['return_versions']},
            'findings': findings,
            'open_leads': ['Meridian 250 proceeds discrepancy: locate exact lot', 'California-source wage allocation from D73',
                           'California AMT not computed', 'Crypto C6 basis/date: assess msg-07 evidence',
                           'Mixed business use and Spotify: evaluate call-01', 'Historical S corporation basis reconciliation',
                           'Due diligence and outside filings', 'Theo identity correction belongs to later replay']}
