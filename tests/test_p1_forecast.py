"""P1-a の有限確率・確認・型境界・打切りを架空資料で検証する。"""

from copy import deepcopy
from fractions import Fraction
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
from med_dsl.forecast import FORECAST_PROFILE, SPEC_SHA256
from med_dsl.validation import digest


def request(name="finite-forecast"):
    return json.loads((ROOT / "examples/p1-a" / (name + ".json")).read_text())["request"]


def rehash(data):
    for entry in data["artifacts"]:
        entry["sha256"] = digest(entry["artifact"])
    return data


def ledger(data):
    return data["report_snapshot"]["ledger"]


def artifact(data):
    return data["artifacts"][0]["artifact"]


def probability(result, index=0):
    answer = result["results"][index]["answer"]
    return Fraction(**answer["probability"])


spec = importlib.util.spec_from_file_location("p1_a_evaluation", ROOT / "scripts/research/evaluate-p1-a.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ForecastMathTests(unittest.TestCase):
    def test_all_finite_event_pairs_against_direct_counting(self):
        # 独立性を仮定せず、等重みの4点上で全256対の積集合を直接数える。
        for left, right in itertools.product(range(16), repeat=2):
            data = request("correlated-forecast")
            a = artifact(data)
            names = [w["ref"] for w in a["worlds"]]
            for w in a["worlds"]:
                w["weight"] = {"numerator": 1, "denominator": 4}
            for event, mask in zip(a["events"], (left, right)):
                event["world_refs"] = [name for i, name in enumerate(names) if mask & (1 << i)]
            data["queries"] = [data["queries"][2]]
            result = evaluate(rehash(data))
            with self.subTest(left=left, right=right):
                self.assertEqual(result["status"], "ok")
                self.assertEqual(probability(result), Fraction((left & right).bit_count(), 4))

    def test_unequal_correlated_worlds_are_not_multiplied(self):
        result = evaluate(request("correlated-forecast"))
        self.assertEqual([probability(result, i) for i in range(3)], [Fraction(3, 5), Fraction(3, 5), Fraction(3, 10)])
        self.assertNotEqual(probability(result, 2), probability(result, 0) * probability(result, 1))

    def test_nonreduced_input_is_reduced_without_rounding(self):
        data = request()
        for w, n in zip(artifact(data)["worlds"], (14, 6)):
            w["weight"] = {"numerator": n, "denominator": 20}
        answer = evaluate(rehash(data))["results"][0]["answer"]
        self.assertEqual(answer["probability"], {"numerator": 7, "denominator": 10})

    def test_63_bit_boundary_is_exact(self):
        data = request()
        denominator = (1 << 63) - 1
        for w, n in zip(artifact(data)["worlds"], (denominator - 1, 1)):
            w["weight"] = {"numerator": n, "denominator": denominator}
        self.assertEqual(probability(evaluate(rehash(data))), Fraction(denominator - 1, denominator))

    def test_empty_and_complete_events_return_canonical_zero_and_one(self):
        for worlds, expected in (([], {"numerator": 0, "denominator": 1}),
                                 (["fiction:wx", "fiction:wn"], {"numerator": 1, "denominator": 1})):
            data = request()
            artifact(data)["events"][0]["world_refs"] = worlds
            result = evaluate(rehash(data))
            self.assertEqual(result["results"][0]["status"], "computed")
            self.assertEqual(result["results"][0]["answer"]["probability"], expected)

    def test_different_models_are_not_averaged(self):
        result = evaluate(request("separate-models"))
        self.assertEqual([probability(result, i) for i in range(2)], [Fraction(7, 10), Fraction(1, 5)])
        self.assertNotEqual(result["results"][0]["answer"]["forecast_ref"], result["results"][1]["answer"]["forecast_ref"])


class ForecastAdoptionTests(unittest.TestCase):
    def test_confirmation_time_certainty_and_polarity_table(self):
        for certainty, polarity, review_time in itertools.product(
                ("confirmed", "suspected"), ("positive", "negative"), (None, "12:00:00", "12:00:01")):
            data = request("probability-one")
            h = ledger(data)["assertions"][0]
            h.update(certainty=certainty, polarity=polarity)
            if review_time is None:
                ledger(data)["reviews"] = []
            else:
                ledger(data)["reviews"][0]["recorded_at"] = "2026-10-18T" + review_time + "Z"
            adopted = certainty == "confirmed" and review_time == "12:00:00"
            expected = ("computed" if polarity == "positive" else "opposed") if adopted else "undetermined"
            result = evaluate(data)
            with self.subTest(certainty=certainty, polarity=polarity, review=review_time):
                self.assertEqual(result["results"][0]["status"], expected)
                if expected != "computed":
                    self.assertIsNone(result["results"][0]["answer"])
                self.assertEqual(h["origin"]["kind"], "ai_candidate")

    def test_future_assertion_is_not_visible_even_with_earlier_review(self):
        data = request()
        ledger(data)["assertions"][0]["recorded_at"] = "2026-10-18T12:00:01Z"
        result = evaluate(data)
        self.assertEqual(result["results"][0]["status"], "undetermined")
        self.assertEqual(result["views"][0]["visible_assertions"], [])

    def test_revision_views_preserve_sources_and_confirmation_evidence(self):
        result = evaluate(request("report-revisions"))
        self.assertEqual([r["status"] for r in result["results"]],
                         ["undetermined", "computed", "computed", "computed", "opposed"])
        self.assertEqual(result["results"][2]["evidence"][0]["assertion_refs"], ["h1", "h2"])
        self.assertEqual(result["results"][2]["evidence"][0]["review_refs"], ["r1", "r2"])
        self.assertEqual(result["views"][4]["superseded_assertions"], ["h1", "h2"])

    def test_conflict_blocks_context_and_retains_both_proofs(self):
        data = request("separate-models")
        h = deepcopy(ledger(data)["assertions"][0])
        h.update(id="h-denial", polarity="negative")
        r = deepcopy(ledger(data)["reviews"][0])
        r.update(id="r-denial", assertion_ref="h-denial")
        ledger(data)["assertions"].append(h)
        ledger(data)["reviews"].append(r)
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]], ["conflict", "conflict"])
        self.assertIsNone(result["results"][0]["answer"])
        conflict = result["results"][1]["conflicts"][0]
        self.assertEqual(conflict["positive"]["assertion_refs"], ["h1"])
        self.assertEqual(conflict["negative"]["assertion_refs"], ["h-denial"])

    def test_unknown_capability_on_superseded_report_still_blocks(self):
        data = request("report-revisions")
        ledger(data)["assertions"][0]["required_capabilities"].append("fiction:unknown@1")
        result = evaluate(data)
        self.assertEqual(result["results"][-1]["status"], "unassessed")
        self.assertEqual(result["results"][-1]["blocking_assertion_refs"], ["h1"])

    def test_unknown_capability_in_another_context_does_not_block(self):
        data = request("separate-models")
        other = deepcopy(data["report_snapshot"]["contexts"][0])
        other["ref"] += ":other"
        data["report_snapshot"]["contexts"].append(other)
        artifact2 = data["artifacts"][1]["artifact"]
        artifact2["context_ref"] = other["ref"]
        ledger(data)["assertions"][1]["context_ref"] = other["ref"]
        ledger(data)["assertions"][1]["required_capabilities"].append("fiction:unknown@1")
        result = evaluate(rehash(data))
        self.assertEqual([r["status"] for r in result["results"]], ["computed", "unassessed"])


