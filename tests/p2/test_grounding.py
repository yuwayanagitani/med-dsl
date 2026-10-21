"""P2-p：手指定期待、別計算との比較、有限格子の全数、期間と文脈の列挙、基の行との差分、構造の事実の出典、共通予算、変異。"""
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
from med_dsl import evaluate, host, structure_grounding as native
from med_dsl.model import Problem
from med_dsl.clinical_library import run_library as child_runner
import gen_grounding_fixtures as make
import grounding_oracle as oracle
import p2_checks
import test_library
lib, q = make.lib, make.q
DIRECTORY = ROOT/'examples/p2-grounding'
FIELDS = native.VALUE_FIELDS
STATES = [lib.METHOD, lib.UNKNOWN, {'kind': 'unspecified'}]


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def compare_row(row, expected, context=None):
    """実装の行を、別計算の期待と照合する。"""
    got = (row['status'], row['reason_codes'], row['base_status'], row['assessment_complete'], row['grounding']['state'], row['grounding']['reasons'],
           row['grounding']['projection'], row['grounding']['structure'], row['flows'], row['requests'], row['output'])
    want = (expected['status'], expected['reasons'], expected['base_status'], True, expected['state'], expected['grounding_reasons'],
            expected['projection'], expected['structure'], expected['flows'], expected['requests'], expected['output'])
    if got != want:
        raise AssertionError((context, got, want))
    if [(e['element'], e['state']) for e in row['elements']] != [(e['element'], e['state']) for e in expected['elements']]:
        raise AssertionError((context, 'elements', row['elements'], expected['elements']))
    if expected['selection'] is None:
        if row['selection'] is not None:
            raise AssertionError((context, 'selection', row['selection']))
    elif 'record_ref' in expected['selection']:
        if (row['selection']['record_ref'], row['selection']['target_at']) != (expected['selection']['record_ref'], expected['selection']['target_at']):
            raise AssertionError((context, 'selection', row['selection']))
    else:
        for end, want_end in expected['selection'].items():
            if (row['selection'][end]['record_ref'], row['selection'][end]['target_at']) != (want_end['record_ref'], want_end['target_at']):
                raise AssertionError((context, 'selection', end, row['selection']))


def reference(req):
    result = evaluate(req)
    if result['status'] != 'ok':
        raise AssertionError(result)
    for row, query in zip(result['results'], sorted(req['library_request']['queries'], key=lambda x: x['id'])):
        compare_row(row, oracle.row(req, query), query['id'])
    if result['steps_used'] != oracle.cost(req) or result['library']['reserved_steps'] != oracle.library_cost(req):
        raise AssertionError((result['steps_used'], oracle.cost(req)))
    return result


def magnitude_of(value):
    return q.point(value.numerator, value.denominator)


def interval_of(low, high, lower_closed, upper_closed):
    return make.ivl((low.numerator, low.denominator), (high.numerator, high.denominator), lower_closed, upper_closed)


def points():
    seen, found = set(), []
    for denominator in range(1, 41):
        for numerator in range(-24, 25):
            value = F(numerator, denominator)
            if value not in seen:
                seen.add(value)
                found.append(value)
    return found


def intervals():
    ends = [F(0), F(1, 8), F(1, 3), F(1, 2), F(1), F(4, 3), F(5, 4), F(2)]
    for low, high in product(ends, ends):
        if low < high:
            for closure in product((True, False), repeat=2):
                yield low, high, closure
        elif low == high:
            yield low, high, (True, True)


def record_ops(method=lib.METHOD, specimen=lib.SPECIMEN):
    return [lib.rec(method=method, specimen=specimen), lib.confirm('A')]


