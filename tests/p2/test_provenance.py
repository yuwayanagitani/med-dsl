"""P2-t：手指定期待、別計算との比較、宣言の全数、訂正の関係と独立なハッシュ、通す行、出典の結び付き、共通予算、変異。"""
from copy import deepcopy
import hashlib
import html
import inspect
from itertools import product
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/research'), str(ROOT/'scripts/research/p2'), str(Path(__file__).parent)]
from med_dsl import evaluate, host, provenance_coding as native
from med_dsl.model import Problem
from med_dsl.observation_projection import run_observation as child_runner
import gen_provenance_fixtures as make
import provenance_oracle as oracle
import p2_checks
import test_observation
obs, ground, lib, q, m = make.obs, make.ground, make.lib, make.q, make.m
DIRECTORY = ROOT/'examples/p2-provenance'
FIELDS = native.VALUE_FIELDS
PB1 = lib.PB1
HUMAN = {'kind': 'human', 'ref': 'fiction:human:observer'}
DEVICE = {'kind': 'device', 'ref': 'fiction:device:meter'}
SUBSETS = [tuple(kind for kind, keep in zip(make.KINDS, mask) if keep) for mask in product([False, True], repeat=3)]


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def page_text(raw):
    text = re.sub(r'<script.*?</script>|<style.*?</style>', '', raw.decode('utf-8'), flags=re.S)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text)))


def activities(subset):
    return {kind: make.activity(kind) for kind in subset}


def compare_coding(got, want, context=None):
    if got != want:
        raise AssertionError((context, got, want))


def reference(req):
    """実装の結果を、別計算の期待と全行で照合する。"""
    result = evaluate(req)
    if result['status'] != 'ok':
        raise AssertionError(result)
    for row, query in zip(result['results'], sorted(req['observation_request']['grounding_request']['library_request']['queries'], key=lambda x: x['id'])):
        expected = oracle.row(req, query, result['ledger'])
        test_observation.compare_row(row, expected, req, query['id'])
        compare_coding(row['coding'], expected['coding'], query['id'])
    if result['steps_used'] != oracle.cost(req) or result['observation_run']['reserved_steps'] != oracle.observation_cost(req):
        raise AssertionError((result['steps_used'], oracle.cost(req)))
    return result


def scenario(case, observer, origin):
    """記録の場合（原本／訂正1件／訂正2件）。観察者・出自は、選ばれる記録（原本 A または訂正 B）に付ける。"""
    change = dict(observer=deepcopy({'unknown': {'kind': 'unknown'}, 'human': HUMAN, 'device': DEVICE}[observer]), origin={'kind': origin, 'ref': 'fiction:origin:X'})
    if case == 'original':
        return [lib.rec(**change), lib.confirm('A')]
    fix = dict(validity=m.span(4, 6), value=lib.value(q.point(3)), method=lib.METHOD2, **change)
    if case == 'one':
        return [lib.rec(), lib.confirm('A'), lib.fix('B', ['A'], **fix), lib.confirm('B', 7)]
    return [lib.rec(), lib.rec('A2', recorded_at=make.day(3)), lib.confirm('A'), lib.confirm('A2', 3), lib.fix('B', ['A', 'A2'], **fix), lib.confirm('B', 7)]


def request_for(ops, subset=make.KINDS, revision=True, reviewer=True, at=5):
    declaration = obs.declare(PB1, correction='amended', reviewer='Practitioner' if reviewer else None, observer_type='Practitioner' if reviewer else None)
    return make.provenance(obs.observation(ground.one(ops=ops, query=lib.single('q1', PB1, at)), [declaration], budget=0), [make.coding(PB1, activities(subset), revision)])


