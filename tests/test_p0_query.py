"""架空データの情報保持・棄権・境界を検証する。独立した臨床評価ではない。"""

from copy import deepcopy
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.validation import digest


def fixture(name="linked-observations"):
    return json.loads((ROOT / "examples/p0" / (name + ".json")).read_text())


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.request = fixture()["request"]

    def result(self, request=None, index=0):
        result = evaluate(self.request if request is None else request)
        self.assertIn(result["status"], ("ok", "resource_limit"), result)
        return result["results"][index]

    def test_existing_query_and_revision_draft_expectations(self):
        for name in ("linked-observations", "assertion-revision"):
            with self.subTest(name=name):
                data = fixture(name)
                result = evaluate(data["request"])
                for check in data["expected"]["checks"]:
                    actual = result
                    for key in check["path"]:
                        actual = actual[key]
                    self.assertEqual(actual, check["equals"])

    def test_role_bindings_match_independent_relation_reference(self):
        # 直接の四項関係を基準に、全検体×方法の組を照合する。
        relation = {(a["atom"]["args"][1], a["atom"]["args"][2], a["atom"]["args"][3])
                    for a in self.request["ledger"]["assertions"]}
        for specimen, method in itertools.product(("fiction:s1", "fiction:s2"), ("fiction:m1", "fiction:m2")):
            with self.subTest(specimen=specimen, method=method):
                request = deepcopy(self.request)
                query = request["queries"][0]
                query["atoms"][0]["args"] = [{"var": "event"}, specimen, method, {"var": "result"}]
                request["queries"] = [query]
                expected = {r for s, m, r in relation if s == specimen and m == method}
                actual = self.result(request)
                self.assertEqual({b["result"] for b in actual["bindings"]}, expected)
                self.assertEqual(actual["status"], "supported" if expected else "undetermined")

    def test_serialization_and_input_are_preserved(self):
        original = deepcopy(self.request)
        roundtrip = json.loads(json.dumps(self.request))
        self.assertEqual(evaluate(self.request), evaluate(roundtrip))
        self.assertEqual(self.request, original)
        self.assertEqual([a["atom"]["args"] for a in roundtrip["ledger"]["assertions"]],
                         [a["atom"]["args"] for a in original["ledger"]["assertions"]])

    def test_projection_keeps_all_values_but_loses_observation_binding(self):
        before = self.result()
        original = deepcopy(self.request["ledger"])
        values = {value for a in original["assertions"] for value in a["atom"]["args"]}
        self.request["package"]["predicates"].append({"ref": "fiction:value@1", "roles": ["value"]})
        self.request["ledger"]["assertions"] = []
        self.request["ledger"]["reviews"] = []
        for index, value in enumerate(sorted(values)):
            a = deepcopy(original["assertions"][0])
            a.update(id=f"flat{index}", atom={"predicate": "fiction:value@1", "args": [value]})
            r = deepcopy(original["reviews"][0])
            r.update(id=f"review{index}", assertion_ref=a["id"])
            self.request["ledger"]["assertions"].append(a)
            self.request["ledger"]["reviews"].append(r)
        after = self.result()
        self.assertEqual({a["atom"]["args"][0] for a in self.request["ledger"]["assertions"]}, values)
        self.assertEqual(before["bindings"], [{"result": "fiction:positive"}])
        self.assertEqual(after["status"], "undetermined")
        self.assertEqual(after["bindings"], [])

    def test_provenance_identifies_exact_observation_and_review(self):
        proof = self.result()["evidence"]
        self.assertEqual(proof, [{"binding": {"result": "fiction:positive"},
                                 "assertion_refs": ["h1"], "review_refs": ["r1"], "definition_refs": []}])

    def test_named_variable_is_shared_within_and_between_patterns(self):
        query = self.request["queries"][0]
        query["atoms"][0]["args"] = [{"var": "same"}, {"var": "same"}, {"var": "m"}, {"var": "r"}]
        self.assertEqual(self.result()["bindings"], [])
        query["atoms"][0]["args"] = [{"var": "e"}, {"var": "s"}, {"var": "m"}, {"var": "r"}]
        second = deepcopy(query["atoms"][0])
        second["args"][1] = "fiction:s2"
        query["atoms"].append(second)
        self.assertEqual(self.result()["bindings"], [{"e": "fiction:e2", "m": "fiction:m2",
                                                    "r": "fiction:negative", "s": "fiction:s2"}])

    def test_duplicate_facts_merge_evidence_without_duplicate_bindings(self):
        a = deepcopy(self.request["ledger"]["assertions"][0]); a["id"] = "h3"
        review = deepcopy(self.request["ledger"]["reviews"][0]); review.update(id="r3", assertion_ref="h3")
        self.request["ledger"]["assertions"].append(a)
        self.request["ledger"]["reviews"].append(review)
        row = self.result()
        self.assertEqual(row["bindings"], [{"result": "fiction:positive"}])
        self.assertEqual(row["evidence"][0]["assertion_refs"], ["h1", "h3"])

    def test_unreviewed_ai_candidate_is_retained_but_not_supported(self):
        self.request["ledger"]["assertions"][0]["origin"]["kind"] = "ai_candidate"
        self.request["ledger"]["reviews"] = self.request["ledger"]["reviews"][1:]
        result = evaluate(self.request)
        self.assertEqual(result["results"][0]["status"], "undetermined")
        self.assertEqual(result["views"][0]["pending_assertions"], ["h1"])
        self.assertIn("h1", result["retained_assertions"])

    def test_future_confirmation_does_not_support_current_view(self):
        self.request["ledger"]["reviews"][0]["recorded_at"] = "2026-01-11T10:00:00Z"
        self.assertEqual(self.result()["status"], "undetermined")

    def test_subject_contexts_are_never_combined(self):
        context = deepcopy(self.request["contexts"][0]); context.update(ref="fiction:family@1", subject_ref="fiction:family:1")
        self.request["contexts"].append(context)
        self.request["ledger"]["assertions"][0]["context_ref"] = context["ref"]
        self.assertEqual(self.result()["status"], "undetermined")

    def test_family_positive_and_patient_negative_are_not_a_conflict(self):
        request = fixture("assertion-revision")["request"]
        family = deepcopy(request["contexts"][0])
        family.update(ref="fiction:family@1", subject_ref="fiction:family:1")
        request["contexts"].append(family)
        first, second = request["ledger"]["assertions"]
        first.update(context_ref=family["ref"], certainty="confirmed")
        first["atom"]["args"] = [family["subject_ref"]]
        second["supersedes"] = []
        request["views"] = request["views"][1:]
        row = self.result(request)
        self.assertEqual(row["status"], "opposed")
        self.assertEqual(row["evidence"][0]["assertion_refs"], ["h2"])

    def test_ground_success_and_exact_budget_boundary(self):
        self.request["ledger"]["assertions"] = self.request["ledger"]["assertions"][:1]
        self.request["ledger"]["reviews"] = self.request["ledger"]["reviews"][:1]
        self.request["queries"] = self.request["queries"][:1]
        self.request["queries"][0]["atoms"][0]["args"][-1] = "fiction:positive"
        self.request["budget"]["max_steps"] = 1
        self.assertEqual(self.result()["bindings"], [{}])

    def test_denial_is_not_derived_from_missing_binding(self):
        self.assertEqual(self.result(index=1)["status"], "undetermined")
        self.request["ledger"]["assertions"][0]["polarity"] = "negative"
        self.request["queries"][0]["atoms"][0]["args"][-1] = "fiction:positive"
        self.assertEqual(self.result()["status"], "opposed")

    def test_conflict_stops_all_queries_in_that_context_with_both_sources(self):
        denial = deepcopy(self.request["ledger"]["assertions"][0]); denial.update(id="h3", polarity="negative")
        review = deepcopy(self.request["ledger"]["reviews"][0]); review.update(id="r3", assertion_ref="h3")
        self.request["ledger"]["assertions"].append(denial)
        self.request["ledger"]["reviews"].append(review)
        row = self.result()
        self.assertEqual(row["status"], "conflict")
        self.assertEqual(row["bindings"], [])
        self.assertEqual(row["evidence"][0]["assertion_refs"], ["h1", "h3"])

    def test_unknown_capability_on_visible_pending_record_blocks_certainty(self):
        self.request["ledger"]["assertions"][1]["required_capabilities"] = ["fiction:unknown-negation@1"]
        self.request["ledger"]["assertions"][1]["certainty"] = "suspected"
        row = self.result()
        self.assertEqual(row["status"], "unassessed")
        self.assertEqual(row["bindings"], [])
        self.assertEqual(row["missing_capabilities"], ["fiction:unknown-negation@1"])

    def test_future_modifier_does_not_affect_historical_view(self):
        a = self.request["ledger"]["assertions"][1]
        a["required_capabilities"] = ["fiction:future@1"]
        a["recorded_at"] = "2026-01-11T10:00:00Z"
        self.assertEqual(self.result()["status"], "supported")

    def test_unrelated_unary_inclusion_keeps_role_query_supported(self):
        package = self.request["package"]
        package["predicates"].extend([{"ref": x, "roles": ["subject"]} for x in ("fiction:A@1", "fiction:B@1")])
        package["inclusions"] = [{"sub": "fiction:A@1", "super": "fiction:B@1"}]
        row = self.result()
        self.assertEqual(row["status"], "supported")
        self.assertEqual(row["reason_codes"], [])

    def test_revision_chain_does_not_resurrect_original(self):
        request = fixture("assertion-revision")["request"]
        third = deepcopy(request["ledger"]["assertions"][1])
        third.update(id="h3", recorded_at="2026-01-12T10:00:00Z", polarity="positive", supersedes=["h2"])
        request["ledger"]["assertions"].append(third)
        review = deepcopy(request["ledger"]["reviews"][1]); review.update(id="r3", assertion_ref="h3", recorded_at="2026-01-12T11:00:00Z")
        request["ledger"]["reviews"].append(review)
        request["views"] = [{"id": "v3", "as_of": "2026-01-12T12:00:00Z", "policy_ref": request["views"][0]["policy_ref"]}]
        result = evaluate(request)
        self.assertEqual(result["views"][0]["superseded_assertions"], ["h1", "h2"])
        self.assertEqual(result["views"][0]["adopted_assertions"], ["h3"])
        self.assertEqual(result["results"][0]["status"], "supported")

    def test_unreviewed_revision_does_not_supersede(self):
        request = fixture("assertion-revision")["request"]
        request["ledger"]["assertions"][0]["certainty"] = "confirmed"
        request["ledger"]["reviews"] = request["ledger"]["reviews"][:1]
        result = evaluate(request)
        self.assertEqual(result["results"][1]["status"], "supported")
        self.assertEqual(result["views"][1]["superseded_assertions"], [])

    def test_required_query_reports_information_need(self):
        self.request["queries"][1]["required"] = True
        self.assertEqual(self.result(index=1)["information_request"], "needs_information")

    def test_zero_and_exhausted_budget_return_no_incomplete_bindings(self):
        self.request["budget"]["max_steps"] = 0
        result = evaluate(self.request)
        self.assertEqual(result["status"], "resource_limit")
        self.assertTrue(all(r["status"] == "unassessed" and not r["bindings"] for r in result["results"]))
        self.request["budget"]["max_steps"] = 1
        self.assertEqual(self.result()["status"], "unassessed")

    def test_binding_overflow_is_not_truncated_success(self):
        package = self.request["package"]
        package["predicates"] = [{"ref": "fiction:item@1", "roles": ["item"]}]
        self.request["ledger"]["assertions"] = []
        self.request["ledger"]["reviews"] = []
        for i in range(33):
            a = deepcopy(fixture()["request"]["ledger"]["assertions"][0])
            a.update(id=f"h{i}", atom={"predicate": "fiction:item@1", "args": [f"fiction:item:{i}"]})
            r = deepcopy(fixture()["request"]["ledger"]["reviews"][0]); r.update(id=f"r{i}", assertion_ref=f"h{i}")
            self.request["ledger"]["assertions"].append(a)
            self.request["ledger"]["reviews"].append(r)
        query = self.request["queries"][0]
        query["atoms"] = [{"predicate": "fiction:item@1", "args": [{"var": var}]} for var in ("x", "y")]
        self.request["queries"] = [query]
        result = evaluate(self.request)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["results"][0]["reason_codes"], ["binding_limit"])
        self.assertEqual(result["results"][0]["bindings"], [])

    def test_order_permutations_do_not_change_semantic_results(self):
        baseline = evaluate(self.request)
        for key in ("assertions", "reviews"):
            self.request["ledger"][key].reverse()
        self.request["queries"].reverse()
        reordered = evaluate(self.request)
        self.assertNotEqual(baseline["input_sha256"], reordered["input_sha256"])
        baseline.pop("input_sha256"); reordered.pop("input_sha256")
        self.assertEqual(baseline, reordered)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.request = fixture()["request"]

    def invalid(self, code):
        result = evaluate(self.request)
        self.assertEqual(result["status"], "invalid_input", result)
        self.assertEqual(result["reason_codes"], [code])

    def test_dependency_hash_and_ownership(self):
        package = deepcopy(self.request["package"])
        package["ref"] = "fiction:dependency@1"
        self.request["dependency_packages"] = [package]
        self.request["package"]["dependencies"] = [{"ref": package["ref"], "sha256": "0" * 64}]
        self.invalid("dependency_hash_mismatch")
        self.request["package"]["dependencies"][0]["sha256"] = digest(package)
        self.invalid("predicate_owner_conflict")
        self.request["package"]["predicates"] = []
        self.assertEqual(evaluate(self.request)["status"], "ok")

    def test_unresolved_dependency_and_redefined_package(self):
        self.request["package"]["dependencies"] = [{"ref": "fiction:absent@1", "sha256": "0" * 64}]
        self.invalid("unresolved_dependency")
        self.request["package"]["dependencies"] = []
        other = deepcopy(self.request["package"]); other["predicates"][0]["roles"].reverse()
        self.request["dependency_packages"] = [other]
        self.invalid("reference_redefined")

    def test_unknown_fields_and_malformed_atoms_are_rejected(self):
        self.request["unexpected"] = True
        self.invalid("unknown_field")
        del self.request["unexpected"]
        self.request["ledger"]["assertions"][0]["atom"]["args"].pop()
        self.invalid("arity_mismatch")

    def test_duplicate_assertion_identifier_is_rejected(self):
        self.request["ledger"]["assertions"][1]["id"] = "h1"
        self.invalid("duplicate_identifier")

    def test_nonhuman_review_is_rejected(self):
        self.request["ledger"]["reviews"][0]["reviewer_kind"] = "ai"
        self.invalid("invalid_review")

    def test_revision_to_another_topic_is_rejected(self):
        request = fixture("assertion-revision")["request"]
        request["ledger"]["assertions"][1]["atom"]["args"] = ["fiction:other-person"]
        result = evaluate(request)
        self.assertEqual(result["reason_codes"], ["invalid_revision"])

    def test_invalid_timestamp_and_boolean_budget(self):
        self.request["views"][0]["as_of"] = "2026-02-30T10:00:00Z"
        self.invalid("invalid_timestamp")
        self.request = fixture()["request"]
        self.request["budget"]["max_steps"] = True
        self.invalid("invalid_step_budget")

    def test_timestamp_digits_must_be_ascii_for_lexical_time_comparison(self):
        self.request["views"][0]["as_of"] = "٢٠٢٦-01-10T12:00:00Z"
        self.invalid("invalid_timestamp")

    def test_python_api_rejects_floats_nonjson_objects_and_cycles(self):
        for value in (1.5, float("nan"), set()):
            with self.subTest(value=repr(value)):
                request = deepcopy(self.request); request["unexpected"] = value
                self.assertEqual(evaluate(request)["status"], "invalid_input")
        request = deepcopy(self.request); request["cycle"] = request
        self.assertEqual(evaluate(request)["status"], "resource_limit")

    def test_invalid_compare_and_unsupported_profile_are_explicit(self):
        compare = {"schema_version": "p0-request-draft-1", "operation": "compare",
                   "before": {}, "after": {}, "view": {}, "queries": [], "budget": {"max_steps": 100}}
        self.assertEqual(evaluate(compare)["reason_codes"], ["missing_field"])
        self.request["package"]["profile"] = "fiction:exists@1"
        self.assertEqual(evaluate(self.request)["status"], "unsupported_profile")


