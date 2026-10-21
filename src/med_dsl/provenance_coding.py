"""R5：Observation の status・code と Provenance の出力（P2-q）を一度だけ実行し、出せた行の Provenance の項目に、宣言した活動の符号と、訂正の
関係（revision の entity）を足す。宣言のない符号は別の種類で代用せず、運べない関係は理由を区別して示す。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .observation_projection import (OBSERVATION_PROFILE, SPEC_SHA256 as OBSERVATION_SPEC_SHA256, VALUE_FIELDS as OBSERVATION_FIELDS, OWN_FEE as OBSERVATION_FEE,
                                     _validate as validate_observation, run_observation)
from .temporal_measurement import _record_hash
from .validation import check_json, fields, string, strings, values

CODING_PROFILE = 'p2-provenance-coding-draft-1'
SPEC_SHA256 = 'd1eb04acda3d8c68e38773fa6895767e762e7e7465c28a35709976a7d400cf93'
OPERATION = 'run_provenance_coding'
ANSWER_KIND = 'provenance_coding'
OBSERVATION_REQUEST_SCHEMA = 'p2-observation-request-draft-1'
VALUE_FIELDS = OBSERVATION_FIELDS + ('coding',)
OWN_FEE = 2


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('provenance_coding_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['observation_profile'] != OBSERVATION_PROFILE or spec['observation_spec_sha256'] != OBSERVATION_SPEC_SHA256:
        _unsupported('observation_profile_mismatch', 'native_spec')
    return spec


def _consumer(consumer):
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'observation_profile', 'observation_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', CODING_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('observation_profile', OBSERVATION_PROFILE, 'observation_profile_mismatch'),
                                ('observation_profile_spec_sha256', OBSERVATION_SPEC_SHA256, 'observation_profile_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')


def _codings(raw, observations, spec):
    items = values(raw, spec['limits']['coding'], 'coding')
    if not items:
        raise Problem('empty_collection', 'coding')
    found = {}
    for item in items:
        fields(item, ('destination_ref',), ('activities', 'revision'), 'coding')
        reference = item['destination_ref']
        fields(reference, ('id', 'version'), path='coding.destination_ref')
        string(reference['id'], 'coding.destination_ref.id')
        string(reference['version'], 'coding.destination_ref.version')
        activities = {}
        if 'activities' in item:
            fields(item['activities'], (), tuple(spec['activity_kinds']), 'coding.activities')
            for kind, coding in item['activities'].items():
                fields(coding, ('system', 'code'), path='coding.activities.' + kind)
                string(coding['system'], 'coding.activities.' + kind + '.system')
                string(coding['code'], 'coding.activities.' + kind + '.code')
                activities[kind] = {'system': coding['system'], 'code': coding['code']}
        revision = item.get('revision', False)
        if type(revision) is not bool:
            raise Problem('expected_boolean', 'coding.revision')
        key = (reference['id'], reference['version'])
        if key in found:
            raise Problem('duplicate_coding', 'coding')
        if key not in observations:
            raise Problem('unresolved_observation', 'coding.destination_ref')
        found[key] = {'activities': activities, 'revision': revision}
    return found


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'observation_request', 'coding', 'budget'))
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
    child = request['observation_request']
    if type(child) is not dict:
        raise Problem('expected_object', 'observation_request')
    if child.get('schema_version') != OBSERVATION_REQUEST_SCHEMA:
        _unsupported('observation_schema_mismatch', 'observation_request.schema_version')
    prepared = validate_observation(child)
    if child['budget']['max_steps'] != 0:
        raise Problem('invalid_child_budget', 'observation_request.budget.max_steps')
    prepared['coding_spec'] = spec
    prepared['codings'] = _codings(request['coding'], prepared['observations'], spec)
    prepared['observation_cost'] = 2 + prepared['grounding_cost'] + OBSERVATION_FEE * len(prepared['queries'])
    prepared['observation_child'] = deepcopy(child)
    return prepared


def _passed(row, state):
    return {**deepcopy(row), 'coding': {'state': state, 'entries': None, 'revision': None}}


def _coded(row, declaration, ledger, reviewer_declared, spec):
    observation = row['observation']
    selection = row['selection']
    record = ledger['records'][selection['record_ref']]
    if _record_hash(ledger['source'], record) != selection['record_sha256']:
        raise Problem('record_hash_mismatch', 'coding')
    correction = observation['status']['state'] == 'correction'
    entries = []
    for index, item in enumerate(observation['provenance']):
        kind = 'confirmation' if item['activity'] == 'confirmation' else ('correction' if correction else 'creation')
        entries.append({'index': index, 'kind': kind, 'activity': deepcopy(declaration['activities'].get(kind)), 'entities': []})
    predecessors = sorted(record['revises']) if correction else []
    generating = [index for index, item in enumerate(observation['provenance']) if item['activity'] == 'creation']
    if not correction:
        state = 'not_applicable'
    elif not declaration['revision']:
        state = 'not_requested'
    elif not reviewer_declared:
        state = 'no_provenance'
    elif not generating:
        state = 'no_agent'
    else:
        state = 'carried'
        for predecessor in predecessors:
            entries[generating[0]]['entities'].append({'role': spec['entity_role'], 'what': {'type': 'Observation', 'record_ref': predecessor,
                                                                                            'record_sha256': _record_hash(ledger['source'], ledger['records'][predecessor])}})
    flows = spec['flows']
    retained, lost, added = set(row['flows']['retained']), set(row['flows']['lost']), set(row['flows']['added'])
    if any(entry['activity'] is not None for entry in entries):
        added.add(flows['assumptions']['activity'])
    for entry in entries:
        if entry['activity'] is None:
            lost.add(flows['activity_lost'].format(kind=entry['kind']))
    if correction:
        if state == 'carried':
            retained |= set(flows['revision_carried'])
            added.add(flows['assumptions']['revision'])
        else:
            lost |= set(flows['revision_lost'])
    out = deepcopy(row)
    out['flows'] = {'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)}
    out['coding'] = {'state': 'coded', 'entries': entries, 'revision': {'state': state, 'predecessors': predecessors}}
    return out


def _row(row, declaration, ledger, reviewer_declared, spec):
    if row['observation']['state'] != 'projected':
        return _passed(row, 'not_evaluated')
    if declaration is None:
        return _passed(row, 'not_declared')
    return _coded(row, declaration, ledger, reviewer_declared, spec)


def run_coding(request):
    prepared = _validate(request)
    spec, cost = prepared['coding_spec'], prepared['observation_cost']
    queries = sorted(prepared['queries'].values(), key=lambda q: q['id'])
    rows = [{'id': q['id'], 'view_ref': q['view_ref'], 'slot_ref': q['slot_ref'], 'destination_ref': deepcopy(q['destination_ref']),
             'status': 'unassessed', 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)} for q in queries]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [], 'ledger': deepcopy(prepared['plan']['source']), 'library': None,
              'grounding_run': None, 'observation_run': None, 'temporal_measurement': None, 'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only',
              'uncertainty_propagated': False, 'converted_to_base': False, 'clinical_assertions_added': [], 'inferred_information': [],
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'reason_codes': ['provenance_coding_is_diagnostic'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'observation', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        child_request = prepared['observation_child']
        child_request['budget']['max_steps'] = cost
        child_hash = check_json(child_request)
        child = run_observation(child_request)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'observation', child['status'])
        if child['steps_used'] != cost:
            raise Problem('observation_cost_mismatch', 'observation')
        result.update(ledger=deepcopy(child['ledger']), library=deepcopy(child['library']), temporal_measurement=deepcopy(child['temporal_measurement']),
                      grounding_run=deepcopy(child['grounding_run']), observation_run={'input_sha256': child_hash, 'reserved_steps': cost, 'steps_used': child['steps_used']})
        source = child['ledger']
        ledger = {'source': source, 'records': {r['id']: r for r in source['records']}}
        found = {r['id']: r for r in child['results']}
        stage = 'queries'
        for row in rows:
            current = row
            for _ in range(OWN_FEE):
                budget.tick()
            query = prepared['queries'][row['id']]
            key = (query['destination_ref']['id'], query['destination_ref']['version'])
            observed = prepared['observations'].get(key)
            row.update(_row(found[row['id']], prepared['codings'].get(key), ledger, observed is not None and observed['reviewer_type'] is not None, spec), assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'observation' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'query': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
