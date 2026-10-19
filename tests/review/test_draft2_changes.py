"""p0-draft-2 の変更（RV-05 の裁定の実装、RV-02/03/04 の修正）を確かめる。

固定した231テスト・P1の20条件とは別の分母（レビュー系列）。実行は
`python3 -m unittest discover -s tests/review -v`。
"""

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.identity import implementation_identity
from med_dsl.validation import canonical_bytes, digest


def request(suite, name):
    return json.loads((ROOT / "examples" / suite / (name + ".json")).read_text())["request"]


class ReviewPrecedesAssertionTests(unittest.TestCase):
    """RV-05：確認は対象が台帳に記録された後にしか存在できない。等しい時刻は許す。"""

    def p0(self, delta):
        data = request("p0", "ai-human-confirmation")   # h1 は 2026-01-10T10:00:00Z、view v1 は 2026-01-10T12:00:00Z
        data["ledger"]["reviews"][0]["recorded_at"] = delta
        return data

    def test_strictly_earlier_review_is_invalid_input_with_a_precise_path(self):
        result = evaluate(self.p0("2026-01-10T09:59:59Z"))
        self.assertEqual((result["status"], result["reason_codes"], result["error_path"]),
                         ("invalid_input", ["review_precedes_assertion"], "review.recorded_at"))
        self.assertNotIn("results", result)

    def test_equal_and_later_reviews_are_accepted(self):
        for when in ("2026-01-10T10:00:00Z", "2026-01-10T10:00:01Z"):
            with self.subTest(review=when):
                result = evaluate(self.p0(when))
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["results"][0]["status"], "supported")

    def test_unreviewed_future_review_still_cannot_adopt_a_visible_assertion(self):
        # 確認が view の時点より後なら、順序が正しくても採用されない（従来どおり）
        result = evaluate(self.p0("2026-01-10T12:00:01Z"))
        self.assertEqual(result["results"][0]["status"], "undetermined")

    def test_rule_reaches_every_entrance_that_reuses_the_p0_validation(self):
        source = request("p1-b", "reify-events")
        source["source"]["ledger"]["reviews"][0]["recorded_at"] = "2026-01-10T09:00:00Z"
        self.assertEqual(evaluate(source)["reason_codes"], ["review_precedes_assertion"])
        forecast = request("p1-a", "finite-forecast")
        forecast["report_snapshot"]["ledger"]["reviews"][0]["recorded_at"] = "2026-10-18T08:00:00Z"
        self.assertEqual(evaluate(forecast)["reason_codes"], ["review_precedes_assertion"])
        compare = request("p0", "conflict-compare")
        compare["before"]["ledger"]["reviews"][0]["recorded_at"] = "2000-01-01T00:00:00Z"
        self.assertEqual(evaluate(compare)["reason_codes"], ["review_precedes_assertion"])

    def test_archive_payload_with_an_early_review_is_not_an_interpretable_snapshot(self):
        data = request("p1-c", "known-native-ready")
        payload = json.loads(base64.b64decode(data["archive"]["bytes_base64"]))
        payload["ledger"]["reviews"][0]["recorded_at"] = "2026-01-10T09:00:00Z"
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        data["archive"]["bytes_base64"] = base64.b64encode(raw).decode()
        data["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        result = evaluate(data)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["legacy_replay"]["status"], "unavailable")
        self.assertEqual(result["legacy_replay"]["input_interpretation"]["reason_codes"], ["review_precedes_assertion"])


class ReferenceReasonCodeTests(unittest.TestCase):
    """RV-02：認定されない理由は、未証明の側を指す。"""

    def reference(self, source_theory, target_theory):
        data = request("p1-c", "existential-without-named-witness")
        data["source"] = {"theory": source_theory, "data": data["source"]["data"]}
        data["target"] = {"theory": target_theory, "data": data["source"]["data"]}
        data["models"] = []
        return data

    def rule(self):
        return request("p1-c", "existential-without-named-witness")["source"]["theory"][0]

    def test_weaker_target_leaves_the_reduct_unproven_not_the_coverage(self):
        result = evaluate(self.reference([self.rule()], []))
        self.assertEqual((result["model_coverage"], result["model_reduct"]), (True, None))
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertEqual(result["certificate"]["reason_codes"], ["model_reduct_not_established"])

    def test_stronger_target_leaves_the_coverage_unproven(self):
        result = evaluate(self.reference([], [self.rule()]))
        self.assertEqual((result["model_coverage"], result["model_reduct"]), (None, True))
        self.assertEqual(result["certificate"]["reason_codes"], ["model_coverage_not_established"])

    def test_unrelated_sentence_sets_leave_both_unproven(self):
        other = deepcopy(self.rule())
        other["var"] = "w"
        other["body"]["left"]["args"] = [{"var": "w"}]
        other["body"]["right"]["body"]["items"][0]["args"][0] = {"var": "w"}
        result = evaluate(self.reference([self.rule()], [other]))
        self.assertEqual((result["model_coverage"], result["model_reduct"]), (None, None))
        self.assertEqual(result["certificate"]["reason_codes"], ["model_coverage_not_established", "model_reduct_not_established"])

    def test_countermodels_and_identity_keep_their_own_reasons(self):
        self.assertEqual(evaluate(request("p1-c", "coverage-countermodel"))["certificate"]["reason_codes"][0], "old_model_not_liftable")
        self.assertEqual(evaluate(request("p1-c", "identity-template"))["certificate"]["reason_codes"], [])

    def test_a_chain_mismatch_is_not_reported_as_incomparable(self):
        data = request("p1-c", "event-renaming-chain")
        fake = {"status": "ok", "comparison": {"status": "mismatch", "results": []}}
        with patch("med_dsl.handover._compare", return_value=fake):
            result = evaluate(data)
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertEqual(result["certificate"]["reason_codes"], ["answers_mismatch"])


class ForecastIncompleteTests(unittest.TestCase):
    """RV-03：未評価の行は、未知能力でも打切りでも incomplete に列挙する（P0 の query／P1-b と同じ）。"""

    def test_unknown_capability_rows_are_listed(self):
        for name in ("unknown-capability", "unknown-capability-pending"):
            with self.subTest(fixture=name):
                result = evaluate(request("p1-a", name))
                self.assertEqual([r["status"] for r in result["results"]], ["unassessed"])
                self.assertEqual(result["incomplete"], [{"view_id": "v1", "query_id": "q1"}])
                self.assertEqual(result["status"], "ok")

    def test_only_unassessed_rows_are_listed_and_completed_rows_stay_out(self):
        data = request("p1-a", "shared-budget")
        full = deepcopy(data)
        full["budget"]["max_steps"] = 100000
        self.assertEqual(evaluate(full)["incomplete"], [])
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        listed = {(i["view_id"], i["query_id"]) for i in result["incomplete"]}
        self.assertEqual(listed, {(r["view_id"], r["query_id"]) for r in result["results"] if r["status"] == "unassessed"})
        self.assertTrue(any(r["status"] == "computed" for r in result["results"]))

    def test_conflict_and_undetermined_rows_are_not_incomplete(self):
        result = evaluate(request("p1-a", "ai-unreviewed"))
        self.assertEqual([r["status"] for r in result["results"]], ["undetermined"])
        self.assertEqual(result["incomplete"], [])


class CertifierTests(unittest.TestCase):
    """RV-04：すべての certificate が、認定を出した実装の束を特定する。"""

    def manifest_bundle(self):
        files = json.loads((ROOT / "examples/p1-evaluation/manifest.json").read_text())["files"]
        return digest({name.rsplit("/", 1)[1]: entry["sha256"] for name, entry in files.items()
                       if name.startswith("src/med_dsl/") and name.count("/") == 2})

    def test_bundle_is_reproducible_from_the_integrated_manifest(self):
        identity = implementation_identity()
        self.assertEqual(identity["bundle_sha256"], self.manifest_bundle())
        self.assertEqual(identity["kind"], "native_python_modules")
        self.assertGreaterEqual(identity["files"], 15)

    def test_every_certificate_carries_the_certifier(self):
        expected = implementation_identity()
        cases = [("p0", "definition-extension", [["certificate"]]),
                 ("p1-c", "event-renaming-chain", [["certificate"], ["finite_checks", 0, "certificate"]]),
                 ("p1-c", "identity-template", [["certificate"]]),
                 ("p1-c", "lossy-composition", [["certificate"], ["second_step_certificate"]]),
                 ("p1-c", "new-guarantee-independent-of-old-binary", [["semantic_handover", "certificate"], ["semantic_handover", "verification", "certificate"]]),
                 ("p1-b", "native-query", []), ("p1-a", "finite-forecast", [])]
        for suite, name, paths in cases:
            result = evaluate(request(suite, name))
            for path in paths:
                actual = result
                for key in path:
                    actual = actual[key]
                with self.subTest(fixture=name, path=path):
                    self.assertEqual(actual["certifier"], expected)
            if not paths:
                self.assertNotIn("certifier", json.dumps(result))

    def test_refusals_and_errors_carry_no_certificate_and_no_certifier(self):
        result = evaluate(request("p1-a", "unnormalized"))
        self.assertEqual(result["status"], "invalid_input")
        self.assertNotIn("certifier", json.dumps(result))

    def test_bundle_changes_when_a_module_the_runtime_pins_do_not_cover_changes(self):
        # events.py は実行時の hash 固定の対象外。認定票の束は、その変更を検出する。
        script = ("import json,sys; sys.path.insert(0, sys.argv[1]); "
                  "from med_dsl.identity import implementation_identity as i; print(json.dumps(i()))")
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT / "src/med_dsl", Path(folder) / "med_dsl", ignore=shutil.ignore_patterns("__pycache__"))
            before = json.loads(subprocess.run([sys.executable, "-B", "-c", script, folder], capture_output=True, text=True, check=True).stdout)
            with (Path(folder) / "med_dsl/events.py").open("a") as handle:
                handle.write("\n# changed\n")
            after = json.loads(subprocess.run([sys.executable, "-B", "-c", script, folder], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(before["bundle_sha256"], implementation_identity()["bundle_sha256"])
        self.assertNotEqual(before["bundle_sha256"], after["bundle_sha256"])
        self.assertEqual(before["files"], after["files"])

    def test_results_stay_deterministic_with_the_certifier(self):
        data = request("p1-c", "event-renaming-chain")
        self.assertEqual(canonical_bytes(evaluate(deepcopy(data))), canonical_bytes(evaluate(deepcopy(data))))


if __name__ == "__main__":
    unittest.main()
