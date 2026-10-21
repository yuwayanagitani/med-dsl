"""R4：型付きの丸め表示へ因子化する問いと、別添えからの回答を分離する。"""
import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .measurement import (MEASUREMENT_PROFILE, SPEC_SHA256 as MEASUREMENT_SPEC_SHA256,
                          QUANTITY_PROFILE, QUANTITY_SPEC_SHA256,
                          _validate as validate_measurements, _visible as visible_measurements, run_measurements)
from .model import Budget, Problem
from .quantity import _rational as rational_input, _bounded as bounded, _encode as encode_rational
from .validation import canonical_bytes, check_json, digest, fields, indexed, string, strings

DISPLAY_PROFILE = 'p2-quantity-display-draft-1'
SPEC_SHA256 = '361563166d4465ccf465b77e5f9421cac1c4181f2b8df3ce8065ce761f883a12'
OPERATION = 'project_measurement_displays'
POLICY = 'fiction:decimal-half-even@1'
ANSWER_KIND = 'measurement_display_projection'
VALUE_FIELDS = ('artifact', 'artifact_sha256', 'rounding_cell', 'question_results', 'projection_evidence', 'source_evidence')


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('display_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['measurement_profile'] != MEASUREMENT_PROFILE or spec['measurement_spec_sha256'] != MEASUREMENT_SPEC_SHA256:
        _unsupported('measurement_profile_mismatch', 'native_spec')
    if spec['quantity_profile'] != QUANTITY_PROFILE or spec['quantity_spec_sha256'] != QUANTITY_SPEC_SHA256:
        _unsupported('quantity_profile_mismatch', 'native_spec')
    return spec


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'measurement_plan', 'displays', 'retention', 'budget'))
    _spec()
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    consumer = request['consumer']
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'measurement_profile', 'measurement_profile_spec_sha256',
                      'quantity_profile', 'quantity_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', DISPLAY_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('measurement_profile', MEASUREMENT_PROFILE, 'measurement_profile_mismatch'),
                                ('measurement_profile_spec_sha256', MEASUREMENT_SPEC_SHA256, 'measurement_profile_mismatch'),
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
    string(request['retention'], 'retention')
    if request['retention'] not in ('none', 'source_bundle'):
        _unsupported('unsupported_retention', 'retention')
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > 100000:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    plan = request['measurement_plan']
    fields(plan, ('schema_version', 'operation', 'consumer', 'source', 'views', 'queries'), path='measurement_plan')
    if plan['schema_version'] != 'p2-measurement-request-draft-1':
        _unsupported('unsupported_measurement_schema', 'measurement_plan.schema_version')
    child = {**deepcopy(plan), 'budget': {'max_steps': 0}}
    check_json(child)
    prepared = validate_measurements(child)
    _, _, slots, quantities, records, reviews, views, queries, _ = prepared
    if any(q['kind'] != 'convert' for q in queries.values()):
        _unsupported('unsupported_measurement_query', 'measurement_plan.queries')
    displays = indexed(request['displays'], 'id', 64, 'displays')
    if not displays:
        raise Problem('empty_collection', 'displays')
    for display in displays.values():
        fields(display, ('id', 'view_ref', 'query_ref', 'decimal_places', 'rounding_policy', 'required_capabilities', 'questions'), path='display')
        for key, table in [('view_ref', views), ('query_ref', queries)]:
            string(display[key], 'display.' + key)
            if display[key] not in table:
                raise Problem('unresolved_' + key, 'display.' + key)
        places = display['decimal_places']
        if type(places) is not int or places < 0:
            raise Problem('invalid_decimal_places', 'display.decimal_places')
        if places > 6:
            _unsupported('unsupported_decimal_places', 'display.decimal_places')
        string(display['rounding_policy'], 'display.rounding_policy')
        if display['rounding_policy'] != POLICY:
            _unsupported('unsupported_rounding_policy', 'display.rounding_policy')
        strings(display['required_capabilities'], 64, 'display.required_capabilities')
        if DISPLAY_PROFILE not in display['required_capabilities']:
            raise Problem('missing_display_capability', 'display.required_capabilities')
        questions = indexed(display['questions'], 'id', 16, 'questions')
        if not questions:
            raise Problem('empty_collection', 'questions')
        for question in questions.values():
            if 'kind' not in question:
                raise Problem('missing_field', 'question.kind')
            string(question['kind'], 'question.kind')
            if question['kind'] in ('display_text', 'exact_value'):
                fields(question, ('id', 'kind'), path='question')
            elif question['kind'] == 'threshold':
                fields(question, ('id', 'kind', 'operator', 'threshold'), path='question')
                string(question['operator'], 'question.operator')
                if question['operator'] not in ('lt', 'le', 'eq', 'ge', 'gt'):
                    _unsupported('unsupported_question_operator', 'question.operator')
                rational_input(question['threshold'], 'question.threshold')
            else:
                _unsupported('unsupported_question_kind', 'question.kind')
    return child, displays, quantities, queries, _plan_cost(slots, quantities, records, reviews, views, queries)


