"""P2-d：独立確認の資料（設計 27、結果 28）の整合。

文書が引くファイル・テスト・コミット・例が実在し、PO13〜PO18 のすべてが、命題・証拠・先に探す反例・覆り得る内部判断を持ち、
内部判断の ID が表と対応し、固定した分母が文書と評価器で食い違わない。文書の主張が正しいことは検査しない（実在と対応だけ）。
"""

import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs/research/27-p2-d-design.md"
RESULTS = ROOT / "docs/research/28-p2-d-results.md"
ROOTS = ("docs/", "src/", "tests/", "scripts/", "examples/", "extensions/")
LABELS = ("命題", "証拠", "先に探す反例", "覆り得る内部判断")


def evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_p2", ROOT / "scripts/research/evaluate-p2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return path.read_text(encoding="utf-8")


def code_spans(text):
    return re.findall(r"`([^`\n]+)`", text)


def has_commit(commit):
    return subprocess.run(["git", "cat-file", "-e", commit], cwd=ROOT, capture_output=True).returncode == 0


def references(text):
    """文書が引く実体：コード片のパス（::テスト名つきも）と、Markdown のリンク先。"""
    found = set()
    for span in code_spans(text):
        if span.startswith(ROOTS) and not any(mark in span for mark in ("<", "…", " ")):
            found.add(span)
    for target in re.findall(r"\]\(([^)#]+?)(?:#[^)]*)?\)", text):
        if not target.startswith(("http", "mailto")):
            found.add(("link", target))
    return found


class MaterialsTests(unittest.TestCase):
    docs = [path for path in (DESIGN, RESULTS) if path.is_file()]

    def test_both_documents_exist(self):
        self.assertTrue(DESIGN.is_file())
        self.assertTrue(RESULTS.is_file(), "結果の文書 28 がない")

    def test_every_path_test_and_link_a_document_cites_exists(self):
        checked = 0
        for doc in self.docs:
            for ref in references(read(doc)):
                if isinstance(ref, tuple):
                    self.assertTrue((doc.parent / ref[1]).exists(), (doc.name, ref[1]))
                    checked += 1
                    continue
                path, _, test = ref.partition("::")
                if "*" in path:
                    self.assertTrue(list(ROOT.glob(path)), (doc.name, ref))
                else:
                    self.assertTrue((ROOT / path).exists(), (doc.name, ref))
                if test:
                    body = read(ROOT / path)
                    cls, _, method = test.partition(".")
                    self.assertIn(f"class {cls}", body, (doc.name, ref))
                    self.assertIn(f"def {method}(", body, (doc.name, ref))
                checked += 1
        self.assertGreater(checked, 60)

    def test_every_commit_a_document_cites_is_in_the_history(self):
        for doc in self.docs:
            for span in code_spans(read(doc)):
                if re.fullmatch(r"[0-9a-f]{7}|[0-9a-f]{40}", span):
                    if not has_commit("HEAD"):
                        self.skipTest("git の履歴がない")
                    self.assertTrue(has_commit(span), (doc.name, span))

    def test_the_six_obligations_match_the_design_and_each_has_the_four_parts(self):
        design = read(ROOT / "docs/research/19-p2-design.md")
        named = dict(re.findall(r"PO(1[3-8]) ([^、。\n]+?)(?=、PO|。)", design))
        self.assertEqual(sorted(named), [f"{n}" for n in range(13, 19)])
        text = read(DESIGN)
        sections = re.split(r"^#### ", text, flags=re.M)[1:]
        self.assertEqual(len(sections), 6)
        for number, section in zip(range(13, 19), sections):
            title = section.splitlines()[0]
            self.assertEqual(title, f"PO{number} {named[str(number)]}")
            for label in LABELS:
                self.assertRegex(section, rf"(?m)^- \*\*{label}\*\*：", f"PO{number} {label}")
            self.assertIn("::", section, f"PO{number} は、テスト名を挙げた証拠を持つ")
            self.assertGreaterEqual(len(re.findall(r"\(\d\)", section)), 3, f"PO{number} の反例は 3 件以上")

    def test_internal_judgments_in_the_obligations_are_defined_in_the_table_and_the_table_is_used(self):
        text = read(DESIGN)
        table = set(re.findall(r"^\| (J\d\d) \|", text, flags=re.M))
        self.assertEqual(len(table), 12)
        used = set()
        for section in re.split(r"^#### ", text, flags=re.M)[1:]:
            line = next(l for l in section.splitlines() if l.startswith("- **覆り得る内部判断**"))
            used |= set(re.findall(r"J\d\d", line))
        self.assertTrue(used <= table, used - table)
        self.assertEqual(table - used, {"J12"} if "J12" not in used else set())     # 等価変異の分類は、特定の PO に属さない

    def test_the_pinned_denominators_in_the_design_match_the_evaluator(self):
        # 文書27/28はP2-d当時の資料。P2-e追加後の現在値へ書き換えない。
        expected = evaluator().P2_D_EXPECTED
        text = read(DESIGN)
        numbers = [expected["extensions"]["obligations"], expected["extensions"]["guards"], expected["extensions"]["guard_gaps"],
                   expected["extensions"]["independent_pairs"], expected["extensions"]["pairs"], expected["budget"]["requests"]]
        numbers += list(expected["extensions"]["evidence"].values())
        for suite in expected["suites"].values():
            numbers += [suite["examples"], suite["checks"]]
        for number in numbers:
            self.assertRegex(text, rf"(?<![\d,]){number}(?![\d,])", number)
        self.assertIn(f"{expected['budget']['budget_evaluations']:,}", text)

    def test_the_review_commands_the_design_lists_exist(self):
        text = read(DESIGN)
        for command in re.findall(r"^python3 -B (scripts/research/[\w./-]+)", text, flags=re.M):
            self.assertTrue((ROOT / command).is_file(), command)
        for directory in re.findall(r"discover -s (tests[\w/]*)", text):
            self.assertTrue((ROOT / directory).is_dir(), directory)

    def test_no_document_claims_an_independent_review_or_a_frozen_evaluation(self):
        for doc in self.docs:
            text = read(doc)
            self.assertNotRegex(text, r"独立(確認|レビュー)(に合格|を完了|を実施した|が完了)")
            self.assertNotIn("evaluation_frozen: true", text)
            self.assertNotIn('"evaluation_frozen": true', text)


if __name__ == "__main__":
    unittest.main()
