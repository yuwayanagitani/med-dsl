"""P2-n：継承の欄（manifest draft-2 の inherits）。書式・解決・証人・列挙・独立・順序、元の拡張の断片の変更の検出、契約の版の更新。"""
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/research'), str(ROOT/'scripts/research/p2'), str(Path(__file__).parent)]
from med_dsl import evaluate, measurement
from med_dsl.extensions import (MANIFEST_SCHEMA, Refused, Registry, affected, independent_pairs, load_manifests, standard_registry)
import inheritance_suspects
import p2_checks
import test_extension_contract as contract
import test_longitudinal

# 直前の契約（draft-1）の最後のコミット。P2-m を含む
OLD_COMMIT = '3c16f68f4e43a5f77953af9f435835bbf93a3519'

# 宣言した継承（継承する側, 元）-> (結ぶ義務, 証人の数)。文書60の一覧（8件）に、監査で見つかった P2-f ← P1 の予測を加えた（予測外）
DECLARED = {
    ('p2-temporal-measurement', 'p2-temporal-assertion'): ('TM-5', 2),
    ('p2-temporal-measurement', 'p2-measurement-binding'): ('TM-5', 7),
    ('p2-temporal-display', 'p2-quantity-display'): ('TD-5', 8),
    ('p2-temporal-display', 'p2-temporal-measurement'): ('TD-10', 2),
    ('p2-validity-refinement', 'p2-temporal-assertion'): ('RF-7', 0),
    ('p2-longitudinal-comparison', 'p2-measurement-binding'): ('LC-10', 5),
    ('p2-longitudinal-comparison', 'p2-temporal-measurement'): ('LC-6', 2),
    ('p2-measurement-binding', 'p2-temporal-assertion'): ('MB-2', 0),
    ('p2-quantity-literal', 'p1-finite-forecast'): ('QT-2', 4),
}
PREDICTED = {key: value for key, value in DECLARED.items() if key != ('p2-quantity-literal', 'p1-finite-forecast')}


def registry_for(target, evaluate_witnesses=True):
    registry = Registry(ROOT, None)
    for ident in contract.prefix(target):
        registry.register(contract.shipped()[ident])
    registry.evaluate = evaluate if evaluate_witnesses else None
    return registry


def refusal(mutate, target='p2-longitudinal-comparison', evaluate_witnesses=True):
    registry = registry_for(target, evaluate_witnesses)
    manifest = deepcopy(contract.shipped()[target])
    mutate(manifest)
    before = [m['id'] for m in registry]
    try:
        registry.register(manifest)
    except Refused as error:
        assert [m['id'] for m in registry] == before, 'refused but the registry changed'
        return error.codes
    return None


def register_all():
    """同梱の全宣言を、防護例と証人を評価しながら順に登録し、拒否された宣言の理由を返す。"""
    registry, refused = Registry(ROOT, evaluate), {}
    for manifest in load_manifests(ROOT/'extensions'):
        try:
            registry.register(manifest)
        except Refused as error:
            refused[manifest['id']] = error.codes
    return registry, refused


