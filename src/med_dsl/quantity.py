"""架空の閉じた単位表による量リテラルのR2計算。臨床状態を読み書きしない。"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .validation import fields, indexed, string, strings

QUANTITY_PROFILE = 'p2-quantity-literal-draft-1'
SPEC_SHA256 = '84af2e771d1868471d0a8441021fde2a7253b1fc17f8ff9b807461e3df7f1f43'
OPERATION = 'evaluate_quantities'
ANSWER_KIND = 'quantity_literal_result'


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('quantity_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    return json.loads(raw)


def _rational(value, path):
    fields(value, ('numerator', 'denominator'), path=path)
    n, d = value['numerator'], value['denominator']
    if type(n) is not int or type(d) is not int or d <= 0:
        raise Problem('invalid_rational', path)
    if abs(n).bit_length() > 63 or d.bit_length() > 63:
        raise Problem('rational_integer_limit', path, 'resource_limit')
    return Fraction(n, d)


def _domain(value, path):
    if type(value) is not dict or 'kind' not in value:
        fields(value, ('kind',), path=path)
    string(value['kind'], path + '.kind')
    if value['kind'] == 'point':
        fields(value, ('kind', 'value'), path=path)
        point = _rational(value['value'], path + '.value')
        return point, point, True, True
    if value['kind'] != 'interval':
        _unsupported('unsupported_magnitude', path)
    fields(value, ('kind', 'lower', 'upper', 'lower_closed', 'upper_closed'), path=path)
    lower = _rational(value['lower'], path + '.lower')
    upper = _rational(value['upper'], path + '.upper')
    lc, uc = value['lower_closed'], value['upper_closed']
    if type(lc) is not bool or type(uc) is not bool or lower > upper or (lower == upper and not (lc and uc)):
        raise Problem('invalid_interval', path)
    return lower, upper, lc, uc


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'quantities', 'queries', 'budget'))
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    spec = _spec()
    consumer = request['consumer']
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations'), path='consumer')
    if consumer['profile'] != QUANTITY_PROFILE:
        _unsupported('unsupported_profile', 'consumer.profile')
    pin = consumer['profile_spec_sha256']
    if type(pin) is not str or len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
        raise Problem('invalid_sha256', 'consumer.profile_spec_sha256')
    if pin != SPEC_SHA256:
        _unsupported('profile_spec_mismatch', 'consumer.profile_spec_sha256')
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > 100000:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    quantities = indexed(request['quantities'], 'id', 64, 'quantities')
    queries = indexed(request['queries'], 'id', 64, 'queries')
    if not quantities or not queries:
        raise Problem('empty_collection', 'quantities/queries')
    domains = {}
    for ident in sorted(quantities):
        item = quantities[ident]
        fields(item, ('id', 'quantity_kind_ref', 'unit_ref', 'magnitude', 'uncertainty', 'origin', 'required_capabilities'), path='quantity')
        string(item['quantity_kind_ref'], 'quantity.quantity_kind_ref')
        string(item['unit_ref'], 'quantity.unit_ref')
        domains[ident] = _domain(item['magnitude'], 'quantity.magnitude')
        uncertainty = item['uncertainty']
        if type(uncertainty) is not dict or 'kind' not in uncertainty:
            fields(uncertainty, ('kind',), path='quantity.uncertainty')
        string(uncertainty['kind'], 'quantity.uncertainty.kind')
        if uncertainty['kind'] != 'not_evaluated':
            _unsupported('unsupported_uncertainty', 'quantity.uncertainty')
        fields(uncertainty, ('kind',), path='quantity.uncertainty')
        fields(item['origin'], ('kind', 'ref'), path='quantity.origin')
        if item['origin']['kind'] not in ('literal', 'imported_literal', 'ai_candidate'):
            raise Problem('invalid_origin', 'quantity.origin.kind')
        string(item['origin']['ref'], 'quantity.origin.ref')
        strings(item['required_capabilities'], 64, 'quantity.required_capabilities')
        if QUANTITY_PROFILE not in item['required_capabilities']:
            raise Problem('missing_quantity_capability', 'quantity.required_capabilities')
        kind, unit = item['quantity_kind_ref'], item['unit_ref']
        if kind in spec['quantity_kinds'] and unit in spec['units']:
            if spec['quantity_kinds'][kind] != spec['units'][unit]['dimension']:
                raise Problem('input_dimension_mismatch', 'quantity.unit_ref')
    for ident in sorted(queries):
        query = queries[ident]
        if 'kind' not in query:
            raise Problem('missing_field', 'query.kind')
        string(query['kind'], 'query.kind')
        if query['kind'] == 'convert':
            fields(query, ('id', 'kind', 'quantity_ref', 'target_unit_ref'), path='query')
            refs = [query['quantity_ref']]
            string(query['target_unit_ref'], 'query.target_unit_ref')
        elif query['kind'] == 'compare':
            fields(query, ('id', 'kind', 'left_ref', 'right_ref'), path='query')
            refs = [query['left_ref'], query['right_ref']]
        else:
            _unsupported('unsupported_query_kind', 'query.kind')
        for ref in refs:
            string(ref, 'query.quantity_ref')
            if ref not in quantities:
                raise Problem('unresolved_quantity', 'query.quantity_ref')
    return spec, quantities, queries, domains


def _bounded(value):
    if abs(value.numerator).bit_length() > 256 or value.denominator.bit_length() > 256:
        raise Problem('rational_intermediate_limit', status='resource_limit')
    return value


def _encode(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def _scaled(domain, factor):
    return _bounded(domain[0] * factor), _bounded(domain[1] * factor), domain[2], domain[3]


def _relations(left, right, alias):
    if alias:
        return ['equal']
    lo, hi = max(left[0], right[0]), min(left[1], right[1])
    equal = lo < hi or (lo == hi and all(
        (lo > d[0] or d[2]) and (lo < d[1] or d[3]) for d in (left, right)))
    return [name for name, holds in [('less', left[0] < right[1]), ('equal', equal), ('greater', left[1] > right[0])] if holds]


def _calculate(query, quantities, domains, spec):
    refs = ([query['quantity_ref']] if query['kind'] == 'convert' else [query['left_ref'], query['right_ref']])
    operands = [quantities[ref] for ref in refs]
    missing = sorted({cap for q in operands for cap in q['required_capabilities'] if cap != QUANTITY_PROFILE})
    if missing:
        return {'status': 'unassessed', 'reason_codes': ['unknown_capability'], 'missing_capabilities': missing}
    reasons = set()
    for q in operands:
        if q['quantity_kind_ref'] not in spec['quantity_kinds']:
            reasons.add('unknown_quantity_kind')
        if q['unit_ref'] not in spec['units']:
            reasons.add('unknown_unit')
    if query['kind'] == 'convert' and query['target_unit_ref'] not in spec['units']:
        reasons.add('unknown_unit')
    if reasons:
        return {'status': 'unassessed', 'reason_codes': sorted(reasons)}
    units = [spec['units'][q['unit_ref']] for q in operands]
    other_dim = spec['units'][query['target_unit_ref']]['dimension'] if query['kind'] == 'convert' else units[1]['dimension']
    if units[0]['dimension'] != other_dim:
        return {'status': 'not_comparable', 'reason_codes': ['incompatible_dimension']}
    if query['kind'] == 'compare' and operands[0]['quantity_kind_ref'] != operands[1]['quantity_kind_ref']:
        return {'status': 'not_comparable', 'reason_codes': ['incompatible_quantity_kind']}
    scales = [Fraction(u['scale']['numerator'], u['scale']['denominator']) for u in units]
    canonical = [_scaled(domains[ref], scale) for ref, scale in zip(refs, scales)]
    evidence = {'profile': QUANTITY_PROFILE, 'profile_spec_sha256': SPEC_SHA256,
                'operands': [{'quantity_ref': ref, 'quantity_kind_ref': q['quantity_kind_ref'], 'unit_ref': q['unit_ref'],
                              'origin': deepcopy(q['origin']), 'scale_to_canonical': _encode(scale)}
                             for ref, q, scale in zip(refs, operands, scales)]}
    value = {'status': 'computed', 'reason_codes': [], 'calculation_evidence': evidence}
    if query['kind'] == 'convert':
        target = spec['units'][query['target_unit_ref']]['scale']
        target_scale = Fraction(target['numerator'], target['denominator'])
        converted = _scaled(canonical[0], 1 / target_scale)
        value['converted_domain'] = {'lower': _encode(converted[0]), 'upper': _encode(converted[1]),
                                     'lower_closed': converted[2], 'upper_closed': converted[3]}
        evidence.update(target_unit_ref=query['target_unit_ref'], conversion_factor=_encode(scales[0]/target_scale))
    else:
        relations = _relations(canonical[0], canonical[1], refs[0] == refs[1])
        value.update(relation_set=relations, certain_relation=relations[0] if len(relations) == 1 else None)
        evidence['shared_reference'] = refs[0] == refs[1]
    return value


def run_quantities(request):
    spec, quantities, queries, domains = _validate(request)
    budget = Budget(request['budget']['max_steps'])
    rows = [{'query': ident, 'kind': queries[ident]['kind'], 'status': 'unassessed', 'converted_domain': None,
             'relation_set': None, 'certain_relation': None, 'calculation_evidence': None, 'reason_codes': ['step_limit']}
            for ident in sorted(queries)]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'converted_to_base': False, 'clinical_assertions_added': [],
              'clinical_confirmation': 'not_evaluated', 'uncertainty_propagated': False,
              'certificate': {'status': 'not_certified', 'evidence_level': 'literal_calculation',
                              'reason_codes': ['no_clinical_or_base_equivalence_claim'], 'scope': None},
              'retained_quantities': [deepcopy(quantities[key]) for key in sorted(quantities)],
              'results': rows, 'reason_codes': []}
    current = None
    try:
        budget.tick()
        for _ in quantities:
            budget.tick()
        for row in rows:
            current = row
            query = queries[row['query']]
            for _ in range(6 if query['kind'] == 'convert' else 9):
                budget.tick()
            value = _calculate(query, quantities, domains, spec)
            row.update(value)
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        if current is not None:
            current['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'query': row['query'], 'reason_codes': row['reason_codes']}
                            for row in rows if row['status'] == 'unassessed']
    return result
