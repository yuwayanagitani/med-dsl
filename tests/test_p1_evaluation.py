"""総合評価が固定・意味層・分母・失敗を取り違えないことを検査する。"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p1_integrated_evaluation", ROOT / "scripts/research/evaluate-p1-d.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class IntegratedEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "data/research/p1-d").mkdir(parents=True, exist_ok=True)

    def copy_snapshot(self, folder):
        root = Path(folder)
        for name in evaluation.inventory(ROOT):
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        lock = evaluation.build_manifest(root)
        self.write(root / evaluation.LOCK, lock)
        return root, lock

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def test_unified_inventory_has_all_cases_and_original_denominators(self):
        lock, _, fixtures = evaluation.preflight(snapshot=evaluation.build_manifest())
        self.assertEqual([c["id"] for c in lock["cases"]], [f"H{i:02}" for i in range(1, 21)])
        self.assertEqual(sum(len(rows) for name, rows in fixtures.items() if name != "p0"), 80)
        self.assertEqual(sum(len(data["expected"]["checks"]) for name, rows in fixtures.items()
                             if name != "p0" for _, data, _ in rows), 417)
        self.assertEqual(len(fixtures["p0"]), 37)
        self.assertFalse(lock["independent_review"])
        self.assertFalse(lock["evaluation_frozen"])

    def test_missing_changed_or_added_pinned_file_is_rejected(self):
        for mutation in ("source", "fixture", "missing", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root, _ = self.copy_snapshot(folder)
                if mutation == "source":
                    (root / "src/med_dsl/forecast_spec.json").write_text("{}")
                elif mutation == "fixture":
                    (root / "examples/p1-c/corrupt-archive.json").write_text("{}")
                elif mutation == "missing":
                    (root / "tests/test_p0_ledger.py").unlink()
                else:
                    (root / "examples/p0/extra.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "snapshot_mismatch"):
                    evaluation.preflight(root)

    def test_missing_duplicate_case_false_review_and_wrong_meaning_mode_are_rejected(self):
        for mutation in ("missing", "duplicate", "review", "frozen", "meaning", "suite"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root, lock = self.copy_snapshot(folder)
                if mutation == "missing":
                    lock["cases"].pop()
                elif mutation == "duplicate":
                    lock["cases"][-1] = deepcopy(lock["cases"][0])
                elif mutation == "review":
                    lock["independent_review"] = True
                elif mutation == "frozen":
                    lock["evaluation_frozen"] = True
                elif mutation == "meaning":
                    lock["cases"][12]["meaning_mode"] = "finite_event_support"
                else:
                    lock["suites"]["p1-c"]["manifest"] = "examples/p1-b/manifest.json"
                self.write(root / evaluation.LOCK, lock)
                with self.assertRaisesRegex(ValueError, "snapshot_mismatch"):
                    evaluation.preflight(root)

    def test_repinning_does_not_bypass_original_manifest_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, _ = self.copy_snapshot(folder)
            (root / "examples/p1-c/corrupt-archive.json").write_text("{}")
            self.write(root / evaluation.LOCK, evaluation.build_manifest(root))
            with self.assertRaisesRegex(ValueError, "fixture_hash_or_size_mismatch"):
                evaluation.preflight(root)

    def test_repinning_does_not_bypass_native_profile_or_specification(self):
        with tempfile.TemporaryDirectory() as folder:
            root, _ = self.copy_snapshot(folder)
            path = root / "examples/p1-b/manifest.json"
            manifest = json.loads(path.read_text())
            manifest["profile_spec_sha256"] = "0" * 64
            self.write(path, manifest)
            self.write(root / evaluation.LOCK, evaluation.build_manifest(root))
            with self.assertRaisesRegex(ValueError, "author_draft_manifest_required"):
                evaluation.preflight(root)

    def test_required_paths_distinguish_missing_null_types_and_container_kind(self):
        expected = [{"path": ["missing"], "equals": None}, {"path": ["flag"], "equals": True},
                    {"path": ["items", True], "equals": "a"}, {"path": ["items", 0], "equals": "a"}]
        checks = evaluation.check_paths({"flag": 1, "items": ["a", "a"]}, expected)
        self.assertEqual([c["passed"] for c in checks], [False, False, False, True])

    def test_invalid_or_duplicate_required_paths_are_rejected(self):
        for paths in ([[]], [[True]], [[-1]], [["status"], ["status"]]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                evaluation._validate_checks({"expected": {"checks": [{"path": p, "equals": None} for p in paths]}})

    def records(self):
        lock, _, fixtures = evaluation.preflight(snapshot=evaluation.build_manifest())
        # 集計だけのテスト用。実際の意味計算は既存テストと総合実行で行う。
        records = [{"suite": name, "fixture_id": data["fixture_id"], "path": str(path),
                    "passed": True, "checks": [{"passed": True} for _ in data["expected"]["checks"]],
                    "result": {"input_sha256": path.name, "status": "ok"}}
                   for name, rows in fixtures.items() for _, data, path in rows]
        return lock, records

    def test_failure_is_not_hidden_by_other_variants_or_p0_regression(self):
        lock, records = self.records()
        next(r for r in records if r["suite"] == "p1-a")["passed"] = False
        summary = evaluation.summarize(records, lock)
        self.assertEqual(summary["p1_cases_passed"], 19)
        self.assertEqual(len(summary["suites"]["p0"]["cases"]), 22)
        self.assertFalse(summary["passed"])

    def test_missing_results_do_not_pass_vacuously(self):
        lock, records = self.records()
        with self.assertRaisesRegex(ValueError, "incomplete_suite_results"):
            evaluation.summarize(records[:-1], lock)

    def test_cross_fixture_reproducibility_is_still_required(self):
        lock, records = self.records()
        next(r for r in records if r["path"].endswith("reproducibility-reordered.json"))["result"]["status"] = "different"
        summary = evaluation.summarize(records, lock)
        self.assertFalse(summary["suites"]["p0"]["cases"]["P22"])
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["p1_cases_passed"], 20)

    def test_api_input_mutation_and_boolean_integer_replay_difference_fail(self):
        data = {"fixture_id": "H01", "request": {"x": 0},
                "expected": {"checks": [{"path": ["flag"], "equals": True}]}}
        def fake(request):
            request["x"] += 1
            return {"status": "ok", "flag": True if fake.calls == 0 else 1}
        fake.calls = 0
        def call(request):
            result = fake(request)
            fake.calls += 1
            return result
        with patch.object(evaluation, "evaluate", side_effect=call):
            record = evaluation.evaluate_fixture("p1-a", {"sha256": "test"}, data,
                                                  ROOT / "examples/p1-a/finite-forecast.json", False)
        self.assertFalse(record["input_preserved"])
        self.assertFalse(record["replay_identical"])
        self.assertFalse(record["passed"])
        self.assertEqual(data["request"], {"x": 0})

    def test_cli_result_and_exit_code_must_both_match(self):
        data = {"fixture_id": "H01", "request": {}, "expected": {"checks": [{"path": ["flag"], "equals": True}]}}
        for response in (SimpleNamespace(returncode=0, stdout=b'{"status":"ok","flag":1}'),
                         SimpleNamespace(returncode=2, stdout=b'{"status":"ok","flag":true}')):
            with self.subTest(response=response), patch.object(evaluation, "evaluate", return_value={"status": "ok", "flag": True}), \
                    patch.object(evaluation.subprocess, "run", return_value=response):
                record = evaluation.evaluate_fixture("p1-a", {"sha256": "test"}, data,
                                                      ROOT / "examples/p1-a/finite-forecast.json", True)
                self.assertFalse(record["cli_matches_api"])
                self.assertFalse(record["passed"])

    def test_late_snapshot_change_does_not_publish_a_completed_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/research/p1-d") as folder:
            output = Path(folder) / "run"
            with patch.object(evaluation, "preflight", side_effect=[({}, "first", {}), ({}, "changed", {})]), \
                    patch.object(evaluation, "summarize", return_value={}):
                with self.assertRaisesRegex(ValueError, "snapshot_changed_during_evaluation"):
                    evaluation.run(output)
            self.assertFalse(output.exists())

    def test_preflight_error_never_evaluates_or_rewrites_previous_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "data/research/p1-d") as folder:
            output = Path(folder)
            report = output / "results.json"
            report.write_text("previous")
            with patch.object(evaluation, "preflight", side_effect=ValueError("broken")), \
                    patch.object(evaluation, "evaluate") as mocked:
                with self.assertRaisesRegex(ValueError, "broken"):
                    evaluation.run(output)
                mocked.assert_not_called()
            self.assertEqual(report.read_text(), "previous")

    def test_output_cannot_overwrite_fixed_inputs(self):
        with self.assertRaisesRegex(ValueError, "output_must_be_under"):
            evaluation.run(ROOT / "examples/p1-a")


if __name__ == "__main__":
    unittest.main()
