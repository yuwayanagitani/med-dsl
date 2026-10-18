"""採用・訂正・未知能力の境界を、架空記録と明示的な期待表で検証する。"""

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
from med_dsl.model import PROFILE
from med_dsl.validation import digest


def request(name):
    return json.loads((ROOT / "examples/p0" / (name + ".json")).read_text())["request"]


def append_review(data, assertion_id, recorded_at):
    review = deepcopy(request("assertion-revision")["ledger"]["reviews"][0])
    review.update(id="review:" + assertion_id, assertion_ref=assertion_id, recorded_at=recorded_at)
    data["ledger"]["reviews"].append(review)


class AdoptionTests(unittest.TestCase):
    def test_confirmation_table_for_all_origins_certainties_polarities_and_review_times(self):
        # 方針の期待表: 生成元の違いで確認条件を緩めず、境界時刻を含む。
        for origin, certainty, polarity, review_case in itertools.product(
                ("observed", "judgment", "imported", "ai_candidate"),
                ("confirmed", "suspected"), ("positive", "negative"),
                ("absent", "before", "exact", "future")):
            with self.subTest(origin=origin, certainty=certainty, polarity=polarity, review=review_case):
                data = request("ai-unreviewed")
                assertion = data["ledger"]["assertions"][0]
                assertion.update(certainty=certainty, polarity=polarity)
                assertion["origin"]["kind"] = origin
                if review_case != "absent":
                    times = {"before": "2026-01-10T11:59:59Z", "exact": "2026-01-10T12:00:00Z",
                             "future": "2026-01-10T12:00:01Z"}
                    append_review(data, assertion["id"], times[review_case])
                accepted = certainty == "confirmed" and review_case in ("before", "exact")
                expected = ("supported" if polarity == "positive" else "opposed") if accepted else "undetermined"
                result = evaluate(data)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["results"][0]["status"], expected)
                self.assertEqual(result["views"][0]["adopted_assertions"], ["h1"] if accepted else [])
                self.assertEqual(result["views"][0]["pending_assertions"], [] if accepted else ["h1"])

    def test_ai_source_is_retained_after_separate_human_confirmation(self):
        data = request("ai-human-confirmation")
        original = deepcopy(data)
        result = evaluate(data)
        self.assertEqual([row["status"] for row in result["results"]], ["undetermined", "supported"])
        self.assertEqual(result["results"][1]["evidence"][0]["review_refs"], ["r1"])
        self.assertEqual(data, original)
        self.assertEqual(data["ledger"]["assertions"][0]["origin"]["kind"], "ai_candidate")

    def test_pending_revision_does_not_remove_previously_adopted_fact(self):
        data = request("assertion-revision")
        data["ledger"]["assertions"][0]["certainty"] = "confirmed"
        data["views"][0]["as_of"] = "2026-01-11T10:30:00Z"
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]], ["supported", "opposed"])
        self.assertEqual(result["views"][0]["adopted_assertions"], ["h1"])
        self.assertEqual(result["views"][0]["pending_assertions"], ["h2"])
        self.assertEqual(result["views"][0]["superseded_assertions"], [])

    def test_branching_revisions_require_explicit_resolution_and_do_not_resurrect(self):
        data = request("unresolved-conflict")
        for aid, day, supersedes in (("h3", "11", ["h1"]), ("h4", "12", ["h2", "h3"])):
            a = deepcopy(data["ledger"]["assertions"][0])
            a.update(id=aid, recorded_at=f"2026-01-{day}T10:00:00Z", supersedes=supersedes,
                     change_reason="架空の明示的な訂正")
            data["ledger"]["assertions"].append(a)
            append_review(data, aid, f"2026-01-{day}T11:00:00Z")
            view = deepcopy(data["views"][0]); view.update(id="v" + day, as_of=f"2026-01-{day}T12:00:00Z")
            data["views"].append(view)
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]], ["conflict", "conflict", "supported"])
        self.assertEqual(result["views"][1]["adopted_assertions"], ["h2", "h3"])
        self.assertEqual(result["views"][2]["adopted_assertions"], ["h4"])
        self.assertEqual(result["views"][2]["superseded_assertions"], ["h1", "h2", "h3"])
        self.assertEqual(result["retained_assertions"], ["h1", "h2", "h3", "h4"])

    def test_late_confirmation_of_old_record_does_not_resurrect_it(self):
        data = request("assertion-revision")
        data["ledger"]["assertions"][0]["certainty"] = "confirmed"
        data["ledger"]["reviews"][0]["recorded_at"] = "2026-01-12T11:00:00Z"
        data["views"][1]["as_of"] = "2026-01-12T12:00:00Z"
        result = evaluate(data)
        self.assertEqual(result["results"][1]["status"], "opposed")
        self.assertEqual(result["views"][1]["superseded_assertions"], ["h1"])
        self.assertEqual(result["views"][1]["adopted_assertions"], ["h2"])

    def test_revision_recomputes_closure_for_each_view(self):
        result = evaluate(request("revision-with-definitions"))
        self.assertEqual([r["status"] for r in result["results"]],
                         ["supported", "supported", "opposed", "undetermined"])
        self.assertEqual(result["results"][1]["evidence"][0]["assertion_refs"], ["h1", "h2"])
        self.assertEqual(result["results"][3]["evidence"], [])

    def test_revision_cannot_cross_context_even_with_same_atom(self):
        data = request("assertion-revision")
        context = deepcopy(data["contexts"][0]); context["ref"] += ":other"
        data["contexts"].append(context)
        data["ledger"]["assertions"][1]["context_ref"] = context["ref"]
        self.assertEqual(evaluate(data)["reason_codes"], ["invalid_revision"])


