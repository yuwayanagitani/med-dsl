"""比較の方向・状態・根拠・参照・共有上限を架空データで検証する。"""

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


def fixture(name):
    return json.loads((ROOT / "examples/p0" / (name + ".json")).read_text())["request"]


def comparison(left=("a",), right=("b",)):
    data = fixture("conflict-compare")
    template = deepcopy(data["before"]["ledger"]["assertions"][0])
    review = deepcopy(data["before"]["ledger"]["reviews"][0])
    for side, members in (("before", left), ("after", right)):
        ledger = data[side]["ledger"]
        ledger.update(assertions=[], reviews=[])
        for index, member in enumerate(members):
            a = deepcopy(template); a.update(id=f"h{index}")
            a["atom"]["args"] = ["fiction:" + member]
            ledger["assertions"].append(a)
            r = deepcopy(review); r.update(id=f"r{index}", assertion_ref=a["id"])
            ledger["reviews"].append(r)
    data["queries"][0]["atoms"][0]["args"] = [{"var": "subject"}]
    return data


class CompareTests(unittest.TestCase):
    def test_all_pairs_of_small_relations_match_direct_reference_sets(self):
        relations = ((), ("a",), ("b",), ("a", "b"))
        for before, after in itertools.product(relations, repeat=2):
            result = evaluate(comparison(before, after))
            self.assertEqual(result["status"], "ok")
            row = result["results"][0]
            self.assertEqual(row["status"], "compared")
            def bindings(members):
                return [{"subject": "fiction:" + member} for member in sorted(members)]
            self.assertEqual(row["lost"], bindings(set(before) - set(after)))
            self.assertEqual(row["added"], bindings(set(after) - set(before)))
            self.assertEqual(row["unchanged"], bindings(set(before) & set(after)))

    def test_all_status_pairs_distinguish_incomparable_from_empty_difference(self):
        statuses = ("supported", "opposed", "undetermined", "conflict", "unassessed")
        for left, right in itertools.product(statuses, repeat=2):
            data = comparison(("a",), ("a",))
            data["queries"][0]["atoms"][0]["args"] = ["fiction:a"]
            for side, status in (("before", left), ("after", right)):
                ledger = data[side]["ledger"]
                if status == "undetermined":
                    ledger.update(assertions=[], reviews=[])
                elif status == "opposed":
                    ledger["assertions"][0]["polarity"] = "negative"
                elif status == "unassessed":
                    ledger["assertions"][0]["required_capabilities"] = ["fiction:unknown@1"]
                elif status == "conflict":
                    a = deepcopy(ledger["assertions"][0]); a.update(id="denial", polarity="negative")
                    r = deepcopy(ledger["reviews"][0]); r.update(id="denial-review", assertion_ref="denial")
                    ledger["assertions"].append(a); ledger["reviews"].append(r)
            result = evaluate(data)
            self.assertEqual(result["status"], "ok")
            row = result["results"][0]
            self.assertEqual((row["before_status"], row["after_status"]), (left, right))
            if {left, right} & {"conflict", "unassessed"}:
                self.assertEqual(row["status"], "incomparable")
                self.assertIsNone(row["lost"]); self.assertIsNone(row["added"])
                self.assertIsNone(row["lost_evidence"])
                self.assertEqual(len(result["incomplete"]), 1)
            else:
                self.assertEqual(row["status"], "compared")
                self.assertEqual(row["lost"], [{}] if left == "supported" and right != "supported" else [])
                self.assertEqual(row["added"], [{}] if right == "supported" and left != "supported" else [])
                self.assertEqual(result["incomplete"], [])

    def test_direction_reversal_swaps_loss_and_addition(self):
        data = comparison(("a",), ("b",))
        forward = evaluate(data)["results"][0]
        data["before"], data["after"] = data["after"], data["before"]
        backward = evaluate(data)["results"][0]
        self.assertEqual(forward["lost"], backward["added"])
        self.assertEqual(forward["added"], backward["lost"])

    def test_local_proof_ids_are_scoped_to_their_ledger(self):
        result = evaluate(comparison())
        row = result["results"][0]
        self.assertEqual(row["lost_evidence"][0]["assertion_refs"], ["h0"])
        self.assertEqual(row["added_evidence"][0]["assertion_refs"], ["h0"])
        self.assertNotEqual(row["lost_evidence"][0]["ledger_ref"], row["added_evidence"][0]["ledger_ref"])
        self.assertEqual(row["lost_evidence"][0]["ledger_ref"], result["before"]["ledger_ref"])
        self.assertEqual(row["added_evidence"][0]["ledger_ref"], result["after"]["ledger_ref"])

    def test_proof_change_alone_is_not_a_new_supported_binding(self):
        data = comparison(("a",), ("a",))
        data["after"]["ledger"]["assertions"][0]["origin"]["ref"] = "fiction:other-source@1"
        data["after"]["ledger"]["reviews"][0]["id"] = "another-review"
        result = evaluate(data)
        self.assertEqual(result["results"][0]["lost"], [])
        self.assertEqual(result["results"][0]["added"], [])
        self.assertEqual(result["results"][0]["unchanged"], [{"subject": "fiction:a"}])
        self.assertNotEqual(result["before"]["results"][0]["evidence"], result["after"]["results"][0]["evidence"])

    def test_projection_retains_values_but_loses_observation_binding(self):
        data = fixture("projection-compare")
        before_values = {v for a in data["before"]["ledger"]["assertions"] for v in a["atom"]["args"]}
        after_values = {a["atom"]["args"][0] for a in data["after"]["ledger"]["assertions"]}
        self.assertEqual(before_values, after_values)
        result = evaluate(data)
        self.assertEqual(result["results"][0]["lost"], [{"result": "fiction:positive"}])
        self.assertEqual(result["results"][1]["added"], [])

    def test_extra_inclusion_has_traceable_effect_without_renaming_old_predicates(self):
        data = fixture("membership-compare")
        # 同じ語彙で公理だけを版更新する。旧 A から旧 B の支持が増える。
        for side in ("before", "after"):
            data[side]["package"]["inclusions"] = []
            data[side]["ledger"] = deepcopy(data["after"]["ledger"])
            data[side]["ledger"]["ref"] = "fiction:ledger:" + side + "@1"
            data[side]["ledger"]["assertions"][0]["atom"]["predicate"] = "fiction:A@1"
        data["after"]["package"]["ref"] = "fiction:definitions:with-inclusion@1"
        data["after"]["package"]["inclusions"] = [{"sub": "fiction:A@1", "super": "fiction:B@1"}]
        row = evaluate(data)["results"][1]
        self.assertEqual(row["added"], [{}])
        self.assertEqual(row["added_evidence"][0]["definition_refs"], ["fiction:definitions:with-inclusion@1#/inclusions/0"])

    def test_budget_is_shared_across_both_sides(self):
        data = comparison(("a",), ("a",))
        data["budget"]["max_steps"] = 1
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["before"]["results"][0]["status"], "supported")
        self.assertEqual(result["after"]["results"][0]["status"], "unassessed")
        self.assertIsNone(result["results"][0]["lost"])
        data["budget"]["max_steps"] = 2
        self.assertEqual(evaluate(data)["results"][0]["status"], "compared")

    def test_zero_budget_returns_no_partial_difference(self):
        data = comparison(); data["budget"]["max_steps"] = 0
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["results"][0]["status"], "incomparable")
        self.assertIsNone(result["results"][0]["added"])

    def test_completed_comparison_survives_later_budget_stop(self):
        data = comparison((), ("a",))
        second = deepcopy(data["queries"][0]); second["id"] = "q2"
        data["queries"].append(second); data["budget"]["max_steps"] = 1
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["results"][0]["added"], [{"subject": "fiction:a"}])
        self.assertEqual(result["results"][1]["status"], "incomparable")
        self.assertEqual(len(result["incomplete"]), 1)

    def test_binding_limit_cannot_be_reported_as_a_complete_loss(self):
        data = fixture("binding-limit")
        snapshot = {key: data[key] for key in ("package", "contexts", "ledger")}
        before = deepcopy(snapshot); before["ledger"].update(ref="fiction:empty@1", assertions=[], reviews=[])
        compare = {"schema_version": data["schema_version"], "operation": "compare", "before": before,
                   "after": snapshot, "view": data["views"][0], "queries": data["queries"], "budget": data["budget"]}
        result = evaluate(compare)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["after"]["results"][0]["evidence"], [])
        self.assertIsNone(result["results"][0]["added"])
        self.assertIn("after_binding_limit", result["results"][0]["reason_codes"])

    def test_replay_and_input_permutation_preserve_semantic_results(self):
        data = fixture("projection-compare"); original = deepcopy(data)
        result = evaluate(data)
        self.assertEqual(data, original)
        self.assertEqual(evaluate(data), result)
        data["queries"].reverse()
        for side in ("before", "after"):
            data[side]["contexts"].reverse()
            for field in ("assertions", "reviews"):
                data[side]["ledger"][field].reverse()
        reordered = evaluate(data)
        self.assertNotEqual(result.pop("input_sha256"), reordered.pop("input_sha256"))
        for side in ("before", "after"):
            result[side].pop("snapshot_sha256"); reordered[side].pop("snapshot_sha256")
        self.assertEqual(result, reordered)


