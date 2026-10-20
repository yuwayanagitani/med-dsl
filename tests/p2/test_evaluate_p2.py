"""P2-d：統合評価（scripts/research/evaluate-p2.py）の分母と照合。

分母は、評価器が使う登録の仕組みとは別に、宣言と例の JSON を直接数えて確かめる。照合（mismatches）は、固定した値と
一つでも食い違えば位置つきで失敗する。評価器の実行は、結果を data/research/p2-d/ の外へは書かない。
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))

SPEC = importlib.util.spec_from_file_location("evaluate_p2", ROOT / "scripts/research/evaluate-p2.py")
evaluate_p2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate_p2)
EXPECTED = evaluate_p2.EXPECTED


def synthetic_report():
    """固定した分母どおりの報告（照合の単位テスト用）。"""
    ext = EXPECTED["extensions"]
    return {
        "base": {**EXPECTED["base"], "passed": True},
        "extensions": {**deepcopy(ext), "refused": []},
        "suites": {name: {"examples": s["examples"], "checks": s["checks"], "failures": []} for name, s in EXPECTED["suites"].items()},
        "budget": {"requests": EXPECTED["budget"]["requests"], "evaluations": EXPECTED["budget"]["budget_evaluations"], "violations": [],
                   "allowed_budget_dependent_refusals": EXPECTED["budget"]["allowed_budget_dependent_refusals"]},
        "versions": [{"record": "r", "status": "passed"}],
    }


class DenominatorTests(unittest.TestCase):
    def test_the_pinned_extension_counts_match_a_direct_count_of_the_declarations(self):
        manifests = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "extensions").glob("*.json")) if p.name != "index.json"]
        obligations = [o for m in manifests for o in m["obligations"]]
        evidence = {}
        for o in obligations:
            evidence[o["evidence"]] = evidence.get(o["evidence"], 0) + 1
        ext = EXPECTED["extensions"]
        self.assertEqual(len(manifests), ext["registered"])
        self.assertEqual(len(obligations), ext["obligations"])
        self.assertEqual(sum(len(o.get("guards", [])) for o in obligations), ext["guards"])
        self.assertEqual(sum(1 for o in obligations if o.get("guard_gap")), ext["guard_gaps"])
        self.assertEqual({k: v for k, v in ext["evidence"].items() if v}, evidence)
        self.assertEqual(sorted(o["id"] for o in obligations if o.get("guard_gap")), ["COMP-3", "R1-3", "R3-3"])

    def test_the_pinned_example_counts_match_a_direct_count_of_the_manifests_and_checks(self):
        for name, want in EXPECTED["suites"].items():
            manifest = json.loads((ROOT / "examples" / name / "manifest.json").read_text(encoding="utf-8"))
            entries = manifest["files"] + manifest.get("accepted_boundaries", [])
            checks = sum(len(json.loads((ROOT / "examples" / name / e["path"]).read_text(encoding="utf-8"))["expected"]["checks"]) for e in entries)
            self.assertEqual((len(entries), checks), (want["examples"], want["checks"]), name)

    def test_the_pinned_request_count_is_the_number_of_requests_the_budget_check_covers(self):
        import p2_checks
        self.assertEqual(sum(isinstance(r, dict) and isinstance(r.get("budget"), dict) for _, r in p2_checks.load_requests()), EXPECTED["budget"]["requests"])

    def test_the_computed_extension_report_equals_the_pinned_one(self):
        report = evaluate_p2.extension_report()
        self.assertEqual(report["refused"], [])
        for key, want in EXPECTED["extensions"].items():
            self.assertEqual(len(report[key]) if key == "refused" else report[key], want, key)
        self.assertEqual(sorted(r["id"] for r in report["rows"] if r["guard_gaps"]), ["p0-definitions", "p1-event-chain", "p1-events"])

    def test_the_suites_pass_their_hand_specified_expectations(self):
        for name, report in evaluate_p2.suites_report().items():
            self.assertEqual(report["failures"], [], name)


class MismatchTests(unittest.TestCase):
    def test_a_report_with_the_pinned_values_has_no_mismatch(self):
        self.assertEqual(evaluate_p2.mismatches(synthetic_report()), [])

    def mismatches(self, mutate):
        report = synthetic_report()
        mutate(report)
        return evaluate_p2.mismatches(report)

    def test_every_pinned_value_is_checked(self):
        self.assertIn("base.p1_checks", self.mismatches(lambda r: r["base"].__setitem__("p1_checks", 416)))
        self.assertIn("base.p0_checks", self.mismatches(lambda r: r["base"].__setitem__("p0_checks", 220)))
        self.assertIn("base.passed", self.mismatches(lambda r: r["base"].__setitem__("passed", False)))
        for key in ("registered", "obligations", "guards", "guard_gaps", "independent_pairs", "pairs"):
            self.assertIn(f"extensions.{key}", self.mismatches(lambda r, k=key: r["extensions"].__setitem__(k, r["extensions"][k] + 1)), key)
        self.assertIn("extensions.evidence", self.mismatches(lambda r: r["extensions"]["evidence"].__setitem__("finite_check", 8)))
        self.assertIn("extensions.refused", self.mismatches(lambda r: r["extensions"].__setitem__("refused", [{"id": "x", "codes": []}])))
        for name in EXPECTED["suites"]:
            self.assertIn(f"suites.{name}", self.mismatches(lambda r, n=name: r["suites"][n].__setitem__("examples", 0)), name)
            self.assertIn(f"suites.{name}", self.mismatches(lambda r, n=name: r["suites"][n].__setitem__("failures", [{"example": "x", "paths": []}])), name)
        self.assertIn("budget.denominator", self.mismatches(lambda r: r["budget"].__setitem__("requests", 202)))
        self.assertIn("budget.denominator", self.mismatches(lambda r: r["budget"].__setitem__("evaluations", 1)))
        self.assertIn("budget.violations", self.mismatches(lambda r: r["budget"].__setitem__("violations", [["x", 0, "certificate_on_stop"]])))
        self.assertIn("budget.allowlist", self.mismatches(lambda r: r["budget"].__setitem__("allowed_budget_dependent_refusals", 2)))

    def test_a_failed_version_comparison_is_a_mismatch_and_a_skipped_one_is_not(self):
        self.assertIn("versions.r", self.mismatches(lambda r: r["versions"].__setitem__(0, {"record": "r", "status": "failed"})))
        self.assertEqual(self.mismatches(lambda r: r["versions"].__setitem__(0, {"record": "r", "status": "not_run", "reason": "missing_commits:from"})), [])


class RunTests(unittest.TestCase):
    def test_the_output_must_be_under_the_p2_d_data_directory(self):
        with self.assertRaises(ValueError):
            evaluate_p2.run(ROOT / "data/research/p1-d/should-not-be-written", versions=False)
        with self.assertRaises(ValueError):
            evaluate_p2.run(Path(tempfile.gettempdir()) / "p2-outside", versions=False)

    def test_a_skipped_comparison_says_why_when_the_history_lacks_the_commits(self):
        with patch.object(evaluate_p2.p2_checks, "has_commit", return_value=False):
            reports = evaluate_p2.versions_report()
        self.assertEqual([(r["status"], r["reason"]) for r in reports], [("not_run", "missing_commits:from,to")])

    def test_a_lock_that_changes_during_the_evaluation_is_not_recorded_as_a_success(self):
        parent = ROOT / "data/research/p2-d"
        parent.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="test-", dir=parent))
        calls = []

        def changing():
            calls.append(1)
            return {**evaluate_p2.EXPECTED["base"], "passed": True, "manifest_sha256": "a" if len(calls) == 1 else "b", "bundle_sha256": "x"}
        try:
            with patch.object(evaluate_p2, "base_report", changing), patch.object(evaluate_p2, "extension_report", lambda: {**EXPECTED["extensions"], "refused": [], "rows": []}), \
                    patch.object(evaluate_p2, "suites_report", lambda: {n: {"examples": s["examples"], "checks": s["checks"], "failures": []} for n, s in EXPECTED["suites"].items()}), \
                    patch.object(evaluate_p2, "budget_report", lambda limit: {"requests": 203, "evaluations": 2936, "violations": [], "allowed_budget_dependent_refusals": 1}):
                with self.assertRaisesRegex(ValueError, "snapshot_changed_during_evaluation"):
                    evaluate_p2.run(folder, versions=False)
            self.assertFalse((folder / "results.json").exists())            # 成功の記録を残さない
        finally:
            shutil.rmtree(folder)

    def test_the_run_fails_when_any_pinned_value_differs(self):
        parent = ROOT / "data/research/p2-d"
        parent.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="test-", dir=parent))
        try:
            with patch.object(evaluate_p2, "mismatches", lambda report: ["extensions.guards"]):
                report = evaluate_p2.run(folder, versions=False)
            self.assertFalse(report["passed"])
            self.assertEqual(report["mismatches"], ["extensions.guards"])
        finally:
            shutil.rmtree(folder)

    def test_a_full_run_without_the_version_comparison_passes_and_stays_a_draft(self):
        parent = ROOT / "data/research/p2-d"
        parent.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="test-", dir=parent))
        try:
            report = evaluate_p2.run(folder, versions=False)
            self.assertEqual(report["mismatches"], [])
            self.assertTrue(report["passed"])
            written = json.loads((folder / "results.json").read_text(encoding="utf-8"))
            self.assertFalse(written["independent_review"])
            self.assertFalse(written["evaluation_frozen"])
            self.assertEqual(written["expected"], EXPECTED)
            self.assertEqual(written["base"]["p1_cases"], 20)
        finally:
            shutil.rmtree(folder)


class CommandLineTests(unittest.TestCase):
    """終了コード：0＝合格、1＝分母の食い違い、2＝実行できない（入力や固定対象の不整合）。"""

    def main(self, outcome):
        def fake_run(output, versions=True, limit=300):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        with patch.object(evaluate_p2, "run", fake_run), patch.object(sys, "argv", ["evaluate-p2.py", "--no-versions"]), \
                patch("builtins.print"), patch.object(sys, "stderr"):
            return evaluate_p2.main()

    def report(self, passed):
        return {"passed": passed, "mismatches": [] if passed else ["x"], "base": {k: 0 for k in ("p1_cases", "p1_files", "p1_checks", "p0_files", "p0_checks", "manifest_sha256", "bundle_sha256")},
                "extensions": {k: 0 for k in ("registered", "obligations", "guards", "guard_gaps", "independent_pairs", "pairs")}, "suites": {},
                "budget": {"violations": []}, "versions": []}

    def test_exit_codes(self):
        self.assertEqual(self.main(self.report(True)), 0)
        self.assertEqual(self.main(self.report(False)), 1)
        self.assertEqual(self.main(ValueError("snapshot_mismatch")), 2)


if __name__ == "__main__":
    unittest.main()
