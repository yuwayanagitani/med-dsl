"""R5：P2-o の臨床ライブラリを一度だけ実行し、満たされた exchange の行が、出力先の構造（FHIR R5 Observation）で、丸めず・閉じず・補わずに表せるかを診断する。"""
from copy import deepcopy
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .clinical_library import (LIBRARY_PROFILE, SPEC_SHA256 as LIBRARY_SPEC_SHA256, _fee as library_fee, _validate as validate_library, run_library)
from .model import Budget, Problem
from .validation import check_json, fields, string, strings, values

GROUNDING_PROFILE = 'p2-structure-grounding-draft-1'
SPEC_SHA256 = '34f88aa6a41e29e605394d129ddc5d84adeee33f931e2d749c3bd834f5647695'
OPERATION = 'run_structure_grounding'
ANSWER_KIND = 'structure_grounding_projection'
LIBRARY_REQUEST_SCHEMA = 'p2-library-request-draft-1'
VALUE_FIELDS = ('selection', 'elements', 'requests', 'output', 'flows', 'grounding', 'base_status')
OWN_FEE = 3


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('structure_grounding_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['library_profile'] != LIBRARY_PROFILE or spec['library_spec_sha256'] != LIBRARY_SPEC_SHA256:
        _unsupported('library_profile_mismatch', 'native_spec')
    return spec


def _consumer(consumer):
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'library_profile', 'library_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', GROUNDING_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('library_profile', LIBRARY_PROFILE, 'library_profile_mismatch'),
                                ('library_profile_spec_sha256', LIBRARY_SPEC_SHA256, 'library_profile_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')


def _targets(raw, destinations, spec):
    items = values(raw, spec['limits']['targets'], 'targets')
    if not items:
        raise Problem('empty_collection', 'targets')
    found = {}
    for target in items:
        fields(target, ('destination_ref', 'structure', 'value', 'context_fields'), ('period',), 'target')
        reference = target['destination_ref']
        fields(reference, ('id', 'version'), path='target.destination_ref')
        string(reference['id'], 'target.destination_ref.id')
        string(reference['version'], 'target.destination_ref.version')
        string(target['structure'], 'target.structure')
        structure = spec['structures'].get(target['structure'])
        if structure is None:
            _unsupported('unsupported_structure', 'target.structure')
        string(target['value'], 'target.value')
        if target['value'] not in structure['values']:
            _unsupported('unsupported_target_value', 'target.value')
        strings(target['context_fields'], 8, 'target.context_fields')
        if any(field not in structure['context_fields'] for field in target['context_fields']):
            _unsupported('unsupported_context_field', 'target.context_fields')
        if 'period' in target:
            fields(target['period'], ('end_convention',), path='target.period')
            string(target['period']['end_convention'], 'target.period.end_convention')
            if target['period']['end_convention'] not in spec['end_conventions']:
                _unsupported('unsupported_end_convention', 'target.period.end_convention')
        key = (reference['id'], reference['version'])
        profile = destinations.get(key)
        if profile is None:
            raise Problem('unresolved_destination', 'target.destination_ref')
        if key in found:
            raise Problem('duplicate_target', 'targets')
        if profile['output']['kind'] != 'exchange':
            _unsupported('unsupported_grounding_output_kind', 'target.destination_ref')
        found[key] = target
    return found


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'library_request', 'targets', 'budget'))
    spec = _spec()
    if request['operation'] != OPERATION:
        _unsupported('unsupported_operation', 'operation')
    _consumer(request['consumer'])
    fields(request['budget'], ('max_steps',), path='budget')
    maximum = request['budget']['max_steps']
    if type(maximum) is not int or maximum < 0:
        raise Problem('invalid_step_budget', 'budget.max_steps')
    if maximum > spec['limits']['max_steps']:
        raise Problem('step_budget_limit', 'budget.max_steps', 'resource_limit')
    child = request['library_request']
    if type(child) is not dict:
        raise Problem('expected_object', 'library_request')
    if child.get('schema_version') != LIBRARY_REQUEST_SCHEMA:
        _unsupported('library_schema_mismatch', 'library_request.schema_version')
    prepared = validate_library(child)
    if child['budget']['max_steps'] != 0:
        raise Problem('invalid_child_budget', 'library_request.budget.max_steps')
    queries = sorted(prepared['queries'].values(), key=lambda q: q['id'])
    prepared['library_cost'] = 2 + prepared['cost'] + sum(
        library_fee(prepared['destinations'][(q['destination_ref']['id'], q['destination_ref']['version'])]) for q in queries)
    prepared['grounding_spec'] = spec
    prepared['targets'] = _targets(request['targets'], prepared['destinations'], spec)
    prepared['child'] = deepcopy(child)
    return prepared


def _fraction(encoded):
    return Fraction(encoded['numerator'], encoded['denominator'])


def _terminating(denominator):
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    return denominator == 1


def _decimal(value):
    """有限小数の正確な表記。分母の素因数が 2 と 5 だけのときだけ呼ぶ。"""
    places, scaled = 0, value
    while scaled.denominator != 1:
        if places > 256:                                    # 入力の上限（256bit）の内側では届かない。判定の誤りで無限に回さないための境界
            raise Problem('decimal_expansion_limit', status='resource_limit')
        scaled *= 10
        places += 1
    digits = str(abs(scaled.numerator)).zfill(places + 1)
    text = digits if places == 0 else digits[:-places] + '.' + digits[-places:]
    return ('-' if value < 0 else '') + text


def _digits(text):
    return sum(character.isdigit() for character in text)


