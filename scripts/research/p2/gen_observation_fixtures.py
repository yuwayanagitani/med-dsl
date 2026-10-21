#!/usr/bin/env python3
"""文書71の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import gen_grounding_fixtures as ground

lib, q, m, day, check = ground.lib, ground.q, ground.m, ground.day, ground.check
ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT/'examples/p2-observation'
PROFILE = 'p2-observation-projection-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/observation_projection_spec.json').read_bytes()).hexdigest()
PROPERTY = lib.PROPERTY
MAP = [{'property_ref': PROPERTY, 'system': 'fiction:code-system:s', 'code': 'fiction-code-1'}]
CODE = {'system': 'fiction:code-system:s', 'code': 'fiction-code-1'}
REVIEWER = 'fiction:human:reviewer'


def declare(profile, original='final', correction=None, code_map=None, reviewer='Practitioner'):
    status = {'original': original}
    if correction is not None:
        status['correction'] = correction
    found = {'destination_ref': lib.ref(profile), 'status': status, 'code_map': deepcopy(MAP if code_map is None else code_map)}
    if reviewer is not None:
        found['provenance'] = {'reviewer_type': reviewer}
    return found


def observation(grounding_request, observations, budget=100000):
    child = deepcopy(grounding_request)
    child['budget'] = {'max_steps': 0}
    return {'schema_version': 'p2-observation-request-draft-1', 'operation': 'run_observation_projection',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['run_observation_projection'],
                         'grounding_profile': ground.PROFILE, 'grounding_profile_spec_sha256': ground.SPEC},
            'grounding_request': child, 'observations': deepcopy(observations), 'budget': {'max_steps': budget}}


def flows_q(base, state='original', code='final', provenance=True, creation=False):
    retained, lost = set(base['retained']) | {'context:property'}, set(base['lost']) - {'context:property'}
    added = set(base['added']) | {'assumption:code_mapping_declared', f'assumption:status_mapping:{state}:{code}'}
    if provenance:
        retained |= {'human_confirmed', 'record:identity'}
        lost -= {'human_confirmed', 'record:identity'}
        added.add('assumption:reviewer_type_declared')
    if creation:
        retained.add('origin_kind')
        lost.discard('origin_kind')
    return {'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)}


def provenance(index, k, activity, record, recorded, who_type, identifier):
    p = ['results', index, 'observation', 'provenance', k]
    return [check(p+['activity'], activity), check(p+['target', 'type'], 'Observation'), check(p+['target', 'record_ref'], record), check(p+['recorded'], recorded),
            check(p+['agents'], [{'who': {'type': who_type, 'identifier': identifier}}])]


def projected(index, flows, state='original', code='final', record='A', entries=(), grounding_value=None):
    p = ['results', index]
    checks = [check(p+['status'], 'satisfied'), check(p+['assessment_complete'], True), check(p+['reason_codes'], []), check(p+['requests'], []),
              check(p+['grounding', 'state'], 'representable'), check(p+['observation', 'state'], 'projected'),
              check(p+['observation', 'status'], {'state': state, 'code': code}), check(p+['observation', 'code'], CODE), check(p+['flows'], flows),
              check(p+['selection', 'record_ref'], record)]
    if grounding_value is not None:
        checks.append(check(p+['grounding', 'projection', 'value'], grounding_value))
    if not entries:
        checks.append(check(p+['observation', 'provenance'], []))
    for k, entry in enumerate(entries):
        checks += provenance(index, k, *entry)
    return checks


def waiting(index, requests, record):
    p = ['results', index]
    return [check(p+['status'], 'needs_information'), check(p+['assessment_complete'], True), check(p+['reason_codes'], ['required_information_missing']),
            check(p+['requests'], requests), check(p+['output'], None), check(p+['flows'], None), check(p+['grounding', 'state'], 'representable'),
            check(p+['observation', 'state'], 'needs_information'), check(p+['observation', 'status'], None), check(p+['observation', 'code'], None),
            check(p+['observation', 'provenance'], None), check(p+['selection', 'record_ref'], record)]


def passed(index, state, status, reasons, grounding_state, flows, requests):
    p = ['results', index]
    return [check(p+['status'], status), check(p+['assessment_complete'], True), check(p+['reason_codes'], list(reasons)), check(p+['requests'], requests),
            check(p+['flows'], flows), check(p+['grounding', 'state'], grounding_state), check(p+['observation', 'state'], state),
            check(p+['observation', 'status'], None), check(p+['observation', 'code'], None), check(p+['observation', 'provenance'], None)]


def unfinished(index=0, reason='step_limit'):
    p = ['results', index]
    return [check(p+['status'], 'unassessed'), check(p+['assessment_complete'], False), check(p+['reason_codes'], [reason])] + \
           [check(p+[key], None) for key in ('selection', 'elements', 'requests', 'output', 'flows', 'grounding', 'base_status', 'observation')]


def code_request(record, property_ref=PROPERTY):
    return {'element': 'code', 'action': 'declare_code_mapping', 'record_ref': record, 'property_ref': property_ref}


def status_request(record):
    return {'element': 'status', 'action': 'declare_correction_status', 'record_ref': record, 'property_ref': None}


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, request_, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'observation_projection'), check(['converted_to_base'], False), check(['clinical_assertions_added'], []),
                       check(['inferred_information'], []), check(['clinical_confirmation'], 'not_evaluated'), check(['review_verification'], 'structural_only'),
                       check(['uncertainty_propagated'], False), check(['certificate', 'status'], 'not_certified'),
                       check(['certificate', 'evidence_level'], 'known_policy_change'), check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(request_), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        (DIRECTORY/(name.lower()+'.json')).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': name.lower()+'.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, request_, rows, steps, grounding_steps):
        emit(name, request_, [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []), check(['grounding_run', 'reserved_steps'], grounding_steps),
                              check(['grounding_run', 'steps_used'], grounding_steps), *rows])

    def bad(name, request_, code, status='invalid_input'):
        emit(name, request_, [check(['status'], status), check(['reason_codes'], [code])], False)

    PB1, PB2 = lib.PB1, lib.PB2
    base_flows = ground.flows_ok()
    confirm_a = ('confirmation', 'A', day(3), 'Practitioner', REVIEWER)

    def standard(**options):
        return observation(ground.one(**options), [declare(PB1)])

    # ---- 出せる行（Q） ----
    good('Q01', standard(), projected(0, flows_q(base_flows), entries=[confirm_a]), 42, 37)
    good('Q02', observation(ground.one(), [declare(PB1, reviewer=None)]), projected(0, flows_q(base_flows, provenance=False)), 42, 37)
    for name, kind in [('Q03-role', 'PractitionerRole'), ('Q03-patient', 'Patient'), ('Q03-related', 'RelatedPerson')]:
        good(name, observation(ground.one(), [declare(PB1, reviewer=kind)]), projected(0, flows_q(base_flows), entries=[('confirmation', 'A', day(3), kind, REVIEWER)]), 42, 37)
    two = [lib.rec(), lib.confirm('A', 3, 'RA'), lib.confirm('A', 4, 'RA2')]
    good('Q04', observation(ground.one(ops=two), [declare(PB1)]), projected(0, flows_q(base_flows), entries=[confirm_a, ('confirmation', 'A', day(4), 'Practitioner', REVIEWER)])
         + [check(['results', 0, 'selection', 'review_refs'], ['RA', 'RA2'])], 43, 38)
    ai = [lib.rec(origin={'kind': 'ai_candidate', 'ref': 'fiction:ai:A'}), lib.confirm('A')]
    good('Q05', observation(ground.one(ops=ai), [declare(PB1)]),
         projected(0, flows_q(base_flows, creation=True), entries=[('creation', 'A', day(2), 'Device', 'fiction:ai:A'), confirm_a]), 42, 37)
    corrected = [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2), lib.confirm('B', 7)]
    fixed = dict(ops=corrected, query=lib.single('q1', PB1, 5))
    for name, kind in [('Q06', 'amended'), ('Q07', 'corrected')]:
        good(name, observation(ground.one(**fixed), [declare(PB1, correction=kind)]),
             projected(0, flows_q(base_flows, 'correction', kind), 'correction', kind, 'B', [('confirmation', 'B', day(7), 'Practitioner', REVIEWER)]), 47, 42)
    good('Q11', observation(ground.one(), [declare(PB1, correction='corrected')]), projected(0, flows_q(base_flows), entries=[confirm_a]), 42, 37)
    good('Q15', observation(ground.one(period='exclusive_end_as_last_second'), [declare(PB1)]), projected(0, flows_q(ground.flows_ok(carried=True)), entries=[confirm_a]), 42, 37)
    unknown_method = [lib.rec(method=lib.UNKNOWN), lib.confirm('A')]
    good('Q16', observation(ground.one(ops=unknown_method), [declare(PB1)]), projected(0, flows_q(ground.flows_ok(known=('specimen',))), entries=[confirm_a]), 42, 37)
    good('Q17', observation(ground.one(value='range'), [declare(PB1)]), projected(0, flows_q(base_flows), entries=[confirm_a], grounding_value={'low': '20', 'high': '20'}), 42, 37)
    late = [lib.rec(), lib.confirm('A', 3, 'RA'), lib.confirm('A', 9, 'RA9')]
    good('Q19', observation(ground.one(ops=late), [declare(PB1)]), projected(0, flows_q(base_flows), entries=[confirm_a])
         + [check(['results', 0, 'selection', 'review_refs'], ['RA'])], 43, 38)

    # ---- 宣言が足りない行（依頼） ----
    good('Q08', observation(ground.one(**fixed), [declare(PB1)]), waiting(0, [status_request('B')], 'B'), 47, 42)
    good('Q09', observation(ground.one(), [declare(PB1, code_map=[])]), waiting(0, [code_request('A')], 'A'), 42, 37)
    good('Q10', observation(ground.one(**fixed), [declare(PB1, code_map=[])]), waiting(0, [code_request('B'), status_request('B')], 'B'), 47, 42)

    # ---- 判定しない行 ----
    good('Q12', observation(ground.one(q.point(1), 'u_third'), [declare(PB1, code_map=[])]),
         passed(0, 'not_evaluated', 'not_representable', ['not_decimal_representable'], 'not_representable', ground.flows_no(['not_decimal_representable']), []), 42, 37)
    both = dict(destinations=[PB1, PB2], queries=[lib.single('q1', PB1), lib.single('q2', PB2)])
    two_query = ground.grounding(lib.request(**both), [ground.target(PB1), ground.target(PB2)])
    good('Q13', observation(two_query, [declare(PB2)]),
         passed(0, 'not_declared', 'satisfied', [], 'representable', base_flows, []) + projected(1, flows_q(base_flows), entries=[confirm_a]), 73, 65)
    good('Q14', observation(ground.grounding(lib.request(unknown_method, destinations=[PB2], queries=[lib.single('q1', PB2)]), [ground.target(PB2)]), [declare(PB2)]),
         passed(0, 'not_evaluated', 'needs_information', ['required_information_missing'], 'not_evaluated', None, [lib.req('context:method', 'observe_and_record', record_ref='A')]), 42, 37)
    both_range = ground.grounding(lib.request(**both), [ground.target(PB1, 'quantity'), ground.target(PB2, 'range')])
    good('Q18', observation(both_range, [declare(PB1), declare(PB2)]),
         projected(0, flows_q(base_flows), entries=[confirm_a], grounding_value={'decimal': '20'}) + projected(1, flows_q(base_flows), entries=[confirm_a], grounding_value={'low': '20', 'high': '20'}),
         73, 65)

    # ---- 静的検査（N） ----
    base = standard()
    for key in ('operation', 'consumer', 'grounding_request', 'observations', 'budget'):
        broken = deepcopy(base)
        del broken[key]
        bad('N01-missing-'+key, broken, 'missing_field')
    broken = deepcopy(base)
    broken['extra'] = 1
    bad('N01-extra', broken, 'unknown_field')
    broken = deepcopy(base)
    broken['grounding_request'] = []
    bad('N01-grounding-not-object', broken, 'expected_object')
    for name, path, value, code in [('profile', 'profile', 'p2-other-draft-1', 'unsupported_profile'), ('profile_spec_sha256', 'profile_spec_sha256', '0'*64, 'profile_spec_mismatch'),
                                    ('grounding_profile', 'grounding_profile', 'p2-other-draft-1', 'grounding_profile_mismatch'),
                                    ('grounding_profile_spec_sha256', 'grounding_profile_spec_sha256', '0'*64, 'grounding_profile_mismatch')]:
        broken = deepcopy(base)
        broken['consumer'][path] = value
        bad('N02-'+name, broken, code, 'unsupported_profile')
    broken = deepcopy(base)
    broken['operation'] = 'other_operation'
    bad('N03-operation', broken, 'unsupported_operation', 'unsupported_profile')
    broken = deepcopy(base)
    broken['consumer']['operations'] = ['other_operation']
    bad('N03-consumer-operations', broken, 'unsupported_operation', 'unsupported_profile')
    broken = deepcopy(base)
    broken['grounding_request']['schema_version'] = 'p2-grounding-request-draft-2'
    bad('N04-grounding-schema', broken, 'grounding_schema_mismatch', 'unsupported_profile')
    broken = deepcopy(base)
    broken['grounding_request']['budget'] = {'max_steps': 5}
    bad('N05-child-budget', broken, 'invalid_child_budget')
    bad('N06-grounding-duplicate-target', observation(ground.grounding(lib.request(destinations=[PB1], queries=[lib.single('q1', PB1)]),
                                                                        [ground.target(PB1), ground.target(PB1, 'range')]), [declare(PB1)]), 'duplicate_target')
    hashed = [lib.rec(), lib.confirm('A')]
    hashed[1]['record_sha256'] = 'x'
    bad('N06-library-hash', observation(ground.grounding(lib.request(hashed, destinations=[PB1], queries=[lib.single('q1', PB1)]), [ground.target(PB1)]), [declare(PB1)]), 'unknown_field')
    broken = deepcopy(base)
    broken['observations'] = []
    bad('N07-empty', broken, 'empty_collection')
    broken = deepcopy(base)
    broken['observations'] = [declare(PB1)]*17
    bad('N07-limit', broken, 'item_limit', 'resource_limit')
    for name, path, value in [('original-amended', 'original', 'amended'), ('original-preliminary', 'original', 'preliminary'),
                              ('correction-final', 'correction', 'final'), ('correction-registered', 'correction', 'registered')]:
        broken = deepcopy(base)
        broken['observations'][0]['status'][path] = value
        bad('N08-'+name, broken, 'unsupported_status_mapping', 'unsupported_profile')
    broken = deepcopy(base)
    broken['observations'][0]['status'] = {}
    bad('N09-status-missing-original', broken, 'missing_field')
    broken = deepcopy(base)
    broken['observations'][0]['status']['extra'] = 1
    bad('N09-status-extra', broken, 'unknown_field')
    for name, mutate, code in [('missing', lambda e: e.pop('code'), 'missing_field'), ('extra', lambda e: e.update(extra=1), 'unknown_field'),
                               ('empty', lambda e: e.update(system=''), 'expected_nonempty_string')]:
        broken = deepcopy(base)
        mutate(broken['observations'][0]['code_map'][0])
        bad('N10-code-map-'+name, broken, code)
    broken = deepcopy(base)
    broken['observations'][0]['code_map'] = MAP*2
    bad('N10-code-map-duplicate', broken, 'duplicate_property_mapping')
    for name, kind in [('device', 'Device'), ('organization', 'Organization'), ('unknown', 'Nurse')]:
        broken = deepcopy(base)
        broken['observations'][0]['provenance']['reviewer_type'] = kind
        bad('N11-reviewer-'+name, broken, 'unsupported_reviewer_type', 'unsupported_profile')
    broken = deepcopy(base)
    broken['observations'] = [declare(PB1), declare(PB1, code_map=[])]
    bad('N12-duplicate-observation', broken, 'duplicate_observation')
    bad('N12-unresolved-target', observation(ground.grounding(lib.request(**both), [ground.target(PB1)]), [declare(PB2)]), 'unresolved_target')
    for name, number in [('bool', True), ('negative', -1), ('limit', 100001)]:
        broken = deepcopy(base)
        broken['budget']['max_steps'] = number
        bad('N13-budget-'+name, broken, 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')

    # ---- 資源（B） ----
    def sweep(prefix, request_, row_builders, total, thresholds, grounding_cost, fees):
        for budget in thresholds:
            copy = deepcopy(request_)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid, unfinished_ids = 1+grounding_cost, []
            names = sorted(qr['id'] for qr in request_['grounding_request']['library_request']['queries'])
            for index, (build, fee) in enumerate(zip(row_builders, fees)):
                paid += fee
                if budget >= paid:
                    checks += build(index)
                else:
                    checks += unfinished(index)
                    unfinished_ids.append(names[index])
            incomplete = [{'query': ident, 'reason_codes': ['step_limit']} for ident in unfinished_ids]
            if budget == total-1:
                incomplete.append({'stage': 'completion', 'reason_codes': ['step_limit']})
            checks.append(check(['incomplete'], incomplete))
            emit(prefix+'-'+str(budget), copy, checks)
    sweep('B01', standard(), [lambda i: projected(i, flows_q(base_flows), entries=[confirm_a])], 42, [0, 1, 37, 38, 39, 40, 41, 42], 37, [3])
    sweep('B02', observation(two_query, [declare(PB1), declare(PB2)]),
          [lambda i: projected(i, flows_q(base_flows), entries=[confirm_a]), lambda i: projected(i, flows_q(base_flows), entries=[confirm_a])],
          73, [0, 65, 66, 68, 69, 71, 72, 73], 65, [3, 3])
    big_ops = [lib.rec('R'+str(i)) for i in range(64)] + [lib.confirm('R'+str(i), 3, 'C'+str(i)) for i in range(64)]
    big = lib.request(big_ops, destinations=[PB1], queries=[lib.single('q'+str(i), PB1, 5, 'v'+str(j)) for i, j in zip(range(32), range(32))],
                      views=[{'id': 'v'+str(i), 'as_of': day(8)} for i in range(64)])
    emit('B03-plan', observation(ground.grounding(big, [ground.target(PB1)]), [declare(PB1)]),
         [check(['status'], 'resource_limit'), check(['steps_used'], 100000), *unfinished(0), check(['certificate', 'status'], 'not_certified')])

    conditions = {letter: len({e['condition'] for e in entries if e['condition'][0] == letter}) for letter in 'QNB'}
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-observation', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': conditions, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries), 'conditions': conditions}))


if __name__ == '__main__':
    main()