def _plan_cost(slots, quantities, records, reviews, views, queries):
    total = 1 + len(slots) + len(quantities)
    for view in views.values():
        total += len(records) + len(reviews)
        visible, _, eligible = visible_measurements(records, reviews, view['as_of'])
        for query in queries.values():
            scoped = {k: r for k, r in visible.items() if r['slot_ref'] == query['slot_ref']}
            total += 10 + len(scoped) + sum(len(scoped[k]['supersedes']) for k in eligible & set(scoped))
    return total


def _rounded(point, places):
    scale = 10**places
    scaled = bounded(point * scale)
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    coefficient = quotient + int(twice > scaled.denominator or (twice == scaled.denominator and quotient % 2 != 0))
    bounded(Fraction(coefficient))
    digits = str(abs(coefficient)).zfill(places + 1)
    text = digits if places == 0 else digits[:-places] + '.' + digits[-places:]
    if coefficient < 0:
        text = '-' + text
    if len(text) > 64:
        raise Problem('display_text_limit', status='resource_limit')
    lower, upper = bounded(Fraction(2 * coefficient - 1, 2 * scale)), bounded(Fraction(2 * coefficient + 1, 2 * scale))
    closed = coefficient % 2 == 0
    return coefficient, text, lower, upper, closed


def _constant(operator, threshold, lower, upper, closed):
    inside = (threshold > lower or (closed and threshold == lower)) and (threshold < upper or (closed and threshold == upper))
    yes = {'lt': upper < threshold or (upper == threshold and not closed), 'le': upper <= threshold,
           'eq': False, 'ge': lower >= threshold, 'gt': lower > threshold or (lower == threshold and not closed)}[operator]
    no = {'lt': lower >= threshold, 'le': lower > threshold or (lower == threshold and not closed),
          'eq': not inside, 'ge': upper < threshold or (upper == threshold and not closed), 'gt': upper <= threshold}[operator]
    return True if yes else False if no else None


def _compare(operator, point, threshold):
    return {'lt': point < threshold, 'le': point <= threshold, 'eq': point == threshold, 'ge': point >= threshold, 'gt': point > threshold}[operator]