class CapabilityAndConflictTests(unittest.TestCase):
    def test_unknown_blockers_include_every_visible_source_in_sorted_order(self):
        data = request("unknown-capability")
        assertions = data["ledger"]["assertions"]
        assertions[0]["required_capabilities"] = ["fiction:z@1", "fiction:a@1"]
        assertions[1]["required_capabilities"] = ["fiction:z@1"]
        data["ledger"]["assertions"].reverse()
        result = evaluate(data)
        self.assertEqual(result["results"][0]["missing_capabilities"], ["fiction:a@1", "fiction:z@1"])
        self.assertEqual(result["results"][0]["blocking_assertion_refs"], ["h1", "h2"])
        self.assertEqual(result["results"][1]["status"], "supported")

    def test_pending_unknown_meaning_cannot_be_dismissed_as_unused(self):
        data = request("unknown-capability")
        data["ledger"]["assertions"][0]["certainty"] = "suspected"
        result = evaluate(data)
        self.assertEqual(result["views"][0]["pending_assertions"], ["h1"])
        self.assertEqual(result["results"][0]["status"], "unassessed")
        self.assertEqual(result["results"][0]["blocking_assertion_refs"], ["h1"])

    def test_superseded_unknown_meaning_still_requires_its_capability(self):
        data = request("assertion-revision")
        data["ledger"]["assertions"][0]["required_capabilities"] = ["fiction:unknown-revision@1"]
        result = evaluate(data)
        self.assertEqual(result["views"][1]["superseded_assertions"], ["h1"])
        self.assertEqual(result["results"][1]["status"], "unassessed")
        self.assertEqual(result["results"][1]["blocking_assertion_refs"], ["h1"])

    def test_future_unknown_record_does_not_block_historical_view(self):
        data = request("unknown-capability")
        data["ledger"]["assertions"][0]["recorded_at"] = "2026-01-11T10:00:00Z"
        later = deepcopy(data["views"][0]); later.update(id="v2", as_of="2026-01-11T12:00:00Z")
        data["views"].append(later)
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]],
                         ["undetermined", "supported", "unassessed", "supported"])
        self.assertNotIn("blocking_assertion_refs", result["results"][0])

    def test_known_capability_is_understood_but_unreviewed_data_is_not_adopted(self):
        data = request("ai-unreviewed")
        data["ledger"]["assertions"][0]["required_capabilities"] = [PROFILE]
        result = evaluate(data)
        self.assertEqual(result["results"][0]["status"], "undetermined")
        self.assertEqual(result["incomplete"], [])

    def test_unsupported_dependency_profile_stops_entire_request(self):
        data = request("ai-human-confirmation")
        dependency = {"ref": "fiction:exists@1", "profile": "fiction:existential-witness@1",
                      "predicates": [], "definitions": [], "inclusions": [], "dependencies": []}
        data["dependency_packages"] = [dependency]
        data["package"]["dependencies"] = [{"ref": dependency["ref"], "sha256": digest(dependency)}]
        result = evaluate(data)
        self.assertEqual(result["status"], "unsupported_profile")
        self.assertEqual(result["incomplete"], ["request"])
        self.assertNotIn("results", result)

    def test_multiple_conflicts_keep_each_atom_and_polarity_separate(self):
        data = request("unresolved-conflict")
        data["package"]["predicates"].append({"ref": "fiction:another@1", "roles": ["subject"]})
        for aid, polarity in (("h3", "positive"), ("h4", "negative")):
            a = deepcopy(data["ledger"]["assertions"][0]); a.update(id=aid, polarity=polarity)
            a["atom"]["predicate"] = "fiction:another@1"
            data["ledger"]["assertions"].append(a)
            append_review(data, aid, "2026-01-10T11:00:00Z")
        row = evaluate(data)["results"][0]
        self.assertEqual(row["evidence"][0]["assertion_refs"], ["h1", "h2", "h3", "h4"])
        conflicts = {c["atom"]["predicate"]: c for c in row["conflicts"]}
        self.assertEqual(conflicts["fiction:another@1"]["positive_evidence"]["assertion_refs"], ["h3"])
        self.assertEqual(conflicts["fiction:another@1"]["negative_evidence"]["assertion_refs"], ["h4"])
        self.assertEqual(conflicts["fiction:uses_p@1"]["positive_evidence"]["assertion_refs"], ["h1"])
        self.assertEqual(conflicts["fiction:uses_p@1"]["negative_evidence"]["assertion_refs"], ["h2"])

    def test_conflict_is_not_resolved_by_more_positive_sources(self):
        data = request("unresolved-conflict")
        for aid in ("h3", "h4"):
            a = deepcopy(data["ledger"]["assertions"][0]); a.update(id=aid)
            data["ledger"]["assertions"].append(a)
            append_review(data, aid, "2026-01-10T11:00:00Z")
        row = evaluate(data)["results"][0]
        self.assertEqual(row["status"], "conflict")
        self.assertEqual(row["conflicts"][0]["positive_evidence"]["assertion_refs"], ["h1", "h3", "h4"])
        self.assertEqual(row["conflicts"][0]["negative_evidence"]["assertion_refs"], ["h2"])

    def test_derived_conflict_identifies_rule_only_on_positive_side(self):
        row = evaluate(request("derived-conflict"))["results"][0]
        conflict = row["conflicts"][0]
        self.assertEqual(conflict["atom"], {"predicate": "fiction:N@1", "args": ["fiction:a"]})
        self.assertEqual(len(conflict["positive_evidence"]["definition_refs"]), 1)
        self.assertEqual(conflict["negative_evidence"]["definition_refs"], [])


