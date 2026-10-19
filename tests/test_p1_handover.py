"""反例と条件付き認定、合成の端点、射影、再実行可用性の境界。"""

import base64
from copy import deepcopy
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.events import _restore, _source
from med_dsl.handover import endpoint, scope_hashes
from med_dsl.model import Budget
from med_dsl.reference import truth
from med_dsl.validation import canonical_bytes, digest


def fixture(name="event-renaming-chain"):
    return json.loads((ROOT / "examples/p1-c" / (name + ".json")).read_text())


def request(name="event-renaming-chain"):
    return fixture(name)["request"]


def seal(data):
    # 変更した入力の宣言を更新する補助。期待結果は各テストで別に指定する。
    middle, packages = _restore(data["intermediate"])
    final, last_packages = _restore(data["target"])
    ordered = _source(data["source"], data["relation_ref"])
    old_scope, new_scope = scope_hashes(data["views"], data["queries"], data["relation_ref"])
    a = endpoint(data["source"], data["source"], ordered)
    b = endpoint(data["intermediate"], middle, packages, True)
    c = endpoint(data["target"], final, last_packages, True)
    data["stages"] = [{"kind": "event_reification", "source": a, "target": b,
                       "source_scope_sha256": old_scope, "target_scope_sha256": new_scope},
                      {"kind": "event_rename", "source": b, "target": c,
                       "source_scope_sha256": new_scope, "target_scope_sha256": new_scope}]
    return data


def change_capabilities(data, capabilities):
    data["source"]["ledger"]["assertions"][0]["required_capabilities"] = capabilities
    for key in ("intermediate", "target"):
        data[key]["ledger"]["assertions"][0]["required_capabilities"] = capabilities
        data[key]["source_sha256"] = digest(data["source"])
    return seal(data)