class InheritanceFormatTests(unittest.TestCase):
    def test_the_field_is_required_and_the_old_schema_is_refused(self):
        self.assertEqual(MANIFEST_SCHEMA, 'p2-extension-manifest-draft-2')
        self.assertIn('missing_field', refusal(lambda m: m.pop('inherits')))
        self.assertIn('unsupported_manifest_schema', refusal(lambda m: m.update(schema_version='p2-extension-manifest-draft-1')))
        self.assertEqual(refusal(lambda m: m.update(inherits=[])), None)                    # 継承なしの明示は登録される

    def test_malformed_items_are_refused_with_their_own_code(self):
        self.assertIn('invalid_inherits', refusal(lambda m: m.update(inherits={})))
        item = lambda m: m['inherits'][0]
        for name, mutate in [('unknown key', lambda m: item(m).update(extra=1)), ('missing from', lambda m: item(m).pop('from')),
                             ('missing fragment', lambda m: item(m).pop('fragment')), ('missing obligation', lambda m: item(m).pop('obligation')),
                             ('missing witnesses', lambda m: item(m).pop('witnesses')), ('empty fragment', lambda m: item(m).update(fragment='')),
                             ('numeric from', lambda m: item(m).update({'from': 3})), ('witnesses not a list', lambda m: item(m).update(witnesses={})),
                             ('item not an object', lambda m: m['inherits'].__setitem__(0, 'x'))]:
            with self.subTest(name):
                self.assertIn('invalid_inheritance', refusal(mutate))

    def test_self_inheritance_duplicates_and_unresolved_sources_are_refused(self):
        self.assertIn('self_inheritance', refusal(lambda m: m['inherits'][0].update({'from': m['id']})))
        self.assertIn('unresolved_inheritance', refusal(lambda m: m['inherits'][0].update({'from': 'p2-not-registered'})))
        self.assertIn('duplicate_inheritance', refusal(lambda m: m['inherits'].append(deepcopy(m['inherits'][0]))))
        # 同じ元でも断片が違えば別の項目
        self.assertIsNone(refusal(lambda m: m['inherits'].append({**deepcopy(m['inherits'][0]), 'fragment': '別の断片', 'witnesses': [], 'witness_gap': '理由'})))

    def test_the_obligation_must_exist_and_carry_checks(self):
        self.assertIn('inheritance_obligation_missing', refusal(lambda m: m['inherits'][0].update(obligation='LC-99')))
        self.assertIn('inheritance_obligation_without_checks', refusal(lambda m: [o.update(checks=[]) for o in m['obligations'] if o['id'] == 'LC-10']))

    def test_a_witness_gap_is_required_exactly_when_there_are_no_witnesses(self):
        self.assertIn('unexplained_witness_gap', refusal(lambda m: m['inherits'][0].update(witnesses=[])))
        self.assertIn('unexplained_witness_gap', refusal(lambda m: m['inherits'][0].update(witnesses=[], witness_gap='')))
        self.assertIn('witness_gap_with_witnesses', refusal(lambda m: m['inherits'][0].update(witness_gap='理由')))
        self.assertIsNone(refusal(lambda m: m['inherits'][0].update(witnesses=[], witness_gap='理由')))

    def test_malformed_witnesses_are_refused(self):
        witness = lambda m: m['inherits'][0]['witnesses'][0]
        for name, mutate in [('empty path', lambda m: witness(m)['to'].update(path=[])), ('path not a list', lambda m: witness(m)['to'].update(path='x')),
                             ('boolean in path', lambda m: witness(m)['to'].update(path=[True])), ('example not a string', lambda m: witness(m)['from'].update(example=5)),
                             ('extra key', lambda m: witness(m).update(extra=1)), ('missing side', lambda m: witness(m).pop('to')),
                             ('missing place key', lambda m: witness(m)['from'].pop('path'))]:
            with self.subTest(name):
                self.assertIn('invalid_witness', refusal(mutate))


class InheritanceWitnessTests(unittest.TestCase):
    def test_a_witness_whose_values_differ_is_refused(self):
        def mutate(m):
            m['inherits'][0]['witnesses'][0]['to']['example'] = 'examples/p2-longitudinal/l20.json'       # 最初の証人は property（m28 ↔ l24）。method の例に替える
        self.assertIn('inheritance_witness_mismatch', refusal(mutate))

    def test_a_place_that_is_not_in_the_result_is_unresolved(self):
        self.assertIn('inheritance_witness_unresolved', refusal(lambda m: m['inherits'][0]['witnesses'][0]['to'].update(path=['results', 0, 'no_such_place'])))
        self.assertIn('inheritance_witness_unresolved', refusal(lambda m: m['inherits'][0]['witnesses'][0]['from'].update(path=['results', 9, 'reason_codes'])))

    def test_examples_must_belong_to_the_declared_sides(self):
        self.assertIn('witness_example_not_owned', refusal(lambda m: m['inherits'][0]['witnesses'][0]['from'].update(example='examples/p2-longitudinal/l20.json')))
        self.assertIn('witness_example_not_owned', refusal(lambda m: m['inherits'][0]['witnesses'][0]['to'].update(example='examples/p2-measurement/m30.json')))
        self.assertIn('witness_example_not_owned', refusal(lambda m: m['inherits'][0]['witnesses'][0]['to'].update(example='../outside.json')))

    def test_an_example_that_does_not_exist_is_refused(self):
        self.assertIn('missing_witness_example', refusal(lambda m: m['inherits'][0]['witnesses'][0]['to'].update(example='examples/p2-longitudinal/zzz.json')))

    def test_witnesses_are_evaluated_only_when_the_registry_can_evaluate(self):
        def mutate(m):
            m['inherits'][0]['witnesses'][0]['to']['example'] = 'examples/p2-longitudinal/l20.json'
        self.assertIsNone(refusal(mutate, evaluate_witnesses=False))

    def test_every_shipped_witness_agrees_and_each_side_names_a_real_example(self):
        registry, refused = register_all()
        self.assertEqual(refused, {})
        count = 0
        for manifest in registry:
            for item in manifest['inherits']:
                source = registry.get(item['from'])
                for witness in item['witnesses']:
                    self.assertTrue((ROOT/witness['from']['example']).is_file() and (ROOT/witness['to']['example']).is_file())
                    count += 1
                self.assertGreater(len(source['obligations']), 0)
        self.assertEqual(count, sum(n for _, n in DECLARED.values()))


