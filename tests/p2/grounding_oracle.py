"""構造への写像の可否の診断の別計算。基の行（臨床ライブラリ）の別計算を再利用し、有限小数の判定と表記は Decimal（モジュールの整数の掛け算とは別の道）、
桁数は文字列の長さ、期間の端は datetime の演算、流れの表は文書68の§1.2の手書きの表で持つ。nativeは読まない。"""
from datetime import datetime, timedelta
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction as F

import library_oracle as library

STRUCTURE = 'fhir-r5-observation'
MAX_DIGITS = 18
CARRIABLE = ('method', 'specimen')
NEVER = ['human_confirmed', 'origin_kind', 'quantity_kind', 'context:property', 'record:identity', 'review:identity', 'revision_history']
REASON_LOST = {'interval_not_representable_as_quantity': 'interval_width', 'open_boundary_not_representable': 'interval_bounds',
               'not_decimal_representable': 'exact_value', 'digits_exceed_limit': 'exact_value', 'period_end_convention_undeclared': 'validity_end'}


def decimal_text(value):
    """有限小数なら正確な表記、そうでなければ None。Decimal の除算が正確に終わるかで判定する。"""
    with localcontext() as context:
        context.prec = 400
        context.traps[Inexact] = True
        try:
            quotient = Decimal(value.numerator)/Decimal(value.denominator)
        except Inexact:
            return None
    return format(quotient, 'f')


def digit_count(text):
    return len(text.lstrip('-').replace('.', ''))


def fraction(encoded):
    return F(encoded['numerator'], encoded['denominator'])


def last_second(stamp):
    moment = datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ')-timedelta(seconds=1)
    return moment.isoformat()+'Z'


def cost(request):
    return 2+library.cost(request['library_request'])+3*len(request['library_request']['queries'])


def library_cost(request):
    return library.cost(request['library_request'])


def target_of(request, query):
    for target in request['targets']:
        if target['destination_ref'] == query['destination_ref']:
            return target
    return None


def row(request, query):
    """問い合わせ一行の期待。基の行は臨床ライブラリの別計算から取る。"""
    libreq = request['library_request']
    base = library.row(libreq, query)
    target = target_of(request, query)
    found = {'status': base['status'], 'reasons': list(base['reasons']), 'base_status': base['status'], 'selection': base['selection'], 'elements': base['elements'],
             'requests': base['requests'], 'output': base['output'], 'flows': base['flows'], 'state': None, 'grounding_reasons': [], 'projection': None,
             'structure': target['structure'] if target else None}
    if target is None:
        found['state'] = 'not_declared'
        return found
    if base['status'] != 'satisfied':
        found['state'] = 'not_evaluated'
        return found
    domain = base['output']['converted_domain']
    low, high = fraction(domain['lower']), fraction(domain['upper'])
    closed = domain['lower_closed'] and domain['upper_closed']
    reasons = set()
    if target['value'] == 'quantity' and not (low == high and closed):
        reasons.add('interval_not_representable_as_quantity')
    if target['value'] == 'range' and not closed:
        reasons.add('open_boundary_not_representable')
    texts = []
    for number in (low, high):
        text = decimal_text(number)
        if text is None:
            reasons.add('not_decimal_representable')
        else:
            texts.append(text)
            if digit_count(text) > MAX_DIGITS:
                reasons.add('digits_exceed_limit')
    period = None
    if 'period' in target:
        if target['period']['end_convention'] == 'undeclared':
            reasons.add('period_end_convention_undeclared')
        else:
            operation = next(op for op in libreq['library']['operations'] if op['id'] == base['selection']['record_ref'])
            period = {'start': operation['validity']['start'], 'end': last_second(operation['validity']['end'])}
    if reasons:
        found.update(status='not_representable', reasons=sorted(reasons), state='not_representable', grounding_reasons=sorted(reasons), output=None, requests=[],
                     flows={'retained': [], 'lost': sorted({REASON_LOST[r] for r in reasons}), 'added': []})
        return found
    record = next(op for op in libreq['library']['operations'] if op['id'] == base['selection']['record_ref'])
    listed = target['context_fields']
    state = {name: record[name] for name in CARRIABLE}
    kept = sorted(name for name in listed if state[name]['kind'] == 'known')
    absent = sorted(name for name in listed if state[name]['kind'] != 'known')
    unlisted = [name for name in CARRIABLE if name not in listed]
    value = {'decimal': texts[0]} if target['value'] == 'quantity' else {'low': texts[0], 'high': texts[1]}
    found.update(state='representable', requests=[],
                 projection={'value': value, 'unit_ref': base['output']['unit_ref'], 'period': period, 'absent': absent,
                             'context': {name: {'ref': state[name]['ref'], 'version': state[name]['version']} for name in kept}},
                 flows={'retained': sorted(['value:exact_domain', 'unit']+['context:'+name for name in kept]+(['validity'] if period else [])),
                        'lost': sorted(NEVER+([] if period else ['validity'])+['context:'+name for name in unlisted]+['context_state_distinction:'+name for name in absent]),
                        'added': ['assumption:end_convention:last_second', 'assumption:second_granularity'] if period else []})
    return found