spec = importlib.util.spec_from_file_location("p1_c_evaluation", ROOT / "scripts/research/evaluate-p1-c.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ReferenceMeaningTests(unittest.TestCase):
    def test_identity_satisfaction_does_not_imply_model_coverage(self):
        result = evaluate(request("coverage-countermodel"))
        self.assertTrue(result["satisfaction_identity"])
        self.assertTrue(result["model_reduct"])
        self.assertFalse(result["model_coverage"])
        self.assertEqual([result["results"][0][s]["entails"] for s in ("source", "target")], [False, True])
        self.assertEqual(result["certificate"]["status"], "not_certified")

    def test_existential_consequence_does_not_create_named_fact(self):
        result = evaluate(request("existential-without-named-witness"))
        self.assertEqual([r["source"]["entails"] for r in result["results"]], [False, True])
        self.assertEqual([r["target"]["entails"] for r in result["results"]], [False, False])
        self.assertEqual(result["results"][1]["source"]["proof"]["named_witness"], None)
        self.assertEqual(result["named_witness_assertions_added"], [])
        self.assertFalse(result["model_reduct"])

    def test_missing_countermodel_is_unassessed_not_nonentailment(self):
        result = evaluate(request("no-countermodel-no-proof"))
        self.assertIsNone(result["model_coverage"])
        self.assertIsNone(result["results"][0]["source"]["entails"])
        self.assertIn({"query_id": "q1", "side": "source"}, result["incomplete"])

    def test_same_sentence_sets_have_an_identity_template_proof(self):
        data = request("identity-template")
        data["source"]["data"] *= 2
        result = evaluate(data)
        self.assertEqual(result["certificate"]["status"], "certified")
        self.assertEqual(result["certificate"]["evidence_level"], "checked_identity_template")
        self.assertTrue(result["model_coverage"])

    def test_reference_rules_are_not_hardcoded_to_example_symbols(self):
        raw = json.dumps(request("coverage-countermodel"))
        for old, new in (("A", "fiction:alpha"), ("B", "fiction:beta"), ("a", "fiction:subject")):
            raw = raw.replace('"' + old + '"', '"' + new + '"')
        result = evaluate(json.loads(raw))
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["results"][0]["source"]["entails"])
        self.assertTrue(result["results"][0]["target"]["entails"])

    def test_equal_report_hashes_do_not_prove_sentence_identity(self):
        with patch("med_dsl.reference.digest", return_value="0" * 64):
            result = evaluate(request("coverage-countermodel"))
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertFalse(result["results"][0]["source"]["entails"])
        self.assertTrue(result["results"][0]["target"]["entails"])

    def test_horn_cycles_terminate_and_proofs_are_sound(self):
        data = request("coverage-countermodel")
        rule = deepcopy(data["target"]["theory"][0])
        reverse = deepcopy(rule)
        reverse["body"]["left"]["predicate"], reverse["body"]["right"]["predicate"] = "B", "A"
        data["source"]["theory"] = [rule, reverse]
        data["models"] = []
        result = evaluate(data)
        self.assertTrue(result["results"][0]["source"]["entails"])
        self.assertEqual(result["results"][0]["source"]["proof"]["kind"], "unary_horn")

    def test_quantified_truth_against_direct_binary_relation_calculation(self):
        var = lambda x: {"var": x}
        formula = {"kind": "forall", "var": "x", "body": {"kind": "exists", "var": "y",
                   "body": {"kind": "atom", "predicate": "r", "args": [var("x"), var("y")]}}}
        pairs = list(itertools.product(("u", "v"), repeat=2))
        for mask in range(16):
            relation = [list(p) for i, p in enumerate(pairs) if mask & (1 << i)]
            model = {"domain": ["u", "v"], "constants": {}, "predicates": {"r": relation}}
            expected = all(any([x, y] in relation for y in model["domain"]) for x in model["domain"])
            self.assertEqual(truth(formula, model, Budget(1000)), expected)
            self.assertEqual(truth({"kind": "not", "body": formula}, model, Budget(1000)), not expected)

    def test_no_unsound_existential_proof_when_consequent_is_another_predicate(self):
        data = request("existential-without-named-witness")
        data["signature"]["predicates"].append({"ref": "C", "arity": 1})
        data["source"]["theory"][0]["body"]["right"]["body"]["items"][1]["predicate"] = "C"
        data["models"] = [{"id": "counter", "model": {"domain": ["u", "v"], "constants": {"a": "u"},
            "predicates": {"A": [["u"]], "B": [], "C": [["v"]], "r": [["u", "v"]]}}}]
        result = evaluate(data)
        self.assertFalse(result["results"][1]["source"]["entails"])
        self.assertIsNone(result["results"][1]["source"]["proof"])

    def test_one_and_two_element_agreement_is_not_all_model_coverage(self):
        result = evaluate(request("finite-check-is-not-coverage"))
        self.assertTrue(all(p["agreement"] for p in result["finite_probes"]))
        self.assertFalse(result["model_coverage"])
        self.assertEqual(result["coverage_countermodel_id"], "three")
        self.assertEqual(result["certificate"]["status"], "not_certified")
        no_witness = evaluate(request("finite-check-without-countermodel"))
        self.assertIsNone(no_witness["model_coverage"])
        self.assertIsNone(no_witness["results"][0]["source"]["entails"])

    def test_invalid_models_and_open_or_shadowed_formulas_are_rejected(self):
        for change in (lambda d: d["models"][0]["model"].update(domain=[]),
                       lambda d: d["models"][0]["model"]["predicates"].pop("B"),
                       lambda d: d["models"][0]["model"]["predicates"]["A"].append(["u"]),
                       lambda d: d["models"][0]["model"]["constants"].update(a="missing"),
                       lambda d: d["queries"][0]["formula"].update(args=[{"var": "x"}])):
            data = request("coverage-countermodel")
            change(data)
            self.assertEqual(evaluate(data)["status"], "invalid_input")
        data = request("identity-template")
        data["queries"][0]["formula"] = {"kind": "forall", "var": "x", "body": {"kind": "exists", "var": "x", "body": data["queries"][0]["formula"]}}
        self.assertEqual(evaluate(data)["reason_codes"], ["shadowed_variable"])