def _assess(display, row, child, child_hash, reserved, quantities, queries, retention):
    reasons = ['unknown_capability'] if set(display['required_capabilities']) - {DISPLAY_PROFILE} else row['reason_codes']
    status = 'unassessed' if reasons == ['unknown_capability'] else row['status']
    domain = row['converted_domain']
    if status == 'computed' and not reasons and (domain['lower'] != domain['upper'] or not domain['lower_closed'] or not domain['upper_closed']):
        reasons, status = ['unsupported_display_domain'], 'unassessed'
    if reasons or status != 'computed':
        questions = [{'id': q['id'], 'status': 'unassessed', 'projection_answer': None, 'source_answer': None, 'reason_codes': list(reasons)}
                     for q in sorted(display['questions'], key=lambda q: q['id'])]
        return {'status': status, 'reason_codes': list(reasons), 'question_results': questions}
    point = Fraction(domain['lower']['numerator'], domain['lower']['denominator'])
    k, text, lower, upper, closed = _rounded(point, display['decimal_places'])
    binding = row['binding_evidence']
    selected = binding['selected'][0]
    kind = quantities[selected['quantity_ref']['ref']]['literal']['quantity_kind_ref']
    artifact = {'schema_version': 'p2-display-artifact-draft-1', 'profile': DISPLAY_PROFILE, 'profile_spec_sha256': SPEC_SHA256,
                'quantity_profile': QUANTITY_PROFILE, 'quantity_profile_spec_sha256': QUANTITY_SPEC_SHA256,
                'quantity_kind_ref': kind, 'unit_ref': queries[display['query_ref']]['target_unit_ref'],
                'rounding_policy': POLICY, 'decimal_places': display['decimal_places'], 'coefficient': k, 'text': text}
    raw = canonical_bytes(artifact)
    if json.loads(raw) != artifact:
        raise Problem('encoding_roundtrip_failed')
    answers = []
    for question in sorted(display['questions'], key=lambda q: q['id']):
        source = None
        if question['kind'] == 'display_text':
            answer = text
        elif question['kind'] == 'exact_value':
            answer = None
            if retention == 'source_bundle':
                source = {'mode': 'source_replay', 'answer': encode_rational(point)}
        else:
            threshold = rational_input(question['threshold'], 'question.threshold')
            # 256bit制限も固定表の上限とは別に検査する。
            for endpoint in (lower, upper):
                bounded(Fraction(endpoint.numerator * threshold.denominator))
                bounded(Fraction(threshold.numerator * endpoint.denominator))
            answer = _constant(question['operator'], threshold, lower, upper, closed)
            if retention == 'source_bundle':
                source = {'mode': 'source_replay', 'answer': _compare(question['operator'], point, threshold)}
        answers.append({'id': question['id'], 'status': 'preserved' if answer is not None else 'out_of_scope',
                        'projection_answer': answer, 'source_answer': source, 'reason_codes': [] if answer is not None else ['query_out_of_scope']})
    evidence = {'profile_spec_sha256': SPEC_SHA256, 'measurement_profile_spec_sha256': MEASUREMENT_SPEC_SHA256,
                'quantity_profile_spec_sha256': QUANTITY_SPEC_SHA256, 'measurement_input_sha256': child_hash,
                'measurement_reserved_steps': reserved, 'measurement_steps_used': child['steps_used'],
                'source_sha256': child['source_sha256'], 'view_ref': display['view_ref'], 'query_ref': display['query_ref'],
                'selected': deepcopy(binding['selected']), 'measurement_certificate': deepcopy(child['certificate']),
                'artifact_encoding': {'kind': 'canonical_json', 'bytes_base64': base64.b64encode(raw).decode('ascii'),
                                      'sha256': digest(artifact), 'roundtrip_matches': True}}
    source_evidence = None if retention == 'none' else {'mode': 'additional_source', 'measurement_input_sha256': child_hash,
        'measurement_row': deepcopy(row), 'measurement_certificate': deepcopy(child['certificate'])}
    return {'status': 'computed', 'reason_codes': [], 'artifact': artifact, 'artifact_sha256': digest(artifact),
            'rounding_cell': {'lower': encode_rational(lower), 'upper': encode_rational(upper), 'lower_closed': closed, 'upper_closed': closed},
            'question_results': answers, 'projection_evidence': evidence, 'source_evidence': source_evidence}


def run_displays(request):
    child_request, displays, quantities, queries, cost = _validate(request)
    rows = [{'id': d['id'], 'view_ref': d['view_ref'], 'query_ref': d['query_ref'], 'status': 'unassessed',
             'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)}
            for d in sorted(displays.values(), key=lambda d: d['id'])]
    plan = deepcopy(request)
    del plan['budget']
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [],
              'source_bundle': {'request_plan': plan} if request['retention'] == 'source_bundle' else None,
              'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only', 'uncertainty_propagated': False, 'converted_to_base': False,
              'clinical_assertions_added': [], 'additional_source_used': False,
              'certificate': {'status': 'not_certified', 'evidence_level': 'lossy_template', 'scope': None, 'reason_codes': []}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'measurement', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        child_request['budget']['max_steps'] = cost
        child_hash = check_json(child_request)
        child = run_measurements(child_request)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'measurement', child['status'])
        if child['steps_used'] != cost:
            raise Problem('measurement_cost_mismatch', 'measurement')
        children = {(r['view'], r['query']): r for r in child['results']}
        stage = 'displays'
        for row in rows:
            current = row
            display = displays[row['id']]
            for _ in range(8 + 2 * len(display['questions'])):
                budget.tick()
            value = _assess(display, children[(display['view_ref'], display['query_ref'])], child, child_hash, cost, quantities, queries, request['retention'])
            row.update(value, assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
        reasons = sorted({code for r in rows for code in r['reason_codes']} |
                         {code for r in rows for q in r['question_results'] for code in q['reason_codes']})
        complete = all(r['status'] == 'computed' and all(q['status'] == 'preserved' for q in r['question_results']) for r in rows)
        result['certificate'].update(status='certified' if complete else 'not_certified',
            evidence_level='checked_native_template' if complete else 'lossy_template', reason_codes=reasons,
            scope={'kind': 'display_questions_only', 'questions': [{'display': r['id'], 'question': q['id'], 'artifact_sha256': r['artifact_sha256']}
                   for r in rows for q in r['question_results']],
                   'excludes': ['source_exact_value', 'source_record_identity', 'source_context', 'source_history', 'clinical_truth', 'measurement_uncertainty']} if complete else None)
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'measurement' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['additional_source_used'] = any(q['source_answer'] is not None for r in rows for q in (r['question_results'] or []))
    result['incomplete'] = [{'display': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
