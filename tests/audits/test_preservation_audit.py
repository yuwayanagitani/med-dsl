"""事前監査の参照計算と、誤った認定・欠落の検出を確認する。"""

from copy import deepcopy
import importlib.util
import itertools
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("preservation_audit", ROOT / "scripts/research/audit-preservation.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class PreservationAuditTests(unittest.TestCase):
    def reference(self):
        request = audit.fixture("p1-c", "coverage-countermodel")
        request["source"] = audit.unary_theory(0)
        request["target"] = audit.unary_theory(4)
        request["queries"] = audit.query_formulas()
        request["models"] = [audit.model_entry(a, b) for a, b in itertools.product(range(4), repeat=2)]
        oracle = {entry["id"]: {"valid": {"source": True, "target": bool(a & 1)}, "truth": audit.query_truth(a, b)}
                  for entry, (a, b) in zip(request["models"], itertools.product(range(4), repeat=2))}
        return request, audit.evaluate(request), oracle

    def test_generated_definitions_are_200_distinct_programs(self):
        self.assertEqual(audit.baseline(), audit.BASELINE_MANIFEST_SHA256)
        requests = list(audit.extension_requests())
        self.assertEqual(len(requests), 200)
        self.assertEqual(len({audit.digest(r) for r in requests}), 200)
        self.assertTrue(all(audit.evaluate(r)["certificate"]["status"] == "certified" for r in requests))

    def test_finite_oracle_detects_old_constraint_hidden_in_an_addition(self):
        request = next(audit.extension_requests())
        old, image, _ = audit.extension_image(request, 2)
        self.assertEqual(old, image)
        request["extension"]["inclusions"] = [{"sub": "fiction:A@1", "super": "fiction:B@1"}]
        old, image, _ = audit.extension_image(request, 2)
        self.assertNotEqual(old, image)
        self.assertIn((1, 0), old - image)
        self.assertEqual(audit.evaluate(request)["certificate"]["status"], "not_certified")

    def test_set_truth_distinguishes_empty_intersection_and_subtype(self):
        request = next(audit.extension_requests())
        request["extension"]["definitions"] = [{"kind": "defined", "symbol": "fiction:N@1",
            "all_of": ["fiction:A@1", "fiction:B@1"]}, {"kind": "subtype", "symbol": "fiction:M@1", "parent": "fiction:N@1"}]
        model = {"fiction:A@1": 1, "fiction:B@1": 2, "fiction:N@1": 0, "fiction:M@1": 0}
        self.assertTrue(audit.satisfies(model, request["extension"]))
        model["fiction:M@1"] = 1
        self.assertFalse(audit.satisfies(model, request["extension"]))

    def test_unary_oracle_uses_universal_rules_and_named_fact_separately(self):
        self.assertFalse(audit.unary_valid(1, 1, 0))
        self.assertTrue(audit.unary_valid(1, 0, 0))
        self.assertTrue(audit.unary_valid(4, 1, 0))
        self.assertFalse(audit.query_truth(1, 0)["forall_A"])
        self.assertTrue(audit.query_truth(1, 0)["exists_A"])

    def test_existential_oracle_distinguishes_relation_direction_and_named_witness(self):
        self.assertTrue(audit.existential_valid("A", "B", False, 1, 1, 2, 2))
        self.assertFalse(audit.existential_valid("A", "B", True, 1, 1, 2, 2))
        self.assertFalse(audit.query_truth(1, 2)["B_a"])
        self.assertTrue(audit.query_truth(1, 2)["exists_B"])
        request = audit.fixture("audits", "existential-reversed")
        result = audit.evaluate(request)
        self.assertEqual(result["results"][1]["source"]["status"], "unassessed")
        self.assertIsNone(result["results"][1]["source"]["entails"])
        self.assertEqual(result["results"][0]["source"]["status"], "not_entailed")
        self.assertTrue(next(m for m in result["models"] if m["model_id"] == "m-source")["source_model"])

    def test_false_entailment_and_invalid_countermodel_are_detected(self):
        request, result, oracle = self.reference()
        self.assertEqual(audit.reference_errors(request, result, oracle), [])
        row = next(r for r in result["results"] if r["query_id"] == "A_a")
        row["source"] = {"status": "entailed", "entails": True, "proof": {"kind": "unverified"}, "countermodel_id": None}
        self.assertIn("unsound_or_malformed_entailment", audit.reference_errors(request, result, oracle))
        row["source"] = {"status": "not_entailed", "entails": False, "proof": None, "countermodel_id": "missing"}
        self.assertIn("invalid_countermodel", audit.reference_errors(request, result, oracle))

    def test_all_abstention_missing_rows_and_false_identity_do_not_pass(self):
        request, result, oracle = self.reference()
        changed = deepcopy(result)
        next(r for r in changed["results"] if r["query_id"] == "A_a")["target"] = {
            "status": "unassessed", "entails": None, "proof": None, "countermodel_id": None}
        self.assertIn("asserted_positive_control_failed", audit.reference_errors(request, changed, oracle))
        changed = deepcopy(result)
        changed["results"].pop()
        self.assertEqual(audit.reference_errors(request, changed, oracle), ["missing_or_duplicate_native_rows"])
        result["certificate"]["status"] = "certified"
        self.assertIn("unsupported_identity_certificate", audit.reference_errors(request, result, oracle))

    def test_unknown_is_neither_false_nor_a_countermodel(self):
        request, result, oracle = self.reference()
        row = result["results"][0]["source"]
        row.update(status="unassessed", entails=None, proof=None, countermodel_id=None)
        self.assertEqual(audit.reference_errors(request, result, oracle), [])
        row["entails"] = False
        self.assertIn("unknown_is_not_false", audit.reference_errors(request, result, oracle))


if __name__ == "__main__":
    unittest.main()
