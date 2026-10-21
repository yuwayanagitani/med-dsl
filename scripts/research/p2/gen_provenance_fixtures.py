#!/usr/bin/env python3
"""文書80の手指定期待を展開する。runtimeはimportせず、出力から期待を作らない。"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import gen_observation_fixtures as obs

ground, lib, q, m, day, check = obs.ground, obs.lib, obs.q, obs.m, obs.day, obs.check
ROOT = Path(os.environ.get('P2_REPO') or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT/'examples/p2-provenance'
PROFILE = 'p2-provenance-coding-draft-1'
SPEC = hashlib.sha256((ROOT/'src/med_dsl/provenance_coding_spec.json').read_bytes()).hexdigest()
KINDS = ('creation', 'correction', 'confirmation')
CODES = {'creation': 'fiction-create', 'correction': 'fiction-correct', 'confirmation': 'fiction-confirm'}
REVIEWER = obs.REVIEWER


def activity(kind, system='fiction:activity-system:s'):
    return {'system': system, 'code': CODES[kind]}


A_ALL = {kind: activity(kind) for kind in KINDS}


def coding(profile, activities=None, revision=None):
    found = {'destination_ref': lib.ref(profile)}
    if activities is not None:
        found['activities'] = deepcopy(activities)
    if revision is not None:
        found['revision'] = revision
    return found


def provenance(observation_request, codings, budget=100000):
    child = deepcopy(observation_request)
    child['budget'] = {'max_steps': 0}
    return {'schema_version': 'p2-provenance-request-draft-1', 'operation': 'run_provenance_coding',
            'consumer': {'profile': PROFILE, 'profile_spec_sha256': SPEC, 'operations': ['run_provenance_coding'],
                         'observation_profile': obs.PROFILE, 'observation_profile_spec_sha256': obs.SPEC},
            'observation_request': child, 'coding': deepcopy(codings), 'budget': {'max_steps': budget}}


def with_coding(flows, coded=(), uncoded=(), revision=None):
    """設計79の§5・文書80のC5：P2-qの行の流れに、符号の仮定・付けられなかった種類・訂正の関係の保持／喪失を足す。"""
    retained, lost, added = set(flows['retained']), set(flows['lost']), set(flows['added'])
    if coded:
        added.add('assumption:activity_coding_declared')
    lost |= {'activity:'+kind for kind in uncoded}
    if revision == 'carried':
        retained.add('revision:predecessor_identity')
        added.add('assumption:revision_role_declared')
    elif revision == 'lost':
        lost.add('revision:predecessor_identity')
    return {'retained': sorted(retained), 'lost': sorted(lost), 'added': sorted(added)}


def coded(index, entries, state, predecessors):
    """entries：(種類, 符号またはNone, 訂正された記録の参照の列)。"""
    p = ['results', index, 'coding']
    checks = [check(p+['state'], 'coded'), check(p+['revision', 'state'], state), check(p+['revision', 'predecessors'], list(predecessors))]
    for k, (kind, code, refs) in enumerate(entries):
        e = p+['entries', k]
        checks += [check(e+['index'], k), check(e+['kind'], kind), check(e+['activity'], code)]
        if refs:
            for j, ref in enumerate(refs):
                checks += [check(e+['entities', j, 'role'], 'revision'), check(e+['entities', j, 'what', 'type'], 'Observation'), check(e+['entities', j, 'what', 'record_ref'], ref)]
        else:
            checks.append(check(e+['entities'], []))
    return checks


def uncoded(index, state):
    p = ['results', index, 'coding']
    return [check(p+['state'], state), check(p+['entries'], None), check(p+['revision'], None)]


def unfinished(index=0, reason='step_limit'):
    return obs.unfinished(index, reason) + [check(['results', index, 'coding'], None)]


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, request_, checks, normal=True):
        checks = list(checks)
        if normal:
            checks += [check(['meaning_mode'], 'provenance_coding'), check(['converted_to_base'], False), check(['clinical_assertions_added'], []),
                       check(['inferred_information'], []), check(['clinical_confirmation'], 'not_evaluated'), check(['review_verification'], 'structural_only'),
                       check(['uncertainty_propagated'], False), check(['certificate', 'status'], 'not_certified'),
                       check(['certificate', 'evidence_level'], 'known_policy_change'), check(['certificate', 'scope'], None)]
        data = {'schema_version': 'p1-fixture-draft-1', 'fixture_version': 1, 'fixture_id': name, 'condition': name[:3], 'fictional': True,
                'review_state': 'author_draft', 'request': deepcopy(request_), 'expected': {'comparison': 'required_paths', 'checks': checks}}
        raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
        (DIRECTORY/(name.lower()+'.json')).write_bytes(raw)
        entries.append({'fixture_id': name, 'condition': name[:3], 'path': name.lower()+'.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def good(name, request_, rows, steps, observation_steps, grounding_steps):
        emit(name, request_, [check(['status'], 'ok'), check(['steps_used'], steps), check(['incomplete'], []),
                              check(['observation_run', 'reserved_steps'], observation_steps), check(['observation_run', 'steps_used'], observation_steps),
                              check(['grounding_run', 'reserved_steps'], grounding_steps), check(['grounding_run', 'steps_used'], grounding_steps), *rows])

    def bad(name, request_, code, status='invalid_input'):
        emit(name, request_, [check(['status'], status), check(['reason_codes'], [code])], False)

    PB1, PB2 = lib.PB1, lib.PB2
    base_flows = ground.flows_ok()
    human, device = {'kind': 'human', 'ref': 'fiction:human:observer'}, {'kind': 'device', 'ref': 'fiction:device:meter'}
    confirm_a = ('confirmation', 'A', day(3), 'Practitioner', REVIEWER)
    confirm_b = ('confirmation', 'B', day(7), 'Practitioner', REVIEWER)
    creation_b_human = ('creation', 'B', day(6), 'Practitioner', 'fiction:human:observer')

    def request_of(ground_request, declarations, codings):
        return provenance(obs.observation(ground_request, declarations, budget=0), codings)

    def fixed(**change):
        return [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2, **change), lib.confirm('B', 7)]

    def of_ops(ops, declarations, codings, at=5):
        return request_of(ground.one(ops=ops, query=lib.single('q1', PB1, at)), declarations, codings)

    # ---- 出せる行（V） ----
    q01 = obs.flows_q(base_flows)
    good('V01', request_of(ground.one(), [obs.declare(PB1)], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q01, coded=['confirmation']), entries=[confirm_a]) + coded(0, [('confirmation', activity('confirmation'), [])], 'not_applicable', []), 46, 42, 37)
    good('V02', request_of(ground.one(), [obs.declare(PB1)], [coding(PB1, {'creation': activity('creation')}, False)]),
         obs.projected(0, with_coding(q01, uncoded=['confirmation']), entries=[confirm_a]) + coded(0, [('confirmation', None, [])], 'not_applicable', []), 46, 42, 37)
    watched = [lib.rec(observer=human), lib.confirm('A')]
    other = {'creation': activity('creation', 'fiction:activity-system:other'), 'confirmation': activity('confirmation')}
    other['creation']['code'] = 'fiction-origin'
    good('V03', request_of(ground.one(ops=watched), [obs.declare(PB1, observer_type='PractitionerRole')], [coding(PB1, other, False)]),
         obs.projected(0, with_coding(obs.flows_q(base_flows, observer='kept', observer_type=True), coded=['creation', 'confirmation']),
                       entries=[('creation', 'A', day(2), 'PractitionerRole', 'fiction:human:observer'), confirm_a])
         + coded(0, [('creation', other['creation'], []), ('confirmation', activity('confirmation'), [])], 'not_applicable', []), 46, 42, 37)
    watched_fix = fixed(observer=human)
    q25 = obs.flows_q(base_flows, 'correction', 'amended', observer='kept', observer_type=True)
    q25_entries = [creation_b_human, confirm_b]
    declare_fix = lambda **kw: obs.declare(PB1, correction='amended', **kw)
    good('V04', of_ops(watched_fix, [declare_fix(observer_type='Practitioner')], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q25, coded=['correction', 'confirmation'], revision='carried'), 'correction', 'amended', 'B', q25_entries)
         + coded(0, [('correction', activity('correction'), ['A']), ('confirmation', activity('confirmation'), [])], 'carried', ['A']), 51, 47, 42)
    good('V05', of_ops(watched_fix, [declare_fix(observer_type='Practitioner')], [coding(PB1, A_ALL, False)]),
         obs.projected(0, with_coding(q25, coded=['correction', 'confirmation'], revision='lost'), 'correction', 'amended', 'B', q25_entries)
         + coded(0, [('correction', activity('correction'), []), ('confirmation', activity('confirmation'), [])], 'not_requested', ['A']), 51, 47, 42)
    q06 = obs.flows_q(base_flows, 'correction', 'amended')
    good('V06', of_ops(fixed(), [declare_fix()], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q06, coded=['confirmation'], revision='lost'), 'correction', 'amended', 'B', [confirm_b])
         + coded(0, [('confirmation', activity('confirmation'), [])], 'no_agent', ['A']), 51, 47, 42)
    good('V07', of_ops(watched_fix, [declare_fix(reviewer=None)], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(obs.flows_q(base_flows, 'correction', 'amended', provenance=False, observer='lost'), revision='lost'), 'correction', 'amended', 'B')
         + [check(['results', 0, 'coding', 'state'], 'coded'), check(['results', 0, 'coding', 'revision', 'state'], 'no_provenance'),
            check(['results', 0, 'coding', 'revision', 'predecessors'], ['A'])], 51, 47, 42)
    ai = {'kind': 'ai_candidate', 'ref': 'fiction:ai:B'}
    good('V08', of_ops(fixed(origin=ai), [declare_fix()], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(obs.flows_q(base_flows, 'correction', 'amended', creation=True), coded=['correction', 'confirmation'], revision='carried'),
                       'correction', 'amended', 'B', [('creation', 'B', day(6), 'Device', 'fiction:ai:B'), confirm_b])
         + coded(0, [('correction', activity('correction'), ['A']), ('confirmation', activity('confirmation'), [])], 'carried', ['A']), 51, 47, 42)
    two_predecessors = [lib.rec(), lib.rec('A2', recorded_at=day(3)), lib.confirm('A'), lib.confirm('A2', 3),
                        lib.fix('B', ['A', 'A2'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2, observer=human), lib.confirm('B', 7)]
    good('V09', of_ops(two_predecessors, [declare_fix(observer_type='Practitioner')], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q25, coded=['correction', 'confirmation'], revision='carried'), 'correction', 'amended', 'B', q25_entries)
         + coded(0, [('correction', activity('correction'), ['A', 'A2']), ('confirmation', activity('confirmation'), [])], 'carried', ['A', 'A2']), 56, 52, 47)
    chain = [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], validity=m.span(3, 8), recorded_at=day(4), value=lib.value(q.point(4)), method=lib.METHOD2), lib.confirm('B', 5),
             lib.fix('C', ['B'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2, observer=human), lib.confirm('C', 7)]
    good('V10', of_ops(chain, [declare_fix(observer_type='Practitioner')], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q25, coded=['correction', 'confirmation'], revision='carried'), 'correction', 'amended', 'C',
                       [('creation', 'C', day(6), 'Practitioner', 'fiction:human:observer'), ('confirmation', 'C', day(7), 'Practitioner', REVIEWER)])
         + coded(0, [('correction', activity('correction'), ['B']), ('confirmation', activity('confirmation'), [])], 'carried', ['B']), 56, 52, 47)
    past = ground.grounding(lib.request(watched_fix, destinations=[PB1], queries=[lib.single('q1', PB1, 4)], views=[{'id': 'v', 'as_of': day(4)}]), [ground.target(PB1)])
    good('V11', request_of(past, [declare_fix(observer_type='Practitioner')], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(q01, coded=['confirmation']), entries=[confirm_a]) + coded(0, [('confirmation', activity('confirmation'), [])], 'not_applicable', []), 49, 45, 40)
    no_correction_code = {'creation': activity('creation'), 'confirmation': activity('confirmation')}
    good('V12', of_ops(watched_fix, [declare_fix(observer_type='Practitioner')], [coding(PB1, no_correction_code, True)]),
         obs.projected(0, with_coding(q25, coded=['confirmation'], uncoded=['correction'], revision='carried'), 'correction', 'amended', 'B', q25_entries)
         + coded(0, [('correction', None, ['A']), ('confirmation', activity('confirmation'), [])], 'carried', ['A']), 51, 47, 42)
    both = dict(destinations=[PB1, PB2], queries=[lib.single('q1', PB1), lib.single('q2', PB2)])
    two_query = ground.grounding(lib.request(**both), [ground.target(PB1), ground.target(PB2)])
    good('V13', request_of(two_query, [obs.declare(PB1), obs.declare(PB2)], [coding(PB2, A_ALL, False)]),
         obs.projected(0, q01, entries=[confirm_a]) + uncoded(0, 'not_declared')
         + obs.projected(1, with_coding(q01, coded=['confirmation']), entries=[confirm_a]) + coded(1, [('confirmation', activity('confirmation'), [])], 'not_applicable', []), 79, 73, 65)
    good('V14', request_of(ground.one(ops=watched), [obs.declare(PB1)], [coding(PB1, A_ALL, True)]),
         obs.waiting(0, [obs.observer_request('A')], 'A') + uncoded(0, 'not_evaluated'), 46, 42, 37)
    good('V15', request_of(ground.one(q.point(1), 'u_third'), [obs.declare(PB1, code_map=[])], [coding(PB1, A_ALL, True)]),
         obs.passed(0, 'not_evaluated', 'not_representable', ['not_decimal_representable'], 'not_representable', ground.flows_no(['not_decimal_representable']), [])
         + uncoded(0, 'not_evaluated'), 46, 42, 37)
    good('V16', request_of(two_query, [obs.declare(PB2)], [coding(PB2, A_ALL, True)]),
         obs.passed(0, 'not_declared', 'satisfied', [], 'representable', base_flows, []) + uncoded(0, 'not_evaluated')
         + obs.projected(1, with_coding(q01, coded=['confirmation']), entries=[confirm_a]) + coded(1, [('confirmation', activity('confirmation'), [])], 'not_applicable', []), 79, 73, 65)
    good('V17', of_ops(fixed(), [declare_fix()], [coding(PB1, {'creation': activity('creation')}, False)]),
         obs.projected(0, with_coding(q06, uncoded=['confirmation'], revision='lost'), 'correction', 'amended', 'B', [confirm_b])
         + coded(0, [('confirmation', None, [])], 'not_requested', ['A']), 51, 47, 42)
    good('V18', request_of(ground.one(), [obs.declare(PB1)], [coding(PB1, {})]),
         obs.projected(0, with_coding(q01, uncoded=['confirmation']), entries=[confirm_a]) + coded(0, [('confirmation', None, [])], 'not_applicable', []), 46, 42, 37)
    ai_original = [lib.rec(origin={'kind': 'ai_candidate', 'ref': 'fiction:ai:A'}), lib.confirm('A')]
    good('V19', request_of(ground.one(ops=ai_original), [obs.declare(PB1)], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(obs.flows_q(base_flows, creation=True), coded=['creation', 'confirmation']),
                       entries=[('creation', 'A', day(2), 'Device', 'fiction:ai:A'), confirm_a])
         + coded(0, [('creation', activity('creation'), []), ('confirmation', activity('confirmation'), [])], 'not_applicable', []), 46, 42, 37)
    good('V20', of_ops(fixed(observer=device), [declare_fix()], [coding(PB1, A_ALL, True)]),
         obs.projected(0, with_coding(obs.flows_q(base_flows, 'correction', 'amended', observer='kept'), coded=['correction', 'confirmation'], revision='carried'),
                       'correction', 'amended', 'B', [('creation', 'B', day(6), 'Device', 'fiction:device:meter'), confirm_b])
         + coded(0, [('correction', activity('correction'), ['A']), ('confirmation', activity('confirmation'), [])], 'carried', ['A']), 51, 47, 42)

    # ---- 静的検査（N） ----
    base = request_of(ground.one(), [obs.declare(PB1)], [coding(PB1, A_ALL, True)])
    for key in ('operation', 'consumer', 'observation_request', 'coding', 'budget'):
        broken = deepcopy(base)
        del broken[key]
        bad('N01-missing-'+key, broken, 'missing_field')
    broken = deepcopy(base)
    broken['extra'] = 1
    bad('N01-extra', broken, 'unknown_field')
    broken = deepcopy(base)
    broken['observation_request'] = []
    bad('N01-observation-not-object', broken, 'expected_object')
    for name, path, value, code in [('profile', 'profile', 'p2-other-draft-1', 'unsupported_profile'), ('profile_spec_sha256', 'profile_spec_sha256', '0'*64, 'profile_spec_mismatch'),
                                    ('observation_profile', 'observation_profile', 'p2-other-draft-1', 'observation_profile_mismatch'),
                                    ('observation_profile_spec_sha256', 'observation_profile_spec_sha256', '0'*64, 'observation_profile_mismatch')]:
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
    broken['observation_request']['schema_version'] = 'p2-observation-request-draft-2'
    bad('N04-observation-schema', broken, 'observation_schema_mismatch', 'unsupported_profile')
    broken = deepcopy(base)
    broken['observation_request']['budget'] = {'max_steps': 5}
    bad('N05-child-budget', broken, 'invalid_child_budget')
    bad('N06-grounding-duplicate-target', provenance(obs.observation(ground.grounding(lib.request(destinations=[PB1], queries=[lib.single('q1', PB1)]),
                                                                                      [ground.target(PB1), ground.target(PB1, 'range')]), [obs.declare(PB1)], budget=0),
                                                     [coding(PB1, A_ALL, True)]), 'duplicate_target')
    bad('N06-duplicate-observation', provenance(obs.observation(ground.one(), [obs.declare(PB1), obs.declare(PB1, code_map=[])], budget=0), [coding(PB1, A_ALL, True)]), 'duplicate_observation')
    broken = deepcopy(base)
    broken['coding'] = []
    bad('N07-empty', broken, 'empty_collection')
    broken = deepcopy(base)
    broken['coding'] = [coding(PB1, A_ALL, True)]*17
    bad('N07-limit', broken, 'item_limit', 'resource_limit')
    for name, kind in [('revision', 'revision'), ('derivation', 'derivation'), ('removal', 'removal'), ('amend', 'amend')]:
        broken = deepcopy(base)
        broken['coding'][0]['activities'][kind] = activity('creation')
        bad('N08-kind-'+name, broken, 'unknown_field')
    for name, mutate, code in [('missing-code', lambda e: e.pop('code'), 'missing_field'), ('extra', lambda e: e.update(display='x'), 'unknown_field'),
                               ('empty-system', lambda e: e.update(system=''), 'expected_nonempty_string')]:
        broken = deepcopy(base)
        mutate(broken['coding'][0]['activities']['creation'])
        bad('N09-activity-'+name, broken, code)
    broken = deepcopy(base)
    broken['coding'][0]['activities']['creation'] = 'fiction-create'
    bad('N09-activity-not-object', broken, 'expected_object')
    for name, value in [('string', 'derivation'), ('integer', 1), ('null', None)]:
        broken = deepcopy(base)
        broken['coding'][0]['revision'] = value
        bad('N10-revision-'+name, broken, 'expected_boolean')
    broken = deepcopy(base)
    broken['coding'] = [coding(PB1, A_ALL, True), coding(PB1, {}, False)]
    bad('N11-duplicate-coding', broken, 'duplicate_coding')
    broken = deepcopy(base)
    broken['coding'] = [coding(PB2, A_ALL, True)]
    bad('N12-unresolved-observation', broken, 'unresolved_observation')
    for name, number in [('bool', True), ('negative', -1), ('limit', 100001)]:
        broken = deepcopy(base)
        broken['budget']['max_steps'] = number
        bad('N13-budget-'+name, broken, 'step_budget_limit' if name == 'limit' else 'invalid_step_budget', 'resource_limit' if name == 'limit' else 'invalid_input')
    broken = deepcopy(base)
    broken['coding'][0]['role'] = 'source'
    bad('N14-role-not-declarable', broken, 'unknown_field')
    broken = deepcopy(base)
    del broken['coding'][0]['destination_ref']['version']
    bad('N15-destination-version', broken, 'missing_field')

    # ---- 資源（B） ----
    def sweep(prefix, request_, row_builders, total, thresholds, observation_cost, fees):
        for budget in thresholds:
            copy = deepcopy(request_)
            copy['budget']['max_steps'] = budget
            checks = [check(['status'], 'ok' if budget >= total else 'resource_limit'), check(['steps_used'], min(budget, total))]
            paid, unfinished_ids = 1+observation_cost, []
            names = sorted(qr['id'] for qr in request_['observation_request']['grounding_request']['library_request']['queries'])
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
    row_single = lambda i: obs.projected(i, with_coding(q01, coded=['confirmation']), entries=[confirm_a]) + coded(i, [('confirmation', activity('confirmation'), [])], 'not_applicable', [])
    sweep('B01', base, [row_single], 46, [0, 1, 42, 43, 44, 45, 46], 42, [2])
    sweep('B02', request_of(two_query, [obs.declare(PB1), obs.declare(PB2)], [coding(PB1, A_ALL, True), coding(PB2, A_ALL, True)]), [row_single, row_single], 79,
          [0, 73, 74, 75, 76, 77, 78, 79], 73, [2, 2])
    big_ops = [lib.rec('R'+str(i)) for i in range(64)] + [lib.confirm('R'+str(i), 3, 'C'+str(i)) for i in range(64)]
    big = lib.request(big_ops, destinations=[PB1], queries=[lib.single('q'+str(i), PB1, 5, 'v'+str(j)) for i, j in zip(range(32), range(32))],
                      views=[{'id': 'v'+str(i), 'as_of': day(8)} for i in range(64)])
    emit('B03-plan', request_of(ground.grounding(big, [ground.target(PB1)]), [obs.declare(PB1)], [coding(PB1, A_ALL, True)]),
         [check(['status'], 'resource_limit'), check(['steps_used'], 100000), *unfinished(0), check(['certificate', 'status'], 'not_certified')])

    conditions = {letter: len({e['condition'] for e in entries if e['condition'][0] == letter}) for letter in 'VNB'}
    manifest = {'schema_version': 'p2-fixture-manifest-draft-1', 'suite': 'p2-provenance', 'review_state': 'author_draft', 'independent_review': False,
                'evaluation_frozen': False, 'conditions': conditions, 'files': entries}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(entries), 'checks': sum(len(json.loads((DIRECTORY/e['path']).read_text())['expected']['checks']) for e in entries), 'conditions': conditions}))


if __name__ == '__main__':
    main()
