"""P2-r：記録に観察者を足す版の更新（P2-i：draft-2 → draft-3、依存する5拡張の再固定）。

版の記録（examples/p2-versions/p2-temporal-measurement-draft-2-to-draft-3.json）に沿って、履歴から旧版を取り出して比べる（版の手順 V1〜V8）。
記録は、新版の実装を含むコミットの後に追加するので、記録がない、または履歴に旧版・新版のコミットがない環境では、履歴を要する部分は行わない。
比較器の判定の検出力（履歴を要しない部分）は test_quantity_version.py で検査している。
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/research"), str(ROOT / "scripts/research/p2")]

import p2_checks as checks
import make_observer_version_record as maker

RECORD_PATH = ROOT / "examples/p2-versions/p2-temporal-measurement-draft-2-to-draft-3.json"
RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8")) if RECORD_PATH.is_file() else None
HISTORY = RECORD is not None and all(checks.has_commit(RECORD[side]["commit"]) for side in ("from", "to"))
ADDED = sorted(name for names in maker.ADDED.values() for name in names)


@unittest.skipUnless(HISTORY, "版の記録、または履歴の旧版・新版のコミットがない")
class ObserverVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = checks.regenerated_report(RECORD)

    def test_the_record_agrees_with_the_measurement(self):
        self.assertEqual(checks.regenerated_mismatches(RECORD, self.report), [])

    def test_the_record_declares_the_change_without_changing_the_record_format(self):
        """Y9：書式 p2-version-record-draft-2 を変えずに、任意の項目の追加を宣言できる。"""
        self.assertEqual(RECORD["schema_version"], "p2-version-record-draft-2")
        self.assertFalse(RECORD["independent_review"])
        self.assertEqual([c["kind"] for c in RECORD["declared_changes"]], ["added_field", "added_field", "added_field", "repinned"])
        self.assertEqual(sorted(n for c in RECORD["declared_changes"] for n in c.get("added_inputs", [])), ADDED)
        self.assertEqual((RECORD["from"]["version"], RECORD["to"]["version"]), ("draft-2", "draft-3"))
        self.assertEqual(RECORD["pins"], [{"file": f"src/med_dsl/{m}.py", "name": "SPEC_SHA256"} for m in maker.MODULES])

    def test_the_old_version_is_kept_and_each_version_reproduces_under_its_own_contract(self):
        """V1・V2（Y1）：旧版のコミットは新版の祖先で、旧版・新版とも自分の木で統合評価が合格し、記録した分母・hash を再現する。"""
        for side in ("from", "to"):
            self.assertTrue(self.report["reproduction"][side]["passed"], side)
            self.assertEqual(self.report["reproduction"][side], RECORD[side]["evaluation"], side)
        self.assertEqual(self.report["reproduction"]["from"]["registered"], 23)
        self.assertNotEqual(self.report["reproduction"]["from"]["bundle_sha256"], self.report["reproduction"]["to"]["bundle_sha256"])

    def test_old_inputs_are_never_silently_reinterpreted(self):
        """V4（Y2）：旧入力を新版へそのまま渡すと、pin を持つ入力は pin で拒否され、pin に届く前に同じ結果になる入力は同一。黙った再解釈は 0。
        予測は「全て pin で拒否」だったが、実測は拒否678・同一59（pin に届く前に拒否される静的な負例など）。"""
        found = self.report["old_inputs_without_regeneration"]
        self.assertEqual(found["changed"], [])
        self.assertEqual(len(found["identical"]) + len(found["pin_refused"]), self.report["inputs"]["old"])
        self.assertGreater(len(found["pin_refused"]), self.report["inputs"]["old"] * 9 // 10)

    def test_regenerated_inputs_differ_from_the_old_ones_only_by_the_declared_additions(self):
        """V5・V6（Y3）：同じ ID の入力は、hash の値を除いて要求・期待・結果が同一。違いは宣言した追加の25件だけ。"""
        self.assertEqual(self.report["request_changed"], [])
        self.assertEqual(self.report["expectation_changed"], [])
        self.assertEqual(self.report["result_differences"], {})
        self.assertEqual(self.report["steps_changed"], [])
        self.assertEqual(sorted(self.report["inputs"]["added"]), ADDED)
        self.assertEqual(self.report["inputs"]["removed"], [])
        self.assertEqual(self.report["inputs"]["new"] - self.report["inputs"]["old"], len(ADDED))

    def test_a_new_field_is_refused_by_the_old_version_not_ignored(self):
        """V8（Y4）：新版で追加した項目を使う入力を旧版の木へ渡すと、新しい pin のままなら pin で拒否され、旧い pin に替えても黙って無視されず拒否される。"""
        for name in ADDED:
            old_pin = self.report["forward"][name + "#old-pin"]
            new_pin = self.report["forward"][name + "#new-pin"]
            self.assertEqual((new_pin["status"], new_pin["reason_codes"]), ("unsupported_profile", ["profile_spec_mismatch"]), name)
            self.assertEqual(old_pin["status"], "invalid_input", name)
            self.assertNotEqual(old_pin["status"], "ok", name)

    def test_substituting_pins_repins_only_the_inputs_that_carry_no_content_bound_hash(self):
        """R1（F27）：旧い pin を新しい値へ置換すると、確認の内容の hash を持つ台帳の入力（P2-i・P2-j・P2-m）は受理されないが、
        操作の列から台帳を組み立てる系列（P2-o・P2-p・P2-q）の入力は hash を持たないので、置換だけで再固定できる。"""
        pure = tuple(RECORD["pure_pin_suites"])
        self.assertEqual(sorted(pure), ["p2-grounding", "p2-library", "p2-observation"])
        bound = {n: s for n, s in self.report["substituted"].items() if not n.startswith(pure)}
        self.assertTrue(bound)
        self.assertNotIn("ok", bound.values())
        free = {n: s for n, s in self.report["substituted"].items() if n.startswith(pure)}
        self.assertTrue(free)
        self.assertEqual(set(free.values()), {"ok"})

    def test_the_enumeration_from_the_declarations_matches_the_prediction(self):
        """V7（Y5）：6拡張を過不足なく列挙する。実際に再固定が要った実体と、列挙の差（過小・過大）を測定値に固定している。
        過小は予測どおり（宣言6件と、仕様の hash を定数に持つが宣言の embedded_in にないモジュール3件）。過大は予測外で118件。"""
        self.assertEqual(self.report["affected"]["extensions"], sorted(RECORD["predicted"]["extensions"]))
        self.assertEqual(RECORD["measured"]["prediction_deviation"], {"missed": [], "wrong": []})
        listed = set(self.report["affected"]["regenerate"]) | set(RECORD["intended_changes"]) | {self.report["affected"]["lock"]}
        necessary = set(self.report["necessary_repin"])
        self.assertEqual(sorted(necessary - listed), sorted(RECORD["measured"]["unpredicted_repin"]))
        self.assertEqual(len(set(self.report["affected"]["regenerate"]) - necessary), RECORD["measured"]["listed_but_unnecessary"])
        for path in necessary:
            self.assertIn(path, self.report["changed_files"])
        self.assertEqual(self.report["pins_changed"], sorted(p["file"] for p in RECORD["pins"]))

    def test_the_cost_of_the_change_is_recorded(self):
        self.assertEqual(len(self.report["changed_files"]), RECORD["measured"]["changed_files"])


if __name__ == "__main__":
    unittest.main()
