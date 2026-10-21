"""P2-d：版を上げる手順の実演（X11）。p0-draft-1 → p0-draft-2。

旧版のコミットを git の履歴から取り出し、(1) 旧版は旧版の契約で再現できる、(2) 旧入力は新版で黙って再解釈されない、
(3) hash を再固定しただけの旧入力は旧版の期待を満たす、(4) 差は宣言した変更だけ、を確かめる。
git の履歴に旧版がない環境（浅い clone など）では、比較の部分は行わず、記録の構造の検査だけを行う。
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))

import p2_checks as checks

RECORD_PATH = ROOT / "examples/p2-versions/p0-draft-1-to-draft-2.json"
RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
HISTORY = all(checks.has_commit(RECORD[side]["commit"]) for side in ("from", "to"))
KINDS = {"added_field", "changed_value", "not_observed"}


class VersionRecordTests(unittest.TestCase):
    """履歴を要しない検査：記録の構造と、宣言の根拠が実在すること。"""

    def test_the_record_is_an_author_draft_with_the_declared_shape(self):
        self.assertEqual(RECORD["schema_version"], "p2-version-record-draft-1")
        self.assertFalse(RECORD["independent_review"])
        self.assertEqual(set(RECORD), {"schema_version", "id", "status", "independent_review", "note", "from", "to", "suites",
                                       "pins_changed", "pin_refusal_codes", "declared_changes", "measured"})
        for side in ("from", "to"):
            self.assertRegex(RECORD[side]["commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(set(RECORD[side]["evaluation"]), {"passed", "p1", "p0", "bundle_sha256", "manifest_sha256"})
        self.assertNotEqual(RECORD["from"]["commit"], RECORD["to"]["commit"])

    def test_every_change_is_declared_with_a_kind_and_a_basis(self):
        ids = [c["id"] for c in RECORD["declared_changes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for change in RECORD["declared_changes"]:
            self.assertIn(change["kind"], KINDS, change["id"])
            self.assertTrue(change["description"].strip(), change["id"])
            self.assertIn("inputs", change)
            if change["kind"] == "changed_value":
                self.assertTrue(change["inputs"], change["id"])         # 値が変わると宣言するなら、観測される入力を挙げる
            if change["kind"] == "not_observed":
                self.assertEqual(change["inputs"], [], change["id"])    # 旧入力で観測されないと宣言するなら、入力は挙げない
                self.assertTrue((ROOT / change["evidence"].split("::")[0]).is_file(), change["id"])   # 代わりの根拠が実在する

    def test_declared_inputs_are_old_fixtures(self):
        names = {f"{suite}/{entry['path']}" for suite in RECORD["suites"]
                 for entry in json.loads((ROOT / "examples" / suite / "manifest.json").read_text(encoding="utf-8"))["files"]}
        for change in RECORD["declared_changes"]:
            for name in change["inputs"]:
                self.assertIn(name, names, (change["id"], name))

    def test_the_pins_named_in_the_record_are_the_ones_the_handover_code_holds(self):
        self.assertEqual(sorted(RECORD["pins_changed"]), sorted(checks.PIN_NAMES))
        self.assertEqual(set(checks.pin_values(ROOT)), set(checks.PIN_NAMES))

    @unittest.skipUnless(HISTORY, "git の履歴に旧版のコミットがない")
    def test_the_versions_are_ordered_in_the_history_and_the_old_version_is_kept(self):
        def is_ancestor(a, b):
            return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT).returncode == 0
        self.assertTrue(is_ancestor(RECORD["from"]["commit"], RECORD["to"]["commit"]))
        self.assertTrue(is_ancestor(RECORD["to"]["commit"], "HEAD"))           # 旧版は消されず、現在の履歴の祖先として残る


class ClassifyTests(unittest.TestCase):
    """旧入力を新版で実行した結果の分類。黙った再解釈を identical や pin_refused に紛れ込ませない。"""

    OLD_PIN, NEW_PIN = "a" * 64, "b" * 64
    MAPPING = {OLD_PIN: NEW_PIN}
    DROPPED = {"certifier"}
    CODES = {"profile_spec_mismatch"}

    def classify(self, old, new, request=None):
        return checks.classify(old, new, request if request is not None else {"pin": self.OLD_PIN}, self.MAPPING, self.DROPPED, self.CODES)

    def test_a_result_that_differs_only_in_a_declared_added_field_is_identical(self):
        self.assertEqual(self.classify({"status": "ok", "x": 1}, {"status": "ok", "x": 1, "certifier": "c"}), "identical")

    def test_a_result_that_differs_only_in_a_hash_value_is_identical(self):
        self.assertEqual(self.classify({"status": "ok", "h": self.OLD_PIN}, {"status": "ok", "h": self.NEW_PIN}), "identical")

    def test_a_refusal_for_a_changed_pin_is_a_pin_refusal_only_when_the_input_embeds_the_old_pin(self):
        refusal = {"status": "invalid_input", "reason_codes": ["profile_spec_mismatch"]}
        self.assertEqual(self.classify({"status": "ok"}, refusal), "pin_refused")
        self.assertEqual(self.classify({"status": "ok"}, refusal, request={"pin": "c" * 64}), "changed")

    def test_only_an_input_refusal_counts_as_a_pin_refusal(self):
        self.assertEqual(self.classify({"status": "ok"}, {"status": "unsupported_profile", "reason_codes": ["profile_spec_mismatch"]}), "changed")

    def test_the_same_refusal_code_under_another_reason_is_not_a_pin_refusal(self):
        self.assertEqual(self.classify({"status": "ok"}, {"status": "invalid_input", "reason_codes": ["review_precedes_assertion"]}), "changed")

    def test_a_different_valid_answer_is_a_silent_change(self):
        self.assertEqual(self.classify({"status": "ok", "x": 1}, {"status": "ok", "x": 2}), "changed")
        self.assertEqual(self.classify({"status": "ok", "x": 1}, {"status": "unsupported_profile"}), "changed")

    def test_dropping_a_field_that_was_not_declared_is_a_change(self):
        self.assertEqual(self.classify({"status": "ok", "x": 1, "y": 2}, {"status": "ok", "x": 1}), "changed")

    def test_contains_key_finds_a_field_at_any_depth(self):
        self.assertTrue(checks.contains_key({"a": [{"b": {"certifier": 1}}]}, "certifier"))
        self.assertFalse(checks.contains_key({"a": [{"b": 1}], "certifierx": 2}, "certifier"))

    def test_normalize_sees_through_hashes_inside_a_base64_encoded_json(self):
        import base64

        def wrap(h, text="0.33"):
            return {"bytes": base64.b64encode(json.dumps({"x": h, "text": text}).encode()).decode()}
        self.assertEqual(checks.normalize(wrap("a" * 64), set()), checks.normalize(wrap("b" * 64), set()))
        self.assertNotEqual(checks.normalize(wrap("a" * 64), set()), checks.normalize(wrap("a" * 64, "0.67"), set()))      # 中身の違いは残る
        self.assertEqual(checks.normalize("AAAAAAAAAAAAAAAAAAAAAAAA", set()), "AAAAAAAAAAAAAAAAAAAAAAAA")                  # JSON でない base64 風の文字列はそのまま
        self.assertEqual(checks.normalize("ordinary-text", set()), "ordinary-text")

    def test_repin_rewrites_only_the_old_values_and_normalize_ignores_hash_values(self):
        self.assertEqual(checks.repin({"a": [self.OLD_PIN, "other"], "b": 1}, self.MAPPING), {"a": [self.NEW_PIN, "other"], "b": 1})
        self.assertEqual(checks.normalize({"a": self.OLD_PIN, "b": "xyz", "certifier": 1}, self.DROPPED), {"a": "<sha256>", "b": "xyz"})
        self.assertEqual(checks.diff_paths({"a": [{"b": 1}], "c": 1}, {"a": [{"b": 2}], "d": 1}), ["/a[]/b", "/c", "/d"])


def compare_versions():
    import importlib.util
    spec = importlib.util.spec_from_file_location("compare_versions", ROOT / "scripts/research/compare-versions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompareCommandTests(unittest.TestCase):
    """比較器の終了コード：0＝記録と測定が一致、1＝食い違い、2＝履歴に旧版がない（比較できない）。"""

    def run_main(self, has_commit, problems):
        module = compare_versions()
        report = {"inputs": 0, "reproduction": {}, "pins_changed": []}
        with patch.object(checks, "has_commit", return_value=has_commit), patch.object(checks, "version_report", return_value=report), \
                patch.object(checks, "record_mismatches", return_value=problems), patch("builtins.print") as printed:
            code = module.main(["--no-current"])
        return code, json.loads(printed.call_args[0][0])

    def test_the_exit_code_and_the_summary(self):
        self.assertEqual(self.run_main(True, [])[0], 0)
        code, summary = self.run_main(True, ["to:undeclared_or_missing_change"])
        self.assertEqual((code, summary["passed"], summary["problems"]), (1, False, ["to:undeclared_or_missing_change"]))
        code, summary = self.run_main(False, [])
        self.assertEqual((code, summary["passed"]), (2, False))


OLD_PINS = {"HANDOVER_SPEC_SHA256": "1" * 64, "P0_SPEC_SHA256": "2" * 64, "P0_RUNTIME_SHA256": "3" * 64}
NEW_PINS = {"HANDOVER_SPEC_SHA256": "4" * 64, "P0_SPEC_SHA256": "5" * 64, "P0_RUNTIME_SHA256": "3" * 64}
FAKE_NAMES = ("plain", "pin", "chg", "decl")


class VersionReportLogicTests(unittest.TestCase):
    """履歴を要しない検査：偽の木で version_report の配線を確かめる。
    plain＝宣言した付加だけが違う／pin＝旧い hash を埋め込み新版は拒否／chg＝宣言のない値の変更／decl＝宣言した値の変更。"""

    def fake_record(self, declared=("decl",)):
        changes = [{"id": "F-1", "kind": "added_field", "path": "certifier", "description": "x", "inputs": []}]
        for name in declared:
            changes.append({"id": f"F-{name}", "kind": "changed_value", "path": "/x" if name == "decl" else "/v", "description": "x", "inputs": [f"s/{name}.json"]})
        return {"suites": ["s"], "pin_refusal_codes": ["profile_spec_mismatch"], "declared_changes": changes,
                "from": {"commit": "A", "evaluation": FAKE_EVALUATION["from"]}, "to": {"commit": "B", "evaluation": FAKE_EVALUATION["to"]},
                "pins_changed": ["HANDOVER_SPEC_SHA256", "P0_SPEC_SHA256"]}

    @staticmethod
    def fake_extract(commit, destination):
        root = Path(destination)
        (root / "examples/s").mkdir(parents=True)
        (root / "src/med_dsl").mkdir(parents=True)
        pins = OLD_PINS if root.name == "from" else NEW_PINS
        (root / "src/med_dsl/handover.py").write_text("".join(f'{name} = "{value}"\n' for name, value in pins.items()), encoding="utf-8")
        (root / "examples/s/manifest.json").write_text(json.dumps({"files": [{"path": f"{n}.json"} for n in FAKE_NAMES]}), encoding="utf-8")
        for name in FAKE_NAMES:
            request = {"id": name, **({"pin": OLD_PINS["HANDOVER_SPEC_SHA256"]} if name == "pin" else {})}
            (root / f"examples/s/{name}.json").write_text(json.dumps({"request": request, "expected": {"checks": [{"path": ["v"], "equals": 1}]}}), encoding="utf-8")
        return root

    @staticmethod
    def fake_evaluate(tree, requests):
        side = "from" if Path(tree).name == "from" else "new"
        out = {}
        for name, request in requests.items():
            result = {"status": "ok", "v": 1, "x": 0, "id": request["id"]}
            if side == "new":
                result["certifier"] = "c"
                if request.get("pin") == OLD_PINS["HANDOVER_SPEC_SHA256"]:
                    result = {"status": "invalid_input", "reason_codes": ["profile_spec_mismatch"]}
                elif request["id"] == "chg":
                    result["v"] = 2
                elif request["id"] == "decl":
                    result["x"] = 1
            out[name] = result
        return out

    def report(self, record):
        with patch.object(checks, "extract", self.fake_extract), patch.object(checks, "evaluate_tree", self.fake_evaluate), \
                patch.object(checks, "tree_evaluation", lambda tree: FAKE_EVALUATION["from" if Path(tree).name == "from" else "to"]):
            return checks.version_report(record, current=True)

    def test_the_four_kinds_of_input_are_classified_and_the_pins_found(self):
        report = self.report(self.fake_record())
        self.assertEqual(report["pins_changed"], ["HANDOVER_SPEC_SHA256", "P0_SPEC_SHA256"])
        self.assertEqual(report["inputs"], 4)
        for side in ("to", "current"):
            part = report[side]
            self.assertEqual(part["old_inputs_without_repin"], {"identical": ["s/plain.json"], "pin_refused": ["s/pin.json"], "changed": ["s/chg.json", "s/decl.json"]})
            self.assertEqual(part["repinned"]["identical"], ["s/pin.json", "s/plain.json"])
            self.assertEqual(part["repinned"]["changed"], {"s/chg.json": ["/v"], "s/decl.json": ["/x"]})
            self.assertEqual(part["repinned"]["failing_old_expectations"], ["s/chg.json"])
            self.assertEqual(part["carry_added_field"], ["s/chg.json", "s/decl.json", "s/pin.json", "s/plain.json"])

    def measured(self, record, report):
        part = report["to"]
        record["measured"] = {"old_inputs_without_repin": {k: len(v) for k, v in part["old_inputs_without_repin"].items()},
                              "repinned": {"identical": len(part["repinned"]["identical"]), "failing_old_expectations": len(part["repinned"]["failing_old_expectations"])},
                              "carry_added_field": len(part["carry_added_field"])}

    def test_an_undeclared_change_is_reported_and_declaring_it_clears_the_report(self):
        record = self.fake_record(declared=("decl",))
        report = self.report(record)
        self.measured(record, report)
        found = checks.record_mismatches(record, report)
        self.assertIn("to:undeclared_or_missing_change", found)
        self.assertIn("to:undeclared_change_without_repin", found)
        record = self.fake_record(declared=("decl", "chg"))
        report = self.report(record)
        self.measured(record, report)
        self.assertEqual(checks.record_mismatches(record, report), [])

    def test_a_declaration_of_a_change_that_does_not_occur_is_reported(self):
        record = self.fake_record(declared=("decl", "chg"))
        record["declared_changes"].append({"id": "F-x", "kind": "changed_value", "path": "/y", "description": "x", "inputs": ["s/plain.json"]})
        report = self.report(record)
        self.measured(record, report)
        self.assertIn("to:undeclared_or_missing_change", checks.record_mismatches(record, report))

    def test_the_current_tree_is_compared_with_the_new_version_and_a_difference_there_is_reported(self):
        record = self.fake_record(declared=("decl", "chg"))
        report = self.report(record)
        self.measured(record, report)
        report["current"]["old_inputs_without_repin"]["identical"].remove("s/plain.json")
        report["current"]["old_inputs_without_repin"]["changed"].append("s/plain.json")
        self.assertIn("current:classification_counts", checks.record_mismatches(record, report))
        self.assertIn("current:undeclared_change_without_repin", checks.record_mismatches(record, report))


FAKE_EVALUATION = {"from": {"passed": True, "p1": [1, 1, 1], "p0": [1, 1], "bundle_sha256": "a" * 64, "manifest_sha256": "b" * 64},
                   "to": {"passed": True, "p1": [1, 1, 1], "p0": [1, 1], "bundle_sha256": "c" * 64, "manifest_sha256": "d" * 64}}


@unittest.skipUnless(HISTORY, "git の履歴に旧版のコミットがない")
class VersionProcedureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = checks.version_report(RECORD, current=True)

    def test_the_record_agrees_with_the_measurement(self):
        self.assertEqual(checks.record_mismatches(RECORD, self.report), [])

    def test_each_version_reproduces_under_its_own_contract(self):
        """V2：旧版・新版とも、自分の木で自分の固定した評価を再現する（P1 20 条件・80 JSON・417 必須パス、P0 37 JSON・221 必須パス）。"""
        for side in ("from", "to"):
            got = self.report["reproduction"][side]
            self.assertTrue(got["passed"], side)
            self.assertEqual((got["p1"], got["p0"]), ([20, 80, 417], [37, 221]), side)
        self.assertNotEqual(self.report["reproduction"]["from"]["bundle_sha256"], self.report["reproduction"]["to"]["bundle_sha256"])

    def test_every_old_input_falls_into_exactly_one_class(self):
        for side in ("to", "current"):
            part = self.report[side]["old_inputs_without_repin"]
            names = sorted(sum(part.values(), []))
            self.assertEqual(len(names), self.report["inputs"], side)
            self.assertEqual(len(names), len(set(names)), side)

    def test_old_inputs_are_never_silently_reinterpreted(self):
        """V4：変わった旧入力は、宣言した変更に属するものだけ。それ以外は、同一か、固定した hash の変更による拒否。"""
        declared = {n for c in RECORD["declared_changes"] for n in c["inputs"]}
        for side in ("to", "current"):
            part = self.report[side]["old_inputs_without_repin"]
            self.assertEqual(set(part["changed"]), declared, side)
            self.assertEqual(len(part["pin_refused"]), 27, side)       # 拒否は、旧い hash を埋め込んだ入力に限る（分類の条件）

    def test_repinned_old_inputs_satisfy_their_old_expectations(self):
        """V5：hash を再固定した旧入力は、旧版で手で指定した期待を、すべて満たす。違いは宣言した経路だけ。"""
        for side in ("to", "current"):
            part = self.report[side]["repinned"]
            self.assertEqual(part["failing_old_expectations"], [], side)
            self.assertEqual(set(part["changed"]), {"p1-a/unknown-capability-pending.json", "p1-a/unknown-capability.json"}, side)
            for paths in part["changed"].values():
                self.assertEqual(paths, ["/incomplete"], side)

    def test_the_declared_added_field_is_carried_by_the_measured_number_of_repinned_results(self):
        for side in ("to", "current"):
            self.assertEqual(len(self.report[side]["carry_added_field"]), RECORD["measured"]["carry_added_field"], side)
            self.assertTrue(set(self.report[side]["carry_added_field"]) <= set(self.report[side]["repinned"]["identical"]) | set(self.report[side]["repinned"]["changed"]), side)

    def test_the_current_implementation_treats_old_inputs_as_the_new_version_does(self):
        self.assertEqual(self.report["current"], self.report["to"])

    # ---- 比較器の検出力：記録を壊すと食い違いとして報告される ----
    def mismatches(self, mutate):
        record = deepcopy(RECORD)
        mutate(record)
        return checks.record_mismatches(record, self.report)

    def test_removing_a_declared_change_is_reported(self):
        found = self.mismatches(lambda r: r.__setitem__("declared_changes", [c for c in r["declared_changes"] if c["id"] != "V-2"]))
        self.assertIn("to:undeclared_or_missing_change", found)
        self.assertIn("to:undeclared_change_without_repin", found)

    def test_declaring_a_change_that_is_not_observed_as_observed_is_reported(self):
        def mutate(record):
            record["declared_changes"].append({"id": "V-9", "kind": "changed_value", "path": "/answer", "description": "x", "inputs": ["p0/assertion-revision.json"]})
        self.assertIn("to:undeclared_or_missing_change", self.mismatches(mutate))

    def test_a_wrong_measured_count_is_reported(self):
        self.assertIn("to:classification_counts", self.mismatches(lambda r: r["measured"]["old_inputs_without_repin"].__setitem__("identical", 89)))
        self.assertIn("to:repinned_counts", self.mismatches(lambda r: r["measured"]["repinned"].__setitem__("identical", 114)))
        self.assertIn("to:added_field_count", self.mismatches(lambda r: r["measured"].__setitem__("carry_added_field", 36)))

    def test_a_wrong_reproduction_or_pin_list_is_reported(self):
        self.assertIn("reproduction_from", self.mismatches(lambda r: r["from"]["evaluation"].__setitem__("bundle_sha256", "0" * 64)))
        self.assertIn("reproduction_to", self.mismatches(lambda r: r["to"]["evaluation"].__setitem__("p0", [37, 220])))
        self.assertIn("pins_changed", self.mismatches(lambda r: r.__setitem__("pins_changed", ["P0_SPEC_SHA256"])))


if __name__ == "__main__":
    unittest.main()