class CompositionTests(unittest.TestCase):
    def test_actual_two_step_template_preserves_bindings_and_old_evidence(self):
        result = evaluate(request())
        self.assertEqual(result["certificate"]["status"], "certified")
        self.assertEqual(result["certificate"]["evidence_level"], "checked_native_template")
        self.assertTrue(all(o["passed"] for o in result["obligations"]))
        self.assertEqual(result["finite_checks"][1]["target_result"]["results"][0]["bindings"], [{"result": "fiction:positive"}])
        self.assertEqual(result["finite_checks"][1]["target_result"]["results"][0]["evidence"][0]["assertion_refs"], ["h1"])
        self.assertIn("execution_completion", result["certificate"]["scope"]["excludes"])

    def test_endpoint_scope_policy_dependencies_are_checked_against_actuals(self):
        for name in ("wrong-intermediate", "wrong-policy", "wrong-dependencies", "wrong-translated-scope"):
            result = evaluate(request(name))
            self.assertEqual(result["certificate"]["status"], "not_certified")
            self.assertTrue(any(not o["passed"] for o in result["obligations"]))

    def test_honestly_rehashed_changed_history_is_not_a_renaming(self):
        data = request()
        changed = deepcopy(data["source"])
        changed["ledger"]["assertions"][0]["origin"]["ref"] = "fiction:changed-origin"
        data["target"]["ledger"]["assertions"][0]["origin"]["ref"] = "fiction:changed-origin"
        data["target"]["source_sha256"] = digest(changed)
        seal(data)
        result = evaluate(data)
        self.assertEqual(result["certificate"]["status"], "not_certified")
        failed = {o["name"] for o in result["obligations"] if not o["passed"]}
        self.assertIn("final_history_roundtrip", failed)
        self.assertIn("actual_second_step_is_only_renaming", failed)

    def test_unknown_capability_and_outside_query_do_not_disappear(self):
        data = change_capabilities(request(), ["fiction:unknown@1"])
        data["queries"].append({"id": "q3", "context_ref": data["queries"][0]["context_ref"], "kind": "event_count", "required": False})
        result = evaluate(seal(data))
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertEqual(result["out_of_scope_query_ids"], ["q3"])
        self.assertTrue(result["incomplete"])
        self.assertTrue(all(r["difference"] is None for c in result["finite_checks"] for r in c["comparison"]["results"]))

    def test_rename_is_total_injective_fresh_and_uses_new_ledger_reference(self):
        self.assertEqual(evaluate(request("noninjective-renaming"))["reason_codes"], ["renaming_not_total_injective"])
        data = request("rename-events")
        data["renames"] = data["renames"][:1]
        self.assertEqual(evaluate(data)["reason_codes"], ["renaming_not_total_injective"])
        data = request("rename-events")
        data["target_ledger_ref"] = data["target"]["ledger"]["ref"]
        self.assertEqual(evaluate(data)["reason_codes"], ["ledger_reference_redefined"])
        data = request("rename-events")
        for i, entry in enumerate(data["renames"]):
            entry["to_ref"] = data["renames"][1 - i]["from_ref"]
        self.assertEqual(evaluate(data)["reason_codes"], ["renaming_capture"])

    def test_renaming_does_not_alias_or_drop_original_history(self):
        data = request("rename-events")
        original = deepcopy(data)
        result = evaluate(data)
        restored, _ = _restore(result["target"])
        self.assertEqual(restored, _restore(data["target"])[0])
        result["target"]["ledger"]["reviews"][0]["reviewer_ref"] = "changed"
        self.assertEqual(data, original)

    def test_new_event_queries_are_not_included_in_the_old_query_certificate(self):
        data = request()
        data["queries"].append({"id": "q3", "context_ref": data["queries"][0]["context_ref"], "kind": "event_identity", "required": False})
        result = evaluate(seal(data))
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertEqual(result["certificate"]["scope"]["query_ids"], ["q1", "q2"])
        self.assertEqual(result["out_of_scope_query_ids"], ["q3"])