class ForecastBoundaryTests(unittest.TestCase):
    def test_forecast_one_does_not_change_clinical_input_or_answer(self):
        clinical = json.loads((ROOT / "examples/p0/ai-unreviewed.json").read_text())["request"]
        before = deepcopy(clinical)
        baseline = evaluate(clinical)
        data = request("probability-one")
        original = deepcopy(data)
        result = evaluate(data)
        self.assertEqual(data, original)
        self.assertEqual(probability(result), 1)
        self.assertEqual(result["results"][0]["answer"]["kind"], "forecast_probability")
        self.assertNotIn("clinical_assertions", result)
        self.assertEqual(clinical, before)
        self.assertEqual(evaluate(clinical), baseline)
        self.assertEqual(baseline["results"][0]["status"], "undetermined")

    def test_caller_mutation_of_result_does_not_change_input(self):
        data = request()
        original = deepcopy(data)
        result = evaluate(data)
        result["results"][0]["answer"]["interval"]["end"] = "changed"
        self.assertEqual(data, original)

    def test_no_clinical_predicate_or_arbitrary_package_is_accepted(self):
        data = request()
        ledger(data)["assertions"][0]["atom"]["predicate"] = "fiction:clinical-X@1"
        self.assertEqual(evaluate(data)["status"], "invalid_input")
        data = request()
        data["package"] = {"profile": FORECAST_PROFILE}
        self.assertEqual(evaluate(data)["reason_codes"], ["unknown_field"])

    def test_subject_context_and_purpose_are_not_merged_implicitly(self):
        for part in ("artifact_subject", "report_subject", "report_context", "purpose"):
            data = request()
            if part == "artifact_subject":
                artifact(data)["subject_ref"] += ":other"
            elif part == "report_subject":
                ledger(data)["assertions"][0]["atom"]["args"][0] += ":other"
            elif part == "report_context":
                ledger(data)["assertions"][0]["context_ref"] += ":other"
            else:
                data["report_snapshot"]["contexts"][0]["purpose"] = "fiction:clinical"
            with self.subTest(part=part):
                self.assertEqual(evaluate(rehash(data))["status"], "invalid_input")

    def test_native_spec_actual_file_is_checked_not_only_client_claim(self):
        with patch("med_dsl.forecast.Path.read_bytes", return_value=b"untrusted specification"):
            result = evaluate(request())
        self.assertEqual(result["reason_codes"], ["native_spec_mismatch"])
        with patch("med_dsl.forecast.Path.read_bytes", side_effect=OSError):
            self.assertEqual(evaluate(request())["reason_codes"], ["native_spec_unavailable"])

    def test_client_cannot_whitelist_unknown_capability(self):
        data = request("unknown-capability")
        data["consumer"]["capabilities"] = ["fiction:unknown-negation@1"]
        self.assertEqual(evaluate(data)["reason_codes"], ["unknown_field"])
        data = request("unknown-capability")
        data["consumer"]["operations"].append("fiction:unknown-negation@1")
        self.assertEqual(evaluate(data)["status"], "unsupported_profile")

    def test_legacy_p0_still_stops_on_forecast_capability(self):
        data = json.loads((ROOT / "examples/p0/ai-human-confirmation.json").read_text())["request"]
        data["ledger"]["assertions"][0]["required_capabilities"] = [FORECAST_PROFILE]
        result = evaluate(data)
        self.assertTrue(all(r["status"] == "unassessed" for r in result["results"]))

    def test_invalid_integer_types_and_interval_are_rejected(self):
        for value in (True, False, 0.5, "1", None, -1):
            data = request()
            artifact(data)["worlds"][0]["weight"]["numerator"] = value
            with self.subTest(value=value):
                self.assertEqual(evaluate(rehash(data))["status"], "invalid_input")
        for end in ("2026-10-18T00:00:00Z", "2026-10-17T00:00:00Z", "2026-10-25T00:00:00+00:00"):
            data = request()
            artifact(data)["interval"]["end"] = end
            self.assertEqual(evaluate(rehash(data))["status"], "invalid_input")

    def test_duplicate_and_cross_artifact_queries_are_rejected(self):
        for name in ("cross-model", "cross-period"):
            self.assertEqual(evaluate(request(name))["reason_codes"], ["unresolved_event"])
        data = request()
        data["queries"][0]["all_of"] *= 2
        self.assertEqual(evaluate(data)["reason_codes"], ["duplicate_reference"])


