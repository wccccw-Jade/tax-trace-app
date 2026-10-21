"""Small explicit registry; signs come from declared formulas, never snapshot inference."""
from decimal import Decimal, ROUND_HALF_UP

D = lambda x: Decimal(str(x))
FORMULAS = {
    'F1040.1z': [('F1040.1a', 1)],
    'SchB.2': [(f'SchB.1.{i}', 1) for i in range(1, 9)],
    'SchB.4': [('SchB.2', 1)],
    'F1040.2b': [('SchB.4', 1)],
    'SchC.5': [('SchC.1', 1)], 'SchC.7': [('SchC.5', 1)],
    'SchC.28': [(f'SchC.{i}', 1) for i in ['8','9','11','13','15','17','18','22','24a','24b','25','27a.1','27a.2']],
    'SchC.29': [('SchC.7', 1), ('SchC.28', -1)],
    'SchC.31': [('SchC.29', 1), ('SchC.30', -1)],
    'SchA.12': [('F8283.A1.stock', 1), ('F8283.A1.vehicle', 1)],
    'SchA.14': [('SchA.11', 1), ('SchA.12', 1)],
}


def check_registry(version):
    lines = {l['key']: l for l in version['lines']}
    result = []
    for key, terms in FORMULAS.items():
        if key not in lines or any(k not in lines for k, _ in terms):
            result.append({'key': key, 'status': 'unavailable'})
            continue
        computed = sum((D(lines[k]['value']) * sign for k, sign in terms), D(0))
        expected = D(lines[key]['value'])
        result.append({'key': key, 'status': 'passed' if computed == expected else 'failed', 'expected': str(expected), 'computed': str(computed)})
    return result


def tax_effect(delta, category, rates):
    delta = D(delta)
    if category == 'payment':
        return {'tax_change': '0', 'balance_change': str(-delta), 'basis': 'exact'}
    if category == 'credit':
        return {'tax_change': str(-delta), 'balance_change': str(-delta), 'basis': 'exact'}
    return {jurisdiction: str((delta * D(rates[category][jurisdiction + '_per_dollar'])).quantize(D('1'), rounding=ROUND_HALF_UP))
            for jurisdiction in ('federal', 'california')} | {'basis': 'estimated'}