class ProjectionAndPolicyTests(unittest.TestCase):
    def test_lossless_second_step_does_not_repair_a_lossy_first_step(self):
        result = evaluate(request("lossy-composition"))
        self.assertTrue(result["projected_value_sets_equal"])
        self.assertEqual(result["second_step_certificate"]["status"], "certified")
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertIsNone(result["results"][0]["target_bindings"])
        self.assertNotEqual(result["results"][0]["source_a_bindings"], result["results"][0]["source_b_bindings"])

    def test_all_eight_tuple_subsets_preserve_queries_using_only_kept_columns(self):
        tuples = [["key", s, m, val] for s, m, val in itertools.product("01", repeat=3)]
        for mask in range(256):
            data = request("kept-query-scope")
            data["projection"]["positions"] = [1, 3]
            data["source_a"] = [row for i, row in enumerate(tuples) if mask & (1 << i)]
            data["source_b"] = []
            data["queries"][0]["where"] = [{"position": 1, "value": "1"}]
            expected = [{"result": v} for v in sorted({row[3] for row in data["source_a"] if row[1] == "1"})]
            result = evaluate(data)
            self.assertEqual(result["results"][0]["target_bindings"], expected)
            self.assertEqual(result["certificate"]["status"], "certified")

    def test_sidecar_is_explicit_extra_information_not_projection_recovery(self):
        result = evaluate(request("sidecar-is-additional-input"))
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertIsNone(result["results"][0]["target_bindings"])
        self.assertEqual(result["results"][0]["sidecar_answer"]["mode"], "sidecar_replay")
        data = request("sidecar-is-additional-input")
        data["source_sidecar"]["sha256"] = "0" * 64
        self.assertEqual(evaluate(data)["reason_codes"], ["sidecar_mismatch"])

    def test_discarded_fields_stay_out_of_scope(self):
        for positions in ([0], [1], [2], [3], [1, 3]):
            data = request("discarded-query-scope")
            data["projection"]["positions"] = positions
            result = evaluate(data)
            self.assertIsNone(result["results"][0]["target_bindings"])
            self.assertEqual(result["certificate"]["status"], "not_certified")

    def test_available_sidecar_is_not_reported_as_used_for_a_kept_query(self):
        data = request("sidecar-is-additional-input")
        data["projection"] = {"kind": "columns", "positions": [0, 1, 2, 3]}
        result = evaluate(data)
        self.assertTrue(result["source_sidecar_available"])
        self.assertFalse(result["additional_source_used"])
        self.assertEqual(result["certificate"]["status"], "certified")

    def test_absence_probe_reports_semantic_change_without_clinical_assertions(self):
        result = evaluate(request("absence-is-negative"))
        row = result["results"][0]
        self.assertEqual([row["before_status"], row["after_status"]], ["undetermined", "opposed"])
        self.assertEqual(row["after_negative_literal_status"], "supported")
        self.assertEqual(row["assumptions"], ["closed_world_assumption"])
        self.assertEqual(result["clinical_assertions_added"], [])
        self.assertEqual(evaluate(request("same-current-answer"))["certificate"]["status"], "not_certified")

    def test_unknown_or_conflicting_source_is_not_closed_world_negative(self):
        result = evaluate(request("unknown-does-not-become-negative"))
        self.assertEqual(result["results"][0]["after_status"], "unassessed")
        self.assertIsNone(result["results"][0]["difference"])
        self.assertTrue(result["incomplete"])
        data = request("absence-is-negative")
        source = json.loads((ROOT / "examples/p1-b/conflict.json").read_text())["request"]["source"]
        data["source"] = source
        result = evaluate(data)
        self.assertEqual(result["results"][0]["after_status"], "conflict")
        self.assertIsNone(result["results"][0]["difference"])


