"""事象化・同一証人の結合・原履歴・有限照合と認定の境界。"""

from copy import deepcopy
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
from med_dsl.events import ACTIVE, EVENT_PROFILE, EVENT_SPEC_SHA256
from med_dsl.validation import digest


def fixture(name="linked-observations"):
    return json.loads((ROOT / "examples/p1-b" / (name + ".json")).read_text())


def request(name="linked-observations"):
    return fixture(name)["request"]


def reify(source, target_ref="fiction:ledger:events@1"):
    data = request("reify-events")
    data.update(source=deepcopy(source), target_ledger_ref=target_ref)
    return evaluate(data)


def target_query(source, queries=None):
    data = request("native-query")
    result = reify(source)
    if result["status"] != "ok":
        raise AssertionError(result)
    data["target"] = result["target"]
    if queries is not None:
        data["queries"] = queries
    return data


def rebuild(data):
    data["target"] = reify(data["source"])["target"]
    return data


def assertion(source, index=0):
    return source["ledger"]["assertions"][index]


spec = importlib.util.spec_from_file_location("p1_b_evaluation", ROOT / "scripts/research/evaluate-p1-b.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ReificationTests(unittest.TestCase):
    def test_reify_and_public_restore_preserve_complete_history(self):
        for name in ("linked-observations", "duplicate-support", "explicit-revisions", "negative-tuple",
                     "ai-unreviewed", "separate-contexts", "unknown-capability"):
            source = request(name)["source"]
            original = deepcopy(source)
            result = reify(source)
            restore = request("restore-events")
            restore["target"] = result["target"]
            restored = evaluate(restore)
            with self.subTest(name=name):
                self.assertEqual(result["status"], "ok")
                self.assertEqual(restored["source"], original)
                self.assertEqual(source, original)
                self.assertEqual(restored["source_sha256"], digest(original))
                self.assertEqual(result["target"]["ledger"]["reviews"], source["ledger"]["reviews"])

    def test_same_key_and_same_tuple_have_distinct_internal_ids(self):
        for name in ("shared-key", "duplicate-support"):
            source = request(name)["source"]
            statements = [h["statement"] for h in reify(source)["target"]["ledger"]["assertions"]]
            self.assertNotEqual(statements[0]["event_ref"], statements[1]["event_ref"])
            for h, statement in zip(source["ledger"]["assertions"], statements):
                self.assertEqual(statement["source_assertion"], {"ledger_ref": source["ledger"]["ref"], "id": h["id"]})

    def test_id_is_scoped_to_original_ledger_and_not_array_order(self):
        source = request()["source"]
        first = reify(source)["target"]
        source["ledger"]["assertions"].reverse()
        reordered = reify(source)["target"]
        ids = lambda t: {h["id"]: h["statement"]["event_ref"] for h in t["ledger"]["assertions"]}
        self.assertEqual(ids(first), ids(reordered))
        source["ledger"]["ref"] += ":other"
        other = reify(source)["target"]
        self.assertTrue(set(ids(first).values()).isdisjoint(ids(other).values()))

    def test_generated_reference_collision_is_detected(self):
        source = request()["source"]
        event_ref = reify(source)["target"]["ledger"]["assertions"][0]["statement"]["event_ref"]
        assertion(source)["origin"]["ref"] = event_ref
        self.assertEqual(reify(source)["reason_codes"], ["event_reference_collision"])
        source = request()["source"]
        self.assertEqual(reify(source, event_ref)["reason_codes"], ["event_reference_collision"])

    def test_empty_relation_roundtrips_without_fabricated_spare_observation(self):
        source = request()["source"]
        source["ledger"].update(assertions=[], reviews=[])
        data = target_query(source)
        self.assertEqual(data["target"]["ledger"]["assertions"], [])
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]], ["undetermined", "undetermined"])

    def test_another_fresh_naming_scheme_has_same_answers(self):
        data = request("native-query")
        baseline = evaluate(data)
        for i, h in enumerate(data["target"]["ledger"]["assertions"]):
            h["statement"]["event_ref"] = f"fiction:renamed-event:{i}"
        result = evaluate(data)
        self.assertEqual(result["results"], baseline["results"])
        self.assertNotEqual(result["target_sha256"], baseline["target_sha256"])

    def test_returned_artifact_and_restored_source_do_not_alias_inputs(self):
        source = request()["source"]
        original = deepcopy(source)
        target = reify(source)["target"]
        target["contexts"][0]["purpose"] = "changed"
        self.assertEqual(source, original)
        data = request("restore-events")
        original = deepcopy(data)
        result = evaluate(data)
        result["source"]["ledger"]["assertions"][0]["origin"]["ref"] = "changed"
        self.assertEqual(data, original)


