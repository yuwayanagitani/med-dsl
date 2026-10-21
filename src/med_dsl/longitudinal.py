"""R5：期間つき数量計画を再実行し、同じ slot の二時点の換算領域を独立な変数として比べる。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .temporal_measurement import (TEMPORAL_MEASUREMENT_PROFILE, SPEC_SHA256 as TEMPORAL_MEASUREMENT_SPEC_SHA256,
                          QUANTITY_PROFILE, QUANTITY_SPEC_SHA256,
                          _validate as validate_temporal_measurements, _visible as visible_temporal_measurements, run_temporal_measurements)
from .model import Budget, Problem
from .quantity import run_quantities
from .validation import check_json, fields, indexed, string, strings

LONGITUDINAL_PROFILE = 'p2-longitudinal-comparison-draft-1'
SPEC_SHA256 = '8e84f9059091605aa9539f43736d860e7a93528863eff1d770fba2e740784575'
OPERATION = 'compare_longitudinal_measurements'
POLICY = 'fiction:independent-time-variables@1'
ANSWER_KIND = 'longitudinal_measurement_comparison'
VALUE_FIELDS = ('relation_set', 'certain_relation', 'context_differences', 'endpoints', 'comparison_evidence')
OWN_FEE, COMPARE_RESERVE = 6, 12
ROW_FEE = OWN_FEE + COMPARE_RESERVE
ASSUMPTIONS = ['independent_time_variables', 'explicit_period_quantity_domain', 'scoped_revision']
CONTEXT_REASONS = (('method', 'different_method'), ('property_ref', 'different_property'), ('specimen', 'different_specimen'))


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('longitudinal_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['temporal_measurement_profile'] != TEMPORAL_MEASUREMENT_PROFILE or spec['temporal_measurement_spec_sha256'] != TEMPORAL_MEASUREMENT_SPEC_SHA256:
        _unsupported('temporal_measurement_profile_mismatch', 'native_spec')
    if spec['quantity_profile'] != QUANTITY_PROFILE or spec['quantity_spec_sha256'] != QUANTITY_SPEC_SHA256:
        _unsupported('quantity_profile_mismatch', 'native_spec')
    return spec


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'temporal_measurement_plan', 'comparisons', 'budget'))
    _spec()
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    consumer = request['consumer']
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'temporal_measurement_profile', 'temporal_measurement_profile_spec_sha256',
                      'quantity_profile', 'quantity_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', LONGITUDINAL_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('temporal_measurement_profile', TEMPORAL_MEASUREMENT_PROFILE, 'temporal_measurement_profile_mismatch'),
                                ('temporal_measurement_profile_spec_sha256', TEMPORAL_MEASUREMENT_SPEC_SHA256, 'temporal_measurement_profile_mismatch'),
                                ('quantity_profile', QUANTITY_PROFILE, 'quantity_profile_mismatch'),
                                ('quantity_profile_spec_sha256', QUANTITY_SPEC_SHA256, 'quantity_profile_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > 100000:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    plan = request['temporal_measurement_plan']
    fields(plan, ('schema_version', 'operation', 'consumer', 'source', 'views', 'queries'), path='temporal_measurement_plan')
    if plan['schema_version'] != 'p2-temporal-measurement-request-draft-1':
        _unsupported('unsupported_temporal_measurement_schema', 'temporal_measurement_plan.schema_version')
    child = {**deepcopy(plan), 'budget': {'max_steps': 0}}
    check_json(child)
    _, _, slots, quantities, records, reviews, views, queries, _ = validate_temporal_measurements(child)
    comparisons = indexed(request['comparisons'], 'id', 64, 'comparisons')
    if not comparisons:
        raise Problem('empty_collection', 'comparisons')
    for comparison in comparisons.values():
        fields(comparison, ('id', 'view_ref', 'from_query_ref', 'to_query_ref', 'comparison_policy', 'required_capabilities'), path='comparison')
        for key, table in [('view_ref', views), ('from_query_ref', queries), ('to_query_ref', queries)]:
            string(comparison[key], 'comparison.' + key)
            if comparison[key] not in table:
                raise Problem('unresolved_' + key, 'comparison.' + key)
        string(comparison['comparison_policy'], 'comparison.comparison_policy')
        if comparison['comparison_policy'] != POLICY:
            _unsupported('unsupported_comparison_policy', 'comparison.comparison_policy')
        strings(comparison['required_capabilities'], 64, 'comparison.required_capabilities')
        if LONGITUDINAL_PROFILE not in comparison['required_capabilities']:
            raise Problem('missing_comparison_capability', 'comparison.required_capabilities')
        start, end = queries[comparison['from_query_ref']], queries[comparison['to_query_ref']]
        if start['slot_ref'] != end['slot_ref']:
            _unsupported('unsupported_cross_slot_comparison', 'comparison')
        # 時刻は UTC 秒精度の固定形式なので、辞書順が時刻の順になる。
        if not start['target_at'] < end['target_at']:
            raise Problem('invalid_comparison_order', 'comparison')
    return child, comparisons, quantities, records, queries, _plan_cost(slots, quantities, records, reviews, views, queries)


def _plan_cost(slots, quantities, records, reviews, views, queries):
    total = 1 + len(slots) + len(quantities)
    for view in views.values():
        total += len(records) + len(reviews)
        visible, _, eligible = visible_temporal_measurements(records, reviews, view['as_of'])
        for query in queries.values():
            scoped = {k: r for k, r in visible.items() if r['slot_ref'] == query['slot_ref']}
            total += 10 + len(scoped) + sum(len(scoped[k]['revises']) for k in eligible & set(scoped))
    return total


def _derived(ident, end, quantities, unit):
    """端点の換算領域を、別の ID を持つ P2-f のリテラルにする。元の量種・出自を保ち、目標単位で表す。"""
    domain = end['converted_domain']
    literal = quantities[end['binding_evidence']['selected'][0]['quantity_ref']['ref']]['literal']
    if domain['lower'] == domain['upper']:
        magnitude = {'kind': 'point', 'value': deepcopy(domain['lower'])}
    else:
        magnitude = {'kind': 'interval', 'lower': deepcopy(domain['lower']), 'upper': deepcopy(domain['upper']),
                     'lower_closed': domain['lower_closed'], 'upper_closed': domain['upper_closed']}
    return {'id': ident, 'quantity_kind_ref': literal['quantity_kind_ref'], 'unit_ref': unit, 'magnitude': magnitude,
            'uncertainty': {'kind': 'not_evaluated'}, 'origin': deepcopy(literal['origin']), 'required_capabilities': [QUANTITY_PROFILE]}


def _assess(comparison, rows, records, quantities, queries, child, child_hash, reserved):
    if set(comparison['required_capabilities']) - {LONGITUDINAL_PROFILE}:
        return {'status': 'unassessed', 'reason_codes': ['unknown_capability']}
    view = comparison['view_ref']
    ends = {'from': deepcopy(rows[(view, comparison['from_query_ref'])]), 'to': deepcopy(rows[(view, comparison['to_query_ref'])])}
    if any(end['status'] != 'computed' for end in ends.values()):
        return {'status': 'unassessed', 'reason_codes': sorted(set(ends['from']['reason_codes']) | set(ends['to']['reason_codes'])), 'endpoints': ends}
    chosen = {name: records[end['binding_evidence']['selected'][0]['record_ref']] for name, end in ends.items()}
    differences = [{'field': field, 'from': deepcopy(chosen['from'][field]), 'to': deepcopy(chosen['to'][field])}
                   for field, _ in CONTEXT_REASONS if chosen['from'][field] != chosen['to'][field]]
    if differences:
        reasons = sorted(reason for field, reason in CONTEXT_REASONS if chosen['from'][field] != chosen['to'][field])
        return {'status': 'not_comparable', 'reason_codes': reasons, 'context_differences': differences, 'endpoints': ends}
    units = {'from': queries[comparison['from_query_ref']]['target_unit_ref'], 'to': queries[comparison['to_query_ref']]['target_unit_ref']}
    request = {'schema_version': 'p2-quantity-request-draft-1', 'operation': 'evaluate_quantities',
               'consumer': {'profile': QUANTITY_PROFILE, 'profile_spec_sha256': QUANTITY_SPEC_SHA256, 'operations': ['evaluate_quantities']},
               'quantities': [_derived('endpoint:from', ends['from'], quantities, units['from']), _derived('endpoint:to', ends['to'], quantities, units['to'])],
               'queries': [{'id': 'relation', 'kind': 'compare', 'left_ref': 'endpoint:from', 'right_ref': 'endpoint:to'}],
               'budget': {'max_steps': COMPARE_RESERVE}}
    request_hash = check_json(request)
    out = run_quantities(request)
    if out['status'] == 'resource_limit':
        raise Problem(out['reason_codes'][0], 'quantity_child', 'resource_limit')
    value = out['results'][0]
    if value['status'] != 'computed':
        return {'status': 'unassessed', 'reason_codes': value['reason_codes'], 'endpoints': ends}
    if out['steps_used'] != COMPARE_RESERVE:
        raise Problem('quantity_compare_cost_mismatch', 'quantity_child')
    evidence = {'profile_spec_sha256': SPEC_SHA256, 'temporal_measurement_profile_spec_sha256': TEMPORAL_MEASUREMENT_SPEC_SHA256,
                'quantity_profile_spec_sha256': QUANTITY_SPEC_SHA256, 'temporal_measurement_input_sha256': child_hash,
                'temporal_measurement_reserved_steps': reserved, 'temporal_measurement_steps_used': child['steps_used'],
                'source_sha256': child['source_sha256'], 'view_ref': view, 'as_of': ends['from']['binding_evidence']['as_of'],
                'comparison_policy': POLICY, 'from_query_ref': comparison['from_query_ref'], 'to_query_ref': comparison['to_query_ref'],
                'from_at': ends['from']['binding_evidence']['target_at'], 'to_at': ends['to']['binding_evidence']['target_at'],
                'direction': 'from_relative_to_to', 'assumptions': list(ASSUMPTIONS),
                'quantity_compare': {'input_sha256': request_hash, 'profile': QUANTITY_PROFILE, 'reserved_steps': COMPARE_RESERVE,
                                     'steps_used': out['steps_used'], 'evidence': value['calculation_evidence']}}
    return {'status': 'computed', 'reason_codes': [], 'relation_set': list(value['relation_set']), 'certain_relation': value['certain_relation'],
            'context_differences': [], 'endpoints': ends, 'comparison_evidence': evidence}


def run_longitudinal(request):
    child_request, comparisons, quantities, records, queries, cost = _validate(request)
    rows = [{'id': c['id'], 'view_ref': c['view_ref'], 'from_query_ref': c['from_query_ref'], 'to_query_ref': c['to_query_ref'],
             'status': 'unassessed', 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)}
            for c in sorted(comparisons.values(), key=lambda c: c['id'])]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [], 'source_sha256': None,
              'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only', 'uncertainty_propagated': False, 'converted_to_base': False,
              'clinical_assertions_added': [], 'time_correlation_assumed': False, 'clinical_significance': 'not_evaluated',
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change',
                              'reason_codes': ['independent_time_variables', 'no_clinical_significance_claim'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'temporal_measurement', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        child_request['budget']['max_steps'] = cost
        child_hash = check_json(child_request)
        child = run_temporal_measurements(child_request)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'temporal_measurement', child['status'])
        if child['steps_used'] != cost:
            raise Problem('temporal_measurement_cost_mismatch', 'temporal_measurement')
        result['source_sha256'] = child['source_sha256']
        endpoints = {(r['view'], r['query']): r for r in child['results']}
        stage = 'comparisons'
        for row in rows:
            current = row
            for _ in range(ROW_FEE):
                budget.tick()
            row.update(_assess(comparisons[row['id']], endpoints, records, quantities, queries, child, child_hash, cost), assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'temporal_measurement' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'comparison': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