class ReplayAvailabilityTests(unittest.TestCase):
    def test_stored_runtime_bytes_are_not_an_interpreter(self):
        result = evaluate(request("stored-runtime-is-not-handler"))
        self.assertTrue(result["archive_bytes_verified"])
        self.assertTrue(result["legacy_replay"]["requirements"][0]["stored_bytes_verified"])
        self.assertFalse(result["legacy_replay"]["requirements"][0]["available"])
        self.assertEqual(result["legacy_replay"]["status"], "unavailable")
        self.assertEqual(result["semantic_handover"]["status"], "unassessed")

    def test_old_runtime_availability_and_new_semantic_guarantee_are_independent(self):
        result = evaluate(request("new-guarantee-independent-of-old-binary"))
        self.assertEqual(result["legacy_replay"]["status"], "unavailable")
        self.assertFalse(result["legacy_replay"]["executed"])
        self.assertEqual(result["semantic_handover"]["status"], "certified")
        ready = evaluate(request("known-native-ready"))
        self.assertEqual(ready["legacy_replay"]["status"], "ready_to_replay")
        self.assertEqual(ready["semantic_handover"]["status"], "unassessed")

    def test_known_runtime_with_uninterpretable_archive_is_not_ready(self):
        data = request("known-native-ready")
        raw = b"not a JSON snapshot"
        data["archive"]["bytes_base64"] = base64.b64encode(raw).decode()
        data["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        result = evaluate(data)
        self.assertTrue(result["archive_bytes_verified"])
        self.assertEqual(result["legacy_replay"]["status"], "unavailable")
        self.assertEqual(result["legacy_replay"]["input_interpretation"]["status"], "unassessed")

    def test_decoded_archive_unicode_is_validated_before_interpretation(self):
        data = request("known-native-ready")
        source = request()["source"]
        source["contexts"][0]["purpose"] = "\ud800"
        raw = json.dumps(source, ensure_ascii=True).encode()
        data["archive"]["bytes_base64"] = base64.b64encode(raw).decode()
        data["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        result = evaluate(data)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["archive_bytes_verified"])
        self.assertEqual(result["legacy_replay"]["status"], "unavailable")
        self.assertEqual(result["legacy_replay"]["input_interpretation"]["reason_codes"], ["invalid_json"])

    def test_encoded_json_does_not_bypass_request_depth_limit(self):
        data = request("known-native-ready")
        value = None
        for _ in range(65):
            value = [value]
        raw = json.dumps(value).encode()
        data["archive"]["bytes_base64"] = base64.b64encode(raw).decode()
        data["archive"]["sha256"] = hashlib.sha256(raw).hexdigest()
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["reason_codes"], ["nesting_limit"])
        self.assertNotIn("legacy_replay", result)

    def test_dependency_integrity_and_archive_to_chain_binding_are_checked(self):
        data = request("known-native-ready")
        data["available_resources"][0]["bytes_base64"] = base64.b64encode(b"changed").decode()
        self.assertEqual(evaluate(data)["reason_codes"], ["resource_hash_mismatch"])
        data = request("new-guarantee-independent-of-old-binary")
        data["semantic_chain"]["source"]["contexts"][0]["purpose"] = "changed"
        self.assertEqual(evaluate(data)["reason_codes"], ["archive_source_mismatch"])
        self.assertEqual(evaluate(request("corrupt-archive"))["reason_codes"], ["archive_hash_mismatch"])


class HandoverLimitsAndCorpusTests(unittest.TestCase):
    def test_shared_chain_budget_includes_final_certificate_commit(self):
        for maximum in (0, 1, 15, 16, 55, 95, 96):
            data = request()
            data["budget"]["max_steps"] = maximum
            result = evaluate(data)
            with self.subTest(maximum=maximum):
                self.assertEqual(result["status"], "resource_limit")
                self.assertNotIn("certificate", result)
        data["budget"]["max_steps"] = 97
        result = evaluate(data)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["steps_used"], 97)
        self.assertEqual(result["certificate"]["status"], "certified")

    def test_replay_and_independent_chain_share_one_budget(self):
        data = request("new-guarantee-independent-of-old-binary")
        data["budget"]["max_steps"] = 99
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertNotIn("semantic_handover", result)
        data["budget"]["max_steps"] = 100
        self.assertEqual(evaluate(data)["semantic_handover"]["status"], "certified")

    def test_each_operation_zero_budget_has_no_partial_report_or_certificate(self):
        for name in ("coverage-countermodel", "absence-is-negative", "rename-events", "event-renaming-chain", "lossy-composition", "missing-runtime"):
            data = request(name)
            data["budget"]["max_steps"] = 0
            result = evaluate(data)
            self.assertEqual(result["status"], "resource_limit")
            for field in ("certificate", "results", "target", "semantic_handover", "model_coverage"):
                self.assertNotIn(field, result)

    def test_quantifier_and_formula_limits_never_look_like_nonentailment(self):
        data = request("finite-check-is-not-coverage")
        data["budget"]["max_steps"] = 5
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertNotIn("results", result)
        data = request("identity-template")
        f = data["queries"][0]["formula"]
        for _ in range(17):
            f = {"kind": "not", "body": f}
        data["queries"][0]["formula"] = f
        self.assertEqual(evaluate(data)["reason_codes"], ["formula_limit"])

    def test_bool_positions_domain_sizes_and_budgets_are_not_integers(self):
        data = request("kept-query-scope")
        data["projection"]["positions"] = [True]
        self.assertEqual(evaluate(data)["status"], "invalid_input")
        data = request("finite-check-is-not-coverage")
        data["finite_domain_sizes"] = [True]
        self.assertEqual(evaluate(data)["status"], "invalid_input")
        for value, status in ((True, "invalid_input"), (-1, "invalid_input"), (100001, "resource_limit")):
            data = request()
            data["budget"]["max_steps"] = value
            self.assertEqual(evaluate(data)["status"], status)

    def test_native_spec_and_runtime_pins_are_checked(self):
        original = Path.read_bytes
        for basename, reason in (("events_spec.json", "event_spec_mismatch"), ("model.py", "native_runtime_mismatch"), ("handover_spec.json", "native_spec_mismatch")):
            def read(path, basename=basename):
                return b"changed" if path.name == basename else original(path)
            with patch("pathlib.Path.read_bytes", read):
                self.assertEqual(evaluate(request())["reason_codes"], [reason])
        data = request()
        data["consumer"]["read_only"] = True
        self.assertEqual(evaluate(data)["reason_codes"], ["unknown_field"])

    def test_author_draft_all_paths_replay_and_input_preservation(self):
        fixtures = runner.load_fixtures(ROOT / "examples/p1-c/manifest.json")
        self.assertEqual(len(fixtures), 27)
        for entry, data, _ in fixtures:
            original = deepcopy(data["request"])
            result = evaluate(data["request"])
            with self.subTest(path=entry["path"]):
                for check in data["expected"]["checks"]:
                    actual = result
                    for key in check["path"]:
                        actual = actual[key]
                    self.assertEqual(digest(actual), digest(check["equals"]), check["path"])
                self.assertEqual(data["request"], original)
                self.assertEqual(result, evaluate(original))

    def test_cli_executes_request_without_trusting_expected(self):
        data = fixture("identity-template")
        data["expected"] = {"certificate": {"status": "arbitrary"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(data))
            process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)], capture_output=True,
                                     env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout), evaluate(data["request"]))


if __name__ == "__main__":
    unittest.main()
