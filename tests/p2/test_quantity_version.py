"""P2-l：数量の単位表の版の更新（draft-1 → draft-2）。

履歴を要しない部分（比較器の判定の検出力）と、記録に沿って履歴から旧版を取り出して比べる部分（版の手順 V1〜V8）に分ける。
記録（examples/p2-versions/p2-quantity-draft-1-to-draft-2.json）は、新版の実装を含むコミットの後に追加するので、
記録がない、または履歴に旧版・新版のコミットがない環境では、履歴を要する部分は行わない。
"""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/research")]

import p2_checks as checks

RECORD_PATH = ROOT / "examples/p2-versions/p2-quantity-draft-1-to-draft-2.json"
RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8")) if RECORD_PATH.is_file() else None
HISTORY = RECORD is not None and all(checks.has_commit(RECORD[side]["commit"]) for side in ("from", "to"))
CHANGED = ["p2-quantity/q03.json", "p2-quantity/q04.json", "p2-quantity/q08.json", "p2-display/p12.json",
           "p2-temporal-measurement/c22-third.json", "p2-temporal-display/j07.json"]


def synthetic():
    """比較器の単位テスト用の、全てが宣言どおりの記録と報告。"""
    record = {"from": {"evaluation": {"passed": True}}, "to": {"evaluation": {"passed": True}},
              "pins": [{"file": "a.py", "name": "X"}, {"file": "b.py", "name": "X"}],
              "pin_refusals": [{"status": "unsupported_profile", "code": "profile_spec_mismatch"}],
              "intended_changes": ["spec.json"], "pure_pin_suites": ["s1"],
              "predicted": {"extensions": ["e1", "e2"], "regenerate": ["a.py", "s1/*.json"]},
              "declared_changes": [{"id": "D-1", "kind": "added_unit", "added_inputs": ["s1/new.json"]},
                                   {"id": "D-2", "kind": "changed_value", "inputs": ["s1/a.json"], "allowed_prefixes": ["/results[]"]}],
              "measured": {"old_inputs_without_regeneration": {"identical": 1, "pin_refused": 2, "changed": 0},
                           "inputs": {"old": 3, "new": 4}, "unpredicted_repin": ["b.py"]}}
    report = {"reproduction": {"from": {"passed": True}, "to": {"passed": True}}, "pins_changed": ["a.py", "b.py"],
              "inputs": {"old": 3, "new": 4, "added": ["s1/new.json"], "removed": []},
              "old_inputs_without_regeneration": {"identical": ["s1/c.json"], "pin_refused": ["s1/a.json", "s1/b.json"], "changed": []},
              "request_changed": [], "expectation_changed": ["s1/a.json"], "result_differences": {"s1/a.json": ["/results[]/converted_domain/lower"]},
              "steps_changed": [], "substituted": {"s1/a.json": "ok", "s2/m.json": "invalid_input"},
              "affected": {"extensions": ["e1", "e2"], "regenerate": ["a.py", "s1/x.json"], "lock": None, "predicted_regenerate": ["a.py", "s1/x.json"]},
              "necessary_repin": ["a.py", "b.py", "spec.json"]}
    return record, report


