"""R5：構造への写像の可否の診断（P2-p）を一度だけ実行し、表せる行に Observation の status・code と Provenance の宣言を適用する。
宣言のない写像は依頼にし、推測で補わない。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .model import Budget, Problem
from .structure_grounding import (GROUNDING_PROFILE, SPEC_SHA256 as GROUNDING_SPEC_SHA256, VALUE_FIELDS as GROUNDING_FIELDS, OWN_FEE as GROUNDING_FEE,
                                  _validate as validate_grounding, run_grounding)
from .validation import check_json, fields, string, strings, values

OBSERVATION_PROFILE = 'p2-observation-projection-draft-1'
SPEC_SHA256 = '847037e60ef393c9f09b8ebb14e389ad799fa33b3ec20969da6c34d706f6c591'
OPERATION = 'run_observation_projection'
ANSWER_KIND = 'observation_projection'
GROUNDING_REQUEST_SCHEMA = 'p2-grounding-request-draft-1'
VALUE_FIELDS = GROUNDING_FIELDS + ('observation',)
OWN_FEE = 3


def _unsupported(code, path):
    raise Problem(code, path, 'unsupported_profile')


def _spec():
    try:
        raw = Path(__file__).with_name('observation_projection_spec.json').read_bytes()
    except OSError as error:
        raise Problem('native_spec_unavailable', 'native_spec') from error
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise Problem('native_spec_mismatch', 'native_spec')
    spec = json.loads(raw)
    if spec['grounding_profile'] != GROUNDING_PROFILE or spec['grounding_spec_sha256'] != GROUNDING_SPEC_SHA256:
        _unsupported('grounding_profile_mismatch', 'native_spec')
    return spec


def _consumer(consumer):
    fields(consumer, ('profile', 'profile_spec_sha256', 'operations', 'grounding_profile', 'grounding_profile_spec_sha256'), path='consumer')
    for key, expected, code in [('profile', OBSERVATION_PROFILE, 'unsupported_profile'),
                                ('profile_spec_sha256', SPEC_SHA256, 'profile_spec_mismatch'),
                                ('grounding_profile', GROUNDING_PROFILE, 'grounding_profile_mismatch'),
                                ('grounding_profile_spec_sha256', GROUNDING_SPEC_SHA256, 'grounding_profile_mismatch')]:
        string(consumer[key], 'consumer.' + key)
        if key.endswith('sha256') and (len(consumer[key]) != 64 or any(c not in '0123456789abcdef' for c in consumer[key])):
            raise Problem('invalid_sha256', 'consumer.' + key)
        if consumer[key] != expected:
            _unsupported(code, 'consumer.' + key)
    strings(consumer['operations'], 64, 'consumer.operations')
    if consumer['operations'] != [OPERATION]:
        _unsupported('unsupported_operation', 'consumer.operations')


def _observations(raw, targets, spec):
    items = values(raw, spec['limits']['observations'], 'observations')
    if not items:
        raise Problem('empty_collection', 'observations')
    found = {}
    for item in items:
        fields(item, ('destination_ref', 'status', 'code_map'), ('provenance',), 'observation')
        reference = item['destination_ref']
        fields(reference, ('id', 'version'), path='observation.destination_ref')
        string(reference['id'], 'observation.destination_ref.id')
        string(reference['version'], 'observation.destination_ref.version')
        status = item['status']
        fields(status, ('original',), ('correction',), 'observation.status')
        for state in ('original', 'correction'):
            if state in status:
                string(status[state], 'observation.status.' + state)
                if status[state] not in spec['status_mapping'][state]:
                    _unsupported('unsupported_status_mapping', 'observation.status.' + state)
        mapping = {}
        for entry in values(item['code_map'], spec['limits']['code_map'], 'observation.code_map'):
            fields(entry, ('property_ref', 'system', 'code'), path='observation.code_map')
            for key in ('property_ref', 'system', 'code'):
                string(entry[key], 'observation.code_map.' + key)
            if entry['property_ref'] in mapping:
                raise Problem('duplicate_property_mapping', 'observation.code_map')
            mapping[entry['property_ref']] = {'system': entry['system'], 'code': entry['code']}
        if 'provenance' in item:
            fields(item['provenance'], ('reviewer_type',), path='observation.provenance')
            string(item['provenance']['reviewer_type'], 'observation.provenance.reviewer_type')
            if item['provenance']['reviewer_type'] not in spec['reviewer_types']:
                _unsupported('unsupported_reviewer_type', 'observation.provenance.reviewer_type')
        key = (reference['id'], reference['version'])
        if key in found:
            raise Problem('duplicate_observation', 'observations')
        if key not in targets:
            raise Problem('unresolved_target', 'observation.destination_ref')
        found[key] = {'status': deepcopy(status), 'code_map': mapping, 'reviewer_type': item['provenance']['reviewer_type'] if 'provenance' in item else None}
    return found


def _validate(request):
    fields(request, ('schema_version', 'operation', 'consumer', 'grounding_request', 'observations', 'budget'))
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
    child = request['grounding_request']
    if type(child) is not dict:
        raise Problem('expected_object', 'grounding_request')
    if child.get('schema_version') != GROUNDING_REQUEST_SCHEMA:
        _unsupported('grounding_schema_mismatch', 'grounding_request.schema_version')
    prepared = validate_grounding(child)
    if child['budget']['max_steps'] != 0:
        raise Problem('invalid_child_budget', 'grounding_request.budget.max_steps')
    prepared['observation_spec'] = spec
    prepared['observations'] = _observations(request['observations'], prepared['targets'], spec)
    prepared['grounding_cost'] = 2 + prepared['library_cost'] + GROUNDING_FEE * len(prepared['queries'])
    prepared['grounding_child'] = deepcopy(child)
    return prepared


def _passed(row, state):
    kept = {key: deepcopy(row[key]) for key in ('status', 'reason_codes', 'base_status', 'selection', 'elements', 'requests', 'output', 'flows', 'grounding')}
    return {**kept, 'observation': {'state': state, 'status': None, 'code': None, 'provenance': None}}


def _project(row, declaration, ledger, spec):
    selection = row['selection']
    record = ledger['records'][selection['record_ref']]
    state = 'correction' if record['revises'] else 'original'
    property_ref = row['output']['context']['property_ref']
    requests = []
    if property_ref not in declaration['code_map']:
        requests.append({'element': 'code', 'action': spec['requests']['code'], 'record_ref': record['id'], 'property_ref': property_ref})
    status_code = declaration['status'].get(state)
    if status_code is None:
        requests.append({'element': 'status', 'action': spec['requests']['status'], 'record_ref': record['id'], 'property_ref': None})
    if requests:
        out = _passed(row, 'needs_information')
        out.update(status='needs_information', reason_codes=['required_information_missing'], requests=sorted(requests, key=lambda r: (r['element'], r['record_ref'])),
                   output=None, flows=None)
        return out
    flows = spec['flows']
    retained, lost, added = set(row['flows']['retained']), set(row['flows']['lost']), set(row['flows']['added'])
    retained |= set(flows['always_retained'])
    lost -= set(flows['always_retained'])
    added |= {flows['assumptions']['code'], flows['assumptions']['status'].format(state=state, code=status_code)}
    provenance = []
    if declaration['reviewer_type'] is not None:
        if selection['record_origin']['kind'] == 'ai_candidate':
            provenance.append({'activity': 'creation', 'target': {'type': 'Observation', 'record_ref': record['id'], 'record_sha256': selection['record_sha256']},
                               'recorded': record['recorded_at'], 'agents': [{'who': {'type': 'Device', 'identifier': selection['record_origin']['ref']}}]})
            retained |= set(flows['creation_retained'])
            lost -= set(flows['creation_retained'])
        for review in sorted((ledger['reviews'][ref] for ref in selection['review_refs']), key=lambda r: (r['recorded_at'], r['id'])):
            provenance.append({'activity': 'confirmation', 'target': {'type': 'Observation', 'record_ref': record['id'], 'record_sha256': review['record_sha256']},
                               'recorded': review['recorded_at'], 'agents': [{'who': {'type': declaration['reviewer_type'], 'identifier': review['reviewer_ref']}}]})
        retained |= set(flows['provenance_retained'])
        lost -= set(flows['provenance_retained'])
        added.add(flows['assumptions']['reviewer'])
    out = _passed(row, 'projected')
    out['flows'] = {'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)}
    out['observation'] = {'state': 'projected', 'status': {'state': state, 'code': status_code}, 'code': deepcopy(declaration['code_map'][property_ref]),
                          'provenance': provenance}
    return out


def _row(row, declaration, ledger, spec):
    if declaration is None:
        return _passed(row, 'not_declared')
    if row['grounding']['state'] != 'representable':
        return _passed(row, 'not_evaluated')
    return _project(row, declaration, ledger, spec)


def run_observation(request):
    prepared = _validate(request)
    spec, cost = prepared['observation_spec'], prepared['grounding_cost']
    queries = sorted(prepared['queries'].values(), key=lambda q: q['id'])
    rows = [{'id': q['id'], 'view_ref': q['view_ref'], 'slot_ref': q['slot_ref'], 'destination_ref': deepcopy(q['destination_ref']),
             'status': 'unassessed', 'assessment_complete': False, 'reason_codes': ['step_limit'], **dict.fromkeys(VALUE_FIELDS)} for q in queries]
    result = {'status': 'ok', 'meaning_mode': ANSWER_KIND, 'results': rows, 'reason_codes': [], 'ledger': deepcopy(prepared['plan']['source']), 'library': None,
              'grounding_run': None, 'temporal_measurement': None, 'clinical_confirmation': 'not_evaluated', 'review_verification': 'structural_only',
              'uncertainty_propagated': False, 'converted_to_base': False, 'clinical_assertions_added': [], 'inferred_information': [],
              'certificate': {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'reason_codes': ['observation_projection_is_diagnostic'], 'scope': None}}
    budget = Budget(request['budget']['max_steps'])
    stage, current = 'grounding', None
    try:
        budget.tick()
        for _ in range(cost):
            budget.tick()
        child_request = prepared['grounding_child']
        child_request['budget']['max_steps'] = cost
        child_hash = check_json(child_request)
        child = run_grounding(child_request)
        if child['status'] != 'ok':
            raise Problem(child['reason_codes'][0], 'grounding', child['status'])
        if child['steps_used'] != cost:
            raise Problem('grounding_cost_mismatch', 'grounding')
        result.update(ledger=deepcopy(child['ledger']), library=deepcopy(child['library']), temporal_measurement=deepcopy(child['temporal_measurement']),
                      grounding_run={'input_sha256': child_hash, 'reserved_steps': cost, 'steps_used': child['steps_used']})
        ledger = {'records': {r['id']: r for r in child['ledger']['records']}, 'reviews': {r['id']: r for r in child['ledger']['reviews']}}
        found = {r['id']: r for r in child['results']}
        stage = 'queries'
        for row in rows:
            current = row
            for _ in range(OWN_FEE):
                budget.tick()
            query = prepared['queries'][row['id']]
            declaration = prepared['observations'].get((query['destination_ref']['id'], query['destination_ref']['version']))
            row.update(_row(found[row['id']], declaration, ledger, spec), assessment_complete=True)
        current, stage = None, 'completion'
        budget.tick()
    except Problem as problem:
        if problem.status != 'resource_limit':
            raise
        result.update(status='resource_limit', reason_codes=[problem.code])
        result['certificate']['reason_codes'] = [problem.code]
        for row in rows:
            if not row['assessment_complete'] and (stage == 'grounding' or row is current):
                row['reason_codes'] = [problem.code]
    result['steps_used'] = budget.used
    result['incomplete'] = [{'query': r['id'], 'reason_codes': r['reason_codes']} for r in rows if not r['assessment_complete']]
    if result['status'] == 'resource_limit' and stage == 'completion':
        result['incomplete'].append({'stage': 'completion', 'reason_codes': result['reason_codes']})
    return result
