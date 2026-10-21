"""P2-q：手指定期待、別計算との比較、宣言の全数、確認と出自、通す行、出典の結び付き、共通予算、変異。"""
from copy import deepcopy
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
from med_dsl import evaluate, host, observation_projection as native
from med_dsl.model import Problem
from med_dsl.structure_grounding import run_grounding as child_runner
import gen_observation_fixtures as make
import observation_oracle as oracle
import p2_checks
import test_grounding
ground, lib, q, m = make.ground, make.lib, make.q, make.m
DIRECTORY = ROOT/'examples/p2-observation'
FIELDS = native.VALUE_FIELDS
REVIEWER_TYPES = ['Practitioner', 'PractitionerRole', 'Patient', 'RelatedPerson']
CORRECTED = [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2), lib.confirm('B', 7)]


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def compare_row(row, expected, request, context=None):
    """実装の行を、別計算の期待と照合する。"""
    got = (row['status'], row['reason_codes'], row['requests'], row['flows'], row['grounding']['state'], row['observation']['state'], row['observation']['status'],
           row['observation']['code'])
    want = (expected['status'], expected['reasons'], expected['requests'], expected['flows'], expected['state'], expected['observation_state'], expected['status_value'],
            expected['code_value'])
    if got != want:
        raise AssertionError((context, got, want))
    if expected['provenance'] is None:
        if row['observation']['provenance'] is not None:
            raise AssertionError((context, 'provenance', row['observation']['provenance']))
    else:
        got_entries = [{'activity': e['activity'], 'record_ref': e['target']['record_ref'], 'recorded': e['recorded'], 'agents': [a['who'] for a in e['agents']],
                        'type': e['target']['type']} for e in row['observation']['provenance']]
        want_entries = [dict(e, type='Observation') for e in expected['provenance']]
        if got_entries != want_entries:
            raise AssertionError((context, 'provenance', got_entries, want_entries))
        for entry in row['observation']['provenance']:                       # 対象は版つき：選択の記録のハッシュ
            if entry['target']['record_sha256'] != row['selection']['record_sha256']:
                raise AssertionError((context, 'target hash', entry))
    if expected['selection'] is not None and 'record_ref' in expected['selection']:
        if row['selection']['record_ref'] != expected['selection']['record_ref']:
            raise AssertionError((context, 'selection', row['selection']))


def reference(req):
    result = evaluate(req)
    if result['status'] != 'ok':
        raise AssertionError(result)
    for row, query in zip(result['results'], sorted(req['grounding_request']['library_request']['queries'], key=lambda x: x['id'])):
        compare_row(row, oracle.row(req, query), req, query['id'])
    if result['steps_used'] != oracle.cost(req) or result['grounding_run']['reserved_steps'] != oracle.grounding_cost(req):
        raise AssertionError((result['steps_used'], oracle.cost(req)))
    return result


def random_observation(rng):
    grounding = test_grounding.random_grounding(rng)
    declarations = []
    for target in grounding['targets']:
        if rng.random() < .15:
            continue                                                         # 宣言のない出力先
        profile = {'id': target['destination_ref']['id'], 'version': target['destination_ref']['version']}
        code_map = rng.choice([make.MAP, [], [{'property_ref': 'fiction:other', 'system': 's', 'code': 'c'}]])
        status = {'original': 'final'}
        if rng.random() < .6:
            status['correction'] = rng.choice(['amended', 'corrected'])
        found = {'destination_ref': profile, 'status': status, 'code_map': deepcopy(code_map)}
        if rng.random() < .8:
            found['provenance'] = {'reviewer_type': rng.choice(REVIEWER_TYPES)}
            if rng.random() < .6:
                found['provenance']['observer_type'] = rng.choice(REVIEWER_TYPES)
        declarations.append(found)
    if not declarations:
        target = grounding['targets'][0]
        declarations.append({'destination_ref': dict(target['destination_ref']), 'status': {'original': 'final'}, 'code_map': deepcopy(make.MAP)})
    return make.observation(grounding, declarations)


class ObservationTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'Q': 25, 'N': 14, 'B': 3})
        self.assertEqual(len(manifest['files']), 83)
        declaration = json.loads((ROOT/'extensions/p2-observation-projection.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'QR-{i}' for i in range(1, 13)})
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
        report = p2_checks.suite_report('p2-observation', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (83, 1446, []))

    def test_declaration_enumeration_against_the_oracle(self):
        """D1：status.correction の有無 × code_map（空／該当／別の性質）× 選ばれる記録（原本／訂正）× provenance（なし／4種の型）の全数。
        足りない宣言は全て依頼になり、推測で補った status・code は決して出ない。"""
        count, seen = 0, set()
        maps = {'empty': [], 'matching': make.MAP, 'other': [{'property_ref': 'fiction:other', 'system': 's', 'code': 'c'}]}
        for correction, (map_name, code_map), day_selected, reviewer in product([None, 'amended', 'corrected'], maps.items(), [3, 5], [None]+REVIEWER_TYPES):
            req = make.observation(ground.one(ops=CORRECTED, query=lib.single('q1', lib.PB1, day_selected)),
                                   [make.declare(lib.PB1, correction=correction, code_map=code_map, reviewer=reviewer)])
            row = reference(req)['results'][0]
            count += 1
            correction_selected = day_selected == 5
            missing = (map_name != 'matching') + (correction_selected and correction is None)
            self.assertEqual(len(row['requests']) if row['observation']['state'] == 'needs_information' else 0, missing)
            self.assertEqual(row['observation']['state'], 'needs_information' if missing else 'projected')
            if missing:
                self.assertIsNone(row['output'])
                self.assertIsNone(row['observation']['status'])
                self.assertIsNone(row['observation']['code'])
            else:
                self.assertEqual(row['observation']['status']['state'], 'correction' if correction_selected else 'original')
                self.assertEqual(row['observation']['status']['code'], correction if correction_selected else 'final')
                self.assertEqual(('human_confirmed' in row['flows']['retained']), reviewer is not None)
            seen.add((row['observation']['state'], missing))
        self.assertEqual(count, 3*3*2*5)
        self.assertEqual(seen, {('projected', 0), ('needs_information', 1), ('needs_information', 2)})
        for name in ['Q01', 'Q04', 'Q05', 'Q06', 'Q08', 'Q10', 'Q13', 'Q14', 'Q15', 'Q19']:
            reference(fixture(name))

    def test_confirmations_origins_and_visibility(self):
        """D4・Z5・Z6：確認の数（見えないものを含む）× 出自。確認ごとに Provenance が一つ、時刻順。AI 由来だけが先頭に生成を持つ。"""
        count = 0
        for confirmations, origin in product([1, 2, 3], ['observed', 'judgment', 'ai_candidate']):
            ops = [lib.rec(origin={'kind': origin, 'ref': 'fiction:origin:A'})] + [lib.confirm('A', 3+k, f'R{k}') for k in range(confirmations)]
            row = reference(make.observation(ground.one(ops=ops), [make.declare(lib.PB1)]))['results'][0]
            entries = row['observation']['provenance']
            self.assertEqual([e['activity'] for e in entries], (['creation'] if origin == 'ai_candidate' else [])+['confirmation']*confirmations)
            confirmations_only = [e for e in entries if e['activity'] == 'confirmation']
            self.assertEqual([e['recorded'] for e in confirmations_only], sorted(e['recorded'] for e in confirmations_only))
            self.assertEqual(('origin_kind' in row['flows']['retained']), origin == 'ai_candidate')
            count += 1
        late = [lib.rec(), lib.confirm('A', 3, 'RA'), lib.confirm('A', 9, 'RA9')]                       # 参照時点より後の確認は出さない
        row = reference(make.observation(ground.one(ops=late), [make.declare(lib.PB1)]))['results'][0]
        self.assertEqual((row['selection']['review_refs'], len(row['observation']['provenance'])), (['RA'], 1))
        self.assertEqual(count, 9)

    def test_observer_creation_provenance_and_types_are_never_guessed(self):
        """P2-r・QR-12：観察者（なし／human／device）× 出自（observed／ai_candidate）× 観察者の型の宣言（なし／4種）× Provenance の宣言（あり／なし）の全数。
        人の観察者で型の宣言がなければ依頼。device は Device。生成の Provenance は、AI 由来か観察者があるときだけ。"""
        human, device = {'kind': 'human', 'ref': 'fiction:human:observer'}, {'kind': 'device', 'ref': 'fiction:device:meter'}
        count = 0
        for observer, origin, observer_type, declared in product([None, human, device], ['observed', 'ai_candidate'], [None]+REVIEWER_TYPES, [True, False]):
            op = lib.rec(origin={'kind': origin, 'ref': 'fiction:origin:A'})
            if observer:
                op['observer'] = deepcopy(observer)
            declaration = make.declare(lib.PB1, reviewer='Practitioner' if declared else None, observer_type=observer_type if declared else None)
            row = reference(make.observation(ground.one(ops=[op, lib.confirm('A')]), [declaration]))['results'][0]
            count += 1
            needs_type = declared and observer is not None and observer['kind'] == 'human' and observer_type is None
            self.assertEqual(row['observation']['state'], 'needs_information' if needs_type else 'projected')
            if needs_type:
                self.assertEqual(row['requests'], [make.observer_request('A')])
                continue
            entries = [e for e in row['observation']['provenance'] if e['activity'] == 'creation']
            self.assertEqual(len(entries), 1 if declared and (origin == 'ai_candidate' or observer) else 0)
            if entries:
                kinds = [a['who']['type'] for a in entries[0]['agents']]
                expected = (['Device'] if origin == 'ai_candidate' else [])+([] if observer is None else ['Device' if observer['kind'] == 'device' else observer_type])
                self.assertEqual(kinds, expected)
            self.assertEqual('observer' in row['flows']['retained'], bool(declared and observer))
            self.assertEqual('observer' in row['flows']['lost'], bool(observer and not declared))
        self.assertEqual(count, 3*2*5*2)

    def test_rows_not_evaluated_or_not_declared_pass_through_the_grounding_rows(self):
        """D5：P2-p 単独の実行との差分。通す行は P2-p の行と全欄が同じ。投影した行は P2-p の欄を保つ。"""
        rng = random.Random(710001)
        seen = set()
        for _ in range(250):
            req = random_observation(rng)
            result = reference(req)
            alone = evaluate({**deepcopy(req['grounding_request']), 'budget': {'max_steps': 100000}})
            self.assertEqual(alone['status'], 'ok')
            for row, base in zip(result['results'], alone['results']):
                state = row['observation']['state']
                seen.add(state)
                self.assertEqual((row['grounding'], row['base_status'], row['selection'], row['elements']), (base['grounding'], base['base_status'], base['selection'], base['elements']))
                if state in ('not_declared', 'not_evaluated'):
                    for key in ('status', 'reason_codes', 'requests', 'output', 'flows'):
                        self.assertEqual(row[key], base[key], (state, key))
                    self.assertEqual([row['observation'][key] for key in ('status', 'code', 'provenance')], [None]*3)
                elif state == 'projected':
                    self.assertEqual(row['output'], base['output'])
                    self.assertEqual(base['grounding']['state'], 'representable')
                else:
                    self.assertEqual(base['grounding']['state'], 'representable')
        self.assertEqual(seen, {'projected', 'needs_information', 'not_evaluated', 'not_declared'})
        self.assertEqual(result['ledger'], alone['ledger'])

    def test_declared_mappings_are_used_but_never_chosen(self):
        """X10・K-INV：宣言の system・code の文字列を変えても判定は同じで、そのまま載る。宣言のない性質には何も補わない。"""
        base = evaluate(make.observation(ground.one(), [make.declare(lib.PB1)]))['results'][0]
        for system, code in [('a', 'b'), ('fiction:other-system', '0'), ('s s', 'c c')]:
            row = evaluate(make.observation(ground.one(), [make.declare(lib.PB1, code_map=[{'property_ref': lib.PROPERTY, 'system': system, 'code': code}])]))['results'][0]
            self.assertEqual(row['observation']['code'], {'system': system, 'code': code})
            for key in ('status', 'reason_codes', 'requests', 'flows'):
                self.assertEqual(row[key], base[key])
        other = [{'property_ref': 'fiction:other', 'system': 's', 'code': 'c'}]
        row = evaluate(make.observation(ground.one(), [make.declare(lib.PB1, code_map=other)]))['results'][0]
        self.assertEqual((row['observation']['state'], row['observation']['code'], row['observation']['status']), ('needs_information', None, None))
        result = evaluate(make.observation(ground.one(ops=CORRECTED, query=lib.single('q1', lib.PB1, 5)), [make.declare(lib.PB1)]))
        self.assertEqual(result['results'][0]['observation']['state'], 'needs_information')          # 訂正の status を推測で補わない
        self.assertEqual(result['inferred_information'], [])
        text = json.dumps(result)
        for word in ('amended', 'corrected'):
            self.assertNotIn(word, text.replace('declare_correction_status', ''))

    def test_structure_facts_are_bound_to_their_sources(self):
        """W7・QR-11：構造の事実が台帳のページのハッシュと一致し、手元にページがあれば、目印の語がページに存在する。呼び出し側は事実を変えられない。"""
        spec = json.loads((ROOT/'src/med_dsl/observation_projection_spec.json').read_text())
        ledger = {x['id']: x for x in json.loads((ROOT/'docs/research/03-materials.json').read_text())['materials']}
        self.assertEqual([f['id'] for f in spec['facts']], ['F-S1', 'F-S2', 'F-S3', 'F-S4', 'F-S5', 'F-S6', 'F-P1', 'F-P2', 'F-P3'])
        present = 0
        for fact in spec['facts']:
            material = ledger[fact['source']]
            self.assertEqual((material['local_sha256'], material['version'], material['commit_payload']), (fact['source_sha256'], '5.0.0', False), fact['id'])
            page = ROOT/material['local_path']
            if page.is_file():
                raw = page.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fact['source_sha256'], fact['id'])
                self.assertIn(fact['marker'], raw.decode('utf-8'), fact['id'])
                present += 1
        self.assertIn(present, (0, 9))
        self.assertEqual(spec['status_mapping'], {'original': ['final'], 'correction': ['amended', 'corrected']})
        self.assertEqual(spec['reviewer_types'], ['Practitioner', 'PractitionerRole', 'Patient', 'RelatedPerson'])
        for key in ('facts', 'status_mapping', 'reviewer_types'):
            req = fixture('Q01')
            req[key] = []
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])
            req = fixture('Q01')
            req['observations'][0][key] = []
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])

    def test_full_cost_funded_once_and_the_child_uses_its_reservation(self):
        for name, total, child_total in [('Q01', 42, 37), ('Q04', 43, 38), ('Q06', 47, 42), ('Q13', 73, 65), ('Q18', 73, 65)]:
            req = fixture(name)
            seen = []

            def tracked(child):
                seen.append(child['budget']['max_steps'])
                out = child_runner(child)
                self.assertEqual(out['steps_used'], child['budget']['max_steps'])
                return out
            with patch('med_dsl.observation_projection.run_grounding', side_effect=tracked):
                result = reference(req)
            self.assertEqual(seen, [child_total])
            self.assertEqual(result['steps_used'], total)
        with patch('med_dsl.observation_projection.run_grounding', side_effect=AssertionError('unfunded child')):
            self.assertEqual(evaluate(fixture('B03-plan'))['status'], 'resource_limit')
        rng = random.Random(710002)
        for _ in range(50):
            req = random_observation(rng)
            self.assertEqual(evaluate(req)['steps_used'], oracle.cost(req))

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-observation',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['Q01', 'Q13', 'Q06']:
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
        req = fixture('Q18')

        def stopped(child):
            out = child_runner(child)
            out.update(status='resource_limit', reason_codes=['injected_grounding_limit'])
            return out
        with patch('med_dsl.observation_projection.run_grounding', side_effect=stopped):
            out = evaluate(req)
        self.assertEqual((out['status'], out['reason_codes'], out['steps_used']), ('resource_limit', ['injected_grounding_limit'], 66))
        for row in out['results']:
            self.assertEqual([row[key] for key in FIELDS], [None]*8)
            self.assertEqual(row['reason_codes'], ['injected_grounding_limit'])

        def wrong_cost(child):
            out = child_runner(child)
            out['steps_used'] -= 1
            return out
        with patch('med_dsl.observation_projection.run_grounding', side_effect=wrong_cost):
            self.assertEqual(evaluate(fixture('Q01'))['reason_codes'], ['grounding_cost_mismatch'])
        calls = []

        def second_row_failure(row, declaration, ledger, spec):
            calls.append(row['id'])
            if len(calls) == 2:
                raise Problem('injected_row_limit', status='resource_limit')
            return native._project(row, declaration, ledger, spec)
        with patch('med_dsl.observation_projection._row', side_effect=second_row_failure):
            out = evaluate(req)
        self.assertEqual(out['status'], 'resource_limit')
        self.assertEqual(out['results'][0]['status'], 'satisfied')
        self.assertEqual(out['results'][1]['reason_codes'], ['injected_row_limit'])
        self.assertEqual([out['results'][1][key] for key in FIELDS], [None]*8)
        self.assertEqual(out['incomplete'][0], {'query': 'q2', 'reason_codes': ['injected_row_limit']})

    def test_static_validation_pins_limits_and_native_refusals(self):
        for path in sorted(DIRECTORY.glob('n*.json')):
            if path.name.startswith('n13') or path.name == 'n01-missing-budget.json':
                continue
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
        for filename in ['observation_projection_spec.json', 'structure_grounding_spec.json', 'clinical_library_spec.json']:
            def corrupt(path):
                return b'{}' if path.name == filename else original(path)
            with patch.object(Path, 'read_bytes', corrupt):
                self.assertEqual(evaluate(fixture('Q01'))['reason_codes'], ['native_spec_mismatch'])
        req = fixture('Q01')
        req['padding'] = 'x'*1048576
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        req = fixture('Q01')
        nested = None
        for _ in range(65):
            nested = [nested]
        req['padding'] = nested
        self.assertEqual(evaluate(req)['status'], 'resource_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req = fixture('Q05')
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
        req = fixture('Q13')
        before = deepcopy(req)
        first = reference(req)
        self.assertEqual(req, before)
        shuffled = deepcopy(req)
        shuffled['observations'].reverse()
        shuffled['grounding_request']['targets'].reverse()
        shuffled['grounding_request']['library_request']['queries'].reverse()
        shuffled['grounding_request']['library_request']['destinations'].reverse()
        second = reference(shuffled)
        for a, b in zip(first['results'], second['results']):
            for key in ('status', 'reason_codes', 'observation', 'flows', 'requests', 'grounding'):
                self.assertEqual(a[key], b[key])

    def test_checker_detects_early_values(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('observation', []), ('grounding', []), ('flows', {}), ('requests', [])]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('observation', fixture('Q01'), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', fixture('Q01'), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        mutants = [
            ('code_guessed', '_project', "    if property_ref not in declaration['code_map']:\n        requests.append(", "    if False:\n        requests.append(", 'Q09'),
            ('status_guessed', '_project', "    if status_code is None:\n        requests.append(", "    status_code = status_code or 'amended'\n    if False:\n        requests.append(", 'Q08'),
            ('correction_taken_as_original', '_project', "    state = 'correction' if record['revises'] else 'original'", "    state = 'original'", 'Q06'),
            ('requests_unsorted', '_project', "requests=sorted(requests, key=lambda r: (r['element'], r['record_ref'])),", "requests=requests[::-1],", 'Q10'),
            ('assumption_not_reported', '_project', "    added |= {flows['assumptions']['code'], flows['assumptions']['status'].format(state=state, code=status_code)}",
             "    added |= set()", 'Q01'),
            ('reviewer_assumption_hidden', '_project', "        added.add(flows['assumptions']['reviewer'])", "        pass", 'Q01'),
            ('creation_for_every_origin', '_project', "        if selection['record_origin']['kind'] == 'ai_candidate':", "        if True:", 'Q01'),
            ('creation_never', '_project', "        if selection['record_origin']['kind'] == 'ai_candidate':", "        if False:", 'Q05'),
            ('confirmation_unsorted', '_project', "key=lambda r: (r['recorded_at'], r['id'])):", "key=lambda r: (-len(r['recorded_at']), r['recorded_at'], r['id']), reverse=True):", 'Q04'),
            ('invisible_review_emitted', '_project', "for ref in selection['review_refs']), key", "for ref in sorted(ledger['reviews'])), key", 'Q06'),
            ('human_confirmation_still_lost', '_project', "        retained |= set(flows['provenance_retained'])\n        lost -= set(flows['provenance_retained'])\n", "", 'Q01'),
            ('property_still_lost', '_project', "    lost -= set(flows['always_retained'])\n", "", 'Q01'),
            ('undeclared_projected', '_row', "        return _passed(row, 'not_declared')", "        return _project(row, {'status': {'original': 'final'}, 'code_map': {}, 'reviewer_type': None}, ledger, spec)", 'Q13'),
            ('unrepresentable_rows_asked', '_row', "        return _passed(row, 'not_evaluated')", "        return _project(row, declaration, ledger, spec)", 'Q12'),
            ('observer_type_guessed', '_project', "declaration['observer_type'] is None:\n        requests.append", "False:\n        requests.append", 'Q21'),
            ('observer_agent_missing', '_project', "        if observer is not None:\n            agents.append(", "        if False:\n            agents.append(", 'Q22'),
            ('observer_flow_not_reported', '_project', "            retained |= set(flows['observer_retained'])\n            lost -= set(flows['observer_retained'])\n", '', 'Q22'),
            ('prepayment_removed', 'run_observation', "        for _ in range(cost):\n            budget.tick()\n", "", 'Q01'),
            ('completion_fee_removed', 'run_observation', "        current, stage = None, 'completion'\n        budget.tick()\n", "        current, stage = None, 'completion'\n", 'B01-41'),
            ('inferred_information', 'run_observation', "'clinical_assertions_added': [], 'inferred_information': []", "'clinical_assertions_added': [], 'inferred_information': ['guess']", 'Q01'),
            ('certified', 'run_observation', "'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'", 'Q01'),
        ]
        for ident, name, old, new, case in mutants:
            source = inspect.getsource(getattr(native, name))
            self.assertEqual(source.count(old), 1, ident)
            namespace = dict(vars(native))
            exec(compile(source.replace(old, new), f'<observation-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-observation-request-draft-1'][:3], namespace['run_observation'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-observation-request-draft-1': surface}):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:                       # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        self.assertEqual(len(mutants), 21)
        data = json.loads((DIRECTORY/'q01.json').read_text())
        with patch.object(native, 'OWN_FEE', 2):
            self.assertTrue(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']))


if __name__ == '__main__':
    unittest.main()
