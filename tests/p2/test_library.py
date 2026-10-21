"""P2-o：手指定期待、別計算との比較、要求の版の差（K14）、AI候補、出力先の追加、継承した規則と元の拡張との差分、共通予算。"""
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
from med_dsl import evaluate, host, clinical_library as native
from med_dsl.model import Problem
from med_dsl.quantity import run_quantities as quantity_runner
from med_dsl.temporal_measurement import run_temporal_measurements as child_runner
import gen_library_fixtures as make
import gen_temporal_display_fixtures as projected
import gen_longitudinal_fixtures as longitudinal
import library_oracle as oracle
import p2_checks
m, q = make.m, make.q
DIRECTORY = ROOT/'examples/p2-library'
FIELDS = native.VALUE_FIELDS
AI = {'kind': 'ai_candidate', 'ref': 'fiction:ai:A2'}
CONTEXTS = [make.METHOD, make.UNKNOWN, {'kind': 'unspecified'}]
PROFILES = [make.PA1, make.line('2', places=0), make.line('3', unit='u_ten', places=2), make.PB1, make.PB2, make.PB3, make.exchange('4', ('method',), form='single_point'),
            make.PC1, make.trend('2', ('property',)), make.trend('3', ('method',)), make.PE1]
MAGNITUDES = [q.point(n, d) for n, d in [(-3, 2), (0, 1), (1, 2), (2, 1), (5, 4), (27, 20)]] + [q.interval(a, b, lc, uc) for a, b in [(0, 1), (1, 2), (2, 3)] for lc in (True, False) for uc in (True, False)]


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def compare_row(row, expected, context=None):
    """実装の行を、別計算の期待と照合する。"""
    if (row['status'], row['reason_codes'], row['assessment_complete']) != (expected['status'], expected['reasons'], True):
        raise AssertionError((context, row['status'], row['reason_codes'], expected['status'], expected['reasons']))
    if row['requests'] != expected['requests']:
        raise AssertionError((context, 'requests', row['requests'], expected['requests']))
    if row['output'] != expected['output'] or row['flows'] != expected['flows']:
        raise AssertionError((context, 'output', row['output'], expected['output']))
    if [(e['element'], e['state']) for e in row['elements']] != [(e['element'], e['state']) for e in expected['elements']]:
        raise AssertionError((context, 'elements', row['elements'], expected['elements']))
    if expected['selection'] is None:
        if row['selection'] is not None:
            raise AssertionError((context, 'selection', row['selection']))
    elif 'record_ref' in expected['selection']:
        if (row['selection']['record_ref'], row['selection']['target_at']) != (expected['selection']['record_ref'], expected['selection']['target_at']):
            raise AssertionError((context, 'selection', row['selection']))
    else:
        for end, want in expected['selection'].items():
            if (row['selection'][end]['record_ref'], row['selection'][end]['target_at']) != (want['record_ref'], want['target_at']):
                raise AssertionError((context, 'selection', end, row['selection']))


def reference(req):
    result = evaluate(req)
    if result['status'] != 'ok':
        raise AssertionError(result)
    for row, query in zip(result['results'], sorted(req['queries'], key=lambda x: x['id'])):
        compare_row(row, oracle.row(req, query), query['id'])
    if result['steps_used'] != oracle.cost(req):
        raise AssertionError((result['steps_used'], oracle.cost(req)))
    return result


def variants():
    """文脈（method・specimen の状態）× 保留中の訂正（なし／AI 由来／人由来）の全数の台帳。"""
    for method, specimen, pending in product(CONTEXTS, CONTEXTS, ('none', 'ai', 'human')):
        ops = [make.rec(method=method, specimen=specimen), make.confirm('A')]
        if pending != 'none':
            ops.append(make.fix('A2', ['A'], origin=AI if pending == 'ai' else {'kind': 'observed', 'ref': 'fiction:library:origin:A2'}))
        yield (method, specimen, pending), ops