class ForecastResourceTests(unittest.TestCase):
    def test_64_worlds_events_and_eight_way_intersection_at_the_boundary(self):
        data = request()
        a = artifact(data)
        a["worlds"] = [{"ref": f"fiction:w:{i:02}", "weight": {"numerator": 1, "denominator": 64}}
                       for i in range(64)]
        a["events"] = [{"ref": f"fiction:e:{i:02}", "world_refs": [w["ref"] for w in a["worlds"]]}
                       for i in range(64)]
        data["queries"][0]["all_of"] = [e["ref"] for e in a["events"][:8]]
        result = evaluate(rehash(data))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(probability(result), 1)
        self.assertEqual(result["steps_used"], 646)
        data["queries"][0]["all_of"].append(a["events"][8]["ref"])
        self.assertEqual(evaluate(data)["status"], "resource_limit")
        data["queries"][0]["all_of"].pop()
        a["events"].append({"ref": "fiction:extra", "world_refs": []})
        self.assertEqual(evaluate(rehash(data))["status"], "resource_limit")

    def test_64_artifacts_queries_and_views_have_separate_shared_limits(self):
        for collection in ("artifacts", "queries", "views"):
            data = request()
            original = deepcopy(data[collection][0])
            data[collection] = []
            for i in range(64):
                item = deepcopy(original)
                if collection == "artifacts":
                    if i:
                        item["artifact"]["ref"] += f":{i:02}"
                else:
                    item["id"] += f":{i:02}"
                data[collection].append(item)
            with self.subTest(collection=collection):
                self.assertEqual(evaluate(rehash(data))["status"], "ok")

    def test_every_budget_cut_before_completion_returns_no_partial_number(self):
        for maximum in range(11):
            data = request()
            data["budget"]["max_steps"] = maximum
            result = evaluate(data)
            with self.subTest(maximum=maximum):
                self.assertEqual(result["status"], "resource_limit")
                self.assertEqual(result["steps_used"], maximum)
                self.assertEqual(result["results"][0]["status"], "unassessed")
                self.assertIsNone(result["results"][0]["answer"])
        self.assertEqual(evaluate(request("exact-budget"))["status"], "ok")

    def test_completed_query_survives_shared_budget_exhaustion(self):
        result = evaluate(request("shared-budget"))
        self.assertEqual(result["status"], "resource_limit")
        self.assertEqual(probability(result), Fraction(7, 10))
        self.assertIsNone(result["results"][1]["answer"])
        self.assertEqual(result["incomplete"], [{"view_id": "v1", "query_id": "q2"}])

    def test_shared_budget_across_views_and_normalization(self):
        data = request()
        data["views"].append({**data["views"][0], "id": "v2"})
        data["budget"]["max_steps"] = 13
        result = evaluate(data)
        self.assertEqual([r["status"] for r in result["results"]], ["computed", "unassessed"])
        self.assertIsNone(result["results"][1]["answer"])
        data = request("unnormalized")
        data["budget"]["max_steps"] = 0
        self.assertEqual(evaluate(data)["status"], "resource_limit")
        data["budget"]["max_steps"] = 4
        self.assertEqual(evaluate(data)["reason_codes"], ["weights_not_normalized"])

    def test_order_does_not_change_values_provenance_or_step_count(self):
        data = request("separate-models")
        baseline = evaluate(data)
        for entry in data["artifacts"]:
            entry["artifact"]["worlds"].reverse()
        data["queries"].reverse()
        data["artifacts"].reverse()
        ledger(data)["assertions"].reverse()
        ledger(data)["reviews"].reverse()
        result = evaluate(rehash(data))
        self.assertEqual(result["steps_used"], baseline["steps_used"])
        for left, right in zip(result["results"], baseline["results"]):
            self.assertEqual(left["status"], right["status"])
            self.assertEqual(left["answer"]["probability"], right["answer"]["probability"])
            self.assertEqual(left["evidence"][0]["assertion_refs"], right["evidence"][0]["assertion_refs"])

    def test_count_and_integer_limits_stop_without_rounding(self):
        for collection in ("artifacts", "queries", "views"):
            data = request()
            data[collection] *= 65
            self.assertEqual(evaluate(data)["status"], "resource_limit")
        data = request()
        artifact(data)["worlds"] *= 33
        self.assertEqual(evaluate(rehash(data))["status"], "resource_limit")
        self.assertEqual(evaluate(request("integer-limit"))["reason_codes"], ["rational_integer_limit"])
        for maximum, status in ((True, "invalid_input"), (-1, "invalid_input"), (100001, "resource_limit")):
            data = request()
            data["budget"]["max_steps"] = maximum
            self.assertEqual(evaluate(data)["status"], status)


