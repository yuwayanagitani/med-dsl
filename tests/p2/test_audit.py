"""P2-u：手指定期待、別計算との比較、差の全数、継続の同一性、属性の方針、入れ替え、並びの不変性、共通予算、変異。"""
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
from med_dsl import evaluate, host, terminology_audit as native
import gen_audit_fixtures as make
import audit_oracle as oracle
import p2_checks
DIRECTORY = ROOT/'examples/p2-audit'
FIELDS = native.VALUE_FIELDS
STATES = make.STATES


def fixture(name):
    return json.loads((DIRECTORY/(name.lower()+'.json')).read_text())['request']


def compare(request, result):
    """実装の結果を、別計算の期待と全行・集計・料金で照合する。"""
    if result['status'] != 'ok':
        raise AssertionError(result)
    refs = sorted(request['references'])
    if [r['reference'] for r in result['results']] != refs:
        raise AssertionError('order')
    rows = []
    for got in result['results']:
        want = oracle.row(request, got['reference'])
        have = {k: got[k] for k in want}
        if have != want:
            raise AssertionError((got['reference'], have, want))
        if (got['assessment_complete'], got['reason_codes']) != (True, []):
            raise AssertionError(got)
        rows.append(want)
    if result['summary'] != oracle.summary(request, rows):
        raise AssertionError((result['summary'], oracle.summary(request, rows)))
    if result['steps_used'] != oracle.cost(request):
        raise AssertionError((result['steps_used'], oracle.cost(request)))
    if sum(result['summary']['by_state'].values()) != len(refs):
        raise AssertionError('partition')
    return result


def reference(request):
    return compare(request, evaluate(request))


def random_audit(rng):
    kinds, labels = ['full', 'syn', 'form'], ['alpha', 'beta', 'gamma', 'delta']
    attribute_names, values = ['strength', 'code_list', 'flag', 'other'], ['v1', 'v2', 'v3']
    count = rng.randrange(6, 16)
    counter = iter(range(1, 10**6))
    old = {}
    for i in range(count):
        atoms = [make.atom(f'a{next(counter)}', rng.choice(kinds), rng.choice(labels)+' '+str(rng.randrange(3)),
                           sorted({(rng.choice(attribute_names), rng.choice(values)) for _ in range(rng.randrange(0, 4))})) for _ in range(rng.randrange(0, 4))]
        targets = sorted({'c'+str(rng.randrange(count+2)) for _ in range(rng.randrange(0, 4))})
        old['c'+str(i)] = make.concept('c'+str(i), rng.choice(['S', 'S', 'S', 'X']), atoms, [(rng.choice(['isa', 'has_part']), t) for t in targets])
    new = deepcopy(old)
    for ident in sorted(new):
        roll = rng.random()
        if roll < .08:
            del new[ident]
            continue
        c = new[ident]
        if rng.random() < .05:
            c['source'] = 'X' if c['source'] == 'S' else 'S'
        for a in c['atoms']:
            if rng.random() < .15:
                a['name'] += ' x'
            if rng.random() < .1:
                a['kind'] = rng.choice(kinds)
            if a['attributes'] and rng.random() < .25:
                a['attributes'][0]['value'] = rng.choice(values+['v4'])
            if rng.random() < .2:
                pair = (rng.choice(attribute_names), rng.choice(values))
                if pair not in {(x['name'], x['value']) for x in a['attributes']}:
                    a['attributes'].append({'name': pair[0], 'value': pair[1]})
            if a['attributes'] and rng.random() < .15:
                a['attributes'].pop()
            unique, seen_pairs = [], set()
            for x in a['attributes']:
                if (x['name'], x['value']) not in seen_pairs:
                    seen_pairs.add((x['name'], x['value']))
                    unique.append(x)
            a['attributes'] = unique
        if rng.random() < .2:
            c['atoms'].append(make.atom(f'a{next(counter)}', rng.choice(kinds), 'new '+str(rng.randrange(3)), [(rng.choice(attribute_names), 'v1')]))
        if c['atoms'] and rng.random() < .15:
            c['atoms'].pop(rng.randrange(len(c['atoms'])))
        if c['relations'] and rng.random() < .25:
            c['relations'].pop(rng.randrange(len(c['relations'])))
        if rng.random() < .25:
            pair = (rng.choice(['isa', 'has_part']), 'c'+str(rng.randrange(count+3)))
            if pair not in {(r['kind'], r['target']) for r in c['relations']}:
                c['relations'].append({'kind': pair[0], 'target': pair[1]})
    for j in range(rng.randrange(0, 4)):
        new['c'+str(count+j)] = make.concept('c'+str(count+j), rng.choice(['S', 'X']), [make.atom(f'a{next(counter)}', 'full', 'fresh '+str(j))])
    policy = [{'name': n, 'class': rng.choice(['definitional', 'administrative'])} for n in attribute_names if rng.random() < .6]
    refs = rng.sample(sorted(old), rng.randrange(1, min(10, count)+1))
    return make.request(old, new, refs, policy, sources=('S',) if rng.random() < .7 else ('S', 'X'))