class ComparatorLogicTests(unittest.TestCase):
    """履歴を要しない：比較器は、宣言にない差、黙った再解釈、予測の食い違いを、それぞれ報告する。"""

    def mismatches(self, mutate_report=None, mutate_record=None):
        record, report = synthetic()
        if mutate_record:
            mutate_record(record)
        if mutate_report:
            mutate_report(report)
        return checks.regenerated_mismatches(record, report)

    def test_a_report_that_matches_the_declarations_has_no_mismatch(self):
        self.assertEqual(self.mismatches(), [])

    def test_a_silent_reinterpretation_is_reported(self):
        def change(report):
            report["old_inputs_without_regeneration"]["changed"] = ["s1/c.json"]
            report["old_inputs_without_regeneration"]["identical"] = []
        found = self.mismatches(change)
        self.assertIn("silent_reinterpretation", found)
        self.assertIn("classification_counts", found)

    def test_a_regenerated_request_that_changed_is_reported(self):
        self.assertIn("regenerated_request_changed", self.mismatches(lambda r: r.__setitem__("request_changed", ["s1/c.json"])))

    def test_an_undeclared_or_missing_expectation_or_result_difference_is_reported(self):
        self.assertIn("undeclared_or_missing_expectation_change", self.mismatches(lambda r: r.__setitem__("expectation_changed", ["s1/a.json", "s1/c.json"])))
        self.assertIn("undeclared_or_missing_expectation_change", self.mismatches(lambda r: r.__setitem__("expectation_changed", [])))
        self.assertIn("undeclared_or_missing_result_difference", self.mismatches(lambda r: r["result_differences"].__setitem__("s1/c.json", ["/status"])))
        self.assertIn("undeclared_or_missing_result_difference", self.mismatches(lambda r: r.__setitem__("result_differences", {})))

    def test_a_difference_outside_the_declared_paths_is_reported(self):
        found = self.mismatches(lambda r: r["result_differences"]["s1/a.json"].append("/certificate/status"))
        self.assertIn("difference_outside_declared_paths:s1/a.json", found)

    def test_a_change_in_the_cost_is_reported(self):
        self.assertIn("steps_changed", self.mismatches(lambda r: r.__setitem__("steps_changed", ["s1/a.json"])))

    def test_added_or_removed_inputs_must_match_the_declaration(self):
        self.assertIn("added_or_removed_inputs", self.mismatches(lambda r: r["inputs"].__setitem__("removed", ["s1/c.json"])))
        self.assertIn("added_or_removed_inputs", self.mismatches(lambda r: r["inputs"].__setitem__("added", [])))

    def test_the_number_of_inputs_must_match_the_record(self):
        self.assertIn("input_counts", self.mismatches(lambda r: r["inputs"].__setitem__("old", 4)))
        self.assertIn("input_counts", self.mismatches(lambda r: r["inputs"].__setitem__("new", 3)))

    def test_pins_and_reproduction_must_match_the_record(self):
        self.assertIn("pins_changed", self.mismatches(lambda r: r.__setitem__("pins_changed", ["a.py"])))
        self.assertIn("reproduction_from", self.mismatches(lambda r: r["reproduction"].__setitem__("from", {"passed": False})))
        self.assertIn("reproduction_to", self.mismatches(lambda r: r["reproduction"].__setitem__("to", {"passed": False})))

    def test_a_content_bound_input_that_a_substitution_repinned_is_reported(self):
        self.assertIn("substitution_repinned_a_content_bound_input", self.mismatches(lambda r: r["substituted"].__setitem__("s2/m.json", "ok")))

    def test_a_change_of_the_enumeration_or_an_unlisted_repin_is_reported(self):
        self.assertIn("affected_prediction_changed", self.mismatches(lambda r: r["affected"].__setitem__("extensions", ["e1"])))
        self.assertIn("affected_prediction_changed", self.mismatches(lambda r: r["affected"].__setitem__("regenerate", ["a.py"])))
        self.assertIn("affected_prediction_changed", self.mismatches(lambda r: r["affected"].__setitem__("predicted_regenerate", ["a.py"])))
        self.assertIn("unpredicted_repin", self.mismatches(lambda r: r["necessary_repin"].append("c.py")))
        self.assertIn("unpredicted_repin", self.mismatches(lambda r: r.__setitem__("necessary_repin", ["a.py", "spec.json"])))

    def test_the_classifier_takes_the_refusal_status_from_the_record(self):
        mapping = {"a" * 64: "b" * 64}
        request = {"pin": "a" * 64}
        refusal = {"status": "unsupported_profile", "reason_codes": ["profile_spec_mismatch"]}
        self.assertEqual(checks.classify({"status": "ok"}, refusal, request, mapping, set(), {"profile_spec_mismatch"}, ("unsupported_profile",)), "pin_refused")
        self.assertEqual(checks.classify({"status": "ok"}, refusal, request, mapping, set(), {"profile_spec_mismatch"}), "changed")       # 既定は P0 の記録と同じ invalid_input
        self.assertEqual(checks.classify({"status": "ok"}, {"status": "invalid_input", "reason_codes": ["profile_spec_mismatch"]}, request, mapping,
                                         set(), {"profile_spec_mismatch"}, ("unsupported_profile",)), "changed")