class CompareValidationTests(unittest.TestCase):
    def invalid(self, data, code):
        result = evaluate(data)
        self.assertEqual(result["status"], "invalid_input", result)
        self.assertEqual(result["reason_codes"], [code])
        self.assertNotIn("results", result)

    def test_context_renaming_requires_explicit_mapping(self):
        data = fixture("mapped-context-compare")
        self.assertEqual(evaluate(data)["status"], "ok")
        del data["context_map"]
        self.invalid(data, "unresolved_context")

    def test_mapping_rejects_subject_effective_time_or_purpose_change(self):
        for field, value in (("subject_ref", "fiction:another-person"), ("effective_at", "2025-01-09T09:00:00Z"),
                             ("purpose", "fiction:billing")):
            data = fixture("mapped-context-compare")
            data["after"]["contexts"][0][field] = value
            self.invalid(data, "context_mismatch")

    def test_duplicate_and_unresolved_context_maps_are_invalid(self):
        data = fixture("mapped-context-compare")
        data["context_map"].append(deepcopy(data["context_map"][0]))
        self.invalid(data, "duplicate_context_mapping")
        for key in ("before_ref", "after_ref"):
            data = fixture("mapped-context-compare"); data["context_map"][0][key] = "fiction:absent@1"
            self.invalid(data, "unresolved_context_mapping")

    def test_explicit_mapping_cannot_collapse_two_contexts(self):
        data = fixture("mapped-context-compare")
        # メタデータが同じでも、二つの異なる文脈参照を合流させない。
        for side in ("before", "after"):
            data[side]["contexts"][1]["subject_ref"] = data[side]["contexts"][0]["subject_ref"]
        data["context_map"][1]["after_ref"] = data["context_map"][0]["after_ref"]
        self.invalid(data, "noninjective_context_mapping")

    def test_mapping_cannot_collide_with_implicit_identity(self):
        data = comparison()
        for side in ("before", "after"):
            c = deepcopy(data[side]["contexts"][0]); c["ref"] = "fiction:another-context@1"
            data[side]["contexts"].append(c)
        data["context_map"] = [{"before_ref": data["before"]["contexts"][0]["ref"], "after_ref": "fiction:another-context@1"}]
        self.invalid(data, "noninjective_context_mapping")

    def test_same_context_reference_cannot_change_metadata(self):
        data = comparison(); data["after"]["contexts"][0]["purpose"] = "fiction:billing"
        self.invalid(data, "context_redefined")

    def test_same_ledger_reference_cannot_name_different_content(self):
        data = comparison(); data["after"]["ledger"]["ref"] = data["before"]["ledger"]["ref"]
        self.invalid(data, "ledger_reference_redefined")

    def test_predicate_roles_are_immutable_across_package_versions(self):
        data = comparison(); data["after"]["package"]["ref"] = "fiction:new-package@1"
        data["after"]["package"]["predicates"][0]["roles"] = ["different-role"]
        self.invalid(data, "predicate_redefined")

    def test_predicate_definition_is_immutable_across_package_versions(self):
        data = fixture("membership-compare")
        data["after"]["package"]["ref"] = "fiction:new-package@1"
        data["after"]["package"]["definitions"][0]["parent"] = "fiction:B@1"
        self.invalid(data, "predicate_redefined")

    def test_query_vocabulary_must_resolve_on_both_sides(self):
        data = comparison(); data["after"]["package"]["ref"] = "fiction:new-package@1"
        data["after"]["package"]["predicates"] = []
        data["after"]["ledger"].update(assertions=[], reviews=[])
        self.invalid(data, "undeclared_predicate")

    def test_both_sides_validate_before_any_execution(self):
        data = comparison(); data["budget"]["max_steps"] = 0
        data["after"]["ledger"]["assertions"][0]["atom"]["args"] = []
        self.invalid(data, "arity_mismatch")

    def test_snapshot_and_mapping_unknown_fields_are_rejected(self):
        data = comparison(); data["after"]["views"] = []
        self.invalid(data, "unknown_field")
        data = fixture("mapped-context-compare"); data["context_map"][0]["confidence"] = True
        self.invalid(data, "unknown_field")

    def test_query_cannot_reference_another_sides_implicit_vocabulary(self):
        data = fixture("projection-compare")
        data["before"]["package"]["ref"] = "fiction:before-subset@1"
        data["before"]["package"]["predicates"] = []
        data["before"]["ledger"].update(assertions=[], reviews=[])
        self.invalid(data, "undeclared_predicate")

    def test_shared_package_registry_checks_hashes_across_snapshots(self):
        data = comparison(); package = deepcopy(data["before"]["package"])
        package.update(ref="fiction:dependency@1", predicates=[])
        data["dependency_packages"] = [package]
        data["after"]["package"]["ref"] = "fiction:after-root@1"
        data["after"]["package"]["dependencies"] = [{"ref": package["ref"], "sha256": "0" * 64}]
        self.invalid(data, "dependency_hash_mismatch")
        data["after"]["package"]["dependencies"][0]["sha256"] = digest(package)
        self.assertEqual(evaluate(data)["status"], "ok")

    def test_definition_budget_covers_union_of_reachable_packages(self):
        data = comparison()
        for side in ("before", "after"):
            data[side]["package"]["ref"] = "fiction:" + side + "@1"
            data[side]["package"]["predicates"].extend(
                {"ref": f"fiction:{side}:{i}@1", "roles": ["subject"]} for i in range(32))
        result = evaluate(data)
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(result["reason_codes"], ["definition_limit"])

    def test_cli_exercises_compare_and_scoped_evidence(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", "examples/p0/projection-compare.json"],
                                 capture_output=True, env=env, cwd=ROOT)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["results"][0]["lost_evidence"][0]["assertion_refs"], ["h1"])


if __name__ == "__main__":
    unittest.main()