class AuditTests(unittest.TestCase):
    def test_hand_expectations_api_cli_manifest_and_obligations(self):
        manifest = json.loads((DIRECTORY/'manifest.json').read_text())
        self.assertEqual(manifest['conditions'], {'U': 27, 'N': 12, 'B': 2})
        self.assertEqual(len(manifest['files']), 88)
        declaration = json.loads((ROOT/'extensions/p2-terminology-audit.json').read_text())
        self.assertEqual({o['id'] for o in declaration['obligations']}, {'K-ID', 'K-STOP', 'K-INV', 'K-RES', 'R5-1', 'R5-2', 'R5-3'} | {f'AU-{i}' for i in range(1, 10)})
        self.assertEqual((declaration['inherits'], declaration['depends_on']), ([], [{'id': 'p0-positive', 'version': 'draft-2'}]))
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
        report = p2_checks.suite_report('p2-audit', evaluate)
        self.assertEqual((report['examples'], report['checks'], report['failures']), (88, 1679, []))

    def test_enumeration_of_differences_against_the_oracle(self):
        """D1：名称の差（なし／あり）×関係の差（なし／対象が残る除去）×属性の差の部分集合（strength・code_list・flag の8通り）×方針（3種）×継続／不在。
        別計算と一致し、各参照がちょうど一つの状態に入り、状態の優先が成り立つ。"""
        policies = {'full': [{'name': 'code_list', 'class': 'administrative'}, {'name': 'strength', 'class': 'definitional'}, {'name': 'flag', 'class': 'administrative'}],
                    'flag_missing': make.POL, 'empty': []}
        count, seen = 0, set()
        for named, related, subset, policy, kept in product([False, True], [False, True], product([False, True], repeat=3), policies, [True, False]):
            old = make.world()
            find = lambda w: make.find_atom(w, 'c1', 'a1')
            new = make.world()
            if kept:
                if named:
                    new['c1']['atoms'].append(make.atom('a5', 'syn', 'extra'))
                if related:
                    new['c1']['relations'] = [r for r in new['c1']['relations'] if r['target'] != 'c8']
                if subset[0]:
                    find(new)['attributes'][1]['value'] = '6 mg'
                if subset[1]:
                    find(new)['attributes'][0]['value'] = 'N2'
                if subset[2]:
                    find(new)['attributes'].append({'name': 'flag', 'value': 'x'})
            else:
                del new['c1']
            req = make.request(old, new, ['c1'], policies[policy])
            row = reference(req)['results'][0]
            count += 1
            seen.add(row['audit_state'])
            if kept:
                declared = {p['name']: p['class'] for p in policies[policy]}
                kinds = {declared.get(n, 'undeclared') for flag, n in zip(subset, ['strength', 'code_list', 'flag']) if flag}
                want = ('changed' if named or related or 'definitional' in kinds else 'needs_information' if 'undeclared' in kinds
                        else 'changed_administrative_only' if 'administrative' in kinds else 'unchanged_in_scope')
                self.assertEqual(row['audit_state'], want)
            else:
                self.assertEqual((row['audit_state'], row['successor']), ('not_found', 'not_determined'))
        self.assertEqual(count, 2*2*8*3*2)
        self.assertEqual(seen, {'unchanged_in_scope', 'changed_administrative_only', 'changed', 'needs_information', 'not_found'})
        for name in ['U01', 'U03', 'U04', 'U07', 'U10', 'U11', 'U22', 'U25']:
            reference(fixture(name))

    def test_continuation_is_by_source_and_id_never_by_name(self):
        """AP4・D5・Z4：旧版の概念と名称・属性・関係が同じ別の ID の概念を何件加えても、旧版の概念は `not_found` で、候補も後継も出ない。
        出典が変わった同じ ID も別の概念として扱う。"""
        old = make.world()
        for clones in range(0, 4):
            new = make.world()
            del new['c2']
            for k in range(clones):
                twin = deepcopy(make.world()['c2'])
                twin['id'] = f'c2clone{k}'
                twin['atoms'][0]['id'] = f'a3clone{k}'
                new[twin['id']] = twin
            result = reference(make.request(old, new, ['c2']))
            row = result['results'][0]
            self.assertEqual((row['presence'], row['audit_state'], row['successor'], row['facets']), ('not_found', 'not_found', 'not_determined', None))
            self.assertNotIn('clone', json.dumps(result['results']))                         # 候補として出さない
            self.assertEqual(result['summary']['to_only'], clones)
        moved = make.world()
        moved['c2']['source'] = 'X'
        self.assertEqual(reference(make.request(old, moved, ['c2']))['results'][0]['audit_state'], 'not_found')
        row = reference(make.request(old, make.world(), ['c2']))['results'][0]                # 名称が違っても、同じ (出典, id) なら継続
        self.assertEqual(row['presence'], 'continues')
        renamed = make.world()
        renamed['c2']['atoms'][0]['name'] = 'completely different'
        row = reference(make.request(old, renamed, ['c2']))['results'][0]
        self.assertEqual((row['presence'], row['audit_state']), ('continues', 'changed'))

    def test_attribute_policy_is_declared_never_guessed(self):
        """AP6・Z1〜Z3・D7：差のあった属性の分類は宣言だけで決まる。未宣言は `undeclared` と依頼で、推測しない。使われなかった宣言は痕跡を残さない。
        値の文字列は不透明。"""
        for name, cls in product(['strength', 'code_list', 'flag', 'zz'], ['definitional', 'administrative', None]):
            new = make.world()
            make.find_atom(new, 'c1', 'a2')['attributes'].append({'name': name, 'value': 'x'})
            policy = [] if cls is None else [{'name': name, 'class': cls}]
            row = reference(make.request(make.world(), new, ['c1'], policy))['results'][0]
            attrs = row['facets']['attributes']
            self.assertEqual([len(attrs[k]) for k in ('definitional', 'administrative', 'undeclared')], [1 if cls == 'definitional' else 0, 1 if cls == 'administrative' else 0, 1 if cls is None else 0])
            self.assertEqual(row['audit_state'], {'definitional': 'changed', 'administrative': 'changed_administrative_only', None: 'needs_information'}[cls])
            self.assertEqual(row['requests'], [] if cls else [make.attribute_request('c1', name)])
            self.assertEqual(row['policy_assumptions'], [f'attribute_class:{name}:{cls}'] if cls else [])
        unused = reference(make.request(make.world(), make.world(), ['c1', 'c2'], make.POL+[{'name': 'zz', 'class': 'definitional'}]))
        self.assertTrue(all(r['policy_assumptions'] == [] for r in unused['results']))
        for value in ['a', '', 'x y', '5 mg']:
            new = make.world()
            make.find_atom(new, 'c2', 'a3')['attributes'][0]['value'] = value
            row = reference(make.request(make.world(), new, ['c2']))['results'][0]
            self.assertEqual(row['facets']['attributes']['definitional'][0]['to'], [value])
        result = evaluate(make.request(make.world(), make.world(), ['c1']))
        self.assertEqual((result['inferred_information'], result['clinical_assertions_added'], result['converted_to_base']), ([], [], False))
        self.assertEqual(result['certificate']['status'], 'not_certified')

    def test_swapping_the_versions_swaps_the_differences_and_infers_nothing(self):
        """AP7・D3・Z8：旧版と新版を入れ替えると、継続した参照の追加と削除、値の from と to が入れ替わり、`not_found` と新版のみの数が入れ替わる。
        どちらの結果も逆向きの推定を含まない。"""
        rng = random.Random(820001)
        compared = 0
        for _ in range(120):
            req = random_audit(rng)
            sources = set(req['scope']['sources'])
            swapped = deepcopy(req)
            swapped['from'], swapped['to'] = deepcopy(req['to']), deepcopy(req['from'])
            swapped['from']['version'], swapped['to']['version'] = req['from']['version'], req['to']['version']
            swapped['references'] = [r for r in req['references'] if any(c['id'] == r and c['source'] in sources for c in req['to']['concepts'])]
            if not swapped['references']:
                continue
            forward = {r['reference']: r for r in reference(req)['results']}
            back = reference(swapped)
            self.assertFalse(back['reverse_inferred'])
            for row in back['results']:
                ahead = forward[row['reference']]
                if row['presence'] != 'continues' or ahead['presence'] != 'continues':
                    continue
                compared += 1
                a, b = ahead['facets'], row['facets']
                self.assertEqual(a['names']['added'], b['names']['removed'])
                self.assertEqual(a['names']['removed'], b['names']['added'])
                self.assertEqual([(m['id'], m['from'], m['to']) for m in a['names']['modified']], [(m['id'], m['to'], m['from']) for m in b['names']['modified']])
                flip = lambda items: [(x['kind'], x['target'], x['target_in_to'], x['target_in_from']) for x in items]
                self.assertEqual([(x['kind'], x['target'], x['target_in_from'], x['target_in_to']) for x in a['relations']['added']], flip(b['relations']['removed']))
                self.assertEqual([(x['kind'], x['target'], x['target_in_from'], x['target_in_to']) for x in a['relations']['removed']], flip(b['relations']['added']))
                for kind in ('definitional', 'administrative', 'undeclared'):
                    self.assertEqual([(x['atom'], x['name'], x['from'], x['to']) for x in a['attributes'][kind]], [(x['atom'], x['name'], x['to'], x['from']) for x in b['attributes'][kind]])
        self.assertGreater(compared, 100)
        old = make.world()
        new = make.world()
        del new['c9']
        there, back = reference(make.request(old, new, ['c9'])), reference(make.request(new, old, ['c1']))
        self.assertEqual((there['summary']['from_only'], there['summary']['to_only'], back['summary']['from_only'], back['summary']['to_only']), (1, 0, 0, 1))

    def test_input_order_never_matters_and_the_input_is_not_changed(self):
        """D4：概念・原子・関係・属性・参照・方針の並びを替えても結果は同じ。入力は変更されない。"""
        rng = random.Random(820002)
        for _ in range(60):
            req = random_audit(rng)
            before = deepcopy(req)
            first = reference(req)
            self.assertEqual(req, before)
            shuffled = deepcopy(req)
            for snapshot in (shuffled['from'], shuffled['to']):
                rng.shuffle(snapshot['concepts'])
                for c in snapshot['concepts']:
                    rng.shuffle(c['atoms'])
                    rng.shuffle(c['relations'])
                    for a in c['atoms']:
                        rng.shuffle(a['attributes'])
            rng.shuffle(shuffled['references'])
            rng.shuffle(shuffled['policy']['attributes'])
            rng.shuffle(shuffled['scope']['sources'])
            second = reference(shuffled)
            for key in ('results', 'summary', 'policy', 'scope', 'steps_used'):
                self.assertEqual(first[key], second[key], key)

    def test_random_requests_against_the_oracle(self):
        """D2：乱数の300要求を別計算と比べる。全ての状態が現れ、集計の和は参照の数に等しい。"""
        rng = random.Random(820003)
        seen = set()
        for _ in range(300):
            result = reference(random_audit(rng))
            seen |= {r['audit_state'] for r in result['results']}
        self.assertEqual(seen, set(STATES))

    def test_the_extension_stands_alone(self):
        """AP1・AP10：この拡張のモジュールは、核の部品（model・validation）のほか、他の拡張のモジュールを import しない。"""
        source = (ROOT/'src/med_dsl/terminology_audit.py').read_text()
        imports = {line.split()[1] for line in source.splitlines() if line.startswith('from .')}
        self.assertEqual(imports, {'.model', '.validation'})

    def test_budget_sweep_keeps_finished_rows_and_has_no_partial_values(self):
        report = p2_checks.budget_report(p2_checks.load_requests(('p2-audit',)), evaluate)
        self.assertEqual(report['violations'], [])
        for name in ['U01', 'U07', 'U25']:
            req = fixture(name)
            full = deepcopy(req)
            full['budget'] = {'max_steps': 100000}
            done = evaluate(full)
            for maximum in range(done['steps_used']+2):
                req['budget']['max_steps'] = maximum
                out = evaluate(req)
                self.assertLessEqual(out['steps_used'], maximum)
                self.assertEqual(out['summary'] is None, maximum < done['steps_used'])
                for row, ready in zip(out['results'], done['results']):
                    if row['assessment_complete']:
                        self.assertEqual(row, ready)
                    else:
                        for key in FIELDS:
                            self.assertIsNone(row[key], (name, maximum, key))
                if out['status'] == 'resource_limit':
                    self.assertEqual(out['certificate']['status'], 'not_certified')

    def test_the_cost_formula_is_exact_and_prepaid_per_reference(self):
        for name, total in [('U01', 30), ('U07', 29), ('U10', 14), ('U11', 13), ('U25', 45)]:
            result = evaluate(fixture(name))
            self.assertEqual((result['steps_used'], oracle.cost(fixture(name))), (total, total), name)
        req = fixture('U01')
        req['budget']['max_steps'] = 21                                                            # c1 の料金（13）を払い切れない：c1 は未完了で値を持たない
        out = evaluate(req)
        self.assertEqual([r['assessment_complete'] for r in out['results']], [False, False])
        req['budget']['max_steps'] = 22
        out = evaluate(req)
        self.assertEqual([r['assessment_complete'] for r in out['results']], [True, False])

    def test_static_validation_pins_limits_and_native_refusals(self):
        for path in sorted(DIRECTORY.glob('n*.json')):
            if path.name.startswith('n12') or path.name == 'n01-missing-budget.json':
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

        def corrupt(path):
            return b'{}' if path.name == 'terminology_audit_spec.json' else original(path)
        with patch.object(Path, 'read_bytes', corrupt):
            self.assertEqual(evaluate(fixture('U01'))['reason_codes'], ['native_spec_mismatch'])
        req = fixture('U01')
        req['padding'] = 'x'*1048576
        self.assertEqual(evaluate(req)['status'], 'resource_limit')
        req = fixture('U01')
        nested = None
        for _ in range(65):
            nested = [nested]
        req['padding'] = nested
        self.assertEqual(evaluate(req)['status'], 'resource_limit')

    def test_all_nodes_type_fuzz_is_total_before_budget(self):
        req = fixture('U04')
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

    def test_checker_detects_early_values(self):
        for key, value in [(key, {'early': True}) for key in FIELDS] + [('facets', []), ('requests', [{'x': 1}]), ('policy_assumptions', ['x']), ('audit_state', 'changed')]:
            def leak(req):
                out = evaluate(req)
                for row in out.get('results', []):
                    if not row['assessment_complete']:
                        row[key] = value
                        break
                return out
            self.assertTrue(p2_checks.budget_violations('audit', fixture('U01'), leak)[0], (key, value))

        def early(req):
            out = evaluate(req)
            if out['status'] == 'resource_limit':
                out['certificate']['status'] = 'certified'
            return out
        self.assertTrue(p2_checks.budget_violations('early-cert', fixture('U01'), early)[0])

    def test_selected_mutants_are_detected_by_reference(self):
        mutants = [
            ('continuation_by_id_only', 'audit_reference', [("    if twin is None or twin['source'] != concept['source']:", '    if twin is None:')], 'U23'),
            ('successor_guessed', 'audit_reference', [("'successor': 'not_determined'}", "'successor': 'c11'}")], 'U10'),
            ('history_request_dropped', 'audit_reference', [("'facets': None, 'requests': [history], 'policy_assumptions': [],", "'facets': None, 'requests': [], 'policy_assumptions': [],")], 'U10'),
            ('undeclared_guessed', '_attributes', [("groups[classes.get(name, 'undeclared')]", "groups[classes.get(name, 'administrative')]")], 'U04'),
            ('unused_declaration_assumed', 'audit_reference', [("used = {entry['name'] for entry in attributes['definitional'] + attributes['administrative']}", 'used = set(classes)')], 'U19'),
            ('priority_swapped', 'audit_reference', [("    elif attributes['undeclared']:\n        state = 'needs_information'\n    elif attributes['administrative']:\n        state = 'changed_administrative_only'",
                                                        "    elif attributes['administrative']:\n        state = 'changed_administrative_only'\n    elif attributes['undeclared']:\n        state = 'needs_information'")], 'U18'),
            ('names_not_a_change', 'audit_reference', [("if names['state'] == 'changed' or relations['state'] == 'changed' or attributes['definitional']:", "if relations['state'] == 'changed' or attributes['definitional']:")], 'U17'),
            ('out_of_scope_compared', 'audit_reference', [("    if concept['source'] not in sources:", '    if False:')], 'U11'),
            ('target_flags_swapped', '_relations', [("'target_in_from': target in old_ids, 'target_in_to': target in new_ids", "'target_in_from': target in new_ids, 'target_in_to': target in old_ids")], 'U07'),
            ('old_unresolved_is_a_change', '_relations', [("any(item['in_from'] for item in unresolved)", 'bool(unresolved)')], 'U12'),
            ('removed_atom_attributes_ignored', '_attributes', [("'removed': sum(len(old_atoms[i]['attributes']) for i in set(old_atoms) - set(new_atoms))}", "'removed': 0}")], 'U16'),
            ('modified_atoms_ignored', '_names', [("for i in sorted(set(old_atoms) & set(new_atoms)) if (old_atoms[i]['kind'], old_atoms[i]['name']) != (new_atoms[i]['kind'], new_atoms[i]['name'])]", 'for i in []]')], 'U06'),
            ('continuing_ignores_source', 'summarize', [("if old_concepts[i]['source'] == new_concepts[i]['source']}", '}')], 'U27'),
            ('to_only_dropped', 'summarize', [("'to_only': len(in_new) - len(continuing)", "'to_only': 0")], 'U09'),
            ('out_of_scope_fee_zero', 'reference_fee', [('        return 1\n', '        return 0\n')], 'U11'),
            ('newer_fee_ignored', 'reference_fee', [('        fee += sum(_counts(twin))\n', '        pass\n')], 'U01'),
            ('index_prepayment_removed', 'run_audit', [("        for _ in range(len(old_concepts) + len(new_concepts)):\n            budget.tick()\n", '')], 'U01'),
            ('completion_fee_removed', 'run_audit', [("        budget.tick()\n        result['summary'] = summarize(", "        result['summary'] = summarize(")], 'B01-29'),
            ('inferred_information', 'run_audit', [("'clinical_assertions_added': [], 'inferred_information': []", "'clinical_assertions_added': [], 'inferred_information': ['guess']")], 'U01'),
            ('certified', 'run_audit', [("'certificate': {'status': 'not_certified'", "'certificate': {'status': 'certified'")], 'U01'),
            ('reverse_inferred', 'run_audit', [("'reverse_inferred': False", "'reverse_inferred': True")], 'U01'),
            ('class_set_widened', '_validate', [("        if item['class'] not in spec['attribute_classes']:", '        if False:')], 'N08-class'),
            ('same_version_accepted', '_validate', [("    if old['version'] == new['version']:", '    if False:')], 'N06-same-version'),
        ]
        for ident, name, replacements, case in mutants:
            source = inspect.getsource(getattr(native, name))
            for old, new in replacements:
                self.assertEqual(source.count(old), 1, ident)
                source = source.replace(old, new)
            namespace = dict(vars(native))
            exec(compile(source, f'<audit-mutant:{ident}>', 'exec'), namespace)
            data = json.loads((DIRECTORY/(case.lower()+'.json')).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks']), [], ident)
            surface = host.Surface(*host.SURFACES['p2-audit-request-draft-1'][:3], namespace['run_audit'])
            with patch.object(native, name, namespace[name]), patch.dict(host.SURFACES, {'p2-audit-request-draft-1': surface}):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data['request'])), data['expected']['checks'])
                except Exception as error:                       # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)
        self.assertEqual(len(mutants), 23)


if __name__ == '__main__':
    unittest.main()