class NativeEventQueryTests(unittest.TestCase):
    def test_all_subsets_of_eight_tuples_against_direct_relation_membership(self):
        tuples = [("fiction:k", "fiction:s" + s, "fiction:m" + m, "fiction:v" + v)
                  for s, m, v in itertools.product("01", repeat=3)]
        for mask in range(256):
            source = request()["source"]
            template_h, template_r = deepcopy(assertion(source)), deepcopy(source["ledger"]["reviews"][0])
            source["ledger"].update(assertions=[], reviews=[])
            relation = [t for i, t in enumerate(tuples) if mask & (1 << i)]
            for i, t in enumerate(relation):
                h, r = deepcopy(template_h), deepcopy(template_r)
                h["id"], h["atom"]["args"] = "h" + str(i), list(t)
                r.update(id="r" + str(i), assertion_ref=h["id"])
                source["ledger"]["assertions"].append(h)
                source["ledger"]["reviews"].append(r)
            q = request("native-query")["queries"][0]
            q["atoms"][0]["args"] = ["fiction:k", "fiction:s1", "fiction:m0", {"var": "result"}]
            result = evaluate(target_query(source, [q]))
            expected = [{"result": v} for k, s, m, v in relation if s == "fiction:s1" and m == "fiction:m0"]
            with self.subTest(mask=mask):
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["results"][0]["bindings"], expected)
                self.assertEqual(result["results"][0]["status"], "supported" if expected else "undetermined")

    def test_native_query_never_uses_legacy_replay_for_answers(self):
        with patch("med_dsl.events.run_query", side_effect=AssertionError("legacy replay called")):
            result = evaluate(request("native-query"))
        self.assertEqual(result["results"][0]["bindings"], [{"result": "fiction:positive"}])

    def test_shared_public_variable_joins_two_different_observations(self):
        source = request("shared-key")["source"]
        q = request("native-query")["queries"][0]
        q["atoms"] = [{"predicate": "fiction:measurement@1", "args": [{"var": "key"}, s, m, {"var": v}]}
                      for s, m, v in (("fiction:s1", "fiction:m1", "left"), ("fiction:s2", "fiction:m2", "right"))]
        result = evaluate(target_query(source, [q]))
        self.assertEqual(result["results"][0]["bindings"], [{"key": "fiction:e1", "left": "fiction:positive", "right": "fiction:negative"}])
        self.assertEqual(result["results"][0]["evidence"][0]["assertion_refs"], ["h1", "h2"])

    def test_internal_variable_is_fresh_even_when_user_uses_its_name(self):
        data = request("native-query")
        q = data["queries"][0]
        q["atoms"][0]["args"][3] = {"var": "_event_1"}
        result = evaluate(data)
        self.assertEqual(result["results"][0]["bindings"], [{"_event_1": "fiction:positive"}])

    def test_projection_deduplicates_without_losing_duplicate_support(self):
        data = request("duplicate-support")
        data["queries"] = [data["queries"][0]]
        data["queries"][0]["atoms"] *= 2
        result = evaluate(data)
        self.assertEqual(result["comparison"]["status"], "matched")
        row = result["target_result"]["results"][0]
        self.assertEqual(row["bindings"], [{"result": "fiction:positive"}])
        self.assertEqual(row["evidence"][0]["assertion_refs"], ["h1", "h2"])
        self.assertEqual(row["evidence"][0]["review_refs"], ["r1", "r2"])

    def test_unchanged_unary_definition_joins_event_and_keeps_rule_evidence(self):
        data = request()
        source = data["source"]
        source["package"]["predicates"] += [{"ref": "fiction:A", "roles": ["value"]}, {"ref": "fiction:B", "roles": ["value"]}]
        source["package"]["inclusions"] = [{"sub": "fiction:A", "super": "fiction:B"}]
        h = deepcopy(assertion(source))
        h.update(id="h3", atom={"predicate": "fiction:A", "args": ["fiction:positive"]})
        r = deepcopy(source["ledger"]["reviews"][0])
        r.update(id="r3", assertion_ref="h3")
        source["ledger"]["assertions"].append(h)
        source["ledger"]["reviews"].append(r)
        data["queries"] = [data["queries"][0]]
        data["queries"][0]["atoms"].append({"predicate": "fiction:B", "args": [{"var": "result"}]})
        result = evaluate(rebuild(data))
        self.assertEqual(result["comparison"]["status"], "matched")
        proof = result["target_result"]["results"][0]["evidence"][0]
        self.assertEqual(proof["assertion_refs"], ["h1", "h3"])
        self.assertEqual(proof["definition_refs"], [source["package"]["ref"] + "#/inclusions/0"])