def random_request(rng):
    ops, count = [], rng.randrange(1, 4)
    spans = [m.span(1, 10), m.span(4, 6), m.span(5, 6)]
    for index in range(count):
        ident = 'ABC'[index]
        change = dict(method=rng.choice(CONTEXTS), specimen=rng.choice(CONTEXTS), value=make.value(rng.choice(MAGNITUDES), rng.choice(['u_base', 'u_ten', 'u_third', 'u_half'])),
                      validity=spans[index], recorded_at=m.day([2, 6, 8][index]))
        if rng.random() < .1:
            change['property_ref'] = 'fiction:measurement:property:A-other@1'
        if rng.random() < .1:
            change['origin'] = AI
        if rng.random() < .15:
            change['observer'] = rng.choice([{'kind': 'human', 'ref': 'fiction:human:observer'}, {'kind': 'device', 'ref': 'fiction:device:meter'}])
        if rng.random() < .1:
            change['certainty'] = 'suspected'
        if rng.random() < .06:
            change['capabilities'] = ['future:capability']
        if count == 1 and rng.random() < .15:                                 # 訂正は有界な区間どうしにだけ許される（P2-i）。unknown は単独の記録だけ
            change['validity'] = {'kind': rng.choice(['unknown', 'unspecified'])}
        ops.append(make.rec(ident, **change) if index == 0 else make.fix(ident, [ 'ABC'[index-1]], **change))
        if rng.random() < .85:
            ops.append(make.confirm(ident, [3, 7, 9][index] + (rng.randrange(0, 3) if rng.random() < .3 else 0)))
    destinations = rng.sample(PROFILES, rng.randrange(1, 5))
    queries = []
    for number in range(rng.randrange(1, 5)):
        profile = rng.choice(destinations)
        if profile['output']['kind'] == 'trend':
            start, end = sorted(rng.sample(range(1, 11), 2))
            queries.append(make.between(f'q{number}', profile, start, end, 'v'))
        else:
            queries.append(make.single(f'q{number}', profile, rng.randrange(1, 12), 'v'))
    return make.request(ops, queries=queries, destinations=destinations, views=[{'id': 'v', 'as_of': m.day(rng.choice([4, 8, 10]))}])