def random_provenance(rng):
    child = test_observation.random_observation(rng)
    for op in child['grounding_request']['library_request']['library']['operations']:
        if op['kind'] in ('record', 'correct'):
            roll = rng.random()
            op['observer'] = deepcopy({'kind': 'unknown'} if roll < .55 else (HUMAN if roll < .8 else DEVICE))
            if rng.random() < .2:
                op['origin'] = {'kind': 'ai_candidate', 'ref': 'fiction:ai:'+op['id']}
    codings = []
    for item in child['observations']:
        if rng.random() < .15:
            continue
        found = make.coding(item['destination_ref'], {kind: make.activity(kind) for kind in make.KINDS if rng.random() < .6}, rng.random() < .6)
        if not found['activities'] and rng.random() < .5:
            del found['activities']
        codings.append(found)
    if not codings:
        codings.append(make.coding(child['observations'][0]['destination_ref'], {'confirmation': make.activity('confirmation')}, True))
    return make.provenance(child, codings)


class ProvenanceTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'V': 20, 'N': 15, 'B': 3})
        self.assertEqual(len(manifest['files']), 73)
        declaration = json.loads((ROOT/'extensions/p2-provenance-coding.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'PT-{i}' for i in range(1, 11)})
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
        report = p2_checks.suite_report('p2-provenance', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (73, 1533, []))

    def test_enumeration_against_the_oracle(self):
        """D1：記録の場合（原本／訂正1件／訂正2件）×観察者（不明／人／装置）×出自（観察／AI）×確認者の型の宣言（あり／なし）×活動の宣言の部分集合（8）×revision（真／偽）。
        revision の状態と流れが別計算と一致し、全ての状態が現れる。"""
        count, seen = 0, set()
        for case, observer, origin, reviewer, subset, revision in product(['original', 'one', 'two'], ['unknown', 'human', 'device'], ['observed', 'ai_candidate'], [True, False], SUBSETS, [True, False]):
            row = reference(request_for(scenario(case, observer, origin), subset, revision, reviewer))['results'][0]
            count += 1
            seen.add((row['coding']['state'], row['coding']['revision']['state'] if row['coding']['revision'] else None))
            if row['coding']['state'] == 'coded' and row['coding']['revision']['state'] == 'carried':
                carried = [e for e in row['coding']['entries'] if e['entities']]
                self.assertEqual(len(carried), 1)
                self.assertEqual(carried[0]['kind'], 'correction')
        self.assertEqual(count, 3*3*2*2*8*2)
        self.assertEqual(seen, {('coded', 'not_applicable'), ('coded', 'not_requested'), ('coded', 'no_provenance'), ('coded', 'no_agent'), ('coded', 'carried')})
        for name in ['V01', 'V04', 'V06', 'V09', 'V10', 'V12', 'V13', 'V16', 'V19']:
            reference(fixture(name))

    def test_activity_codes_are_declared_never_substituted(self):
        """T3・D6：符号は宣言した種類のものだけ。宣言のない種類は null で、別の種類の符号で代用しない。付けられなかった種類は失うものに残り、
        使われなかった宣言は流れに痕跡を残さない。符号の文字列を替えても判定は変わらない。"""
        for case, subset, revision in product(['original', 'one'], SUBSETS, [True, False]):
            req = request_for(scenario(case, 'human', 'observed'), subset, revision)
            row = reference(req)['results'][0]
            kinds = {e['kind'] for e in row['coding']['entries']}
            for entry in row['coding']['entries']:
                self.assertEqual(entry['activity'], make.activity(entry['kind']) if entry['kind'] in subset else None)
                self.assertEqual('activity:'+entry['kind'] in row['flows']['lost'], entry['kind'] not in subset)
            self.assertEqual('assumption:activity_coding_declared' in row['flows']['added'], bool(kinds & set(subset)))
            self.assertEqual({token for token in row['flows']['lost'] if token.startswith('activity:')}, {'activity:'+k for k in kinds - set(subset)})
        std = lambda subset: evaluate(make.provenance(obs.observation(ground.one(), [obs.declare(PB1)], budget=0), [make.coding(PB1, activities(subset), False)]))['results'][0]
        self.assertEqual(std(('creation',))['flows'], std(())['flows'])                      # 使われない宣言（生成の符号）は痕跡を残さない
        base = evaluate(request_for(scenario('one', 'human', 'observed')))['results'][0]
        for system, code in [('a', 'b'), ('fiction:other-system', '0'), ('s s', 'c c')]:
            req = request_for(scenario('one', 'human', 'observed'))
            req['coding'][0]['activities']['correction'] = {'system': system, 'code': code}
            row = evaluate(req)['results'][0]
            self.assertEqual(row['coding']['entries'][0]['activity'], {'system': system, 'code': code})
            self.assertEqual({k: row[k] for k in row if k != 'coding'}, {k: base[k] for k in base if k != 'coding'})
            self.assertEqual(row['coding']['revision'], base['coding']['revision'])
            self.assertEqual(row['coding']['entries'][0]['entities'], base['coding']['entries'][0]['entities'])
        result = evaluate(request_for(scenario('one', 'human', 'observed')))
        self.assertEqual((result['inferred_information'], result['clinical_assertions_added'], result['converted_to_base']), ([], [], False))
        self.assertEqual(result['certificate']['status'], 'not_certified')
        self.assertIn('assumption:revision_role_declared', result['results'][0]['flows']['added'])

    def test_revision_entities_carry_the_revised_record_with_an_independent_hash(self):
        """T4・Z1〜Z3・D2：向き（target＝選ばれた訂正、what＝訂正された側）、同一性（記録の参照と独立に計算したハッシュ）、多重度（記録ごとに一つ、昇順）、
        付ける場所（生成側の項目だけ）。連鎖では直接の前の版だけ。"""
        for name, refs in [('V04', ['A']), ('V08', ['A']), ('V09', ['A', 'A2']), ('V10', ['B']), ('V20', ['A'])]:
            result = evaluate(fixture(name))
            row = result['results'][0]
            records = {r['id']: r for r in result['ledger']['records']}
            entries = row['coding']['entries']
            self.assertEqual(row['coding']['revision'], {'state': 'carried', 'predecessors': refs}, name)
            self.assertEqual(len(entries), len(row['observation']['provenance']), name)
            holder = [e for e in entries if e['entities']]
            self.assertEqual([e['index'] for e in holder], [0], name)
            self.assertEqual(row['observation']['provenance'][0]['activity'], 'creation')
            self.assertEqual(row['observation']['provenance'][0]['target']['record_ref'], row['selection']['record_ref'])        # target＝新しい版
            self.assertEqual([e['what']['record_ref'] for e in holder[0]['entities']], refs, name)
            self.assertTrue(set(refs) <= set(records[row['selection']['record_ref']]['revises']), name)
            for entity in holder[0]['entities']:
                self.assertEqual(entity['role'], 'revision')
                self.assertEqual(entity['what']['type'], 'Observation')
                self.assertEqual(entity['what']['record_sha256'], oracle.record_hash(result['ledger'], records[entity['what']['record_ref']]), name)
                self.assertNotEqual(entity['what']['record_sha256'], row['selection']['record_sha256'])
            for entry in entries:
                if entry['kind'] == 'confirmation':
                    self.assertEqual(entry['entities'], [], name)
        chain = evaluate(fixture('V10'))['results'][0]
        self.assertNotIn('A', json.dumps(chain['coding']['entries']))
        self.assertIn('revision_history', chain['flows']['lost'])                              # 連鎖の全体は運ばない
        before = evaluate(fixture('V04'))['results'][0]['coding']['entries'][0]['entities'][0]['what']['record_sha256']
        req = fixture('V04')
        req['observation_request']['grounding_request']['library_request']['library']['operations'][0]['value'] = lib.value(q.point(9))
        after = reference(req)['results'][0]['coding']['entries'][0]['entities'][0]['what']['record_sha256']
        self.assertNotEqual(before, after)                                                     # 訂正された記録の内容が変わるとハッシュが変わる

    def test_the_relation_needs_a_known_agent(self):
        """T5・T6・Z4・Z5・Z7：訂正の関係は生成側の項目（agent が分かる）にだけ付く。観察者が不明で出自が AI でない訂正は、確認済みでも運べない（no_agent）。
        観察者を足す、または出自が AI なら運べる。確認者の型の宣言がなければ no_provenance、人の観察者の型の宣言がなければ P2-q が依頼で止まる。"""
        count = 0
        for observer, origin in product(['unknown', 'human', 'device'], ['observed', 'ai_candidate']):
            row = reference(request_for(scenario('one', observer, origin)))['results'][0]
            count += 1
            agent = observer != 'unknown' or origin == 'ai_candidate'
            self.assertEqual(row['coding']['revision']['state'], 'carried' if agent else 'no_agent', (observer, origin))
            self.assertEqual(row['coding']['revision']['predecessors'], ['A'])
            self.assertEqual(any(e['entities'] for e in row['coding']['entries']), agent)
            self.assertEqual('revision:predecessor_identity' in row['flows']['retained'], agent)
            self.assertEqual('revision:predecessor_identity' in row['flows']['lost'], not agent)
            self.assertIn('revision_history', row['flows']['lost'])
            self.assertEqual([e['kind'] for e in row['coding']['entries']], (['correction'] if agent else [])+['confirmation'])
        self.assertEqual(count, 6)
        row = reference(request_for(scenario('one', 'human', 'observed'), reviewer=False))['results'][0]
        self.assertEqual((row['coding']['state'], row['coding']['revision']['state'], row['coding']['entries']), ('coded', 'no_provenance', []))
        req = request_for(scenario('one', 'human', 'observed'))
        del req['observation_request']['observations'][0]['provenance']['observer_type']
        row = reference(req)['results'][0]
        self.assertEqual((row['observation']['state'], row['coding']), ('needs_information', {'state': 'not_evaluated', 'entries': None, 'revision': None}))
        self.assertEqual(row['requests'], [obs.observer_request('B')])
        self.assertEqual(json.dumps(evaluate(request_for(scenario('one', 'unknown', 'observed')))).count('"agents"'), 1)        # Provenance の項目は確認の1件だけ。agent を作らない

    def test_rows_not_evaluated_or_not_declared_pass_through_the_observation_rows(self):
        """T2・D3：P2-q 単独の実行との差分。coding を除くと全欄が同じ（出せた行の流れだけが、宣言した差で増える）。通す行の coding は null。"""
        rng = random.Random(800001)
        seen = set()
        for _ in range(250):
            req = random_provenance(rng)
            result = reference(req)
            alone = evaluate({**deepcopy(req['observation_request']), 'budget': {'max_steps': 100000}})
            self.assertEqual(alone['status'], 'ok')
            for key in ('ledger', 'library', 'temporal_measurement', 'grounding_run', 'clinical_confirmation', 'review_verification', 'uncertainty_propagated'):
                self.assertEqual(result[key], alone[key], key)
            for row, base in zip(result['results'], alone['results']):
                state = row['coding']['state']
                seen.add(state)
                self.assertEqual(set(row) - {'coding'}, set(base))
                for key in base:
                    if key == 'flows' and state == 'coded':
                        continue
                    self.assertEqual(row[key], base[key], (state, key))
                if state == 'coded':
                    self.assertEqual(base['observation']['state'], 'projected')
                    for part in ('retained', 'lost', 'added'):                       # P2-q が報告したことを一つも取り除かない
                        self.assertTrue(set(base['flows'][part]) <= set(row['flows'][part]), part)
                    self.assertFalse(set(row['flows']['retained']) & set(row['flows']['lost']))
                else:
                    self.assertEqual((row['coding']['entries'], row['coding']['revision']), (None, None))
                    self.assertEqual(row['flows'], base['flows'])
                    self.assertEqual(state == 'not_declared', base['observation']['state'] == 'projected')
        self.assertEqual(seen, {'coded', 'not_declared', 'not_evaluated'})

    def test_structure_facts_are_bound_to_their_sources(self):
        """PT-10：構造の事実が台帳のページのハッシュと一致し、手元にページがあれば、目印の語がページに存在する。呼び出し側は事実・種類・役割を変えられない。"""
        spec = json.loads((ROOT/'src/med_dsl/provenance_coding_spec.json').read_text())
        ledger = {x['id']: x for x in json.loads((ROOT/'docs/research/03-materials.json').read_text())['materials']}
        self.assertEqual([f['id'] for f in spec['facts']], ['F-A1', 'F-A2', 'F-E1', 'F-E2', 'F-E3', 'F-E4', 'F-E5', 'F-V1'])
        present = 0
        for fact in spec['facts']:
            material = ledger[fact['source']]
            self.assertEqual((material['local_sha256'], material['version'], material['commit_payload']), (fact['source_sha256'], '5.0.0', False), fact['id'])
            page = ROOT/material['local_path']
            if page.is_file():
                raw = page.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fact['source_sha256'], fact['id'])
                self.assertIn(fact['marker'], page_text(raw), fact['id'])
                present += 1
        self.assertIn(present, (0, 8))
        self.assertEqual(spec['entity_role'], 'revision')
        role_marker = next(f for f in spec['facts'] if f['id'] == 'F-E2')['marker']
        self.assertIn(spec['entity_role'], role_marker.split(' | '))                       # 固定した役割は、必須の集合に含まれる
        self.assertIn('derivation', next(f for f in spec['facts'] if f['id'] == 'F-V1')['marker'])
        self.assertNotIn('derivation', role_marker)                                        # R4 の語は R5 の集合にない
        self.assertEqual((spec['activity_kinds'], spec['revision_states']), (['creation', 'correction', 'confirmation'], ['not_applicable', 'not_requested', 'no_provenance', 'no_agent', 'carried']))
        for key in ('facts', 'activity_kinds', 'entity_role', 'revision_states'):
            req = fixture('V01')
            req[key] = []
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])
            req = fixture('V01')
            req['coding'][0][key] = []
            self.assertEqual(evaluate(req)['reason_codes'], ['unknown_field'])

    def test_full_cost_funded_once_and_the_child_uses_its_reservation(self):
        for name, total, child_total in [('V01', 46, 42), ('V04', 51, 47), ('V09', 56, 52), ('V11', 49, 45), ('V13', 79, 73)]:
            req = fixture(name)
            seen = []

            def tracked(child):
                seen.append(child['budget']['max_steps'])
                out = child_runner(child)
                self.assertEqual(out['steps_used'], child['budget']['max_steps'])
                return out
            with patch('med_dsl.provenance_coding.run_observation', side_effect=tracked):
                result = reference(req)
            self.assertEqual(seen, [child_total])
            self.assertEqual((result['steps_used'], result['observation_run']['reserved_steps'], result['observation_run']['steps_used']), (total, child_total, child_total))
        with patch('med_dsl.provenance_coding.run_observation', side_effect=AssertionError('unfunded child')):
            self.assertEqual(evaluate(fixture('B03-plan'))['status'], 'resource_limit')
        rng = random.Random(800002)
        for _ in range(50):
            req = random_provenance(rng)
            self.assertEqual(evaluate(req)['steps_used'], oracle.cost(req))

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-provenance',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['V01', 'V13', 'V04']:
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
        req = fixture('V13')

        def stopped(child):
            out = child_runner(child)
            out.update(status='resource_limit', reason_codes=['injected_observation_limit'])
            return out
        with patch('med_dsl.provenance_coding.run_observation', side_effect=stopped):
            out = evaluate(req)
        self.assertEqual((out['status'], out['reason_codes'], out['steps_used']), ('resource_limit', ['injected_observation_limit'], 74))
        for row in out['results']:
            self.assertEqual([row[key] for key in FIELDS], [None]*9)
            self.assertEqual(row['reason_codes'], ['injected_observation_limit'])

        def wrong_cost(child):
            out = child_runner(child)
            out['steps_used'] -= 1
            return out
        with patch('med_dsl.provenance_coding.run_observation', side_effect=wrong_cost):
            self.assertEqual(evaluate(fixture('V01'))['reason_codes'], ['observation_cost_mismatch'])
        with patch('med_dsl.provenance_coding._record_hash', return_value='0'*64):             # 結ばれたハッシュの自己検証
            out = evaluate(fixture('V04'))
        self.assertEqual((out['status'], out['reason_codes']), ('invalid_input', ['record_hash_mismatch']))
        calls, real_row = [], native._row

        def second_row_failure(row, declaration, ledger, reviewer_declared, spec):
            calls.append(row['id'])
            if len(calls) == 2:
                raise Problem('injected_row_limit', status='resource_limit')
            return real_row(row, declaration, ledger, reviewer_declared, spec)
        with patch('med_dsl.provenance_coding._row', side_effect=second_row_failure):
            out = evaluate(req)
        self.assertEqual(out['status'], 'resource_limit')
        self.assertEqual(out['results'][0]['status'], 'satisfied')
        self.assertEqual(out['results'][1]['reason_codes'], ['injected_row_limit'])
        self.assertEqual([out['results'][1][key] for key in FIELDS], [None]*9)
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
        for filename in ['provenance_coding_spec.json', 'observation_projection_spec.json', 'structure_grounding_spec.json', 'clinical_library_spec.json']:
            def corrupt(path):
                return b'{}' if path.name == filename else original(path)
            with patch.object(Path, 'read_bytes', corrupt):
                self.assertEqual(evaluate(fixture('V01'))['reason_codes'], ['native_spec_mismatch'], filename)
        req = fixture('V01')
        req['padding'] = 'x'*1048576
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        req = fixture('V01')
        nested = None
        for _ in range(65):
            nested = [nested]
        req['padding'] = nested
        self.assertEqual(evaluate(req)['status'], 'resource_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req = fixture('V04')
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
        req = fixture('V13')
        before = deepcopy(req)
        first = reference(req)
        self.assertEqual(req, before)
        shuffled = deepcopy(req)
        shuffled['coding'].reverse()
        child = shuffled['observation_request']
        child['observations'].reverse()
        child['grounding_request']['targets'].reverse()
        child['grounding_request']['library_request']['queries'].reverse()
        child['grounding_request']['library_request']['destinations'].reverse()
        second = reference(shuffled)
        for a, b in zip(first['results'], second['results']):
            for key in ('status', 'reason_codes', 'observation', 'flows', 'requests', 'grounding', 'coding'):
                self.assertEqual(a[key], b[key])

    def test_checker_detects_early_values(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('observation', []), ('grounding', []), ('flows', {}), ('requests', []), ('coding', {}), ('coding', [])]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('provenance', fixture('V01'), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', fixture('V01'), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        both = "'activity': deepcopy(declaration['activities'].get(kind))"
        mutants = [
            ('activity_substituted', '_coded', [(both, "'activity': deepcopy(declaration['activities'].get(kind) or declaration['activities'].get('creation'))")], 'V12'),
            ('correction_called_creation', '_coded', [("('correction' if correction else 'creation')", "'creation'")], 'V04'),
            ('activity_assumption_always', '_coded', [("if any(entry['activity'] is not None for entry in entries):", 'if True:')], 'V02'),
            ('uncoded_not_lost', '_coded', [("        if entry['activity'] is None:", '        if False:')], 'V02'),
            ('revision_without_flag', '_coded', [("    elif not declaration['revision']:\n        state = 'not_requested'", "    elif False:\n        state = 'not_requested'")], 'V05'),
            ('revision_on_original', '_coded', [("    if not correction:\n        state = 'not_applicable'", "    if False:\n        state = 'not_applicable'")], 'V01'),
            ('selected_hash_instead', '_coded', [("'record_sha256': _record_hash(ledger['source'], ledger['records'][predecessor])", "'record_sha256': selection['record_sha256']")], 'V04'),
            ('first_predecessor_only', '_coded', [('for predecessor in predecessors:', 'for predecessor in predecessors[:1]:')], 'V09'),
            ('predecessors_reversed', '_coded', [('for predecessor in predecessors:', 'for predecessor in reversed(predecessors):')], 'V09'),
            ('role_source', '_coded', [("'role': spec['entity_role']", "'role': 'source'")], 'V04'),
            ('no_agent_attached_anyway', '_coded', [('    elif not generating:', '    elif not entries:'), ('entries[generating[0]]', 'entries[(generating or [len(entries)-1])[0]]')], 'V06'),
            ('revision_not_retained', '_coded', [("retained |= set(flows['revision_carried'])", 'pass')], 'V04'),
            ('revision_loss_not_reported', '_coded', [("lost |= set(flows['revision_lost'])", 'pass')], 'V05'),
            ('predecessors_hidden_when_not_carried', '_coded', [("'predecessors': predecessors}", "'predecessors': predecessors if state == 'carried' else []}")], 'V05'),
            ('p2q_row_altered', '_coded', [('    out = deepcopy(row)\n', "    out = deepcopy(row)\n    out['requests'] = [{'x': 1}]\n")], 'V04'),
            ('not_declared_as_not_evaluated', '_row', [("return _passed(row, 'not_declared')", "return _passed(row, 'not_evaluated')")], 'V13'),
            ('unprojected_row_coded', '_row', [("if row['observation']['state'] != 'projected':", 'if False:')], 'V14'),
            ('reviewer_ignored', 'run_coding', [("observed is not None and observed['reviewer_type'] is not None", 'True')], 'V07'),
            ('prepayment_removed', 'run_coding', [('        for _ in range(cost):\n            budget.tick()\n', '')], 'V01'),
            ('completion_fee_removed', 'run_coding', [("        current, stage = None, 'completion'\n        budget.tick()\n", "        current, stage = None, 'completion'\n")], 'B01-45'),
            ('inferred_information', 'run_coding', [("'clinical_assertions_added': [], 'inferred_information': []", "'clinical_assertions_added': [], 'inferred_information': ['guess']")], 'V01'),
            ('certified', 'run_coding', [("'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'")], 'V01'),
            ('kinds_widened', '_codings', [("tuple(spec['activity_kinds'])", "tuple(spec['activity_kinds']) + ('revision', 'derivation', 'removal', 'amend')")], 'N08-kind-derivation'),
            ('boolean_unchecked', '_codings', [('if type(revision) is not bool:', 'if False:')], 'N10-revision-string'),
        ]
        for ident, name, replacements, case in mutants:
            source = inspect.getsource(getattr(native, name))
            for old, new in replacements:
                self.assertEqual(source.count(old), 1, ident)
                source = source.replace(old, new)
            namespace = dict(vars(native))
            exec(compile(source, f'<provenance-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-provenance-request-draft-1'][:3], namespace['run_coding'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-provenance-request-draft-1': surface}):
                try:
                    out = evaluate(deepcopy(data['request']))
                    bad = p2_checks.failed_checks(out, data['expected']['checks'])
                    if not bad and out['status'] == 'ok':
                        try:                                          # 期待の確認で見つからない変異（ハッシュなど）は、別計算との照合で確かめる
                            reference(deepcopy(data['request']))
                        except AssertionError as error:
                            bad = [repr(error)]
                except Exception as error:                       # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        self.assertEqual(len(mutants), 24)
        data = json.loads((DIRECTORY/'v01.json').read_text())
        with patch.object(native, 'OWN_FEE', 1):
            self.assertTrue(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']))


if __name__ == '__main__':
    unittest.main()
