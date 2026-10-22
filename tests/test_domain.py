import hashlib
import json
from copy import deepcopy
from backend.domain.audit import run_audit
from backend.domain.formulas import check_registry, tax_effect
from backend.domain.locators import locate, packet_locators
from backend.domain.packet import pointer
from backend.domain.security import sensitive_tokens, redact


def test_packet_integrity_and_all_links(packet):
    assert hashlib.sha256(packet.original.encode()).hexdigest() == packet.digest
    assert len(packet.data['documents']) == 74
    assert len(packet.data['extracted_values']) == 3012
    assert sum(len(v['lines']) for v in packet.data['return_versions']) == 1877
    assert all(edge['resolved'] for edge in packet.edges())
    assert packet.resolve('v2:F1040.11')['value'] == 429820
    assert packet.resolve('F1040.11', 'v3')['value'] == 445590
    assert packet.resolve('py:/return_2024/lines/F1040.24') == 37557
    assert packet.resolve('ref:fx.SEK.2025_average') == 9.86
    assert packet.resolve('agency:/efile/0')['status'] == 'rejected'
    assert packet.resolve('doc:D23#page3')['page'] == 3
    assert packet.resolve('missing') is None
    assert pointer({'a/b': {'~': 42}}, '/a~1b/~0') == 42


def test_audit_rederives_evidence(packet):
    report = run_audit(packet)
    f = {x['id']:x for x in report['findings']}
    assert len(f) == 14
    assert f['E4']['proposed'] == '151300.00'
    assert f['E5']['proposed'] == '140.00'
    assert f['E8']['proposed'] == '8100'
    assert f['E8']['effect_input']['profit_delta'] == '2590.0'
    assert f['E10']['proposed'] == '12000'
    assert f['E11']['proposed'] == '10500'
    assert f['E12']['proposed'] == '-60.00'
    assert f['E12']['new_claim']
    assert f['E13']['proposed'] == '2172.00'
    assert f['E13']['tax_effect']['federal'] == '464'
    assert f['E14']['proposed'] == '6634.00'
    investigations = {i['lead']:i for i in report['investigations']}
    assert investigations['Corrected brokerage statement']['status']=='reconciled'
    assert investigations['S-corporation historical basis']['status']=='reconciled'
    # Source changes must change the finding, not return a canned report.
    clone = deepcopy(packet)
    delattr(clone, '_index')
    doc = next(d for d in clone.data['documents'] if d['id']=='D66')
    doc['pages'][0]['printed_content'] = doc['pages'][0]['printed_content'].replace('2,900.00','3,100.00')
    changed = {x['id']:x for x in run_audit(clone)['findings']}
    assert changed['E3']['proposed'] == '3100.00'


def test_explicit_arithmetic_and_effect_units(packet):
    v = packet.data['return_versions'][-1]
    assert all(c['status']=='passed' for c in check_registry(v))
    altered = deepcopy(v)
    next(l for l in altered['lines'] if l['key']=='SchC.28')['value'] += 1
    results = {c['key']:c for c in check_registry(altered)}
    assert results['SchC.29']['status'] == 'failed'
    assert tax_effect(100,'payment',v['tax_effect_rates'])['balance_change'] == '-100'
    assert tax_effect(100,'credit',v['tax_effect_rates'])['tax_change'] == '-100'
    assert tax_effect(-12400,'schc_profit',v['tax_effect_rates'])['federal'] == '-4402'


def test_locator_spans_and_ambiguity(packet):
    results = packet_locators(packet)
    for e in packet.data['extracted_values']:
        loc = results[e['id']]
        if loc['resolved']:
            page = packet.resolve(f"doc:{e['document_id']}#page{e['page']}")
            assert page['printed_content'][loc['start']:loc['end']] == loc['quote']
    assert not locate({'field':'unknown','text_as_read':'100.00'}, 'A 100.00; B 100.00')['resolved']
    loc = locate({'field':'box4c','text_as_read':'6,000.00'}, 'Box 4c gross proceeds from sale 2,900.00.')
    assert loc['quote']=='2,900.00'  # locate printed field even if extraction differs


def test_sensitive_redaction_covers_strings_and_original_text(packet):
    tokens = sensitive_tokens(packet)
    serialized = json.dumps(redact(packet.data, tokens))
    for person in packet.data['household']['people']:
        assert person['ssn'] not in serialized
    bank = packet.data['household']['bank_account_for_refund_or_payment']
    assert bank['account'] not in serialized
    assert bank['routing'] not in serialized
    assert packet.data['household']['people'][0]['ip_pin'] not in serialized
    assert packet.data['extracted_values'][0]['value'] == '2026-01-12'  # redaction is non-mutating


def test_row_scoped_dates_repeated_numbers_and_trips():
    text='1099-B detail: X1 Alpha 2 sh acquired 2023-01-02 sold 2025-02-03 proceeds 100.00 basis 100.00 wash sale loss disallowed 0.00 short-term covered; X2 Beta 3 sh acquired 2024-01-02 sold 2025-02-03 proceeds 100.00 basis 90.00 wash sale loss disallowed 0.00 long-term covered.'
    acquired=locate({'field':'X2_acq','text_as_read':'01/02/2024'},text)
    assert acquired['quote']=='2024-01-02'
    basis=locate({'field':'X1_basis','text_as_read':'100.00'},text)
    assert basis['resolved'] and text[basis['start']-6:basis['start']]=='basis '
    trip=locate({'field':'trip2_destination','text_as_read':'Client'}, '2025-01-01 Client (meeting) 12 mi; 2025-01-02 Client (shoot) 22 mi.')
    assert trip['quote']=='Client' and trip['start']>30
