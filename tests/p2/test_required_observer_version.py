"""P2-s：記録の観察者を必須にする版の更新（P2-i：draft-3 → draft-4、依存する5拡張の再固定。旧入力を拒否する）。

履歴を要しない部分（比較器が、必須にした項目の宣言 `required_field` を読む）と、版の記録に沿って履歴から旧版を取り出して比べる部分（V1〜V8）に分ける。
記録（examples/p2-versions/p2-temporal-measurement-draft-3-to-draft-4.json）は、新版の実装を含むコミットの後に追加するので、記録がない、または履歴に
旧版・新版のコミットがない環境では、履歴を要する部分は行わない。
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/research"), str(ROOT / "scripts/research/p2")]

import p2_checks as checks
import make_required_observer_version_record as maker

RECORD_PATH = ROOT / "examples/p2-versions/p2-temporal-measurement-draft-3-to-draft-4.json"
RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8")) if RECORD_PATH.is_file() else None
HISTORY = RECORD is not None and all(checks.has_commit(RECORD[side]["commit"]) for side in ("from", "to"))
ADDED = sorted(name for names in maker.ADDED.values() for name in names)


def synthetic():
    """比較器の単位テスト用の、全てが宣言どおりの記録と報告（必須にした項目 observer）。"""
    record = {"from": {"evaluation": {"passed": True}}, "to": {"evaluation": {"passed": True}},
              "pins": [{"file": "a.py", "name": "X"}], "pin_refusals": [{"status": "unsupported_profile", "code": "profile_spec_mismatch"}],
              "intended_changes": ["spec.json"], "pure_pin_suites": [],
              "predicted": {"extensions": ["e1"], "regenerate": ["a.py"]},
              "declared_changes": [{"id": "D-1", "kind": "required_field", "inputs": ["s1/a.json"], "added_inputs": ["s1/new.json"],
                                    "request_leaf": "observer", "result_leaf": "record_observer",
                                    "substitution_refusal": {"status": "invalid_input", "code": "missing_field"}}],
              "measured": {"old_inputs_without_regeneration": {"identical": 1, "pin_refused": 2, "changed": 0}, "inputs": {"old": 3, "new": 4}, "unpredicted_repin": []}}
    report = {"reproduction": {"from": {"passed": True}, "to": {"passed": True}}, "pins_changed": ["a.py"],
              "inputs": {"old": 3, "new": 4, "added": ["s1/new.json"], "removed": []},
              "old_inputs_without_regeneration": {"identical": ["s1/c.json"], "pin_refused": ["s1/a.json", "s1/b.json"], "changed": []},
              "request_changed": ["s1/a.json", "s1/b.json"], "request_diffs": {"s1/a.json": ["/source/records[]/observer"], "s1/b.json": ["/source/records[]/observer"]},
              "expectation_changed": ["s1/a.json", "s1/b.json"],
              "expectation_diffs": {"s1/a.json": ["[]/equals/x"], "s1/b.json": ["/retained_source/records[]/observer"]},
              "result_differences": {"s1/b.json": ["/results[]/binding_evidence/selected[]/record_observer"]},
              "steps_changed": [], "substituted": {"s1/a.json": "invalid_input", "s1/b.json": "invalid_input"},
              "substituted_reasons": {"s1/a.json": ["missing_field"], "s1/b.json": ["missing_field"]},
              "affected": {"extensions": ["e1"], "regenerate": ["a.py"], "lock": None, "predicted_regenerate": ["a.py"]}, "necessary_repin": ["a.py", "spec.json"]}
    return record, report


class RequiredFieldComparatorTests(unittest.TestCase):
    """履歴を要しない：比較器は、宣言した項目名の追加だけを許し、それ以外の差と、置換した入力の受理を報告する。"""

    def mismatches(self, mutate_report=None, mutate_record=None):
        record, report = synthetic()
        if mutate_record:
            mutate_record(record)
        if mutate_report:
            mutate_report(report)
        return checks.regenerated_mismatches(record, report)

    def test_a_report_that_matches_the_declarations_has_no_mismatch(self):
        self.assertEqual(self.mismatches(), [])

    def test_a_request_difference_outside_the_declared_item_is_reported(self):
        self.assertIn("regenerated_request_changed", self.mismatches(lambda r: r["request_diffs"]["s1/a.json"].append("/source/records[]/certainty")))
        self.assertIn("regenerated_request_changed", self.mismatches(lambda r: r["request_diffs"].pop("s1/a.json")))      # 材料のない差は、許さない

    def test_an_expectation_or_result_difference_outside_the_declared_item_is_reported(self):
        self.assertIn("undeclared_or_missing_expectation_change", self.mismatches(lambda r: r["expectation_diffs"]["s1/b.json"].append("/status")))
        self.assertIn("undeclared_or_missing_expectation_change", self.mismatches(lambda r: r["expectation_diffs"].__setitem__("s1/a.json", ["/retained_source/records[]/observer"])))
        self.assertIn("undeclared_or_missing_result_difference", self.mismatches(lambda r: r["result_differences"]["s1/b.json"].append("/results[]/status")))
        self.assertIn("undeclared_or_missing_result_difference", self.mismatches(lambda r: r["result_differences"].__setitem__("s1/a.json", ["/results[]/status"])))

    def test_a_substituted_input_that_is_accepted_or_refused_for_another_reason_is_reported(self):
        self.assertIn("substitution_not_refused_as_declared", self.mismatches(lambda r: r["substituted"].__setitem__("s1/a.json", "ok")))
        self.assertIn("substitution_not_refused_as_declared", self.mismatches(lambda r: r["substituted_reasons"].__setitem__("s1/a.json", ["invalid_timestamp"])))
        self.assertIn("substitution_repinned_a_content_bound_input", self.mismatches(lambda r: r["substituted"].__setitem__("s1/a.json", "ok")))

    def test_a_record_without_the_declaration_keeps_the_stricter_old_behaviour(self):
        def plain(record):
            record["declared_changes"] = [{"id": "D-1", "kind": "added_field", "inputs": [], "added_inputs": ["s1/new.json"]}]
        found = self.mismatches(None, plain)
        self.assertIn("regenerated_request_changed", found)
        self.assertIn("undeclared_or_missing_result_difference", found)


@unittest.skipUnless(HISTORY, "版の記録、または履歴の旧版・新版のコミットがない")
class RequiredObserverVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = checks.regenerated_report(RECORD)

    def test_the_record_agrees_with_the_measurement(self):
        self.assertEqual(checks.regenerated_mismatches(RECORD, self.report), [])

    def test_the_record_declares_the_change_without_changing_the_record_format(self):
        """S6：書式 p2-version-record-draft-2 のまま、宣言の種類 required_field（要求・結果の項目名と、置換の拒否の理由）で宣言できる。"""
        self.assertEqual(RECORD["schema_version"], "p2-version-record-draft-2")
        self.assertFalse(RECORD["independent_review"])
        self.assertEqual([c["kind"] for c in RECORD["declared_changes"]], ["required_field", "added_field", "repinned"])
        self.assertEqual(sorted(n for c in RECORD["declared_changes"] for n in c.get("added_inputs", [])), ADDED)
        self.assertEqual((RECORD["from"]["version"], RECORD["to"]["version"]), ("draft-3", "draft-4"))

    def test_the_old_version_is_kept_and_each_version_reproduces_under_its_own_contract(self):
        """V1・V2（S1）。"""
        for side in ("from", "to"):
            self.assertTrue(self.report["reproduction"][side]["passed"], side)
            self.assertEqual(self.report["reproduction"][side], RECORD[side]["evaluation"], side)
        self.assertEqual((self.report["reproduction"]["from"]["registered"], self.report["reproduction"]["from"]["obligations"]), (23, 316))

    def test_old_inputs_are_never_silently_reinterpreted(self):
        """V4（S2）：旧入力を新版へそのまま渡すと、pin を持つ入力は pin で拒否され、他は同一。黙った再解釈は 0。"""
        found = self.report["old_inputs_without_regeneration"]
        self.assertEqual(found["changed"], [])
        self.assertEqual(len(found["identical"]) + len(found["pin_refused"]), self.report["inputs"]["old"])
        self.assertGreater(len(found["pin_refused"]), self.report["inputs"]["old"] * 9 // 10)

    def test_a_substituted_old_input_is_refused_for_the_missing_required_field_never_accepted(self):
        """V4′（S3）：旧い pin を新しい値へ置換した入力は、全て invalid_input／missing_field で拒否される。受理 0（P2-r で置換だけで再固定できた3系列も）。"""
        self.assertEqual(len(self.report["substituted"]), 18)                                      # 6系列×先頭3件
        self.assertEqual(set(self.report["substituted"].values()), {"invalid_input"})
        self.assertEqual({tuple(reasons[:1]) for reasons in self.report["substituted_reasons"].values()}, {("missing_field",)})

    def test_migrated_inputs_differ_from_the_old_ones_only_by_the_declared_item(self):
        """V5・V6（S4・S5）：移行した入力（既定で明示の unknown を足した入力）は、要求・期待・結果が、hash の値と宣言した項目の追加を除いて旧入力と同一。
        期待を個別に変えたのは O04 だけ。料金は変わらない。追加は宣言した7件。"""
        leaves = {"observer", "record_observer"}

        def only_leaves(paths):
            return bool(paths) and all(path.rsplit("/", 1)[-1] in leaves for path in paths)
        self.assertTrue(self.report["request_changed"])
        self.assertTrue(all(only_leaves(paths) for paths in self.report["request_diffs"].values()))
        self.assertEqual({n for n, paths in self.report["expectation_diffs"].items() if not only_leaves(paths)}, set(maker.EXPLICIT))
        self.assertTrue(all(only_leaves(paths) for paths in self.report["result_differences"].values()))
        self.assertEqual(self.report["steps_changed"], [])
        self.assertEqual(sorted(self.report["inputs"]["added"]), ADDED)
        self.assertEqual(self.report["inputs"]["removed"], [])

    def test_the_new_inputs_that_state_an_unknown_observer_are_refused_by_the_old_version(self):
        """V8（S9）：新版の入力を旧い pin に替えて旧版（draft-3）へ渡すと、明示の unknown を含む入力は旧版が受理しない（未知の値を黙って受理しない）。
        人・機器の観察者だけの入力は、旧版が受理する（互換の部分集合）。"""
        forward = self.report["forward_old_pin"]
        accepted = sorted(n for n, r in forward.items() if r["status"] == "ok")
        self.assertTrue(accepted)
        self.assertEqual(len(accepted), RECORD["measured"]["forward_to_old_version"]["accepted"])
        refused = [n for n, r in forward.items() if (r["reason_codes"] or [None])[0] == "invalid_observer"]
        self.assertEqual(len(refused), RECORD["measured"]["forward_to_old_version"]["invalid_observer"])
        self.assertGreater(len(refused), len(accepted))
        self.assertNotIn("p2-temporal-measurement/o23.json", accepted)                              # 既定の unknown の入力
        self.assertNotIn("p2-temporal-measurement/o21.json", accepted)                              # 明示の unknown の入力

    def test_the_enumeration_from_the_declarations_matches_the_prediction(self):
        """V7（S8）：6拡張を過不足なく列挙する。過小は P2-r と同じ9件（予測どおり）。"""
        self.assertEqual(self.report["affected"]["extensions"], sorted(RECORD["predicted"]["extensions"]))
        self.assertEqual(RECORD["measured"]["prediction_deviation"], {"missed": [], "wrong": []})
        listed = set(self.report["affected"]["regenerate"]) | set(RECORD["intended_changes"]) | {self.report["affected"]["lock"]}
        necessary = set(self.report["necessary_repin"])
        self.assertEqual(sorted(necessary - listed), sorted(RECORD["measured"]["unpredicted_repin"]))
        for path in necessary:
            self.assertIn(path, self.report["changed_files"])
        self.assertEqual(self.report["pins_changed"], sorted(p["file"] for p in RECORD["pins"]))

    def test_the_cost_of_the_change_is_recorded(self):
        self.assertEqual(len(self.report["changed_files"]), RECORD["measured"]["changed_files"])


if __name__ == "__main__":
    unittest.main()