@unittest.skipUnless(HISTORY, "版の記録、または履歴の旧版・新版のコミットがない")
class QuantityVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = checks.regenerated_report(RECORD)

    def test_the_record_agrees_with_the_measurement(self):
        self.assertEqual(checks.regenerated_mismatches(RECORD, self.report), [])

    def test_the_record_declares_the_revision_of_the_design(self):
        self.assertEqual(RECORD["schema_version"], "p2-version-record-draft-2")
        self.assertFalse(RECORD["independent_review"])
        kinds = {c["kind"]: c for c in RECORD["declared_changes"]}
        self.assertEqual(kinds["added_unit"]["unit"], "u_hundred")
        self.assertEqual((kinds["changed_value"]["unit"], kinds["changed_value"]["from_scale"], kinds["changed_value"]["to_scale"]), ("u_third", [1, 3], [2, 3]))
        self.assertEqual(sorted(kinds["changed_value"]["inputs"]), sorted(CHANGED))
        self.assertEqual(kinds["added_unit"]["added_inputs"], ["p2-quantity/q25.json"])

    def test_the_old_version_is_kept_and_each_version_reproduces_under_its_own_contract(self):
        """V1・V2：旧版のコミットは新版の祖先で、旧版・新版とも自分の木で統合評価が合格し、記録した分母・hash を再現する。"""
        for side in ("from", "to"):
            self.assertTrue(self.report["reproduction"][side]["passed"], side)
            self.assertEqual(self.report["reproduction"][side], RECORD[side]["evaluation"], side)
        self.assertNotEqual(self.report["reproduction"]["from"]["bundle_sha256"], self.report["reproduction"]["to"]["bundle_sha256"])

    def test_old_inputs_are_never_silently_reinterpreted(self):
        """V4：旧入力を新版へそのまま渡すと、同一、または宣言した拒否のどちらか。それ以外 0。"""
        found = self.report["old_inputs_without_regeneration"]
        self.assertEqual(found["changed"], [])
        self.assertEqual(len(found["identical"]) + len(found["pin_refused"]), self.report["inputs"]["old"])
        self.assertGreater(len(found["pin_refused"]), self.report["inputs"]["old"] // 2)

    def test_regenerated_inputs_differ_from_the_old_ones_only_by_the_declared_changes(self):
        """V5・V6（VR-1）：同じ ID の入力は、hash の値を除いて要求が同一で、期待と結果は宣言した6件だけが違い、違う経路は宣言の範囲に限る。"""
        self.assertEqual(self.report["request_changed"], [])
        self.assertEqual(sorted(self.report["expectation_changed"]), sorted(CHANGED))
        self.assertEqual(sorted(self.report["result_differences"]), sorted(CHANGED))
        for paths in self.report["result_differences"].values():
            self.assertTrue(all(path.startswith("/results[]") for path in paths), paths)
        self.assertEqual(self.report["steps_changed"], [])
        self.assertEqual(self.report["inputs"]["added"], ["p2-quantity/q25.json"])
        self.assertEqual(self.report["inputs"]["removed"], [])
        self.assertEqual((self.report["inputs"]["old"], self.report["inputs"]["new"]), (682, 683))

    def test_a_new_unit_is_unknown_to_the_old_version(self):
        """V8：新版で追加した単位を使う入力を旧版の木へ渡すと、旧版は未知の単位で行を止める（旧い pin を付けた場合）。新しい pin のままなら pin で拒否される。"""
        old_pin = self.report["forward"]["p2-quantity/q25.json#old-pin"]
        self.assertEqual((old_pin["status"], old_pin["row_reasons"]), ("ok", [["unknown_unit"]]))
        new_pin = self.report["forward"]["p2-quantity/q25.json#new-pin"]
        self.assertEqual((new_pin["status"], new_pin["reason_codes"]), ("unsupported_profile", ["profile_spec_mismatch"]))

    def test_substituting_pins_cannot_repin_inputs_that_carry_content_bound_hashes(self):
        """R1：旧い pin を新しい値へ置換しても、確認が拘束する内容の hash を持つ系列の入力は受理されない。"""
        content_bound = {n: s for n, s in self.report["substituted"].items() if not n.startswith(tuple(RECORD["pure_pin_suites"]))}
        self.assertTrue(content_bound)
        self.assertNotIn("ok", content_bound.values())
        pure = {n: s for n, s in self.report["substituted"].items() if n.startswith(tuple(RECORD["pure_pin_suites"]))}
        self.assertTrue(pure)
        self.assertEqual(set(pure.values()), {"ok"})                         # pin だけの入力は置換で足りる（対照）

    def test_the_enumeration_from_the_declarations_undercounts_the_repin_exactly_as_predicted(self):
        """V7（Z5）：列挙した範囲は、実際に再固定が要った実体のうち、予測した不足の分だけ小さい。"""
        listed = set(self.report["affected"]["regenerate"]) | set(RECORD["intended_changes"]) | {self.report["affected"]["lock"]}
        necessary = set(self.report["necessary_repin"])
        unpredicted = sorted(necessary - listed)
        self.assertEqual(unpredicted, sorted(RECORD["measured"]["unpredicted_repin"]))
        # 文書54の予測（不足は display.py ほか7件と索引）との差：生成器の複製が予測外、索引は直接の埋め込みではなかった（文書55）
        deviation = RECORD["measured"]["prediction_deviation"]
        self.assertEqual(deviation["missed"], sorted(set(unpredicted) - set(RECORD["predicted"]["undercount"])))
        self.assertEqual(deviation["wrong"], sorted(set(RECORD["predicted"]["undercount"]) - set(unpredicted)))
        self.assertEqual(deviation, {"missed": ["scripts/research/p2/gen_temporal_measurement_fixtures.py"], "wrong": ["extensions/index.json"]})
        self.assertEqual(self.report["affected"]["extensions"], sorted(RECORD["predicted"]["extensions"]))
        for path in necessary:
            self.assertIn(path, self.report["changed_files"])                  # 再固定が要った実体は、実際に更新されている
        self.assertEqual(self.report["pins_changed"], sorted(p["file"] for p in RECORD["pins"]))

    def test_the_cost_of_the_revision_is_recorded(self):
        self.assertEqual(len(self.report["changed_files"]), RECORD["measured"]["changed_files"])


class RecordSyntaxTests(unittest.TestCase):
    @unittest.skipUnless(RECORD is not None, "版の記録がまだない")
    def test_the_record_has_the_declared_fields(self):
        self.assertEqual(set(RECORD), {"schema_version", "id", "status", "independent_review", "note", "from", "to", "extensions", "suites", "pins",
                                       "pin_refusals", "pure_pin_suites", "intended_changes", "predicted", "declared_changes", "measured"})


if __name__ == "__main__":
    unittest.main()