class HandoverBoundaryTests(unittest.TestCase):
    def test_finite_match_is_not_a_universal_certificate(self):
        result = evaluate(request())
        self.assertEqual(result["comparison"]["status"], "matched")
        self.assertEqual(result["certificate"], {"status": "not_certified", "evidence_level": "finite_execution_check", "reason_codes": ["template_obligations_pending"]})

    def test_split_witness_is_an_explicit_finite_countermodel(self):
        result = evaluate(request("split-witness"))
        self.assertEqual(result["comparison"]["status"], "mismatch")
        counter = result["comparison"]["counterexamples"][0]
        self.assertEqual([counter[k] for k in ("source_truth", "correct_target_truth", "incorrect_target_truth")], [False, False, True])
        self.assertEqual(counter["meaning_mode"], "truth_in_listed_model")
        self.assertEqual(result["certificate"]["reason_codes"], ["satisfaction_condition_failed"])

    def test_event_count_identity_and_unknown_expressions_are_out_of_scope(self):
        data = request("out-of-scope")
        data["queries"][2]["kind"] = "arbitrary_program"
        result = evaluate(data)
        self.assertEqual(result["comparison"]["status"], "partial")
        self.assertEqual([r["status"] for r in result["comparison"]["results"]], ["matched", "matched", "out_of_scope", "out_of_scope"])

    def test_history_change_is_not_hidden_by_equal_bindings(self):
        data = request()
        changed = deepcopy(data["source"])
        assertion(changed)["origin"]["ref"] = "fiction:different-source"
        data["target"] = reify(changed)["target"]
        result = evaluate(data)
        self.assertEqual(result["comparison"]["results"][0]["status"], "matched")
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertFalse(result["comparison"]["history_matches"])
        self.assertIn("history_not_preserved", result["certificate"]["reason_codes"])

    def test_negative_tuple_does_not_negate_the_shared_method(self):
        data = request("negative-tuple")
        source = data["source"]
        assertion(source, 1)["atom"]["args"][2] = "fiction:m1"
        q = deepcopy(data["queries"][0])
        q.update(id="q2", atoms=[deepcopy(assertion(source, 1)["atom"])])
        data["queries"].append(q)
        result = evaluate(rebuild(data))
        self.assertEqual([r["status"] for r in result["target_result"]["results"]], ["opposed", "supported"])

    def test_pending_revision_conflict_contexts_and_unknown_caps_keep_p0_selection(self):
        for name in ("explicit-revisions", "conflict", "confirmation-times", "separate-contexts", "unknown-capability"):
            result = evaluate(request(name))
            with self.subTest(name=name):
                self.assertTrue(result["comparison"]["history_matches"])
                self.assertTrue(result["comparison"]["adoption_matches"])
                self.assertEqual(result["source_result"]["views"], result["target_result"]["views"])
                if name in ("conflict", "unknown-capability"):
                    self.assertTrue(all(r["difference"] is None for r in result["comparison"]["results"]))

    def test_native_spec_and_consumer_cannot_be_spoofed(self):
        for field, value, status in (("profile", "unknown", "unsupported_profile"),
                                     ("profile_spec_sha256", "0" * 64, "invalid_input"),
                                     ("operations", [], "unsupported_profile")):
            data = request("native-query")
            data["consumer"][field] = value
            self.assertEqual(evaluate(data)["status"], status)
        data = request("native-query")
        data["consumer"]["read_only"] = True
        self.assertEqual(evaluate(data)["reason_codes"], ["unknown_field"])
        with patch("med_dsl.events.Path.read_bytes", return_value=b"untrusted spec"):
            self.assertEqual(evaluate(request())["reason_codes"], ["native_spec_mismatch"])

    def test_invalid_roles_collisions_and_hashes_stop_before_answering(self):
        for name in ("missing-method", "multiple-methods", "duplicate-event-id", "existing-name-collision", "wrong-source-assertion", "wrong-source-hash"):
            result = evaluate(request(name))
            self.assertEqual(result["status"], "invalid_input")
            self.assertNotIn("target_result", result)
        data = request("native-query")
        data["target"]["ledger"]["assertions"][0]["statement"]["event_ref"] = data["target"]["ledger"]["ref"]
        self.assertEqual(evaluate(data)["reason_codes"], ["event_reference_collision"])

    def test_selected_relation_cannot_remain_as_old_atom_or_collide_with_native_predicate(self):
        data = request("native-query")
        data["target"]["ledger"]["assertions"][0]["statement"] = {"kind": "unchanged_atom", "atom": assertion(request()["source"])["atom"]}
        self.assertEqual(evaluate(data)["reason_codes"], ["unreified_relation"])
        source = request()["source"]
        source["package"]["predicates"].append({"ref": ACTIVE, "roles": ["event"]})
        self.assertEqual(reify(source)["reason_codes"], ["native_predicate_collision"])