class CliTests(unittest.TestCase):
    def run_cli(self, *args, raw=None):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        return subprocess.run([sys.executable, "-m", "med_dsl", *args], input=raw,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=ROOT)

    def test_fixture_entrypoint_ignores_expected_values(self):
        data = fixture(); data["expected"] = {"deliberately": "not a rule"}
        process = self.run_cli("--fixture", "-", raw=json.dumps(data).encode())
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["results"][0]["bindings"], [{"result": "fiction:positive"}])

    def test_strict_json_and_size_errors_have_structured_exit_status(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.1}', b'\xff', b'[]'):
            with self.subTest(raw=raw):
                process = self.run_cli("-", raw=raw)
                self.assertEqual(process.returncode, 2)
                self.assertEqual(json.loads(process.stdout)["status"], "invalid_input")
        process = self.run_cli("-", raw=b" " * (1024 * 1024 + 1))
        self.assertEqual(process.returncode, 4)
        self.assertEqual(json.loads(process.stdout)["status"], "resource_limit")

    def test_io_failure_invalid_compare_and_unsupported_profile_exit_codes(self):
        self.assertEqual(self.run_cli("does-not-exist.json").returncode, 2)
        process = self.run_cli("--fixture", "examples/p0/definition-extension.json")
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout)["certificate"]["status"], "certified")
        request = {"schema_version": "p0-request-draft-1", "operation": "compare",
                   "before": {}, "after": {}, "view": {}, "queries": [], "budget": {"max_steps": 100}}
        self.assertEqual(self.run_cli("-", raw=json.dumps(request).encode()).returncode, 2)
        self.assertEqual(self.run_cli("--fixture", "examples/p0/unsupported-existence-profile.json").returncode, 3)


if __name__ == "__main__":
    unittest.main()
