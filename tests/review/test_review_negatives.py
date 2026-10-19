"""レビュー AI-001 の RV-01：認定・可用性・射影の主要ゲートの負例。

固定済みの168ファイル・231テスト・P1の20条件とは別の分母。期待結果は各ゲートの意味から
手で指定した。実行は `python3 -m unittest discover -s tests/review -v`（tests/ 直下には置かない）。
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.validation import canonical_bytes, decode_json
import hashlib

SERIES = ROOT / "examples/review"
IDS = [f"RN{i:02}" for i in range(1, 13)]
KNOWN_IDS = ["KD01"]
STATUS_CODES = {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}


def manifest():
    return decode_json((SERIES / "manifest.json").read_bytes())


def fixtures(group="files"):
    for entry in manifest()[group]:
        yield entry, decode_json((SERIES / entry["path"]).read_bytes())


def lookup(result, path):
    actual = result
    for key in path:
        if ((type(actual) is dict and type(key) is str and key in actual)
                or (type(actual) is list and type(key) is int and 0 <= key < len(actual))):
            actual = actual[key]
        else:
            return False, None
    return True, actual


class ReviewNegativeSeriesTests(unittest.TestCase):
    def test_series_is_closed_and_separate_from_the_pinned_denominators(self):
        data = manifest()
        self.assertEqual(data["status"], "ai_reviewer_draft")
        self.assertFalse(data["independent_review"])
        self.assertFalse(data["evaluation_frozen"])
        self.assertEqual([e["fixture_id"] for e in data["files"]], IDS)
        self.assertEqual([e["fixture_id"] for e in data["known_deviations"]], KNOWN_IDS)
        listed = data["files"] + data["known_deviations"]
        self.assertEqual({e["path"] for e in listed}, {p.name for p in SERIES.glob("*.json")} - {"manifest.json"})
        for entry in listed:
            raw = (SERIES / entry["path"]).read_bytes()
            self.assertEqual(len(raw), entry["bytes"], entry["path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"], entry["path"])
        spec = importlib.util.spec_from_file_location("p1d", ROOT / "scripts/research/evaluate-p1-d.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pinned = module.inventory(ROOT)
        self.assertFalse([n for n in pinned if n.startswith(("examples/review/", "tests/review/"))])

    def test_every_negative_expects_a_refusal_or_a_failed_gate_and_not_a_positive_claim(self):
        for entry, data in fixtures():
            with self.subTest(fixture=entry["fixture_id"]):
                self.assertTrue(data["fictional"])
                self.assertEqual(data["review_state"], "ai_reviewer_draft")
                self.assertEqual(data["finding"], "RV-01")
                expected = {tuple(c["path"]): c["equals"] for c in data["expected"]["checks"]}
                # 主たる認定・可用性の主張を肯定側で期待しない（二段目の符号化の認定は範囲が別なので除く）
                self.assertNotEqual(expected.get(("certificate", "status")), "certified")
                self.assertNotEqual(expected.get(("legacy_replay", "status")), "ready_to_replay")
                self.assertNotEqual(expected.get(("semantic_handover", "status")), "certified")
                self.assertTrue(len(expected) >= 3)

    def test_required_paths_hold_and_input_is_preserved(self):
        for entry, data in [*fixtures(), *fixtures("known_deviations")]:
            with self.subTest(fixture=entry["fixture_id"], path=entry["path"]):
                original = deepcopy(data["request"])
                request = deepcopy(original)
                result = evaluate(request)
                self.assertEqual(canonical_bytes(request), canonical_bytes(original))
                self.assertEqual(canonical_bytes(evaluate(deepcopy(original))), canonical_bytes(result))
                for check in data["expected"]["checks"]:
                    found, actual = lookup(result, check["path"])
                    self.assertTrue(found, check["path"])
                    self.assertEqual(canonical_bytes(actual), canonical_bytes(check["equals"]), check["path"])

    def test_cli_returns_the_same_result_and_exit_code(self):
        for entry, data in [*fixtures(), *fixtures("known_deviations")]:
            with self.subTest(fixture=entry["fixture_id"]):
                result = evaluate(deepcopy(data["request"]))
                run = subprocess.run([sys.executable, "-B", "-m", "med_dsl", "--fixture", str(SERIES / entry["path"])],
                                     capture_output=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}, timeout=30)
                self.assertEqual(run.returncode, STATUS_CODES[result["status"]])
                self.assertEqual(canonical_bytes(decode_json(run.stdout)), canonical_bytes(result))

    def test_forged_vouchers_are_refused_only_by_the_per_key_gate_when_stages_still_compose(self):
        # 両段で一貫した偽の票は「段の接続」検査を通る。拒否できるのは実体からの再計算だけ。
        for fixture_id in ("RN03", "RN04", "RN05"):
            data = next(d for e, d in fixtures() if d["fixture_id"] == fixture_id)
            result = evaluate(deepcopy(data["request"]))
            names = {o["name"]: o["passed"] for o in result["obligations"]}
            with self.subTest(fixture=fixture_id):
                self.assertTrue(names["stage_endpoints_compose"] and names["translated_query_scopes_compose"])
                self.assertEqual(result["certificate"]["status"], "not_certified")
                self.assertNotIn("finite_checks", result)

    def test_known_deviation_records_current_behavior_and_the_ruled_behavior_separately(self):
        # RV-05：現行版は確認が主張より前でも採用する。裁定は次の契約版で入力不正とする。
        # この例は現行版の挙動を固定する。契約版を上げたら、期待を after_adoption へ反転させる。
        (entry, data), = list(fixtures("known_deviations"))
        self.assertEqual(data["expected"]["kind"], "current_behavior_of_known_deviation")
        self.assertEqual(data["known_deviation"]["ruling"], "RV-05")
        after = data["known_deviation"]["after_adoption"]
        self.assertEqual((after["status"], after["reason_codes"]), ("invalid_input", ["review_precedes_assertion"]))
        request = data["request"]
        review = request["ledger"]["reviews"][0]
        assertion = next(a for a in request["ledger"]["assertions"] if a["id"] == review["assertion_ref"])
        self.assertLess(review["recorded_at"], assertion["recorded_at"])
        result = evaluate(deepcopy(request))
        self.assertEqual((result["status"], result["results"][0]["status"]), ("ok", "supported"))
        # 等しい時刻の確認は裁定後も許される。厳密に前の場合だけが対象。
        request["ledger"]["reviews"][0]["recorded_at"] = assertion["recorded_at"]
        self.assertEqual(evaluate(request)["results"][0]["status"], "supported")

    def test_honest_chain_is_still_certified_so_the_negatives_are_not_vacuous(self):
        base = json.loads((ROOT / "examples/p1-c/event-renaming-chain.json").read_text())["request"]
        self.assertEqual(evaluate(base)["certificate"]["status"], "certified")


if __name__ == "__main__":
    unittest.main()
