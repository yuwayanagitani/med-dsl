"""P2-u の道具（audit-cpc-versions.py）：正規化の写像を架空の RRF 形式の ZIP で確かめ、手元に台帳どおりの CPC があれば、実データの既知の値・不変条件・別計算との照合を確かめる。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
import zipfile
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/research'), str(ROOT/'scripts/research/p2'), str(Path(__file__).parent)]
from med_dsl import evaluate
import audit_oracle as oracle
import gen_audit_fixtures as make

spec = importlib.util.spec_from_file_location('audit_cpc_versions', ROOT/'scripts/research/audit-cpc-versions.py')
tool = importlib.util.module_from_spec(spec)
sys.modules['audit_cpc_versions'] = tool
spec.loader.exec_module(tool)

STANDARD = {'RXNCONSO': ['RXCUI', 'LAT', 'TS', 'LUI', 'STT', 'SUI', 'ISPREF', 'RXAUI', 'SAUI', 'SCUI', 'SDUI', 'SAB', 'TTY', 'CODE', 'STR', 'SRL', 'SUPPRESS', 'CVF'],
            'RXNREL': ['RXCUI1', 'RXAUI1', 'STYPE1', 'REL', 'RXCUI2', 'RXAUI2', 'STYPE2', 'RELA', 'RUI', 'SRUI', 'SAB', 'SL', 'DIR', 'RG', 'SUPPRESS', 'CVF'],
            'RXNSAT': ['RXCUI', 'LUI', 'SUI', 'RXAUI', 'STYPE', 'CODE', 'ATUI', 'SATUI', 'ATN', 'SAB', 'ATV', 'SUPPRESS', 'CVF']}


def sql_of(columns):
    return '\n'.join(f'DROP TABLE IF EXISTS {t};\nCREATE TABLE {t}\n(\n' + ',\n'.join(f'   {c}  varchar(20)' for c in names) + '\n)\n;\n' for t, names in columns.items())


def conso(rxcui, rxaui, sab, tty, text):
    return {'RXCUI': rxcui, 'RXAUI': rxaui, 'SAB': sab, 'TTY': tty, 'STR': text, 'SUPPRESS': 'N', 'CVF': '4096'}


def rel(rxcui1, rxcui2, relation, rela, sab='RXNORM', stype1='CUI', stype2='CUI'):
    return {'RXCUI1': rxcui1, 'RXCUI2': rxcui2, 'REL': relation, 'RELA': rela, 'SAB': sab, 'STYPE1': stype1, 'STYPE2': stype2, 'SUPPRESS': '', 'CVF': '4096'}


def sat(rxaui, atn, atv, sab='RXNORM', stype='AUI'):
    return {'RXAUI': rxaui, 'ATN': atn, 'ATV': atv, 'SAB': sab, 'STYPE': stype, 'SUPPRESS': 'N', 'CVF': '4096'}


def make_zip(path, rows, columns=None):
    columns = columns or STANDARD
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(tool.SQL_MEMBER, sql_of(columns))
        for table, member in [('RXNCONSO', 'rrf/RXNCONSO.RRF'), ('RXNREL', 'rrf/RXNREL.RRF'), ('RXNSAT', 'rrf/RXNSAT.RRF')]:
            archive.writestr(member, ''.join('|'.join(row.get(name, '') for name in columns[table]) + '|\n' for row in rows[table]))


FICTION = {'RXNCONSO': [conso('C1', 'A1', 'RXNORM', 'T1', 'name one'), conso('C1', 'A2', 'RXNORM', 'T2', 'name two'), conso('C2', 'A3', 'RXNORM', 'T1', 'name three'),
                        conso('C3', 'A4', 'OTHER', 'T1', 'other source'), conso('C1', 'A1', 'RXNORM', 'T1', 'name one')],
           'RXNREL': [rel('C2', 'C1', 'RO', 'has_part'), rel('C2', 'C1', 'SY', ''), rel('C2', 'C1', 'RO', 'has_part'), rel('C2', 'C1', 'RO', 'x', stype1='AUI', stype2='AUI'),
                      rel('C2', 'C9', 'RO', 'has_part'), rel('C2', 'C1', 'RO', 'has_part', sab='OTHER')],
           'RXNSAT': [sat('A1', 'ATN1', 'V1'), sat('A1', 'ATN1', 'V1'), sat('A99', 'ATN1', 'V1'), sat('A1', 'ATN2', 'V2', stype='CUI'), sat('A4', 'ATN1', 'V3', sab='OTHER'),
                      sat('A3', 'ATN3', '')]}


class NormalizationTests(unittest.TestCase):
    def normalized(self, columns=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fiction.zip'
            make_zip(path, FICTION, columns)
            return tool.normalize(path, 'v1')

    def test_the_column_order_comes_from_the_bundled_sql_by_name(self):
        reordered = {table: list(reversed(names)) for table, names in STANDARD.items()}
        self.assertEqual(self.normalized(), self.normalized(reordered))
        self.assertEqual(tool.columns_from_sql(sql_of(STANDARD))['RXNREL'], STANDARD['RXNREL'])

    def test_the_mapping_of_concepts_atoms_relations_and_attributes(self):
        """(a)〜(e)：概念＝出典 RXNORM の RXCUI、原子＝RXAUI・TTY・STR、関係の所有者＝RXCUI2・対象＝RXCUI1・種類＝RELA（空なら REL）、属性＝原子（RXAUI）に付く。
        重複・他の出典・原子対原子・原子に結べない行・所有者のない関係は件数として報告する。"""
        snapshot, stats = self.normalized()
        concepts = {c['id']: c for c in snapshot['concepts']}
        self.assertEqual(sorted(concepts), ['C1', 'C2'])
        self.assertEqual([(a['id'], a['kind'], a['name'], a['attributes']) for a in concepts['C1']['atoms']],
                         [('A1', 'T1', 'name one', [{'name': 'ATN1', 'value': 'V1'}]), ('A2', 'T2', 'name two', [])])
        self.assertEqual(concepts['C2']['atoms'][0]['attributes'], [{'name': 'ATN3', 'value': ''}])           # 空の値も属性
        self.assertEqual(concepts['C1']['relations'], [{'kind': 'SY', 'target': 'C2'}, {'kind': 'has_part', 'target': 'C2'}])
        self.assertEqual(concepts['C2']['relations'], [])                                                    # 向きを反転しない：所有者は RXCUI2
        self.assertEqual(stats, {'conso_atoms': 3, 'conso_other_source': 1, 'conso_duplicate_atom': 1, 'sat_attributes': 2, 'sat_duplicate': 1, 'sat_orphan_atom': 1,
                                 'sat_not_atom': 1, 'sat_other_source': 1, 'rel_relations': 2, 'rel_duplicate': 1, 'rel_not_concept': 1, 'rel_orphan_owner': 1, 'rel_other_source': 1,
                                 'conso_suppress_flagged': 0, 'conso_cvf_not_4096': 0, 'sat_suppress_flagged': 0, 'sat_cvf_not_4096': 0, 'rel_suppress_flagged': 0, 'rel_cvf_not_4096': 0})
        self.assertEqual(snapshot['ref'], 'rxnorm:cpc')

    def test_a_normalized_snapshot_is_a_valid_request_and_the_audit_runs_on_it(self):
        old, _ = self.normalized()
        new = deepcopy(old)
        new['version'] = 'v2'
        new['concepts'][0]['atoms'][0]['attributes'][0]['value'] = 'V1b'
        request = make.request({c['id']: c for c in old['concepts']}, {c['id']: c for c in new['concepts']}, ['C1', 'C2'], [{'name': 'ATN1', 'class': 'definitional'}], sources=('RXNORM',))
        request['from'], request['to'] = old, new
        result = evaluate(request)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([r['audit_state'] for r in result['results']], ['changed', 'unchanged_in_scope'])

    def test_suppressed_and_unflagged_rows_are_counted_not_dropped(self):
        """F-N5・F-N8：抑制の印（空か N 以外）と、CVF が 4096 でない行は、件数として報告する（読み飛ばさない）。"""
        rows = deepcopy(FICTION)
        rows['RXNCONSO'][0]['SUPPRESS'] = 'O'
        rows['RXNREL'][0]['CVF'] = ''
        rows['RXNSAT'][0]['SUPPRESS'] = 'Y'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fiction.zip'
            make_zip(path, rows)
            snapshot, stats = tool.normalize(path, 'v1')
        self.assertEqual((stats['conso_suppress_flagged'], stats['rel_cvf_not_4096'], stats['sat_suppress_flagged']), (1, 1, 1))
        self.assertEqual(len(snapshot['concepts']), 2)

    def test_the_policies_are_declared_never_inferred_from_the_audit(self):
        full, partial = tool.policies({'NDC', 'RXN_STRENGTH', 'RXN_AI', 'OTHER'}).values()
        self.assertEqual([(p['name'], p['class']) for p in full], [('NDC', 'administrative'), ('OTHER', 'definitional'), ('RXN_AI', 'definitional'), ('RXN_STRENGTH', 'definitional')])
        self.assertEqual([(p['name'], p['class']) for p in partial], [('NDC', 'administrative'), ('RXN_STRENGTH', 'definitional')])


class FactTests(unittest.TestCase):
    def test_the_nlm_facts_are_bound_to_the_ledger_and_the_fetched_pages(self):
        """事実は台帳の取得状態・ハッシュ（commit_payload は false）に結ばれ、手元にページがあれば、ハッシュと目印の語が一致する。"""
        ledger = {m['id']: m for m in json.loads((ROOT/'docs/research/03-materials.json').read_text())['materials']}
        self.assertEqual([f['id'] for f in tool.NLM_FACTS], [f'F-N{i}' for i in range(1, 11)])
        for fact in tool.NLM_FACTS:
            material = ledger[fact['source']]
            self.assertEqual((material['local_sha256'], material['acquisition_status'], material['commit_payload'], material['content_verified']),
                             (fact['source_sha256'], 'acquired_file_checks_passed', False, False), fact['id'])
        statuses = {f['status'] for f in tool.verify_facts()}
        self.assertIn(statuses, ({'verified'}, {'page_absent'}))
        if statuses == {'verified'}:
            for fact in tool.NLM_FACTS:
                self.assertIn(fact['marker'], tool.page_text((ROOT/ledger[fact['source']]['local_path']).read_bytes()), fact['id'])

    def test_a_changed_fact_is_not_verified(self):
        original = tool.NLM_FACTS[0]
        for change in ({'source_sha256': '0'*64}, {'marker': 'a sentence the page does not contain'}, {'source': 'rxnorm-cpc-2026-10-05'}):
            tool.NLM_FACTS[0] = {**original, **change}
            try:
                self.assertNotEqual(tool.verify_facts()[0]['status'], 'verified', change)
            finally:
                tool.NLM_FACTS[0] = original


@unittest.skipUnless(all((ROOT/'data/research/r3'/f).is_file() for f in ('RxNorm_full_prescribe_09082026.zip', 'RxNorm_full_prescribe_10052026.zip')), '台帳どおりの CPC 二版が手元にない')
class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entries = tool.ledger_entries()                                                    # 台帳の SHA-256 と取得状態を確かめる
        cls.old, cls.old_stats = tool.normalize(entries[tool.OLD_ID]['path'], entries[tool.OLD_ID]['version'])
        cls.new, cls.new_stats = tool.normalize(entries[tool.NEW_ID]['path'], entries[tool.NEW_ID]['version'])
        cls.policies = tool.policies(tool.attribute_names(cls.old) | tool.attribute_names(cls.new))
        cls.runs = {name: tool.run_policy(cls.old, cls.new, policy) for name, policy in cls.policies.items()}

    def test_known_values_from_the_exploration_are_reproduced(self):
        """RP1：設計の前に集計した既知の値（概念・原子・名称）の再現。"""
        rows, summary = self.runs['P-full']
        self.assertEqual((summary['from_concepts'], summary['to_concepts'], summary['continuing'], summary['from_only'], summary['to_only']), (81468, 81620, 81298, 170, 322))
        counts = tool.aggregate(rows)['counts']
        self.assertEqual((counts['atoms_modified'], counts['atoms_added'], counts['atoms_removed'], counts['refs_names_changed']), (0, 1, 2, 2))
        self.assertEqual((self.old_stats['conso_atoms'], self.new_stats['conso_atoms']), (140841, 141074))

    def test_every_reference_is_in_exactly_one_state(self):
        for name, (rows, summary) in self.runs.items():
            self.assertEqual(sum(summary['by_state'].values()), summary['references'], name)
            self.assertEqual(len(rows), 81468)
            self.assertEqual(len({r['reference'] for r in rows}), 81468)
            self.assertEqual(summary['by_state']['not_found'], 170)
            self.assertEqual(summary['by_state']['not_compared'], 0)

    def test_measured_values_of_both_policies(self):
        """RP2〜RP7 の実測（予測ではなく、再現の検査）。方針の違いは、未宣言の属性の差だけの参照を `changed` から `needs_information` に移す。"""
        full, partial = (tool.aggregate(self.runs[n][0])['counts'] for n in ('P-full', 'P-partial'))
        self.assertEqual(self.runs['P-full'][1]['by_state'], {'unchanged_in_scope': 79699, 'changed_administrative_only': 1229, 'changed': 370, 'needs_information': 0, 'not_found': 170, 'not_compared': 0})
        self.assertEqual(self.runs['P-partial'][1]['by_state'], {'unchanged_in_scope': 79699, 'changed_administrative_only': 1229, 'changed': 343, 'needs_information': 27, 'not_found': 170, 'not_compared': 0})
        self.assertEqual((full['refs_attribute_difference'], full['refs_attribute_difference_not_ndc'], full['refs_definitional_difference']), (1317, 77, 77))
        self.assertEqual((full['refs_relations_changed'], full['relations_added'], full['relations_removed']), (326, 326, 422))
        self.assertEqual((full['relations_removed_target_still_in_to'], full['relations_added_target_already_in_from'], full['unresolved_in_to_known_in_from'],
                          full['unresolved_in_to_unknown_in_from']), (0, 0, 0, 0))
        self.assertEqual(full['state:changed'] - partial['state:changed'], partial['state:needs_information'])
        self.assertEqual(partial['refs_undeclared_difference'], partial['state:needs_information'])

    def test_the_relation_direction_and_the_flags_agree_with_the_documentation(self):
        """F-N1・F-N4（関係の向き）：has_ingredient で、対象が成分（IN）で所有者が成分でない関係が多数あり、所有者が成分で対象が成分でない関係は0。
        F-N5・F-N8：抑制の印のある行は0、CVF が 4096 でない行は0（出典 RXNORM）。"""
        kinds = {c['id']: {a['kind'] for a in c['atoms']} for c in self.new['concepts']}
        forward = backward = 0
        for c in self.new['concepts']:
            for r in c['relations']:
                if r['kind'] == 'has_ingredient':
                    forward += 'IN' in kinds.get(r['target'], ()) and 'IN' not in kinds[c['id']]
                    backward += 'IN' in kinds[c['id']] and 'IN' not in kinds.get(r['target'], ())
        self.assertEqual((forward, backward), (28026, 0))
        for stats in (self.old_stats, self.new_stats):
            for table in ('conso', 'sat', 'rel'):
                self.assertEqual((stats[table + '_suppress_flagged'], stats[table + '_cvf_not_4096']), (0, 0), table)

    def test_swapping_the_versions_swaps_the_new_only_and_not_found_counts(self):
        """AP7（実データ）：入れ替えても継続の数は同じで、旧のみと新のみが入れ替わる。"""
        _, summary = tool.run_policy(self.new, self.old, self.policies['P-full'])
        forward = self.runs['P-full'][1]
        self.assertEqual((summary['continuing'], summary['from_only'], summary['to_only']), (forward['continuing'], forward['to_only'], forward['from_only']))
        self.assertEqual(summary['by_state']['not_found'], forward['to_only'])

    def test_a_sample_run_through_the_host_agrees_with_the_core_and_the_independent_oracle(self):
        """実データの標本（契約の限界内の参照）を、小さな要求として host の経路で実行し、核の結果と別計算の両方と照合する。対象の存在の旗のため、
        標本の外の対象は空の概念として加える。"""
        rows, _ = self.runs['P-full']
        old_by, new_by = {c['id']: c for c in self.old['concepts']}, {c['id']: c for c in self.new['concepts']}
        fits = lambda c: len(c['atoms']) <= 32 and len(c['relations']) <= 64 and all(len(a['attributes']) <= 32 for a in c['atoms'])
        by_state = {}
        for row in rows:
            if fits(old_by[row['reference']]) and (row['presence'] != 'continues' or fits(new_by[row['reference']])):
                by_state.setdefault(row['audit_state'], []).append(row['reference'])
        rng = random.Random(820004)
        sample = sorted({r for state, refs in by_state.items() for r in rng.sample(refs, min(len(refs), 12))})
        self.assertGreaterEqual(len(by_state), 4)
        stubs = lambda ids, by: [{'id': t, 'source': tool.SOURCE, 'atoms': [], 'relations': []} for t in sorted(ids) if t in by]
        targets = {r['target'] for ref in sample for c in (old_by[ref], new_by.get(ref)) if c for r in c['relations']} - set(sample)
        old_part = [old_by[r] for r in sample] + stubs(targets, old_by)
        new_part = [new_by[r] for r in sample if r in new_by] + stubs(targets, new_by)
        self.assertLessEqual(max(len(old_part), len(new_part)), 512)
        request = {'schema_version': 'p2-audit-request-draft-1', 'operation': 'run_terminology_audit',
                   'consumer': {'profile': make.PROFILE, 'profile_spec_sha256': make.SPEC, 'operations': ['run_terminology_audit']},
                   'from': {'ref': self.old['ref'], 'version': self.old['version'], 'concepts': old_part}, 'to': {'ref': self.new['ref'], 'version': self.new['version'], 'concepts': new_part},
                   'scope': {'sources': [tool.SOURCE]}, 'policy': {'attributes': self.policies['P-full']}, 'references': sample, 'budget': {'max_steps': 100000}}
        result = evaluate(request)
        self.assertEqual(result['status'], 'ok', result.get('reason_codes'))
        core = {r['reference']: r for r in rows}
        for got in result['results']:
            expected = core[got['reference']]
            for key in ('concept_source', 'presence', 'audit_state', 'facets', 'requests', 'policy_assumptions', 'successor'):
                self.assertEqual(got[key], expected[key], (got['reference'], key))
            want = oracle.row(request, got['reference'])
            self.assertEqual({k: got[k] for k in want}, want, got['reference'])
        self.assertEqual(result['steps_used'], oracle.cost(request))


if __name__ == '__main__':
    unittest.main()