def random_grounding(rng):
    while True:
        child = test_library.random_request(rng)
        exchanges = [p for p in child['destinations'] if p['output']['kind'] == 'exchange']
        if exchanges:
            break
    chosen = rng.sample(exchanges, rng.randrange(1, len(exchanges)+1))
    targets = [make.target(p, rng.choice(['quantity', 'range']), rng.sample(['method', 'specimen'], rng.randrange(0, 3)),
                           rng.choice([None, 'undeclared', 'exclusive_end_as_last_second'])) for p in chosen]
    return make.grounding(child, targets)


class GroundingTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'G': 27, 'P': 5, 'C': 6, 'R': 4, 'D': 4, 'N': 12, 'B': 3})
        self.assertEqual(len(manifest['files']), 97)
        declaration = json.loads((ROOT/'extensions/p2-structure-grounding.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'GR-{i}' for i in range(1, 11)})
        self.assertEqual(declaration['inherits'], [])
        self.assertEqual({p.name for p in DIRECTORY.glob('*.json')}, {e['path'] for e in manifest['files']} | {'manifest.json'})
        for entry in manifest['files']:
            path = DIRECTORY/entry['path']
            raw = path.read_bytes()
            data = json.loads(raw)
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (entry['bytes'], entry['sha256']))
            self.assertEqual(p2_checks.failed_checks(evaluate(data['request']), data['expected']['checks']), [], entry['path'])
            done = subprocess.run([sys.executable, '-B', '-m', 'med_dsl', '--fixture', str(path)], cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT/'src')},
                                  capture_output=True, text=True, timeout=30)
            out = json.loads(done.stdout)
            self.assertEqual(done.returncode, {'ok': 0, 'invalid_input': 2, 'unsupported_profile': 3, 'resource_limit': 4}[out['status']], done.stderr)
            self.assertEqual(p2_checks.failed_checks(out, data['expected']['checks']), [], entry['path'])
        report = p2_checks.suite_report('p2-grounding', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (97, 1998, []))

    def test_value_rules_over_the_finite_grid_against_the_oracle(self):
        """W2：分母1〜40・分子−24〜24の点と、端の開閉4通りの区間の全数。可否と理由が別計算（Decimal）と一致し、小数で書ける分母は素因数が2・5だけ。"""
        count, outcomes = 0, set()
        for value in points():
            for kind in ('quantity', 'range'):
                result = reference(make.one(magnitude_of(value), 'u_base', value=kind))
                row = result['results'][0]
                outcomes.add((kind, row['grounding']['state'], tuple(row['reason_codes'])))
                rest = value.denominator
                for prime in (2, 5):
                    while rest % prime == 0:
                        rest //= prime
                terminating = rest == 1
                self.assertEqual(row['grounding']['state'] == 'representable', terminating, value)
                count += 1
        self.assertEqual(count, 2*len(points()))
        for low, high, (lower_closed, upper_closed) in intervals():
            for kind in ('quantity', 'range'):
                result = reference(make.one(interval_of(low, high, lower_closed, upper_closed), 'u_base', value=kind))
                outcomes.add((kind, result['results'][0]['grounding']['state'], tuple(result['results'][0]['reason_codes'])))
                count += 1
        self.assertGreater(count, 2400)
        for wanted in [('quantity', 'representable', ()), ('range', 'representable', ()), ('quantity', 'not_representable', ('not_decimal_representable',)),
                       ('range', 'not_representable', ('open_boundary_not_representable',)), ('quantity', 'not_representable', ('interval_not_representable_as_quantity',)),
                       ('range', 'not_representable', ('not_decimal_representable', 'open_boundary_not_representable')),
                       ('quantity', 'not_representable', ('interval_not_representable_as_quantity', 'not_decimal_representable'))]:
            self.assertIn(wanted, outcomes)
        for name in ['G01', 'G03', 'G13', 'G20', 'G26', 'G30', 'G31', 'G33', 'G34']:
            reference(fixture(name))

    def test_period_conventions_and_context_carriage_over_the_enumeration(self):
        """W4・W5：期間の規約3通り × method・specimen の3状態 × 運ぶ欄の5通り（順序違いを含む）の全数。区別の損失の数は、運ぶ欄のうち known でない欄の数に等しい。"""
        count = 0
        for method, specimen, listed, period in product(STATES, STATES, [[], ['method'], ['specimen'], ['method', 'specimen'], ['specimen', 'method']],
                                                      [None, 'undeclared', 'exclusive_end_as_last_second']):
            result = reference(make.one(ops=record_ops(method, specimen), contexts=listed, period=period))
            row = result['results'][0]
            count += 1
            unknown = [f for f, state in (('method', method), ('specimen', specimen)) if f in listed and state['kind'] != 'known']
            if period == 'undeclared':
                self.assertEqual((row['status'], row['reason_codes']), ('not_representable', ['period_end_convention_undeclared']))
                continue
            lost = [item for item in row['flows']['lost'] if item.startswith('context_state_distinction:')]
            self.assertEqual(len(lost), len(unknown))
            self.assertEqual(row['grounding']['projection']['absent'], sorted(unknown))
            for item in ('human_confirmed', 'origin_kind'):
                self.assertIn(item, row['flows']['lost'])
            self.assertEqual(bool(period), 'validity' in row['flows']['retained'])
            self.assertEqual(row['flows']['added'], make.ASSUMPTIONS if period else [])
        self.assertEqual(count, 3*3*5*3)
        for start in range(1, 9):                                              # 期間の端：すべての半開区間 [day s, day e)
            for end in range(start+1, 11):
                ops = [lib.rec(validity=lib.m.span(start, end)), lib.confirm('A')]
                req = make.one(ops=ops, query=lib.single('q1', lib.PB1, start), period='exclusive_end_as_last_second')
                row = reference(req)['results'][0]
                self.assertEqual(row['grounding']['projection']['period']['start'], lib.day(start))
                self.assertEqual(row['grounding']['projection']['period']['end'], f'2026-10-{end-1:02}T23:59:59Z')

    def test_other_rows_pass_through_and_representable_rows_keep_the_library_columns(self):
        """W3：基の行（臨床ライブラリ単独の実行）との差分。通す行は全欄が同じ。表せる行・表せない行は、選択・要素が同じ。"""
        rng = random.Random(680001)
        seen = set()
        for _ in range(300):
            req = random_grounding(rng)
            result = reference(req)
            alone = evaluate({**deepcopy(req['library_request']), 'budget': {'max_steps': 100000}})
            self.assertEqual(alone['status'], 'ok')
            for row, base in zip(result['results'], alone['results']):
                state = row['grounding']['state']
                seen.add(state)
                self.assertEqual(row['base_status'], base['status'])
                self.assertEqual((row['selection'], row['elements']), (base['selection'], base['elements']))
                if state in ('not_declared', 'not_evaluated'):
                    for key in ('status', 'reason_codes', 'requests', 'output', 'flows'):
                        self.assertEqual(row[key], base[key], (state, key))
                else:
                    self.assertEqual(base['status'], 'satisfied')
                    if state == 'representable':
                        self.assertEqual(row['output'], base['output'])
        self.assertEqual(seen, {'representable', 'not_representable', 'not_evaluated', 'not_declared'})
        self.assertEqual(result['ledger'], alone['ledger'])

    def test_nothing_is_rounded_closed_or_added(self):
        """GR-6：表せる行の小数は、元の領域の端と等しい（丸めない）。表せない行は出力を持たない。足す仮定は、宣言した規約を使った行だけ。"""
        for value in points()[::3]:
            for kind in ('quantity', 'range'):
                row = evaluate(make.one(magnitude_of(value), 'u_base', value=kind))['results'][0]
                if row['grounding']['state'] == 'representable':
                    shown = row['grounding']['projection']['value']
                    texts = [shown['decimal']] if kind == 'quantity' else [shown['low'], shown['high']]
                    self.assertEqual({F(text) for text in texts}, {value})
                    self.assertEqual(row['flows']['added'], [])
                else:
                    self.assertIsNone(row['output'])
                    self.assertEqual(row['flows']['retained'], [])
                    self.assertEqual(row['flows']['added'], [])
        for low, high, (lower_closed, upper_closed) in intervals():
            row = evaluate(make.one(interval_of(low, high, lower_closed, upper_closed), 'u_base', value='range'))['results'][0]
            self.assertEqual(row['grounding']['state'] == 'representable', lower_closed and upper_closed and all(oracle.decimal_text(x) for x in (low, high)))
            if row['grounding']['state'] == 'representable':
                shown = row['grounding']['projection']['value']
                self.assertEqual((F(shown['low']), F(shown['high'])), (low, high))
        rng = random.Random(680002)
        for _ in range(100):
            result = evaluate(random_grounding(rng))
            for row in result['results']:
                declared = row['grounding']['state'] in ('representable',)
                self.assertEqual(result['inferred_information'], [])
                if row['flows'] and row['flows']['added'] and declared:
                    self.assertEqual(row['flows']['added'], make.ASSUMPTIONS)
        # 小数で書けない値を、近い値に丸めた入力は別の入力：元の値は丸めた値と違う
        self.assertEqual(evaluate(fixture('G03'))['results'][0]['grounding']['state'], 'not_representable')

    def test_structure_facts_are_bound_to_their_sources(self):
        """W7・GR-9：構造の事実が、台帳のページのハッシュと一致し、手元にページがあれば、目印の語がページに存在する。呼び出し側は事実を変えられない。"""
        spec = json.loads((ROOT/'src/med_dsl/structure_grounding_spec.json').read_text())
        ledger = {m['id']: m for m in json.loads((ROOT/'docs/research/03-materials.json').read_text())['materials']}
        facts = spec['structures']['fhir-r5-observation']['facts']
        self.assertEqual([f['id'] for f in facts], [f'F-R{i}' for i in range(1, 7)])
        present = 0
        for fact in facts:
            material = ledger[fact['source']]
            self.assertEqual((material['local_sha256'], material['version'], material['commit_payload']), (fact['source_sha256'], '5.0.0', False), fact['id'])
            page = ROOT/material['local_path']
            if page.is_file():
                raw = page.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fact['source_sha256'], fact['id'])
                self.assertIn(fact['marker'], raw.decode('utf-8'), fact['id'])
                present += 1
        self.assertIn(present, (0, 6))                                          # ページがあれば全て（取得物は Git 管理外なので、無ければ台帳のハッシュだけを検査する）
        for key in ('structure_facts', 'facts', 'decimal', 'max_digits'):
            req = fixture('G01')
            req[key] = 18
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])
            req = fixture('G01')
            req['targets'][0][key] = 18
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])

    def test_full_cost_funded_once_and_the_child_uses_its_reservation(self):
        for name, total, child_total in [('G01', 37, 32), ('P06', 42, 37), ('R01', 93, 82), ('D03', 108, 97), ('D04', 65, 57)]:
            req = fixture(name)
            seen = []

            def tracked(child):
                seen.append(child['budget']['max_steps'])
                out = child_runner(child)
                self.assertEqual(out['steps_used'], child['budget']['max_steps'])
                return out
            with patch('med_dsl.structure_grounding.run_library', side_effect=tracked):
                result = reference(req)
            self.assertEqual(seen, [child_total])
            self.assertEqual(result['steps_used'], total)
        with patch('med_dsl.structure_grounding.run_library', side_effect=AssertionError('unfunded child')):
            self.assertEqual(evaluate(fixture('B03-plan'))['status'], 'resource_limit')
        rng = random.Random(680003)
        for _ in range(60):
            req = random_grounding(rng)
            self.assertEqual(evaluate(req)['steps_used'], oracle.cost(req))

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-grounding',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['G01', 'R01', 'D03', 'P06']:
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

    def test_child_failure_and_mismatch_are_atomic_and_refused(self):
        req = fixture('D04')

        def stopped(child):
            out = child_runner(child)
            out.update(status='resource_limit', reason_codes=['injected_library_limit'])
            return out
        with patch('med_dsl.structure_grounding.run_library', side_effect=stopped):
            out = evaluate(req)
        self.assertEqual((out['status'], out['reason_codes']), ('resource_limit', ['injected_library_limit']))
        self.assertEqual(out['steps_used'], 58)
        for row in out['results']:
            self.assertEqual([row[key] for key in FIELDS], [None]*7)
            self.assertEqual(row['reason_codes'], ['injected_library_limit'])
        self.assertEqual(out['certificate']['status'], 'not_certified')

        def wrong_cost(child):
            out = child_runner(child)
            out['steps_used'] -= 1
            return out
        with patch('med_dsl.structure_grounding.run_library', side_effect=wrong_cost):
            self.assertEqual(evaluate(fixture('G01'))['reason_codes'], ['library_cost_mismatch'])
        calls = []

        def second_row_failure(row, target, spec):
            calls.append(row['id'])
            if len(calls) == 2:
                raise Problem('injected_row_limit', status='resource_limit')
            return native._ground(row, target, spec) if target else native._passed(row, 'not_declared', None)
        with patch('med_dsl.structure_grounding._row', side_effect=second_row_failure):
            out = evaluate(req)
        self.assertEqual(out['status'], 'resource_limit')
        self.assertEqual(out['results'][0]['status'], 'satisfied')
        self.assertEqual(out['results'][1]['reason_codes'], ['injected_row_limit'])
        self.assertEqual([out['results'][1][key] for key in FIELDS], [None]*7)
        self.assertEqual(out['incomplete'][0], {'query': 'b2', 'reason_codes': ['injected_row_limit']})

    def test_static_validation_pins_limits_and_native_refusals(self):
        for path in sorted(DIRECTORY.glob('n*.json')):
            if path.name.startswith('n12') or path.name == 'n01-missing-budget.json':
                continue                                                      # 予算欄そのものの不正は、予算の置換の対象外
            req = json.loads(path.read_text())['request']
            before = evaluate(req)
            original = deepcopy(req)
            for budget in [0, 1, 7]:
                req['budget'] = {'max_steps': budget}
                out = evaluate(req)
                self.assertEqual((out['status'], out['reason_codes']), (before['status'], before['reason_codes']), path.name)
            req['budget'] = original['budget']
            self.assertEqual(req, original)
        original = Path.read_bytes
        for filename in ['structure_grounding_spec.json', 'clinical_library_spec.json']:
            def corrupt(path):
                return b'{}' if path.name == filename else original(path)
            with patch.object(Path, 'read_bytes', corrupt):
                self.assertEqual(evaluate(fixture('G01'))['reason_codes'], ['native_spec_mismatch'])
        req = fixture('G01')
        req['padding'] = 'x'*1048576
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        req = fixture('G01')
        nested = None
        for _ in range(65):
            nested = [nested]
        req['padding'] = nested
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        with self.assertRaises(Problem) as caught:
            native._decimal(F(1, 3))
        self.assertEqual(caught.exception.code, 'decimal_expansion_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req = fixture('G13')
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

    def test_order_and_input_immutability(self):
        req = fixture('R01')
        before = deepcopy(req)
        first = reference(req)
        self.assertEqual(req, before)
        shuffled = deepcopy(req)
        shuffled['targets'].reverse()
        shuffled['library_request']['destinations'].reverse()
        shuffled['library_request']['queries'].reverse()
        second = reference(shuffled)
        for a, b in zip(first['results'], second['results']):
            for key in ('status', 'reason_codes', 'grounding', 'flows', 'requests'):
                self.assertEqual(a[key], b[key])
        reordered = fixture('C06')
        again = deepcopy(reordered)
        again['targets'][0]['context_fields'].reverse()
        self.assertEqual(evaluate(reordered)['results'][0]['grounding'], evaluate(again)['results'][0]['grounding'])

    def test_checker_detects_early_values(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('grounding', []), ('base_status', ''), ('flows', {}), ('requests', [])]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('grounding', fixture('G01'), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', fixture('G01'), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        mutants = [
            ('open_boundary_accepted', '_ground', "    elif not closed:\n        reasons.add('open_boundary_not_representable')", "    elif False:\n        reasons.add('open_boundary_not_representable')", 'G22'),
            ('interval_pressed_into_quantity', '_ground', "        if not (lower == upper and closed):", "        if False:", 'G10'),
            ('digits_unchecked', '_ground', "            if _digits(text[end]) > structure['decimal']['max_digits']:", "            if False:", 'G31'),
            ('sign_counted_as_digit', '_digits', "    return sum(character.isdigit() for character in text)", "    return len(text) - (1 if '.' in text else 0)", 'G32'),
            ('leading_zero_not_counted', '_digits', "    return sum(character.isdigit() for character in text)", "    return sum(character.isdigit() for character in text.lstrip('-0'))", 'G34'),
            ('prime_three_allowed', '_terminating', "    for prime in (2, 5):", "    for prime in (2, 3, 5):", 'G03'),
            ('convention_silently_used', '_ground', "        if period['end_convention'] == 'undeclared':", "        if False:", 'P01'),
            ('assumption_not_reported', '_ground', "             'added': sorted(spec['assumptions'][period['end_convention']]) if carried else []}", "             'added': []}", 'P02'),
            ('period_end_not_moved', '_last_second', "- timedelta(seconds=1)", "- timedelta(seconds=0)", 'P02'),
            ('distinction_not_reported', '_ground', "                            + ['context_state_distinction:' + field for field in absent]),", "                            ),", 'C01'),
            ('confirmation_loss_hidden', '_ground', "'lost': sorted(structure['not_carried'] + ", "'lost': sorted(", 'G01'),
            ('context_order_dependent', '_ground', "    for field in sorted(target['context_fields']):", "    for field in target['context_fields']:", 'C06'),
            ('low_high_swapped', '_ground', "{'low': text['lower'], 'high': text['upper']}", "{'low': text['upper'], 'high': text['lower']}", 'G27'),
            ('undeclared_as_representable', '_row', "        return _passed(row, 'not_declared', None)", "        return _passed(row, 'representable', None)", 'D01'),
            ('unsatisfied_rows_grounded', '_row', "        return _passed(row, 'not_evaluated', target)", "        return _ground(row, target, spec)", 'R01'),
            ('prepayment_removed', 'run_grounding', "        for _ in range(cost):\n            budget.tick()\n", "", 'G01'),
            ('completion_fee_removed', 'run_grounding', "        current, stage = None, 'completion'\n        budget.tick()\n", "        current, stage = None, 'completion'\n", 'B01-36'),
            ('inferred_information', 'run_grounding', "'clinical_assertions_added': [], 'inferred_information': []", "'clinical_assertions_added': [], 'inferred_information': ['guess']", 'G01'),
            ('certified', 'run_grounding', "'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'", 'G01'),
        ]
        for ident, name, old, new, case in mutants:
            source = inspect.getsource(getattr(native, name))
            self.assertEqual(source.count(old), 1, ident)
            namespace = dict(vars(native))
            exec(compile(source.replace(old, new), f'<grounding-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-grounding-request-draft-1'][:3], namespace['run_grounding'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-grounding-request-draft-1': surface}):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:                       # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        self.assertEqual(len(mutants), 19)
        for ident, attribute, value_, case in [('own_fee_reduced', 'OWN_FEE', 2, 'G01')]:
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            with patch.object(native, attribute, value_):
                bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
            self.assertTrue(bad, ident)


if __name__ == '__main__':
    unittest.main()