class ForecastCorpusTests(unittest.TestCase):
    def test_frozen_author_draft_paths_and_input_preservation(self):
        loaded = runner.load_fixtures(ROOT / "examples/p1-a/manifest.json")
        self.assertEqual(len(loaded), 31)
        for entry, data, _ in loaded:
            original = deepcopy(data["request"])
            result = evaluate(data["request"])
            with self.subTest(path=entry["path"]):
                for check in data["expected"]["checks"]:
                    value = result
                    for key in check["path"]:
                        value = value[key]
                    self.assertEqual(digest(value), digest(check["equals"]), check["path"])
                self.assertEqual(data["request"], original)
                self.assertEqual(result, evaluate(original))

    def test_manifest_tampering_fails_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            for path in (ROOT / "examples/p1-a").glob("*.json"):
                (dest / path.name).write_bytes(path.read_bytes())
            (dest / "finite-forecast.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "fixture_hash_or_size_mismatch"):
                runner.load_fixtures(dest / "manifest.json")

    def test_cli_fixture_never_executes_expected_or_design_schema(self):
        data = json.loads((ROOT / "examples/p1-a/finite-forecast.json").read_text())
        data["expected"] = {"status": "arbitrary"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(data))
            process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)],
                                     capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            self.assertEqual(process.returncode, 0)
            self.assertEqual(json.loads(process.stdout), evaluate(data["request"]))
        process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture",
                                  str(ROOT / "examples/p1/finite-forecast.json")],
                                 capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)["reason_codes"], ["invalid_fixture"])


if __name__ == "__main__":
    unittest.main()
