"""P2-d：独立確認の資料（scripts/research/p2/）の整合。

変異表の置換元が現在の実装にちょうど一つ現れる（実装が変わって表が古くなっていない）、意図した例が実在する、
生成器が固定した例・宣言をバイト単位で再現する、固定済みの全例・改変入力・予算掃引の出力（22,052 件）が基準と一致する。
変異の実行そのもの（各変異後の木でテストを動かす）は時間がかかるので、ここでは行わない（scripts/research/p2/README.md）。
"""

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "scripts/research/p2"
sys.path.insert(0, str(TOOLS))

# 拡張の追加前（P2-a の前）に取った基準と同じ。以後の P2-a〜P2-d の変更で、固定済みの例の挙動は変わっていない。
BEHAVIOUR_DIGEST = "d0a2233574ab350e65217ef6da8ed037fe34020e8ee79eee2506bd9ce4320236"
BEHAVIOUR_OUTCOMES = 22052


def table(name):
    """実行器の変異表 M を、モジュールを実行せずに読む（実行器は import すると変異の実行を始める）。"""
    tree = ast.parse((TOOLS / f"{name}.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "M":
            return ast.literal_eval(node.value)
    raise AssertionError("変異表がない: " + name)


def checker_table():
    """検査器の変異表。定数（テストモジュール名・対象ファイル）を使うので、定義の部分だけを実行して読む。"""
    source = (TOOLS / "mutrun_checkers.py").read_text(encoding="utf-8")
    namespace = {}
    exec(source[source.index("BUDGET, VERSIONS, EVALUATE"):source.index('\nif __name__ == "__main__"')], namespace)
    return namespace["M"]


def target(filename):
    """変異の対象：実装は src/med_dsl/、検査器はリポジトリ相対のパス。"""
    return ROOT / filename if filename.startswith("scripts/") else ROOT / "src/med_dsl" / filename


class MutantTableTests(unittest.TestCase):
    def tables(self):
        import mutants_extensions
        return {"mutants_extensions": [(r[0], r[1], r[2], r[3], [], "") for r in mutants_extensions.M],
                "mutrun_split": table("mutrun_split"), "mutrun_splits": table("mutrun_splits"),
                "mutrun_guards": [(r[0], r[1], r[2], r[3], r[4], "") for r in table("mutrun_guards")],
                "mutrun_checkers": [(r[0], r[1], r[2], r[3], [], "") for r in checker_table()]}

    def test_the_tables_have_the_documented_sizes(self):
        sizes = {name: len(rows) for name, rows in self.tables().items()}
        # guards の 29 ＝ 変異 28 ＋ 対照 C0、checkers の 72 ＝ 変異 71 ＋ 対照 Z0
        self.assertEqual(sizes, {"mutants_extensions": 72, "mutrun_split": 35, "mutrun_splits": 39, "mutrun_guards": 29, "mutrun_checkers": 72})

    def test_every_pattern_occurs_exactly_once_in_the_current_source(self):
        for name, rows in self.tables().items():
            idents = [r[0] for r in rows]
            self.assertEqual(len(idents), len(set(idents)), name)
            for ident, filename, old, new, _, _ in rows:
                text = target(filename).read_text(encoding="utf-8")
                if old == new:
                    self.assertIn(ident, ("C0", "Z0"), (name, ident))   # 変異でない行は、実行器の対照だけ
                else:
                    self.assertEqual(text.count(old), 1, (name, ident))

    def test_every_mutation_changes_the_source_and_the_result_still_parses(self):
        for name, rows in self.tables().items():
            for ident, filename, old, new, _, _ in rows:
                if old == new:
                    continue
                text = target(filename).read_text(encoding="utf-8")
                try:
                    compile(text.replace(old, new), filename, "exec")
                except SyntaxError as error:
                    self.fail(f"{name} {ident}: 変異後の構文が壊れている（{error}）")

    def test_the_examples_a_mutant_is_meant_to_trip_exist(self):
        folders = {"mutrun_split": "p2-split", "mutrun_splits": "p2-splits", "mutrun_guards": "p2"}
        for name, rows in self.tables().items():
            if name not in folders:
                continue
            for ident, _, _, _, intended, _ in rows:
                for example in intended:
                    self.assertTrue((ROOT / "examples" / folders[name] / f"{example}.json").is_file(), (name, ident, example))


class GeneratorTests(unittest.TestCase):
    def test_the_generators_reproduce_the_committed_examples_and_declarations_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            for part in ("src", "examples", "extensions"):
                shutil.copytree(ROOT / part, work / part, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "docs/research", work / "docs/research")
            env = {"P2_REPO": str(work), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
            for generator in ("gen_extension_manifests", "gen_guard_fixtures", "gen_split_fixtures", "gen_splits_fixtures", "gen_temporal_fixtures", "gen_quantity_fixtures", "gen_measurement_fixtures", "gen_display_fixtures", "gen_temporal_measurement_fixtures", "gen_temporal_display_fixtures", "gen_refinement_fixtures", "gen_longitudinal_fixtures"):
                done = subprocess.run([sys.executable, "-I", "-B", str(TOOLS / f"{generator}.py")], capture_output=True, text=True, env=env)
                self.assertEqual(done.returncode, 0, (generator, done.stderr[-300:]))
            for part in ("examples/p2", "examples/p2-split", "examples/p2-splits", "examples/p2-temporal", "examples/p2-quantity", "examples/p2-measurement", "examples/p2-display", "examples/p2-temporal-measurement", "examples/p2-temporal-display", "examples/p2-refinement", "examples/p2-longitudinal", "extensions"):
                committed = {p.name: p.read_bytes() for p in (ROOT / part).iterdir() if p.is_file()}
                generated = {p.name: p.read_bytes() for p in (work / part).iterdir() if p.is_file()}
                self.assertEqual(sorted(generated), sorted(committed), part)
                for name in committed:
                    self.assertEqual(generated[name], committed[name], f"{part}/{name}")


class BehaviourDigestTests(unittest.TestCase):
    def test_the_outcomes_of_the_pinned_suites_are_identical_to_the_baseline_taken_before_p2(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "outcomes.json"
            done = subprocess.run([sys.executable, "-I", "-B", str(TOOLS / "refactor_digest.py"), str(ROOT), str(target)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr[-300:])
            rows = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), BEHAVIOUR_OUTCOMES)
        self.assertEqual([k for k, v in rows.items() if v.startswith("EXC:")], [])
        self.assertEqual(hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(), BEHAVIOUR_DIGEST)


if __name__ == "__main__":
    unittest.main()