def independent_record_hash(ledger, record):
    payload = {'binding_profile': 'p2-temporal-measurement-draft-1', 'binding_spec_sha256': m.SPEC, 'source_ref': ledger['ref'], 'record': record}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class LibraryTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'O': 44, 'N': 8, 'B': 4})
        self.assertEqual(len(manifest['files']), 147)
        declaration = json.loads((ROOT/'extensions/p2-clinical-library.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'CL-{i}' for i in range(1, 14)})
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
        report = p2_checks.suite_report('p2-library', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (147, 2527, []))

    def test_selection_stops_and_requests_against_the_oracle(self):
        rows = 0
        seen = set()
        for _, ops in variants():
            for target in (3, 5, 11):
                req = make.request(ops, destinations=[make.PA1, make.PB1, make.PB2, make.PB3, make.PC1],
                                   queries=[make.single('a', make.PA1, target), make.single('b1', make.PB1, target), make.single('b2', make.PB2, target),
                                            make.single('b3', make.PB3, target), make.between('t', make.PC1, 3, max(target, 4))])
                result = reference(req)
                rows += len(result['results'])
                seen |= {(r['status'], tuple(r['reason_codes'])) for r in result['results']}
        self.assertEqual(rows, 27*3*5)
        for wanted in [('satisfied', ()), ('needs_information', ('required_information_missing',))]:
            self.assertIn(wanted, seen)
        rng = random.Random(640001)
        statuses = set()
        for _ in range(400):
            result = reference(random_request(rng))
            statuses |= {r['status'] for r in result['results']}
        self.assertEqual(statuses, {'satisfied', 'needs_information', 'not_representable', 'unassessed'})
        for name in ['O01', 'O03', 'O13', 'O14', 'O23', 'O24', 'O30', 'O41', 'O42', 'O46', 'O60']:
            reference(fixture(name))

    def test_observer_passes_through_and_selection_shows_it_only_when_present(self):
        """P2-r・CL-13：操作の observer は台帳の記録へそのまま渡り、選択の根拠に、選ばれた記録が持つときだけ出る。確認の操作は持たない。"""
        human, device = {'kind': 'human', 'ref': 'fiction:human:observer'}, {'kind': 'device', 'ref': 'fiction:device:meter'}
        for first, second in product([None, human, device], [None, human, device]):
            ops = [make.rec(), make.confirm('A'), make.fix('B', ['A'], validity=m.span(4, 6), value=make.value(q.point(3))), make.confirm('B', 7)]
            for index, observer in ((0, first), (2, second)):
                if observer:
                    ops[index]['observer'] = deepcopy(observer)
            req = make.request(ops, destinations=[make.PB1], queries=[make.single('q3', make.PB1, 3), make.single('q5', make.PB1, 5)])
            result = reference(req)
            for row, observer in zip(result['results'], (first, second)):
                if observer:
                    self.assertEqual(row['selection']['record_observer'], observer)
                else:
                    self.assertNotIn('record_observer', row['selection'])
            records = {r['id']: r for r in result['ledger']['records']}
            self.assertEqual(records['A'].get('observer'), first)
            self.assertEqual(records['B'].get('observer'), second)
        ops = [make.rec(), make.confirm('A')]
        ops[1]['observer'] = deepcopy(human)
        self.assertEqual(evaluate(make.request(ops))['reason_codes'], ['unknown_field'])
        for value in (None, 'x', {}, {'kind': 'robot', 'ref': 'x'}, {'kind': 'human', 'ref': ''}):
            self.assertEqual(evaluate(make.request([make.rec(observer=value), make.confirm('A')]))['status'], 'invalid_input', value)

    def test_requirement_versions_and_information_requests(self):
        """V3・CL-10：要求の版 v1→v2→v3 の依頼の数の差は、選択された記録で新しく要求される欄が known でない数に等しい。情報が揃えば0。"""
        for (method, specimen, pending), ops in variants():
            req = make.request(ops, destinations=[make.PB1, make.PB2, make.PB3], queries=[make.single('b1', make.PB1), make.single('b2', make.PB2), make.single('b3', make.PB3)])
            counts = [len(r['requests']) for r in evaluate(req)['results']]
            missing_method, missing_specimen = int(method['kind'] != 'known'), int(specimen['kind'] != 'known')
            self.assertEqual(counts, [0, missing_method, missing_method+missing_specimen], (method, specimen, pending))
            for result in evaluate(req)['results']:
                if result['status'] == 'needs_information':
                    self.assertTrue(result['requests'])
                else:
                    self.assertEqual(result['requests'], [])
            self.assertEqual(evaluate(req)['results'][0]['status'], 'satisfied')
        # 答えとして1つの確認（候補があるとき）または訂正と確認（ないとき）を足すと満たされ、元の記録は変わらない
        ops = [make.rec(method=make.UNKNOWN), make.confirm('A')]
        answered = ops+[make.fix('A3', ['A']), make.confirm('A3', 7)]
        before, after = evaluate(make.request(ops, destinations=[make.PB2], queries=[make.single('b2', make.PB2)])), \
            evaluate(make.request(answered, destinations=[make.PB2], queries=[make.single('b2', make.PB2)]))
        self.assertEqual((before['results'][0]['status'], after['results'][0]['status']), ('needs_information', 'satisfied'))
        self.assertEqual(after['ledger']['records'][0], before['ledger']['records'][0])

    def test_ai_candidates_never_satisfy_a_requirement_and_nothing_is_inferred(self):
        for (method, specimen, pending), ops in variants():
            req = make.request(ops, destinations=[make.PB3], queries=[make.single('b3', make.PB3)])
            result = evaluate(req)
            row = result['results'][0]
            self.assertEqual(result['inferred_information'], [])
            self.assertEqual(result['clinical_assertions_added'], [])
            if pending != 'none':
                self.assertEqual(row['selection']['record_ref'], 'A')                                  # 保留中の訂正は選ばれない
            expected_met = method['kind'] == 'known' and specimen['kind'] == 'known'
            self.assertEqual(row['status'], 'satisfied' if expected_met else 'needs_information')
            for request in row['requests']:
                for candidate in request['candidates']:
                    self.assertEqual(candidate['record_ref'], 'A2')
                    self.assertEqual(candidate['origin_kind'], 'ai_candidate' if pending == 'ai' else 'observed')
                if request['candidates']:
                    self.assertEqual(request['action'], 'confirm_candidate')
                else:
                    self.assertEqual(request['action'], 'observe_and_record')
        confirmed = evaluate(fixture('O14'))['results'][0]
        self.assertEqual((confirmed['status'], confirmed['output']['origin']), ('satisfied', {'record': 'ai_candidate', 'quantity': 'ai_candidate'}))
        words = {'diagnosis', 'treatment', 'trend_label', 'improved', 'worsened', 'significance', 'delta'}

        def walk(value):
            if type(value) is dict:
                for key, item in value.items():
                    yield key
                    yield from walk(item)
            elif type(value) is list:
                for item in value:
                    yield from walk(item)
            elif type(value) is str:
                yield value
        for name in ['O01', 'O11', 'O13', 'O14', 'O40', 'O60']:
            self.assertFalse(words & set(walk(evaluate(fixture(name)))), name)
        result = evaluate(fixture('O01'))
        self.assertEqual({k: result['certificate'][k] for k in ('status', 'evidence_level', 'scope')}, {'status': 'not_certified', 'evidence_level': 'known_policy_change', 'scope': None})

    def test_outputs_keep_provenance_and_flows(self):
        """V5・CL-12：出力がある行には必ず選択の出所があり、exchange は出自の種類と人の確認を持つ。流れの表が出力の種類と一致する。"""
        rng = random.Random(640002)
        checked = 0
        for _ in range(300):
            result = evaluate(random_request(rng))
            for row in result['results']:
                if row['output'] is not None:
                    checked += 1
                    self.assertIsNotNone(row['selection'])
                    self.assertEqual(row['status'], 'satisfied')
                    if 'converted_domain' in row['output']:
                        self.assertIn('human_confirmed', row['output'])
                        self.assertEqual(set(row['output']['origin']), {'record', 'quantity'})
                        self.assertEqual(row['flows'], oracle.FLOWS['exchange'])
                    elif 'text' in row['output']:
                        self.assertEqual(row['flows'], oracle.FLOWS['line'])
                    else:
                        self.assertEqual(row['flows'], oracle.FLOWS['trend'])
                if row['status'] != 'satisfied':
                    self.assertIsNone(row['output'])
                if row['status'] == 'not_representable':
                    self.assertEqual(row['flows']['retained'], [])
                    self.assertTrue(row['flows']['lost'])
        self.assertGreater(checked, 100)
        for name in ['O01', 'O40', 'O10']:
            for row in evaluate(fixture(name))['results']:
                selection = row['selection']
                ends = selection.values() if 'from' in selection else [selection]
                for end in ends:
                    self.assertTrue({'record_ref', 'record_sha256', 'review_refs', 'as_of', 'target_at', 'record_origin', 'quantity_origin', 'validity'} <= set(end))

    def test_a_new_destination_needs_only_a_profile(self):
        """V2・Q1：出力先を足すことは要求プロファイルのデータの追加だけ。出力先の名前（id）で処理は分岐しない。"""
        source = inspect.getsource(native)
        for name in ('dest:record-line', 'dest:numeric-exchange', 'dest:trend-summary', 'dest:registry-entry', 'registry', 'numeric-exchange'):
            self.assertNotIn(name, source)
        base = evaluate(fixture('O50'))['results'][0]
        self.assertEqual(base['status'], 'satisfied')
        renamed = deepcopy(fixture('O50'))
        renamed['destinations'][0].update(id='dest:something-else', version='9')
        renamed['queries'][0]['destination_ref'] = {'id': 'dest:something-else', 'version': '9'}
        again = evaluate(renamed)['results'][0]
        for key in ('status', 'reason_codes', 'output', 'flows', 'requests'):
            self.assertEqual(again[key], base[key])
        for template in (make.PA1, make.PB2, make.PC1):                       # 名前を替えても結果の意味は同じ
            req = make.request(destinations=[template], queries=[make.single('q', template)] if template['output']['kind'] != 'trend' else [make.between('q', template)])
            a = evaluate(req)['results'][0]
            other = deepcopy(template)
            other.update(id='dest:renamed', version='42')
            req2 = make.request(destinations=[other], queries=[make.single('q', other)] if other['output']['kind'] != 'trend' else [make.between('q', other)])
            b = evaluate(req2)['results'][0]
            for key in ('status', 'reason_codes', 'output', 'flows', 'requests', 'elements'):
                self.assertEqual(a[key], b[key], (template['id'], key))
        # 新しい出力先を、ライブラリの変更なしに足す：ここで宣言する profile は fixture にない
        invented = {'id': 'dest:invented', 'version': '1', 'output': {'kind': 'exchange'},
                    'elements': [{'element': 'value', 'form': 'single_point', 'unit_ref': 'u_half'}, {'element': 'context', 'field': 'specimen', 'requires': 'known'}]}
        row = evaluate(make.request(destinations=[invented], queries=[make.single('q', invented)]))['results'][0]
        self.assertEqual((row['status'], row['output']['converted_domain']['lower']), ('satisfied', {'numerator': 40, 'denominator': 1}))
        for change in (lambda p: p['elements'].append({'element': 'laterality'}), lambda p: p['output'].update(kind='form_letter')):
            profile = deepcopy(invented)
            change(profile)
            self.assertEqual(evaluate(make.request(destinations=[profile], queries=[make.single('q', invented)]))['status'], 'unsupported_profile')

    def test_order_future_operations_and_input_immutability(self):
        base = fixture('O60')
        before = deepcopy(base)
        first = reference(base)
        self.assertEqual(base, before)
        shuffled = fixture('O61')
        second = reference(shuffled)
        for a, b in zip(first['results'], second['results']):
            for key in ('status', 'reason_codes', 'output', 'flows', 'requests'):
                self.assertEqual(a[key], b[key])
        self.assertEqual([r['selection'] for r in first['results']], [r['selection'] for r in second['results']])
        later = reference(fixture('O62'))
        for a, b in zip(first['results'], later['results']):
            for key in ('status', 'reason_codes', 'output', 'flows', 'requests', 'selection'):
                self.assertEqual(a[key], b[key])
        self.assertNotEqual(first['steps_used'], later['steps_used'])
        self.assertNotEqual(first['temporal_measurement']['source_sha256'], later['temporal_measurement']['source_sha256'])
        rng = random.Random(640003)
        for _ in range(60):                                                   # 参照時点より後の操作は、完成した行を変えない
            req = random_request(rng)
            extra = deepcopy(req)
            extra['library']['operations'] += [make.rec('Z', recorded_at=m.day(12), method=make.UNKNOWN), make.confirm('Z', 13)]
            for a, b in zip(evaluate(req)['results'], evaluate(extra)['results']):
                for key in ('status', 'reason_codes', 'output', 'flows', 'requests', 'selection'):
                    self.assertEqual(a[key], b[key])

    def test_full_plan_cost_funded_once_and_children_use_their_reservation(self):
        for name, total in [('O01', 32), ('O40', 47), ('O41', 54), ('O10', 82), ('O30', 91), ('O60', 97), ('O13', 35), ('O14', 37), ('O46', 52)]:
            req = fixture(name)
            seen, converts, compares = [], [], []

            def tracked(child):
                seen.append(child['budget']['max_steps'])
                out = child_runner(child)
                self.assertEqual(out['steps_used'], child['budget']['max_steps'])
                return out

            def counted(child):
                (compares if child['queries'][0]['kind'] == 'compare' else converts).append(child['budget']['max_steps'])
                out = quantity_runner(child)
                self.assertEqual(out['steps_used'], child['budget']['max_steps'])
                return out
            with patch('med_dsl.clinical_library.run_temporal_measurements', side_effect=tracked), patch('med_dsl.clinical_library.run_quantities', side_effect=counted):
                result = reference(req)
            self.assertEqual(len(seen), 1)
            self.assertEqual(result['steps_used'], total)
            self.assertEqual(set(converts), {8} if converts else set())
            self.assertEqual(set(compares), {12} if compares else set())
        with patch('med_dsl.clinical_library.run_temporal_measurements', side_effect=AssertionError('unfunded child')):
            self.assertEqual(evaluate(fixture('B04-plan'))['status'], 'resource_limit')
        rng = random.Random(640004)
        for _ in range(60):
            req = random_request(rng)
            self.assertEqual(evaluate(req)['steps_used'], oracle.cost(req))

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-library',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['O01', 'O13', 'O40', 'O60', 'O46', 'O03']:
            req = fixture(name)
            full = deepcopy(req)
            full['budget'] = {'max_steps': 100000}
            done = evaluate(full)
            for maximum in range(done['steps_used']+2):
                req['budget']['max_steps'] = maximum
                out = evaluate(req)
                self.assertLessEqual(out['steps_used'], maximum)
                for row, ready in zip(out['results'], done['results']):
                    if row['assessment_complete']:
                        self.assertEqual(row, ready)
                    else:
                        for key in FIELDS:
                            self.assertIsNone(row[key], (name, maximum, key))
                if out['status'] == 'resource_limit':
                    self.assertEqual(out['certificate']['status'], 'not_certified')

    def test_child_partial_and_later_row_resource_failure_are_atomic(self):
        req = fixture('O60')

        def stopped(child):
            out = child_runner(child)
            out.update(status='resource_limit', reason_codes=['injected_child_limit'])
            return out
        with patch('med_dsl.clinical_library.run_temporal_measurements', side_effect=stopped):
            out = evaluate(req)
        self.assertEqual((out['status'], out['steps_used'], out['reason_codes']), ('resource_limit', 50, ['injected_child_limit']))
        for row in out['results']:
            self.assertEqual([row[key] for key in FIELDS], [None]*5)
        calls = []

        def second(request):
            calls.append(request)
            if len(calls) == 2:
                raise Problem('injected_row_limit', status='resource_limit')
            return quantity_runner(request)
        with patch('med_dsl.clinical_library.run_quantities', side_effect=second):
            out = evaluate(req)
        self.assertEqual(out['status'], 'resource_limit')
        self.assertEqual(out['results'][0]['status'], 'satisfied')
        self.assertEqual(out['results'][1]['reason_codes'], ['injected_row_limit'])
        self.assertEqual([out['results'][1][key] for key in FIELDS], [None]*5)
        self.assertEqual(out['incomplete'][0], {'query': 'q2', 'reason_codes': ['injected_row_limit']})
        self.assertEqual(out['certificate']['status'], 'not_certified')

        def wrong_cost(child):
            out = child_runner(child)
            out['steps_used'] -= 1
            return out
        with patch('med_dsl.clinical_library.run_temporal_measurements', side_effect=wrong_cost):
            self.assertEqual(evaluate(fixture('O01'))['reason_codes'], ['temporal_measurement_cost_mismatch'])

        def wrong_convert(request):
            out = quantity_runner(request)
            out['steps_used'] = 7
            return out
        with patch('med_dsl.clinical_library.run_quantities', side_effect=wrong_convert):
            self.assertEqual(evaluate(fixture('O01'))['reason_codes'], ['quantity_convert_cost_mismatch'])
        with patch('med_dsl.clinical_library.run_quantities', side_effect=wrong_convert):
            self.assertEqual(evaluate(fixture('O40'))['reason_codes'], ['quantity_compare_cost_mismatch'])

    def test_static_validation_hashes_pins_limits_and_native_refusals(self):
        for path in DIRECTORY.glob('n*.json'):
            req = json.loads(path.read_text())['request']
            original = deepcopy(req)
            before = evaluate(req)
            if path.name.startswith('n07-budget') or 'budget' not in req:
                continue
            for budget in [0, 1, 7]:
                req['budget'] = {'max_steps': budget}
                out = evaluate(req)
                self.assertEqual((out['status'], out['reason_codes']), (before['status'], before['reason_codes']), path.name)
            req['budget'] = original['budget']
            self.assertEqual(req, original)
        original = Path.read_bytes
        for filename in ['clinical_library_spec.json', 'temporal_measurement_spec.json', 'quantity_spec.json']:
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
        req = fixture('O13')
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

    def test_operations_build_a_ledger_that_the_temporal_measurement_extension_accepts(self):
        """CL-2：操作から組み立てた台帳が、P2-i に受理され、確認の内容 hash が独立に計算した値と一致し、台帳を改ざんすると拒否される。"""
        for name in ['O01', 'O14', 'O30', 'O41', 'O23']:
            result = evaluate(fixture(name))
            ledger = result['ledger']
            plan = {'schema_version': 'p2-temporal-measurement-request-draft-1', 'operation': 'evaluate_temporal_measurements',
                    'consumer': {'profile': m.PROFILE, 'profile_spec_sha256': m.SPEC, 'operations': ['evaluate_temporal_measurements'],
                                 'quantity_profile': m.QPROFILE, 'quantity_profile_spec_sha256': m.QSPEC},
                    'source': deepcopy(ledger), 'views': [{'id': 'v', 'as_of': m.day(8), 'policy_ref': m.POLICY}], 'queries': [m.convert(at=5)], 'budget': {'max_steps': 100000}}
            self.assertEqual(evaluate(plan)['status'], 'ok', name)
            records = {r['id']: r for r in ledger['records']}
            for review in ledger['reviews']:
                self.assertEqual(review['record_sha256'], independent_record_hash(ledger, records[review['record_ref']]), (name, review['id']))
                self.assertEqual(review['reviewer_kind'], 'human')
            for row in result['results']:
                selection = row['selection']
                if selection is None:
                    continue
                for end in (selection.values() if 'from' in selection else [selection]):
                    self.assertEqual(end['record_sha256'], independent_record_hash(ledger, records[end['record_ref']]))
            for tamper in (lambda r: r['specimen'].update(ref='fiction:specimen:other'), lambda r: r.update(certainty='suspected')):
                changed = deepcopy(plan)
                reviewed = next(r for r in changed['source']['records'] if r['id'] == changed['source']['reviews'][0]['record_ref'])
                tamper(reviewed)
                self.assertEqual(evaluate(changed)['reason_codes'], ['review_record_hash_mismatch'], name)
        for key in ('record_sha256', 'quantity_ref', 'quantity_sha256', 'revises'):
            ops = make.std()
            ops[0][key] = 'x'
            self.assertEqual(evaluate(make.request(ops))['reason_codes'], ['unknown_field'], key)

    def test_rounding_and_relations_agree_with_the_restated_extensions(self):
        """CL-7：丸め（P2-j）・関係と文脈の規則（P2-m）・料金（P2-i）を再び述べた部分が、元の拡張の実装と一致する（証人の外の全数・乱数）。"""
        compared = 0
        for n in range(-60, 61, 3):
            for d in (1, 2, 3, 4, 7, 20, 100):
                for places in range(0, 7):
                    mine = evaluate(make.request([make.rec(value=make.value(q.point(n, d), 'u_base')), make.confirm('A')], destinations=[make.line(places=places)],
                                                 queries=[make.single('q', make.line(places=places))]))['results'][0]
                    theirs = evaluate(projected.request(n, d, places))['results'][0]
                    self.assertEqual((mine['output']['text'], mine['output']['coefficient']), (theirs['artifact']['text'], theirs['artifact']['coefficient']), (n, d, places))
                    compared += 1
        self.assertEqual(compared, 41*7*7)
        relations = 0
        for left, right in product(MAGNITUDES, MAGNITUDES):
            ops = [make.rec(value=make.value(left)), make.confirm('A'), make.fix('B', ['A'], validity=m.span(4, 6), value=make.value(right)), make.confirm('B', 7)]
            mine = evaluate(make.request(ops, destinations=[make.PC1], queries=[make.between('t', make.PC1)]))['results'][0]
            plan = longitudinal.chain()
            for index, magnitude in enumerate((left, right)):
                plan['source']['quantities'][index]['literal']['magnitude'] = deepcopy(magnitude)
            theirs = evaluate(longitudinal.request(m.seal(plan)))['results'][0]
            self.assertEqual((mine['output']['relation_set'], mine['output']['certain_relation']), (theirs['relation_set'], theirs['certain_relation']), (left, right))
            relations += 1
        self.assertEqual(relations, len(MAGNITUDES)**2)
        for method in (make.METHOD2, make.METHOD):                              # 文脈の規則：method の version の違いは、P2-m でも contexts_differ に当たる
            ops = [make.rec(), make.confirm('A'), make.fix('B', ['A'], validity=m.span(4, 6), method=method), make.confirm('B', 7)]
            mine = evaluate(make.request(ops, destinations=[make.PC1], queries=[make.between('t', make.PC1)]))['results'][0]
            plan = longitudinal.chain()
            plan['source']['records'][1]['method'] = deepcopy(method)
            theirs = evaluate(longitudinal.request(m.seal(plan)))['results'][0]
            self.assertEqual(mine['status'] == 'not_representable', theirs['status'] == 'not_comparable')
        for name, ledger in [('c01', 'O01'), ('c25', 'O40'), ('c30', 'O41')]:      # 料金 C：P2-i を直接実行した実費と一致する
            direct = json.loads((ROOT/f'examples/p2-temporal-measurement/{name}.json').read_text())['request']
            self.assertEqual(evaluate(direct)['steps_used'], evaluate(fixture(ledger))['temporal_measurement']['reserved_steps'])

    def test_interface_closure_holds_near_the_limits(self):
        """V8：P2-m で見つかった接続面の閉包。P2-i が換算した領域が P2-f の入力の上限（63bit）を超えても、比較は元のリテラルで行うので止まらない。"""
        big = (1 << 63)-1
        for first, second in [(big, big-1), (big, big), (big-1, big)]:
            ops = [make.rec(value=make.value(q.point(first, 1), 'u_ten')), make.confirm('A'),
                   make.fix('B', ['A'], validity=m.span(4, 6), value=make.value(q.point(second, 1), 'u_ten')), make.confirm('B', 7)]
            req = make.request(ops, destinations=[make.PC1, make.PB1, make.PA1], queries=[make.between('t', make.PC1), make.single('e', make.PB1, 5), make.single('l', make.PA1, 5)])
            out = reference(req)
            self.assertEqual([r['status'] for r in out['results']], ['satisfied']*3)
            exchange = out['results'][0]['output']['converted_domain']
            self.assertGreater(exchange['lower']['numerator'].bit_length(), 63)             # 換算した領域は P2-f の入力の上限を超えている
        order = {(big, big-1): ['greater'], (big, big): ['equal'], (big-1, big): ['less']}
        for (first, second), want in order.items():
            ops = [make.rec(value=make.value(q.point(first, 1), 'u_ten')), make.confirm('A'),
                   make.fix('B', ['A'], validity=m.span(4, 6), value=make.value(q.point(second, 1), 'u_ten')), make.confirm('B', 7)]
            out = evaluate(make.request(ops, destinations=[make.PC1], queries=[make.between('t', make.PC1)]))
            self.assertEqual(out['results'][0]['output']['relation_set'], want)
        # 丸めの文字列の上限（64文字）は、入力の上限（256bitの中間値）の内側にあるので、関数への直接の注入でだけ確かめられる（P2-j と同じ）
        with self.assertRaises(Problem) as caught:
            native._round(F(10**64), 0)
        self.assertEqual((caught.exception.code, caught.exception.status), ('display_text_limit', 'resource_limit'))
        with self.assertRaises(Problem):
            native._round(F(2**257), 0)
        self.assertEqual(native._round(F(125, 100), 1), (12, '1.2'))

    def test_checker_detects_early_values_and_certificates(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('requests', []), ('elements', []), ('flows', {}), ('output', {})]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('library', make.request(), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', make.request(), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        mutants = [
            ('context_requirement_skipped', '_context', "met = record[field]['kind'] == 'known'", 'met = True', 'O11'),
            ('guess_by_default', '_context', "met = record[field]['kind'] == 'known'", "met = record[field]['kind'] != 'x'", 'O11'),
            ('candidate_counted', '_context', "if met:\n        return entry, None\n    candidates", "if met or _candidates(state, row, field, at):\n        return entry, None\n    candidates", 'O13'),
            ('single_point_unchecked', '_value', "if element['form'] == 'single_point' and not single:", 'if False:', 'O03'),
            ('dimension_ignored', '_value', "if result['status'] == 'not_comparable':", 'if False:', 'O05'),
            ('vocabulary_ignored', '_value', "if result['status'] == 'unassessed':", 'if False:', 'O06'),
            ('latest_wins', '_select', "request = _request('selection', 'resolve_conflict', records=diagnostics['candidate_refs'][slot])",
             "return {'state': 'met', 'reasons': [], 'record': diagnostics['candidate_refs'][slot][-1], 'requests': []}", 'O23'),
            ('pending_not_asked', '_select', "pending = sorted(key for key in diagnostics['pending_records'] if state['records'][key]['certainty'] == 'confirmed' and _covers(state['records'][key], at))", 'pending = []', 'O21'),
            ('suspected_confirmable', '_select', "state['records'][key]['certainty'] == 'confirmed' and _covers", "_covers", 'O22'),
            ('capability_ignored', '_select', "if 'unknown_capability' in reasons:", 'if False:', 'O25'),
            ('priority_swapped', '_aggregate', "(('unassessed', 'unassessed'), ('unrepresentable', 'not_representable'), ('unmet', 'needs_information'))",
             "(('unassessed', 'unassessed'), ('unmet', 'needs_information'), ('unrepresentable', 'not_representable'))", 'O08'),
            ('unassessed_demoted', '_aggregate', "(('unassessed', 'unassessed'), ('unrepresentable', 'not_representable'), ('unmet', 'needs_information'))",
             "(('unrepresentable', 'not_representable'), ('unmet', 'needs_information'), ('unassessed', 'unassessed'))", 'O09'),
            ('half_up', '_round', 'twice > scaled.denominator or (twice == scaled.denominator and quotient % 2 != 0)', 'twice >= scaled.denominator', 'O02-5-4'),
            ('flows_retained_for_unrepresentable', '_flows', "if status == 'not_representable':", "if status in ('not_representable',) and False:", 'O03'),
            ('contexts_not_compared', '_trend', "if trend['differences']:", 'if False:', 'O42'),
            ('ends_dropped', '_trend', "requests.append(_request(name, 'confirm_candidate' if candidates else 'observe_and_record', record_ref=record_ref, candidates=candidates, ends=sorted(ends)))",
             "requests.append(_request(name, 'confirm_candidate' if candidates else 'observe_and_record', record_ref=record_ref, candidates=candidates, ends=None))", 'O43'),
            ('output_without_selection_check', '_single', "if selection['state'] != 'met':", 'if False:', 'O20'),
            ('requests_on_unsettled', '_single', "requests = requests if status == 'needs_information' else []", 'requests = requests', 'O08'),
            ('origin_lost', '_single', "'origin': {'record': record['origin']['kind'], 'quantity': literal['origin']['kind']}", "'origin': {'record': 'observed', 'quantity': 'literal'}", 'O14'),
            ('observer_dropped', '_ledger', "        if 'observer' in op:\n            record['observer'] = deepcopy(op['observer'])\n", '', 'O70'),
            ('observer_not_shown', '_evidence', "    if 'observer' in record:\n        evidence['record_observer'] = deepcopy(record['observer'])\n", '', 'O71'),
            ('child_prepayment_removed', 'run_library', '        for _ in range(cost):\n            budget.tick()\n', '', 'O01'),
            ('completion_fee_removed', 'run_library', "        current, stage = None, 'completion'\n        budget.tick()\n", "        current, stage = None, 'completion'\n", 'B01-31'),
            ('inferred_information', 'run_library', "'clinical_assertions_added': [], 'inferred_information': []", "'clinical_assertions_added': [], 'inferred_information': ['guess']", 'O01'),
            ('certified', 'run_library', "'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'", 'O01'),
        ]
        for ident, name, old, new, case in mutants:
            source = inspect.getsource(getattr(native, name))
            self.assertEqual(source.count(old), 1, ident)
            namespace = dict(vars(native))
            exec(compile(source.replace(old, new), f'<library-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-library-request-draft-1'][:3], namespace['run_library'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-library-request-draft-1': surface}):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:                       # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        for ident, attribute, value_, case in [('fee_reduced', 'OWN_FEE', 5, 'O01'), ('convert_reserve_reduced', 'CONVERT_RESERVE', 7, 'O01'),
                                               ('compare_reserve_reduced', 'COMPARE_RESERVE', 11, 'O40')]:
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            with patch.object(native, attribute, value_):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        # 選択の探りに使う単位は、選択の結果に影響しない（同値な変更として記録する。検出の対象にはしない）
        for entry in json.loads((DIRECTORY/'manifest.json').read_text())['files']:
            request = json.loads((DIRECTORY/entry['path']).read_text())['request']
            before = evaluate(deepcopy(request))
            with patch.object(native, 'PROBE_UNIT', 'u_ten'):
                after = evaluate(deepcopy(request))
            for result in (before, after):                                  # 子の計画の入力 hash だけが、探りの単位を含むので違う
                if type(result.get('temporal_measurement')) is dict:
                    result['temporal_measurement'].pop('input_sha256', None)
            self.assertEqual(after, before, entry['path'])


if __name__ == '__main__':
    unittest.main()