def _last_second(end):
    moment = datetime.strptime(end, '%Y-%m-%dT%H:%M:%SZ') - timedelta(seconds=1)
    return f'{moment.year:04d}-{moment.month:02d}-{moment.day:02d}T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}Z'


def _passed(row, state, target):
    return {'status': row['status'], 'reason_codes': deepcopy(row['reason_codes']), 'base_status': row['status'], 'selection': deepcopy(row['selection']),
            'elements': deepcopy(row['elements']), 'requests': deepcopy(row['requests']), 'output': deepcopy(row['output']), 'flows': deepcopy(row['flows']),
            'grounding': {'structure': target['structure'] if target else None, 'state': state, 'reasons': [], 'projection': None}}


def _ground(row, target, spec):
    structure = spec['structures'][target['structure']]
    output, domain = row['output'], row['output']['converted_domain']
    lower, upper = _fraction(domain['lower']), _fraction(domain['upper'])
    closed = domain['lower_closed'] and domain['upper_closed']
    reasons, text = set(), {}
    if target['value'] == 'quantity':
        if not (lower == upper and closed):
            reasons.add('interval_not_representable_as_quantity')
    elif not closed:
        reasons.add('open_boundary_not_representable')
    for end, number in (('lower', lower), ('upper', upper)):
        if not _terminating(number.denominator):
            reasons.add('not_decimal_representable')
        else:
            text[end] = _decimal(number)
            if _digits(text[end]) > structure['decimal']['max_digits']:
                reasons.add('digits_exceed_limit')
    period, carried = target.get('period'), None
    if period is not None:
        if period['end_convention'] == 'undeclared':
            reasons.add('period_end_convention_undeclared')
        else:
            validity = row['selection']['validity']
            carried = {'start': validity['start'], 'end': _last_second(validity['end'])}
    if reasons:
        reasons = sorted(reasons)
        lost = sorted({item for reason in reasons for item in spec['reasons'][reason]})
        return {'status': 'not_representable', 'reason_codes': reasons, 'base_status': 'satisfied', 'selection': deepcopy(row['selection']),
                'elements': deepcopy(row['elements']), 'requests': [], 'output': None, 'flows': {'retained': [], 'lost': lost, 'added': []},
                'grounding': {'structure': target['structure'], 'state': 'not_representable', 'reasons': reasons, 'projection': None}}
    context, absent, known = output['context'], [], {}
    for field in sorted(target['context_fields']):
        state = context[field]
        if state['kind'] == 'known':
            known[field] = {'ref': state['ref'], 'version': state['version']}
        else:
            absent.append(field)
    unlisted = [field for field in structure['context_fields'] if field not in target['context_fields']]
    flows = {'retained': sorted(['value:exact_domain', 'unit'] + ['context:' + field for field in known] + (['validity'] if carried else [])),
             'lost': sorted(structure['not_carried'] + ([] if carried else ['validity']) + ['context:' + field for field in unlisted]
                            + ['context_state_distinction:' + field for field in absent]),
             'added': sorted(spec['assumptions'][period['end_convention']]) if carried else []}
    value = {'decimal': text['lower']} if target['value'] == 'quantity' else {'low': text['lower'], 'high': text['upper']}
    projection = {'value': value, 'unit_ref': output['unit_ref'], 'period': carried, 'absent': absent, 'context': known}
    return {'status': 'satisfied', 'reason_codes': [], 'base_status': 'satisfied', 'selection': deepcopy(row['selection']), 'elements': deepcopy(row['elements']),
            'requests': [], 'output': deepcopy(output), 'flows': flows,
            'grounding': {'structure': target['structure'], 'state': 'representable', 'reasons': [], 'projection': projection}}


def _row(row, target, spec):
    if target is None:
        return _passed(row, 'not_declared', None)
    if row['status'] != 'satisfied':
        return _passed(row, 'not_evaluated', target)
    return _ground(row, target, spec)


def run_grounding(request):
    prepared = _validate(request)
    spec, cost = prepared['grounding_spec'], prepared['library_cost']
    queries = sorted(prepared['queries'].values(), key=lambda q: q['id'])
    rows = [{'id': q['id'], 'view_ref': q['view_ref'], 'slot_ref': q['slot_ref'], 'destination_ref': deepcopy(q['destination_ref']),
             'status': 'unassessed', 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)} for q in queries]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [], 'ledger': deepcopy(prepared['plan']['source']), 'library': None,
              'temporal_measurement': None, 'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only', 'uncertainty_propagated': False,
              'converted_to_base': False, 'clinical_assertions_added': [], 'inferred_information': [],
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'reason_codes': ['structure_mapping_is_diagnostic'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'library', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        child_request = prepared['child']
        child_request['budget']['max_steps'] = cost
        child_hash = check_json(child_request)
        child = run_library(child_request)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'library', child['status'])
        if child['steps_used'] != cost:
            raise Problem('library_cost_mismatch', 'library')
        result.update(ledger=deepcopy(child['ledger']), temporal_measurement=deepcopy(child['temporal_measurement']),
                      library={'input_sha256': child_hash, 'reserved_steps': cost, 'steps_used': child['steps_used']})
        found = {r['id']: r for r in child['results']}
        stage = 'queries'
        for row in rows:
            current = row
            for _ in range(OWN_FEE):
                budget.tick()
            query = prepared['queries'][row['id']]
            target = prepared['targets'].get((query['destination_ref']['id'], query['destination_ref']['version']))
            row.update(_row(found[row['id']], target, spec), assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'library' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'query': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