class EventResourceTests(unittest.TestCase):
    def test_reify_restore_never_publish_partial_history(self):
        for operation, name, output_key in (("reify_events", "reify-events", "target"), ("restore_events", "restore-events", "source")):
            for maximum in range(6):
                data = request(name)
                data["budget"]["max_steps"] = maximum
                result = evaluate(data)
                with self.subTest(operation=operation, maximum=maximum):
                    self.assertEqual(result["status"], "resource_limit")
                    self.assertNotIn(output_key, result)
            data["budget"]["max_steps"] = 6
            self.assertEqual(evaluate(data)["status"], "ok")

    def test_all_query_cuts_drop_partial_bindings_and_keep_completed_other_query(self):
        for maximum in range(34):
            data = request("native-query")
            data["budget"]["max_steps"] = maximum
            result = evaluate(data)
            with self.subTest(maximum=maximum):
                self.assertEqual(result["status"], "resource_limit")
                if maximum:
                    self.assertEqual(result["steps_used"], maximum)
                    self.assertEqual(result["results"][1]["status"], "unassessed")
                    self.assertEqual(result["results"][1]["bindings"], [])
                    self.assertEqual(result["results"][0]["status"], "supported" if maximum >= 20 else "unassessed")
        data["budget"]["max_steps"] = 34
        self.assertEqual(evaluate(data)["status"], "ok")

    def test_comparison_budget_is_shared_including_final_comparison(self):
        data = request()
        data["budget"]["max_steps"] = 40
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["steps_used"], 40)
        self.assertIsNone(result["certificate"])
        self.assertEqual(result["comparison"]["results"][0]["status"], "matched")
        self.assertIsNone(result["comparison"]["results"][1]["difference"])
        data["budget"]["max_steps"] = 41
        self.assertEqual(evaluate(data)["comparison"]["status"], "matched")

    def test_intermediate_limit_is_distinct_from_semantic_loss(self):
        data = request("duplicate-support")
        source = data["source"]
        h, r = deepcopy(assertion(source)), deepcopy(source["ledger"]["reviews"][0])
        source["ledger"].update(assertions=[], reviews=[])
        for i in range(65):
            item, review = deepcopy(h), deepcopy(r)
            item["id"] = "h" + str(i)
            review.update(id="r" + str(i), assertion_ref=item["id"])
            source["ledger"]["assertions"].append(item)
            source["ledger"]["reviews"].append(review)
        data["queries"] = [data["queries"][0]]
        data["queries"][0]["atoms"] *= 2
        result = evaluate(rebuild(data))
        self.assertEqual(result["status"], "resource_limit")
        self.assertIn("intermediate_binding_limit", result["reason_codes"])
        self.assertEqual(result["target_result"]["results"][0]["bindings"], [])
        self.assertIsNone(result["comparison"]["results"][0]["difference"])
        self.assertIsNone(result["certificate"])

    def test_public_binding_limit_does_not_return_first_thousand_as_complete(self):
        source = request()["source"]
        source["package"]["predicates"].append({"ref": "fiction:tag", "roles": ["value"]})
        h, r = deepcopy(assertion(source)), deepcopy(source["ledger"]["reviews"][0])
        source["ledger"].update(assertions=[], reviews=[])
        for i in range(33):
            item, review = deepcopy(h), deepcopy(r)
            item.update(id="h" + str(i), atom={"predicate": "fiction:tag", "args": ["fiction:v:" + str(i)]})
            review.update(id="r" + str(i), assertion_ref=item["id"])
            source["ledger"]["assertions"].append(item)
            source["ledger"]["reviews"].append(review)
        q = request("native-query")["queries"][0]
        q["atoms"] = [{"predicate": "fiction:tag", "args": [{"var": v}]} for v in ("x", "y")]
        result = evaluate(target_query(source, [q]))
        self.assertEqual(result["reason_codes"], ["binding_limit"])
        self.assertEqual(result["results"][0]["bindings"], [])

    def test_source_and_translated_query_limits_are_explicit(self):
        # 構文上限を検査する。多数の証人による中間結合上限とは分ける。
        source = request()["source"]
        source["ledger"]["assertions"] = source["ledger"]["assertions"][:1]
        source["ledger"]["reviews"] = source["ledger"]["reviews"][:1]
        data = target_query(source)
        atom0 = data["queries"][0]["atoms"][0]
        data["queries"] = [data["queries"][0]]
        data["queries"][0]["atoms"] = [deepcopy(atom0) for _ in range(64)]
        self.assertEqual(evaluate(data)["status"], "ok")
        data["queries"][0]["atoms"].append(deepcopy(atom0))
        self.assertEqual(evaluate(data)["status"], "resource_limit")
        for value, status in ((True, "invalid_input"), (-1, "invalid_input"), (100001, "resource_limit")):
            data = request("native-query")
            data["budget"]["max_steps"] = value
            self.assertEqual(evaluate(data)["status"], status)


class EventCorpusTests(unittest.TestCase):
    def test_author_draft_inventory_paths_replay_and_input_preservation(self):
        loaded = runner.load_fixtures(ROOT / "examples/p1-b/manifest.json")
        self.assertEqual(len(loaded), 22)
        for entry, data, _ in loaded:
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

    def test_cli_ignores_expected_and_keeps_design_examples_nonexecutable(self):
        data = fixture("native-query")
        data["expected"] = {"status": "arbitrary"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(data))
            process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)],
                                     capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout), evaluate(data["request"]))
        process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(ROOT / "examples/p1/event-reification.json")],
                                 capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()
