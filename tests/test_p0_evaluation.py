"""評価器が入力・期待値の照合と再現性を省略しないことを確認する。"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p0_evaluation", ROOT / "scripts/research/evaluate-p0.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
    def test_full_manifest_has_all_22_cases_and_replay_relations(self):
        with tempfile.TemporaryDirectory() as folder:
            report = evaluation.run(ROOT / "examples/p0/manifest.json", Path(folder))
            self.assertEqual(report["cases_passed"], 22)
            self.assertEqual(report["fixtures_passed"], report["fixture_count"])
            self.assertEqual(report["checks_passed"], report["checks_total"])
            self.assertTrue(all(report["relations"].values()))
            self.assertFalse(report["independent_review"])

    def test_changed_fixture_hash_is_rejected_before_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "fixtures"
            shutil.copytree(ROOT / "examples/p0", root)
            manifest = root / "manifest.json"
            data = json.loads(manifest.read_text()); data["files"][-1]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "fixture_hash_or_size_mismatch"):
                evaluation.run(manifest, Path(folder) / "results")
            self.assertFalse((Path(folder) / "results").exists())

    def test_missing_expected_paths_and_wrong_json_types_fail_checks(self):
        expected = [{"path": ["missing"], "equals": None}, {"path": ["value"], "equals": True}]
        original = deepcopy(expected)
        checks = evaluation._checks({"value": 1}, expected)
        self.assertFalse(any(c["passed"] for c in checks))
        self.assertEqual(expected, original)


if __name__ == "__main__":
    unittest.main()
