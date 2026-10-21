"""P2-m：手指定期待、別計算（二つの経路）との比較、P2-gとの文脈の差分、P2-iの直接実行との差分、共通予算と接続面の閉包。"""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import inspect
from itertools import product
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/research'), str(ROOT/'scripts/research/p2'), str(Path(__file__).parent)]
from med_dsl import evaluate, host, longitudinal as native
from med_dsl.model import Problem
from med_dsl.quantity import run_quantities as quantity_runner
from med_dsl.temporal_measurement import run_temporal_measurements as child_runner
import gen_longitudinal_fixtures as make
import gen_measurement_fixtures as measurement
import longitudinal_oracle as oracle
import p2_checks
DIRECTORY = ROOT/'examples/p2-longitudinal'
FIELDS = native.VALUE_FIELDS
m, q = make.m, make.q
UNITS = ['u_base', 'u_ten', 'u_third', 'u_half', 'u_hundred']
MAGNITUDES = [q.point(n, d) for n, d in [(-3, 2), (0, 1), (1, 2), (1, 1), (3, 2), (2, 1), (3, 1)]] + \
             [q.interval(a, b, lc, uc) for a, b in [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)] for lc in (True, False) for uc in (True, False)]


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def two_records(left, right, units=('u_ten', 'u_ten'), times=(3, 5), targets=('u_base', 'u_base')):
    plan = make.chain(times=times, targets=targets)
    for index, (magnitude, unit) in enumerate(zip((left, right), units)):
        literal = plan['source']['quantities'][index]['literal']
        literal['magnitude'], literal['unit_ref'] = deepcopy(magnitude), unit
    return make.request(m.seal(plan))


def check_row(row, expected):
    """実装の行を、別計算の期待（二つの経路の一致を含む）と照合する。"""
    if (row['status'], row['reason_codes'], row['assessment_complete']) != (expected['status'], expected['reason_codes'], True):
        raise AssertionError((row, expected))
    if expected['status'] == 'computed':
        relation = expected['relation']
        if relation != expected['original']:
            raise AssertionError(('routes differ', row, expected))
        if (row['relation_set'], row['certain_relation'], row['context_differences']) != (relation, relation[0] if len(relation) == 1 else None, []):
            raise AssertionError((row, expected))
        if [row['endpoints'][side]['binding_evidence']['selected'][0]['record_ref'] for side in ('from', 'to')] != expected['selected']:
            raise AssertionError((row, expected))
        if row['comparison_evidence']['direction'] != 'from_relative_to_to' or row['comparison_evidence']['assumptions'] != native.ASSUMPTIONS:
            raise AssertionError(row)
    else:
        if (row['relation_set'], row['certain_relation'], row['comparison_evidence']) != (None, None, None):
            raise AssertionError(row)
        if expected['status'] == 'not_comparable':
            if [d['field'] for d in row['context_differences']] != expected['differences']:
                raise AssertionError((row, expected))
        elif row['context_differences'] is not None:
            raise AssertionError(row)
        if (row['endpoints'] is not None) != expected['endpoints']:
            raise AssertionError((row, expected))


def reference(req):
    """実装の結果全体を、別計算と照合する。接続面の上限で止まる比較は、ID順の最初のものだけが止まり、以降は未完了。"""
    result = evaluate(req)
    ordered = sorted(req['comparisons'], key=lambda c: c['id'])
    expected = [oracle.row(req, c) for c in ordered]
    stop = next((i for i, e in enumerate(expected) if e['status'] == 'resource_limit'), None)
    if stop is None:
        if result['status'] != 'ok':
            raise AssertionError(result)
        for row, e in zip(result['results'], expected):
            check_row(row, e)
        if result['steps_used'] != oracle.cost(req):
            raise AssertionError((result['steps_used'], oracle.cost(req)))
        return result
    if (result['status'], result['reason_codes']) != ('resource_limit', ['rational_integer_limit']):
        raise AssertionError(result)
    plan_cost = oracle.cost(req)-2-18*len(ordered)
    if result['steps_used'] != 1+plan_cost+18*(stop+1):
        raise AssertionError(result['steps_used'])
    for index, (row, e) in enumerate(zip(result['results'], expected)):
        if index < stop:
            check_row(row, e)
        else:
            if row['assessment_complete'] or any(row[key] is not None for key in FIELDS):
                raise AssertionError(row)
    return result


class LongitudinalTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'L': 41, 'N': 11, 'B': 5})
        self.assertEqual(len(manifest['files']), 103)
        declaration = json.loads((ROOT/'extensions/p2-longitudinal-comparison.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'LC-{i}' for i in range(1, 13)})
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')}, {e['path'] for e in manifest['files']} | {'manifest.json'})
        for entry in manifest['files']:
            path = DIRECTORY/entry['path']
            raw = path.read_bytes()
            data = json.loads(raw)
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (entry['bytes'], entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']), data['expected']['checks']), [], entry['path'])
            done = subprocess.run([sys.executable, '-B', '-m', 'med_dsl', '--fixture', str(path)], cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT/'src')}, capture_output=True, text=True, timeout=30)
            out = json.loads(done.stdout)
            self.assertEqual(done.returncode, {'ok': 0, 'invalid_input': 2, 'unsupported_profile': 3, 'resource_limit': 4}[out['status']], done.stderr)
            self.assertEqual(p2_checks.failed_checks(out, data['expected']['checks']), [], entry['path'])
        report = p2_checks.suite_report('p2-longitudinal', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (103, 2020, []))

    def test_finite_relations_against_the_oracle_and_the_original_route(self):
        rows = 0
        seen = set()
        for (left, start), (right, end) in product(product(MAGNITUDES, ['u_ten', 'u_third']), product(MAGNITUDES, ['u_half', 'u_hundred', 'u_base'])):
            result = reference(two_records(left, right, (start, end)))
            rows += 1
            seen.add(tuple(result['results'][0]['relation_set']))
        self.assertEqual(rows, 27*2*27*3)
        self.assertEqual(seen, {('less',), ('greater',), ('equal',), ('less', 'equal'), ('equal', 'greater'), ('less', 'equal', 'greater')})

    def test_the_target_unit_does_not_change_the_relation(self):
        """W7：目標単位を変えても関係の集合は変わらない（63bitの範囲）。第二の経路（元のリテラル）とも一致する。"""
        checked = 0
        pairs = list(product(MAGNITUDES, MAGNITUDES))[::13]
        for left, right in pairs:
            plan = make.chain()
            for index, magnitude in enumerate((left, right)):
                plan['source']['quantities'][index]['literal']['magnitude'] = deepcopy(magnitude)
            plan['queries'] = [m.convert(ident=f'a-{u}', target=u, at=3) for u in UNITS] + [m.convert(ident=f'b-{u}', target=u, at=5) for u in UNITS]
            comparisons = [make.comparison(f'{x}-{y}', start=f'a-{x}', end=f'b-{y}') for x, y in product(UNITS, UNITS)]
            result = reference(make.request(m.seal(plan), comparisons))
            relations = {tuple(r['relation_set']) for r in result['results']}
            self.assertEqual(len(relations), 1, (left, right))
            checked += len(result['results'])
        self.assertEqual(checked, len(pairs)*25)

    def test_context_agrees_with_the_measurement_extension_on_the_common_fragment(self):
        """W4：property×specimen×methodの18通りの組み合わせ324対で、P2-mの文脈の不一致の理由が、P2-gの matched_context の比較と一致する。"""
        contexts = [(prop, {'kind': 'known', 'ref': ref, 'version': ver}, {'kind': 'known', 'ref': mref, 'version': mver})
                    for prop in (make.PROPERTY, make.OTHER_PROPERTY)
                    for ref, ver in (('fiction:specimen:s', '1'), ('fiction:specimen:s', '2'), ('fiction:specimen:t', '1'))
                    for mref, mver in (('fiction:method:m', '1'), ('fiction:method:m', '2'), ('fiction:method:n', '1'))]
        self.assertEqual(len(contexts), 18)
        reasons_seen = set()
        for first, second in product(contexts, contexts):
            plan = make.chain()
            req = measurement.pair()
            for record, other, context in zip(plan['source']['records'], req['source']['records'], (first, second)):
                for target in (record, other):
                    target['property_ref'], target['specimen'], target['method'] = deepcopy(context[0]), deepcopy(context[1]), deepcopy(context[2])
            measurement.seal(req)
            old = evaluate(req)['results'][0]
            new = evaluate(make.request(m.seal(plan)))['results'][0]
            old_reasons = set(old['reason_codes']) if old['status'] == 'not_comparable' else set()
            new_reasons = set(new['reason_codes']) if new['status'] == 'not_comparable' else set()
            self.assertEqual(old_reasons, new_reasons, (first, second))
            self.assertEqual((old['status'], new['status']), ('not_comparable', 'not_comparable') if old_reasons else ('computed', 'computed'))
            reasons_seen.add(frozenset(new_reasons))
        self.assertEqual(len(reasons_seen), 8)        # 三つの理由の部分集合を全て経由する

    def test_endpoint_rows_equal_the_direct_temporal_measurement_rows(self):
        """LC-7・W8：端点の行は、同じ計画をP2-iへ直接渡した行と完全に一致する（継承の差分）。"""
        compared = 0
        requests = [r for _, r in p2_checks.load_requests(('p2-longitudinal',)) if r.get('schema_version') == 'p2-longitudinal-request-draft-1']
        rng = random.Random(570011)
        requests += [self.random_request(rng) for _ in range(60)]
        for req in requests:
            result = evaluate(deepcopy(req))
            if result['status'] != 'ok':
                continue
            direct = deepcopy(req['temporal_measurement_plan'])
            direct['budget'] = {'max_steps': 100000}
            rows = {(r['view'], r['query']): r for r in evaluate(direct)['results']}
            for row in result['results']:
                if row['endpoints'] is not None:
                    self.assertEqual(row['endpoints']['from'], rows[(row['view_ref'], row['from_query_ref'])])
                    self.assertEqual(row['endpoints']['to'], rows[(row['view_ref'], row['to_query_ref'])])
                    compared += 1
        self.assertGreater(compared, 150)

    def test_independent_variables_are_not_one_shared_variable(self):
        """W2・LC-9：同じ二つの端点の領域から、共有参照（alias）と独立な変数では別の関係が出る。P2-mは常に独立な変数。"""
        for name, shared in [('L02', ['equal']), ('L03', ['equal'])]:
            req = fixture(name)
            row = evaluate(req)['results'][0]
            self.assertEqual(row['relation_set'], ['less', 'equal', 'greater'])
            domain = row['endpoints']['from']['converted_domain']
            literal = {'id': 'x', 'quantity_kind_ref': 'k_a', 'unit_ref': 'u_base', 'magnitude': {'kind': 'interval', 'lower': domain['lower'], 'upper': domain['upper'],
                       'lower_closed': domain['lower_closed'], 'upper_closed': domain['upper_closed']}, 'uncertainty': {'kind': 'not_evaluated'},
                       'origin': {'kind': 'literal', 'ref': 'fiction:x'}, 'required_capabilities': ['p2-quantity-literal-draft-1']}
            alias = quantity_runner(q.request([literal], [q.compare('x', 'x')]))
            self.assertEqual(alias['results'][0]['relation_set'], shared)
        point = evaluate(fixture('L01'))['results'][0]
        self.assertEqual(point['relation_set'], ['equal'])         # 点の領域では、二つの組み方が一致する
        self.assertEqual(evaluate(fixture('L06'))['results'][0]['relation_set'], ['equal'])

    def test_context_changes_by_partial_revision_are_not_replaced_by_the_slot(self):
        first = evaluate(fixture('L20'))['results'][0]
        self.assertEqual((first['status'], first['reason_codes']), ('not_comparable', ['different_method']))
        again = evaluate(fixture('L27'))['results'][0]
        self.assertEqual((again['status'], again['relation_set']), ('computed', ['equal']))

    def random_request(self, rng):
        count = rng.randrange(1, 4)
        plan = m.chain(count, rng.choice([8, 9]))
        for literal in (w['literal'] for w in plan['source']['quantities']):
            literal['magnitude'] = deepcopy(rng.choice(MAGNITUDES))
            literal['unit_ref'] = rng.choice(UNITS)
        for record in plan['source']['records']:
            if rng.random() < .25:
                record['method'] = {'kind': 'known', 'ref': 'fiction:method:m', 'version': rng.choice(['1', '2'])}
            if rng.random() < .15:
                record['specimen'] = {'kind': 'known', 'ref': rng.choice(['fiction:specimen:s', 'fiction:specimen:t']), 'version': '1'}
            if rng.random() < .1:
                record['property_ref'] = make.OTHER_PROPERTY
            if rng.random() < .08:
                record['method'] = {'kind': rng.choice(['unknown', 'unspecified'])}
            if rng.random() < .06:
                record['required_capabilities'].append('future:capability')
            if rng.random() < .1:
                record['certainty'] = 'suspected'
        for review in plan['source']['reviews']:
            if rng.random() < .2:
                review['recorded_at'] = m.day(11)
        times = sorted(rng.sample(range(2, 10), 4))
        plan['queries'] = [m.convert(ident=name, target=rng.choice(UNITS), at=t) for name, t in zip('abcd', times)]
        if rng.random() < .15:
            plan['queries'][1]['target_unit_ref'] = 'v_base'
        m.seal(plan)
        comparisons = [make.comparison(f'{x}{y}', start=x, end=y, caps=[make.PROFILE, 'future:capability'] if rng.random() < .05 else None)
                       for x, y in rng.sample([('a', 'b'), ('a', 'c'), ('a', 'd'), ('b', 'c'), ('b', 'd'), ('c', 'd')], rng.randrange(1, 5))]
        return make.request(plan, comparisons)

    def test_seeded_plans_with_contexts_units_and_stops_against_the_oracle(self):
        rng = random.Random(570001)
        statuses = set()
        for _ in range(400):
            result = reference(self.random_request(rng))
            statuses |= {r['status'] for r in result['results']}
        self.assertEqual(statuses, {'computed', 'unassessed', 'not_comparable'})
        for name in ['L02', 'L07', 'L08', 'L20', 'L32', 'L33', 'L37', 'L41', 'L44']:
            reference(fixture(name))

    def test_full_plan_cost_funded_once_and_compare_children_use_twelve(self):
        for name, cost, comparisons, computed in [('L01', 27, 1, 1), ('L04', 34, 1, 1), ('L36', 27, 2, 1), ('L41', 62, 2, 2), ('L44', 71, 3, 3), ('L20', 34, 1, 0), ('L30', 27, 1, 0)]:
            req = fixture(name)
            self.assertEqual(oracle.cost(req), 2+cost+18*comparisons)
            seen, compared = [], []

            def tracked(child):
                seen.append(child['budget']['max_steps'])
                out = child_runner(child)
                self.assertEqual(out['steps_used'], cost)
                return out

            def counted(child):
                compared.append(child['budget']['max_steps'])
                out = quantity_runner(child)
                self.assertEqual(out['steps_used'], 12)
                return out
            with patch('med_dsl.longitudinal.run_temporal_measurements', side_effect=tracked), patch('med_dsl.longitudinal.run_quantities', side_effect=counted):
                result = reference(req)
            self.assertEqual(seen, [cost])
            self.assertEqual(compared, [12]*computed)
            self.assertEqual(result['steps_used'], 2+cost+18*comparisons)
        with patch('med_dsl.longitudinal.run_temporal_measurements', side_effect=AssertionError('unfunded child')):
            self.assertEqual(evaluate(fixture('B05-plan'))['status'], 'resource_limit')
        rng = random.Random(570002)
        for _ in range(30):
            reference(self.random_request(rng))

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-longitudinal',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['L01', 'L36', 'L41', 'L43', 'L44', 'L30', 'L50']:
            req = fixture(name)
            full_req = deepcopy(req)
            full_req['budget'] = {'max_steps': 100000}
            full = evaluate(full_req)
            for maximum in range(full['steps_used']+2):
                req['budget']['max_steps'] = maximum
                out = evaluate(req)
                self.assertLessEqual(out['steps_used'], maximum)
                for row, done in zip(out['results'], full['results']):
                    if row['assessment_complete']:
                        self.assertEqual(row, done)
                    else:
                        for key in FIELDS:
                            self.assertIsNone(row[key], (name, maximum, key))
                if out['status'] == 'resource_limit':
                    self.assertEqual(out['certificate']['status'], 'not_certified')

    def test_child_partial_and_later_row_resource_failure_are_atomic(self):
        req = fixture('L43')

        def stopped(child):
            out = child_runner(child)
            out.update(status='resource_limit', reason_codes=['injected_child_limit'])
            return out
        with patch('med_dsl.longitudinal.run_temporal_measurements', side_effect=stopped):
            out = evaluate(req)
        self.assertEqual((out['status'], out['steps_used'], out['reason_codes']), ('resource_limit', 28, ['injected_child_limit']))
        for row in out['results']:
            self.assertEqual([row[key] for key in FIELDS], [None]*5)
        calls = []

        def second(request):
            calls.append(request)
            if len(calls) == 2:
                raise Problem('injected_row_limit', status='resource_limit')
            return quantity_runner(request)
        with patch('med_dsl.longitudinal.run_quantities', side_effect=second):
            out = evaluate(req)
        self.assertEqual((out['status'], out['steps_used']), ('resource_limit', 1+27+36))
        self.assertEqual(out['results'][0]['relation_set'], ['equal'])
        self.assertEqual([out['results'][1][key] for key in FIELDS], [None]*5)
        self.assertEqual(out['results'][1]['reason_codes'], ['injected_row_limit'])
        self.assertEqual(out['incomplete'], [{'comparison': 'c2', 'reason_codes': ['injected_row_limit']}])
        self.assertEqual(out['certificate']['status'], 'not_certified')

        def wrong_cost(child):
            out = child_runner(child)
            out['steps_used'] -= 1
            return out
        with patch('med_dsl.longitudinal.run_temporal_measurements', side_effect=wrong_cost):
            self.assertEqual(evaluate(fixture('L01'))['reason_codes'], ['temporal_measurement_cost_mismatch'])

        def wrong_compare(request):
            out = quantity_runner(request)
            out['steps_used'] = 11
            return out
        with patch('med_dsl.longitudinal.run_quantities', side_effect=wrong_compare):
            self.assertEqual(evaluate(fixture('L01'))['reason_codes'], ['quantity_compare_cost_mismatch'])

        def undone(request):
            out = quantity_runner(request)
            out['results'][0].update(status='unassessed', reason_codes=['injected_stop'])
            return out
        with patch('med_dsl.longitudinal.run_quantities', side_effect=undone):
            row = evaluate(fixture('L01'))['results'][0]
        self.assertEqual((row['status'], row['reason_codes'], row['relation_set'], row['comparison_evidence']), ('unassessed', ['injected_stop'], None, None))

    def test_the_input_limit_of_the_compare_stops_instead_of_switching_routes(self):
        """W6・LC-12：P2-iは計算できるが、導出リテラルがP2-fの63bit上限を超えると、元のリテラルへ切り替えず止まる。"""
        req = fixture('L50')
        direct = deepcopy(req['temporal_measurement_plan'])
        direct['budget'] = {'max_steps': 100000}
        row = evaluate(direct)['results'][0]
        self.assertEqual(row['status'], 'computed')
        self.assertEqual(row['converted_domain']['lower'], {'numerator': 10*2**62, 'denominator': 1})
        self.assertGreater(10*2**62, 2**63)
        calls = []

        def counted(request):
            calls.append([quantity['id'] for quantity in request['quantities']])
            return quantity_runner(request)
        with patch('med_dsl.longitudinal.run_quantities', side_effect=counted):
            out = evaluate(req)
        self.assertEqual(calls, [['endpoint:from', 'endpoint:to']])
        self.assertEqual((out['status'], out['reason_codes'], out['steps_used']), ('resource_limit', ['rational_integer_limit'], 46))
        original = deepcopy(direct['source']['quantities'][0]['literal'])
        both = quantity_runner(q.request([dict(original, id='x'), dict(original, id='y')], [q.compare('x', 'y')]))
        self.assertEqual(both['results'][0]['relation_set'], ['equal'])        # 元のリテラルどうしなら比較できる
        for name, status in [('L51', 'ok'), ('L52', 'ok'), ('L53', 'resource_limit')]:
            self.assertEqual(evaluate(fixture(name))['status'], status)
        # 63bitの境界：分子 2^63-1 は通り、導出で超える組み合わせは止まる。分母も同じ。
        edge = 2**63-1
        for magnitude, unit, targets, stops in [(q.point(edge), 'u_base', ('u_base', 'u_base'), False), (q.point(edge), 'u_ten', ('u_base', 'u_base'), True),
                                                 (q.point(edge), 'u_ten', ('u_ten', 'u_ten'), False), (q.point(1, 2**62), 'u_base', ('u_third', 'u_base'), True),
                                                 (q.point(1, 2**62-1), 'u_base', ('u_third', 'u_third'), False), (q.point(3, 2**62), 'u_third', ('u_base', 'u_base'), False)]:
            req = make.request(make.pair(magnitude=magnitude, unit=unit, targets=targets))
            out = reference(req)
            self.assertEqual(out['status'], 'resource_limit' if stops else 'ok', (magnitude, unit, targets))

    def test_static_validation_hashes_pins_limits_and_native_refusals(self):
        for path in DIRECTORY.glob('n*.json'):
            req = json.loads(path.read_text())['request']
            original = deepcopy(req)
            before = evaluate(req)
            if path.name.startswith('n11-budget') or 'budget' not in req:
                continue
            for budget in [0, 1, 7]:
                req['budget'] = {'max_steps': budget}
                out = evaluate(req)
                self.assertEqual((out['status'], out['reason_codes']), (before['status'], before['reason_codes']), path.name)
            req['budget'] = original['budget']
            self.assertEqual(req, original)
        for field in ['comparison_policy', 'required_capabilities', 'from_query_ref']:
            req = make.request()
            req['comparisons'][0][field] = None
            self.assertEqual(evaluate(req)['status'], 'invalid_input')
        original = Path.read_bytes
        for filename in ['longitudinal_spec.json', 'temporal_measurement_spec.json', 'quantity_spec.json']:
            def corrupt(path):
                return b'{}' if path.name == filename else original(path)
            with patch.object(Path, 'read_bytes', corrupt):
                self.assertEqual(evaluate(make.request())['reason_codes'], ['native_spec_mismatch'])
        req = make.request()
        req['padding'] = 'x'*1048576
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        req = make.request()
        nested = None
        for _ in range(65):
            nested = [nested]
        req['padding'] = nested
        self.assertEqual(evaluate(req)['status'], 'resource_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req = fixture('L36')
        paths = []

        def walk(value, path):
            paths.append(path)
            if type(value) is dict:
                for key, item in value.items():
                    walk(item, path+[key])
            elif type(value) is list:
                for key, item in enumerate(value):
                    walk(item, path+[key])
        walk(req, [])
        for path in paths:
            for value in [None, False, 0, '', [], {}]:
                copy = deepcopy(req)
                if path:
                    target = copy
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = value
                else:
                    copy = value
                self.assertIn(evaluate(copy)['status'], ['ok', 'invalid_input', 'unsupported_profile', 'resource_limit'])

    def test_upstream_static_negatives_are_never_repaired(self):
        manifest = json.loads((ROOT/'examples/p2-temporal-measurement/manifest.json').read_text())
        checked = 0
        for entry in manifest['files']:
            if not entry['path'].startswith('n'):
                continue
            child = json.loads((ROOT/'examples/p2-temporal-measurement'/entry['path']).read_text())['request']
            if 'budget' not in child:
                continue
            child = deepcopy(child)
            child['budget'] = {'max_steps': 0}
            expected = evaluate(child)
            if expected['status'] not in ('invalid_input', 'unsupported_profile'):
                continue
            req = make.request(plan=child, comparisons=[make.comparison(start='q', end='q')], budget=0)
            with patch('med_dsl.longitudinal.run_temporal_measurements', side_effect=AssertionError('invalid plan executed')):
                out = evaluate(req)
            self.assertEqual(out['status'], expected['status'], entry['path'])
            self.assertNotIn('results', out)
            checked += 1
        self.assertGreater(checked, 40)
        req = make.request()
        plan = req['temporal_measurement_plan']
        import gen_measurement_fixtures as old
        plan['source']['reviews'][0]['record_sha256'] = old.record_hash(plan['source'], plan['source']['records'][0])
        self.assertEqual(evaluate(req)['reason_codes'], ['review_record_hash_mismatch'])

    def test_order_snapshot_future_additions_and_input_immutability(self):
        base = fixture('L44')
        before = deepcopy(base)
        first = reference(base)
        self.assertEqual(base, before)
        self.assertEqual(reference(base), first)
        shuffled = deepcopy(base)
        plan = shuffled['temporal_measurement_plan']
        for key in ('slots', 'quantities', 'records', 'reviews'):
            plan['source'][key].reverse()
        for key in ('views', 'queries'):
            plan[key].reverse()
        shuffled['comparisons'].reverse()
        second = reference(shuffled)
        self.assertNotEqual(first['input_sha256'], second['input_sha256'])
        for a, b in zip(first['results'], second['results']):
            self.assertEqual((a['relation_set'], a['endpoints']['from']['binding_evidence']['selected'], a['comparison_evidence']['source_sha256']),
                             (b['relation_set'], b['endpoints']['from']['binding_evidence']['selected'], b['comparison_evidence']['source_sha256']))
        now, future = evaluate(fixture('L01'))['results'][0], evaluate(fixture('L40'))['results'][0]
        self.assertEqual((now['relation_set'], now['endpoints']['from']['binding_evidence']['selected'], now['endpoints']['to']['binding_evidence']['selected']),
                         (future['relation_set'], future['endpoints']['from']['binding_evidence']['selected'], future['endpoints']['to']['binding_evidence']['selected']))
        self.assertNotEqual(now['comparison_evidence']['source_sha256'], future['comparison_evidence']['source_sha256'])
        earlier, later = evaluate(fixture('L41'))['results']
        self.assertEqual((earlier['relation_set'], later['relation_set']), (['equal'], ['less']))
        self.assertEqual(earlier['endpoints']['from']['binding_evidence']['selected'], earlier['endpoints']['to']['binding_evidence']['selected'])

    def test_ai_origin_old_profiles_and_no_clinical_labels(self):
        out = reference(fixture('L45'))
        selected = out['results'][0]['endpoints']['to']['binding_evidence']['selected'][0]
        self.assertEqual((selected['record_origin']['kind'], selected['quantity_origin']['kind']), ('ai_candidate', 'ai_candidate'))
        self.assertEqual((out['clinical_confirmation'], out['clinical_assertions_added'], out['clinical_significance'], out['time_correlation_assumed']), ('not_evaluated', [], 'not_evaluated', False))
        self.assertEqual({key: out['certificate'][key] for key in ('status', 'evidence_level', 'scope', 'reason_codes')},
                         {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'scope': None,
                          'reason_codes': ['independent_time_variables', 'no_clinical_significance_claim']})
        import gen_display_fixtures as display
        req = make.request()
        req['temporal_measurement_plan'] = display.request()['measurement_plan']
        self.assertEqual(evaluate(req)['status'], 'unsupported_profile')
        import gen_temporal_display_fixtures as projected
        old = projected.request()
        self.assertEqual(evaluate(old)['status'], 'ok')
        forbidden = {'delta', 'difference', 'trend', 'improved', 'worsened', 'increase', 'decrease', 'change_rate', 'significance'}

        def keys_and_text(value):
            if type(value) is dict:
                for key, item in value.items():
                    yield key
                    yield from keys_and_text(item)
            elif type(value) is list:
                for item in value:
                    yield from keys_and_text(item)
            elif type(value) is str:
                yield value
        for name in ['L01', 'L04', 'L07', 'L20', 'L44']:
            words = set(keys_and_text(evaluate(fixture(name))))
            self.assertFalse(forbidden & words, (name, forbidden & words))

    def test_checker_detects_early_values_and_certificates(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('relation_set', []), ('context_differences', []), ('endpoints', {}), ('certain_relation', False)]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('longitudinal', make.request(), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', make.request(), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        mutants = [
            ('alias', '_assess', "'left_ref': 'endpoint:from', 'right_ref': 'endpoint:to'", "'left_ref': 'endpoint:from', 'right_ref': 'endpoint:from'", 'L02'),
            ('direction_swapped', '_assess', "_derived('endpoint:from', ends['from'], quantities, units['from']), _derived('endpoint:to', ends['to'], quantities, units['to'])",
             "_derived('endpoint:from', ends['to'], quantities, units['to']), _derived('endpoint:to', ends['from'], quantities, units['from'])", 'L04'),
            ('context_skipped', '_assess', 'if differences:', 'if False:', 'L20'),
            ('slot_first_record_context', '_assess', "chosen = {name: records[end['binding_evidence']['selected'][0]['record_ref']] for name, end in ends.items()}",
             "chosen = {name: records['A'] for name, end in ends.items()}", 'L20'),
            ('latest_record_context', '_assess', "chosen = {name: records[end['binding_evidence']['selected'][0]['record_ref']] for name, end in ends.items()}",
             "chosen = {name: records[sorted(records)[-1]] for name, end in ends.items()}", 'L28'),
            ('reasons_from_one_endpoint', '_assess', "sorted(set(ends['from']['reason_codes']) | set(ends['to']['reason_codes']))", "sorted(set(ends['from']['reason_codes']))", 'L32'),
            ('stopped_endpoint_compared', '_assess', "if any(end['status'] != 'computed' for end in ends.values()):", 'if False:', 'L30'),
            ('capability_gate_removed', '_assess', "if set(comparison['required_capabilities']) - {LONGITUDINAL_PROFILE}:", 'if False:', 'L35'),
            ('unit_ignored', '_derived', "'unit_ref': unit,", "'unit_ref': 'u_base',", 'L13'),
            ('interval_collapsed_to_point', '_derived', "if domain['lower'] == domain['upper']:", 'if True:', 'L02'),
            ('certain_from_first', '_assess', "'certain_relation': value['certain_relation']", "'certain_relation': value['relation_set'][0]", 'L02'),
            ('assumptions_dropped', '_assess', "'assumptions': list(ASSUMPTIONS)", "'assumptions': []", 'L01'),
            ('direction_label', '_assess', "'direction': 'from_relative_to_to'", "'direction': 'to_relative_to_from'", 'L01'),
            ('fallback_to_original_literals', '_assess', '    out = run_quantities(request)\n', '''    try:
        out = run_quantities(request)
    except Problem:
        request['quantities'] = [dict(deepcopy(quantities[ends[name]['binding_evidence']['selected'][0]['quantity_ref']['ref']]['literal']), id=ident)
                                 for name, ident in (('from', 'endpoint:from'), ('to', 'endpoint:to'))]
        out = run_quantities(request)
''', 'L50'),
            ('order_unchecked', '_validate', "if not start['target_at'] < end['target_at']:", 'if False:', 'N03-reversed'),
            ('equal_time_accepted', '_validate', "if not start['target_at'] < end['target_at']:", "if not start['target_at'] <= end['target_at']:", 'N03-equal-time'),
            ('slot_unchecked', '_validate', "if start['slot_ref'] != end['slot_ref']:", 'if False:', 'N04'),
            ('policy_unchecked', '_validate', "if comparison['comparison_policy'] != POLICY:", 'if False:', 'N05-policy'),
            ('own_capability_unchecked', '_validate', 'if LONGITUDINAL_PROFILE not in comparison[\'required_capabilities\']:', 'if False:', 'N06-missing'),
            ('child_prepayment_removed', 'run_longitudinal', '        for _ in range(cost):\n            budget.tick()\n', '', 'L01'),
            ('completion_fee_removed', 'run_longitudinal', "        current, stage = None, 'completion'\n        budget.tick()\n", "        current, stage = None, 'completion'\n", 'B01-46'),
            ('certified', 'run_longitudinal', "'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'", 'L01'),
        ]
        for ident, name, old, new, case in mutants:
            source = inspect.getsource(getattr(native, name))
            self.assertEqual(source.count(old), 1, ident)
            namespace = dict(vars(native))
            exec(compile(source.replace(old, new), f'<longitudinal-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-longitudinal-request-draft-1'][:3], namespace['run_longitudinal'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-longitudinal-request-draft-1': surface}):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:                      # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        for ident, attribute, value, case in [('fee_reduced', 'ROW_FEE', 6, 'L01'), ('method_ignored', 'CONTEXT_REASONS', native.CONTEXT_REASONS[1:], 'L20'),
                                              ('property_ignored', 'CONTEXT_REASONS', (native.CONTEXT_REASONS[0], native.CONTEXT_REASONS[2]), 'L24'),
                                              ('specimen_ignored', 'CONTEXT_REASONS', native.CONTEXT_REASONS[:2], 'L22'), ('quantity_reserve_reduced', 'COMPARE_RESERVE', 11, 'L01')]:
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            with patch.object(native, attribute, value):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:
                    bad = [repr(error)]
            self.assertTrue(bad, ident)


if __name__ == '__main__':
    unittest.main()