class QueryBoundaryTests(unittest.TestCase):
    def test_context_fields_and_reference_identity_never_imply_a_join(self):
        for field, value in (("subject_ref", "fiction:family"), ("effective_at", "2025-01-10T09:00:00Z"),
                             ("purpose", "fiction:billing"), (None, None)):
            data = request("definition-entailment")
            context = deepcopy(data["contexts"][0]); context["ref"] += ":other"
            if field is not None:
                context[field] = value
            data["contexts"].append(context)
            data["ledger"]["assertions"][1]["context_ref"] = context["ref"]
            self.assertEqual(evaluate(data)["results"][0]["status"], "undetermined", field)

    def test_negative_record_does_not_refute_a_variable_query_or_conjunction(self):
        for mode in ("variable", "conjunction"):
            data = request("negative-defined-symbol")
            query = data["queries"][0]
            if mode == "variable":
                query["atoms"][0]["args"] = [{"var": "subject"}]
            else:
                query["atoms"].append(deepcopy(data["queries"][1]["atoms"][0]))
            row = evaluate(data)["results"][0]
            self.assertEqual(row["status"], "undetermined")
            self.assertEqual(row["evidence"], [])

    def test_required_information_requests_cover_each_non_success_status(self):
        table = (("ai-unreviewed", "undetermined", "needs_information"),
                 ("negative-defined-symbol", "opposed", "needs_information"),
                 ("unresolved-conflict", "conflict", "needs_resolution"),
                 ("unknown-capability", "unassessed", "needs_capability_or_completion"),
                 ("required-method-present", "supported", None))
        for name, status, information in table:
            data = request(name); data["queries"][0]["required"] = True
            row = evaluate(data)["results"][0]
            self.assertEqual(row["status"], status, name)
            if information:
                self.assertEqual(row["information_request"], information, name)
            else:
                self.assertNotIn("information_request", row)

    def test_missing_method_fixture_has_no_recorded_method_to_recover(self):
        data = request("required-method-missing")
        self.assertEqual(data["package"]["predicates"][0]["roles"], ["event", "specimen", "result"])
        self.assertFalse(any(a["atom"]["predicate"] == "fiction:method_known@1" for a in data["ledger"]["assertions"]))
        result = evaluate(data)
        self.assertEqual(result["results"][0]["status"], "undetermined")
        self.assertEqual(result["results"][0]["bindings"], [])

    def test_p22_replay_and_permutation_preserve_results_and_inputs(self):
        first, second = (request("reproducibility-" + name) for name in ("original", "reordered"))
        before = (deepcopy(first), deepcopy(second))
        result1, result2 = evaluate(first), evaluate(second)
        self.assertEqual(evaluate(first), result1)
        self.assertEqual(evaluate(second), result2)
        self.assertEqual((first, second), before)
        self.assertNotEqual(result1.pop("input_sha256"), result2.pop("input_sha256"))
        self.assertEqual(result1, result2)

    def test_p22_permutation_preserves_budget_cutoff_as_well(self):
        for limit in (0, 1, 4):
            results = []
            for name in ("original", "reordered"):
                data = request("reproducibility-" + name); data["budget"]["max_steps"] = limit
                result = evaluate(data); result.pop("input_sha256")
                results.append(result)
            self.assertEqual(results[0], results[1], limit)

    def test_cli_distinguishes_semantic_stops_from_unsupported_profile(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        for name, code, status in (("unknown-capability", 0, "ok"), ("unresolved-conflict", 0, "ok"),
                                   ("unsupported-existence-profile", 3, "unsupported_profile")):
            process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", f"examples/p0/{name}.json"],
                                     capture_output=True, env=env, cwd=ROOT)
            self.assertEqual(process.returncode, code, process.stderr)
            self.assertEqual(json.loads(process.stdout)["status"], status)


if __name__ == "__main__":
    unittest.main()