class InheritanceResolutionTests(unittest.TestCase):
    def test_mutual_inheritance_cannot_be_resolved(self):
        template = contract.shipped()['p1-finite-forecast']
        with tempfile.TemporaryDirectory() as folder:
            for name in ('p0-positive',):
                (Path(folder)/f'{name}.json').write_text(json.dumps(contract.shipped()[name]), encoding='utf-8')
            for ident, other in (('x-a', 'x-b'), ('x-b', 'x-a')):
                manifest = deepcopy(template)
                manifest.update(id=ident, owns={key: [] for key in manifest['owns']},
                                inherits=[{'from': other, 'fragment': '相互', 'obligation': 'K-ID', 'witnesses': [], 'witness_gap': '相互の継承は解決できない'}])
                (Path(folder)/f'{ident}.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(Refused) as caught:
                standard_registry(ROOT, directory=folder)
            self.assertIn('unresolved_inheritance', caught.exception.codes)

    def test_shipped_sources_are_always_registered_before_their_inheritors(self):
        order = [m['id'] for m in load_manifests(ROOT/'extensions')]
        for manifest in load_manifests(ROOT/'extensions'):
            for item in manifest['inherits']:
                self.assertLess(order.index(item['from']), order.index(manifest['id']), (manifest['id'], item['from']))
            for dependency in manifest['depends_on']:
                self.assertLess(order.index(dependency['id']), order.index(manifest['id']))


class ShippedInheritanceTests(unittest.TestCase):
    """文書60の§1・§2：手で挙げた継承の一覧、列挙、独立。予測外は一件（P2-f ← P1 の予測。監査と疑いの探索で見つかった）。"""

    @classmethod
    def setUpClass(cls):
        cls.registry, refused = register_all()
        assert not refused, refused

    def test_every_declaration_states_its_inheritance_and_the_audited_table_is_exactly_the_shipped_one(self):
        shipped = {}
        for manifest in self.registry:
            self.assertIn('inherits', manifest)
            for item in manifest['inherits']:
                key = (manifest['id'], item['from'])
                self.assertNotIn(key, shipped)                           # 組ごとに一項目（この表では）
                shipped[key] = (item['obligation'], len(item['witnesses']))
                self.assertEqual(bool(item['witnesses']), 'witness_gap' not in item)
        self.assertEqual(shipped, DECLARED)

    def test_the_hand_listed_prediction_is_included_and_exactly_one_was_not_predicted(self):
        self.assertEqual(len(PREDICTED), 8)
        self.assertTrue(set(PREDICTED) < set(DECLARED))
        self.assertEqual(set(DECLARED) - set(PREDICTED), {('p2-quantity-literal', 'p1-finite-forecast')})
        with_witnesses = [key for key, (_, n) in PREDICTED.items() if n]
        self.assertEqual((len(with_witnesses), sum(PREDICTED[k][1] for k in with_witnesses)), (6, 26))     # 予測：6項目・26証人

    def test_the_enumeration_follows_inheritance_transitively_and_in_one_direction(self):
        one = lambda path: affected(self.registry, [f'src/med_dsl/{path}.py'])['extensions']
        self.assertEqual(one('measurement'), sorted(['p2-measurement-binding', 'p2-quantity-display', 'p2-temporal-measurement', 'p2-longitudinal-comparison', 'p2-temporal-display']))
        self.assertEqual(one('temporal'), sorted(['p2-temporal-assertion', 'p2-temporal-measurement', 'p2-validity-refinement', 'p2-measurement-binding',
                                                  'p2-quantity-display', 'p2-temporal-display', 'p2-longitudinal-comparison']))
        self.assertEqual(one('display'), ['p2-quantity-display', 'p2-temporal-display'])
        self.assertEqual(one('temporal_measurement'), sorted(['p2-temporal-measurement', 'p2-temporal-display', 'p2-longitudinal-comparison']))
        self.assertEqual(one('quantity'), sorted(['p2-quantity-literal', 'p2-measurement-binding', 'p2-quantity-display', 'p2-temporal-measurement',
                                                  'p2-temporal-display', 'p2-longitudinal-comparison']))
        self.assertEqual(one('forecast'), contract.FORECAST_FAMILY)
        # 継承する側の変更は元に及ばない
        self.assertEqual(one('longitudinal'), ['p2-longitudinal-comparison'])
        self.assertEqual(one('refinement'), ['p2-validity-refinement'])

    def test_the_reason_names_the_inheritance(self):
        result = affected(self.registry, ['src/med_dsl/measurement.py'])
        self.assertTrue(any(reason.startswith('inherits:') and 'p2-measurement-binding' in reason for reason in result['reasons']['p2-longitudinal-comparison']))
        self.assertTrue(result['reasons']['p2-measurement-binding'][0].startswith('src/med_dsl/measurement'))

    def test_the_same_enumeration_is_obtained_from_the_tree_by_its_own_registry(self):
        self.assertEqual(p2_checks.tree_affected(ROOT, ['src/med_dsl/measurement.py'])['extensions'], affected(self.registry, ['src/med_dsl/measurement.py'])['extensions'])

    def test_inheritance_couples_a_pair_and_the_independent_pairs_fall_from_150_to_143(self):
        pairs = set(independent_pairs(self.registry))
        self.assertEqual(len(pairs), 143)
        coupled = {tuple(sorted(key)) for key in DECLARED}
        previously_independent = {('p2-temporal-assertion', 'p2-temporal-measurement'), ('p2-measurement-binding', 'p2-temporal-measurement'),
                                  ('p2-quantity-display', 'p2-temporal-display'), ('p2-temporal-assertion', 'p2-validity-refinement'),
                                  ('p2-longitudinal-comparison', 'p2-measurement-binding'), ('p2-measurement-binding', 'p2-temporal-assertion'),
                                  ('p1-finite-forecast', 'p2-quantity-literal')}
        self.assertTrue(previously_independent <= coupled)
        self.assertFalse(pairs & coupled)
        self.assertEqual(len(previously_independent), 7)               # 8件の予測のうち6組＋予測外の1組。他の2件は依存で既に結ばれていた
        self.assertEqual({('p2-longitudinal-comparison', 'p2-temporal-measurement'), ('p2-temporal-display', 'p2-temporal-measurement')} & pairs, set())


class InheritanceLogicTests(unittest.TestCase):
    """列挙と独立の規則を、小さな人工の木で一つずつ確かめる（実際の宣言では他の規則と重なって見える規則を含む）。"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        package = self.root/'src/med_dsl'
        package.mkdir(parents=True)
        for name in 'abcd':
            (package/f'{name}.py').write_text('v = 1\n')

    def tearDown(self):
        self.folder.cleanup()

    def ext(self, ident, module, **kwargs):
        composition = {'shares_names_with': [], 'reads_extensions': [], 'order_dependent': False}
        return contract.toy_manifest(ident, [f'src/med_dsl/{module}.py'], **{'class': 'R2', 'composition': composition}, **kwargs)

    def affected_ids(self, items, changed):
        return affected(contract.FakeRegistry(self.root, items), changed, self.root)['extensions']

    def test_a_change_to_the_source_reaches_the_inheritor_but_not_the_other_way(self):
        source, inheritor = self.ext('S', 'a'), self.ext('I', 'b', inherits=[{'from': 'S'}])
        self.assertEqual(self.affected_ids([source, inheritor], ['src/med_dsl/a.py']), ['I', 'S'])
        self.assertEqual(self.affected_ids([source, inheritor], ['src/med_dsl/b.py']), ['I'])

    def test_inheritance_is_followed_through_a_chain_and_mixed_with_dependencies(self):
        s, i, j = self.ext('S', 'a'), self.ext('I', 'b', inherits=[{'from': 'S'}]), self.ext('J', 'c', depends_on=[{'id': 'I', 'version': 'v'}])
        k = self.ext('K', 'd', inherits=[{'from': 'J'}])
        self.assertEqual(self.affected_ids([s, i, j, k], ['src/med_dsl/a.py']), ['I', 'J', 'K', 'S'])
        self.assertEqual(self.affected_ids([s, i, j, k], ['src/med_dsl/c.py']), ['J', 'K'])

    def test_the_reason_lists_the_dependency_and_the_inheritance_separately(self):
        s, i = self.ext('S', 'a'), self.ext('I', 'b', depends_on=[{'id': 'S', 'version': 'v'}], inherits=[{'from': 'S'}])
        reasons = affected(contract.FakeRegistry(self.root, [s, i]), ['src/med_dsl/a.py'], self.root)['reasons']
        self.assertEqual(reasons['I'], ['depends_on:S', 'inherits:S'])

    def test_a_manifest_without_the_field_is_treated_as_inheriting_nothing_by_the_enumeration(self):
        self.assertEqual(self.affected_ids([self.ext('S', 'a'), self.ext('I', 'b')], ['src/med_dsl/a.py']), ['S'])

    def pairs(self, *items):
        base = contract.toy_manifest('BASE', ['src/med_dsl/d.py'], **{'class': 'BASE', 'composition': {'shares_names_with': [], 'reads_extensions': [], 'order_dependent': False}})
        return independent_pairs(contract.FakeRegistry(self.root, [base, *items]), self.root)

    def test_an_inheritance_in_either_direction_makes_a_pair_dependent(self):
        self.assertEqual(self.pairs(self.ext('A', 'a'), self.ext('B', 'b')), [('A', 'B')])
        self.assertEqual(self.pairs(self.ext('A', 'a'), self.ext('B', 'b', inherits=[{'from': 'A'}])), [])
        self.assertEqual(self.pairs(self.ext('A', 'a', inherits=[{'from': 'B'}]), self.ext('B', 'b')), [])


class SourceDriftTests(unittest.TestCase):
    """文書60のE1：元の拡張（P2-g）の matched_context の判定を断片の中で壊し、元の登録・継承する側の証人・差分の検査のどれが捕まえるかを分ける。"""

    DRIFTS = [
        ('d1', "('method', 'different_method'), ", ''),
        ('d2', "('specimen', 'different_specimen'), ", ''),
        ('d3', "('property_ref', 'different_property'),\n", ''),
        ('d4', 'if selected[0][field] != selected[1][field]:', 'if _bare(selected[0][field]) != _bare(selected[1][field]):'),
        ('d5', "('subject_ref', 'different_subject'), ", ''),
        ('d6', '                reasons.add(reason)\n', '                reasons.add(reason)\n                break\n'),
    ]

    @classmethod
    def classify(cls, old, new):
        source = inspect.getsource(measurement._assess)
        assert source.count(old) == 1, (old, source.count(old))
        namespace = dict(vars(measurement), _bare=lambda v: v.get('ref') if isinstance(v, dict) else v)
        exec(compile(source.replace(old, new), '<drift>', 'exec'), namespace)
        with patch.object(measurement, '_assess', namespace['_assess']):
            _, refused = register_all()
            try:
                test_longitudinal.LongitudinalTests().test_context_agrees_with_the_measurement_extension_on_the_common_fragment()
                differential = False
            except AssertionError:
                differential = True
        return {'source_refused': 'p2-measurement-binding' in refused,
                'witness': any('inheritance_witness_mismatch' in codes for codes in refused.values()),
                'unresolved': any('unresolved_inheritance' in codes for codes in refused.values()),
                'differential': differential, 'refused': refused}

    @classmethod
    def setUpClass(cls):
        cls.matrix = {name: cls.classify(old, new) for name, old, new in cls.DRIFTS}

    def test_a_drift_the_source_refuses_leaves_the_inheritors_unresolved_not_misled(self):
        d1 = self.matrix['d1']
        self.assertTrue(d1['source_refused'] and d1['unresolved'] and d1['differential'])

    def test_a_drift_outside_the_fragment_is_seen_by_nothing_that_belongs_to_the_fragment(self):
        d5 = self.matrix['d5']
        self.assertEqual((d5['source_refused'], d5['witness'], d5['differential']), (False, False, False))

    def test_some_drift_escapes_the_sources_own_guards_and_is_caught_by_a_witness(self):
        caught = [name for name, row in self.matrix.items() if not row['source_refused'] and row['witness']]
        self.assertTrue(caught, self.matrix)

    def test_some_drift_escapes_the_guards_and_every_witness_and_only_the_differential_check_catches_it(self):
        only_differential = [name for name, row in self.matrix.items() if not row['source_refused'] and not row['witness'] and row['differential']]
        self.assertTrue(only_differential, self.matrix)

    def test_the_differential_check_is_never_weaker_than_the_witnesses_on_the_fragment(self):
        for name, row in self.matrix.items():
            if row['witness'] and name != 'd5':
                self.assertTrue(row['differential'], name)

    def test_the_matrix_is_recorded(self):
        print({name: {k: v for k, v in row.items() if k != 'refused'} for name, row in self.matrix.items()})


class SuspectProbeTests(unittest.TestCase):
    """文書60のE2：継承の疑いの機械的な探索（登録の条件ではない）。"""

    def test_exclusive_shared_literals_find_most_declared_pairs_with_one_false_suspect(self):
        report = inheritance_suspects.suspects(minimum=2)
        self.assertEqual(report['independent_pairs'], 150)
        found = {tuple(sorted(pair)) for pair in report['suspects']}
        declared = {tuple(sorted(key)) for key in DECLARED}
        pre_independent = {tuple(sorted(pair)) for pair in {k for k in declared} - {('p2-longitudinal-comparison', 'p2-temporal-measurement'), ('p2-temporal-display', 'p2-temporal-measurement')}}
        self.assertEqual(len(pre_independent), 7)
        self.assertEqual((len(found), len(found & pre_independent)), (6, 5))               # 適合率 5/6、再現率 5/7
        self.assertEqual(found - pre_independent, {('p2-longitudinal-comparison', 'p2-temporal-display')})   # 偽の疑い：同じ親（P2-i）の語彙を共有
        self.assertEqual(pre_independent - found, {('p2-temporal-assertion', 'p2-temporal-measurement'), ('p2-measurement-binding', 'p2-temporal-assertion')})

    def test_counting_the_shared_vocabulary_makes_almost_everything_a_suspect(self):
        report = inheritance_suspects.suspects(minimum=3, exclusive=False)
        self.assertEqual((report['independent_pairs'], len(report['suspects'])), (150, 104))


class ContractVersionTests(unittest.TestCase):
    """文書60のE3：契約の書式の更新（draft-1 → draft-2）を、版の手順で検証する。履歴がなければ行わない。"""

    @classmethod
    def setUpClass(cls):
        if not p2_checks.has_commit(OLD_COMMIT):
            raise unittest.SkipTest('git の履歴（直前の契約のコミット）がない')
        cls.old = {}
        for manifest in load_manifests(ROOT/'extensions'):
            raw = p2_checks.git('show', f"{OLD_COMMIT}:extensions/{manifest['id']}.json").stdout
            cls.old[manifest['id']] = json.loads(raw)

    def test_the_old_declarations_are_all_refused_by_the_new_registry(self):
        for ident, manifest in self.old.items():
            with self.subTest(ident):
                self.assertEqual(manifest['schema_version'], 'p2-extension-manifest-draft-1')
                with self.assertRaises(Refused) as caught:
                    Registry(ROOT, None).register(manifest)
                self.assertIn('unsupported_manifest_schema', caught.exception.codes)

    def test_the_new_declarations_differ_from_the_old_only_in_the_declared_fields(self):
        self.assertEqual(len(self.old), 20)
        for manifest in load_manifests(ROOT/'extensions'):
            with self.subTest(manifest['id']):
                old = {k: v for k, v in self.old[manifest['id']].items() if k != 'schema_version'}
                new = {k: v for k, v in manifest.items() if k not in ('schema_version', 'inherits')}
                self.assertEqual(new, old)
                self.assertEqual(manifest['schema_version'], 'p2-extension-manifest-draft-2')

    def test_the_comparator_enumerates_an_old_tree_with_that_trees_own_registry(self):
        with tempfile.TemporaryDirectory() as folder:
            tree = p2_checks.extract(OLD_COMMIT, Path(folder)/'old')
            result = p2_checks.tree_affected(tree, ['src/med_dsl/measurement.py'])
            self.assertEqual(result['extensions'], ['p2-measurement-binding', 'p2-quantity-display'])      # 旧い契約：継承の辺を持たない
            registry = standard_registry(ROOT, evaluate=evaluate)
            self.assertEqual(len(affected(registry, ['src/med_dsl/measurement.py'])['extensions']), 5)
            with self.assertRaises(Refused):
                standard_registry(tree)                                                                  # 作業ツリーの registry は旧い宣言を拒否する


if __name__ == '__main__':
    unittest.main()
