"""S1/S2 の条件、有限モデルの独立参照計算、根拠・停止を検査する。"""

from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.validation import digest


def fixture(name):
    return json.loads((ROOT / "examples/p0" / (name + ".json")).read_text())["request"]


def predicate(name):
    return {"ref": "fiction:" + name + "@1", "roles": ["subject"]}


def add_fact(request, name, subject="a", *, polarity="positive", context=None):
    template = fixture("linked-observations")
    index = len(request["ledger"]["assertions"]) + 1
    assertion = deepcopy(template["ledger"]["assertions"][0])
    assertion.update(id=f"h{index}", atom={"predicate": "fiction:" + name + "@1", "args": ["fiction:" + subject]},
                     polarity=polarity, context_ref=context or request["contexts"][0]["ref"])
    review = deepcopy(template["ledger"]["reviews"][0])
    review.update(id=f"r{index}", assertion_ref=assertion["id"])
    request["ledger"]["assertions"].append(assertion)
    request["ledger"]["reviews"].append(review)


def ask(request, *names):
    request["queries"] = [{"id": f"q{i}", "context_ref": request["contexts"][0]["ref"],
                           "atoms": [{"predicate": "fiction:" + name + "@1", "args": ["fiction:a"]}],
                           "required": False} for i, name in enumerate(names, 1)]


class FixtureTests(unittest.TestCase):
    def test_manifest_hashes_and_all_draft_required_paths(self):
        manifest = json.loads((ROOT / "examples/p0/manifest.json").read_text())
        for entry in manifest["files"]:
            with self.subTest(fixture=entry["path"]):
                raw = (ROOT / "examples/p0" / entry["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])
                self.assertEqual(len(raw), entry["bytes"])
                data = json.loads(raw)
                original = deepcopy(data["request"])
                result = evaluate(data["request"])
                self.assertEqual(data["request"], original)
                for check in data["expected"]["checks"]:
                    actual = result
                    for part in check["path"]:
                        actual = actual[part]
                    self.assertEqual(actual, check["equals"], check["path"])


class CertificateTests(unittest.TestCase):
    def test_scope_pins_theories_and_excludes_new_memberships(self):
        request = fixture("definition-extension")
        certificate = evaluate(request)["certificate"]
        self.assertEqual(certificate["base_sha256"], digest(request["base_package"]))
        self.assertEqual(certificate["extension_sha256"], digest(request["extension"]))
        self.assertEqual(certificate["scope"]["guarantee"], "model_conservative_extension_over_old_signature")
        self.assertIn("new_membership_data", certificate["scope"]["excludes"])

    def test_mixed_s1_s2_chain_can_be_declared_out_of_order(self):
        request = fixture("subtype-extension")
        extension = request["extension"]
        extension["predicates"].append(predicate("M"))
        extension["definitions"].insert(0, {"kind": "defined", "symbol": "fiction:M@1", "all_of": ["fiction:N@1", "fiction:B@1"]})
        result = evaluate(request)["certificate"]
        self.assertEqual(result["status"], "certified")
        self.assertEqual(result["definition_order"], ["fiction:N@1", "fiction:M@1"])

    def test_individual_shared_symbol_certificates_cannot_be_composed(self):
        first = fixture("definition-extension")
        first["extension"]["definitions"][0]["all_of"] = ["fiction:A@1"]
        second = deepcopy(first)
        second["extension"]["ref"] = "fiction:second@1"
        second["extension"]["definitions"] = [{"kind": "subtype", "symbol": "fiction:N@1", "parent": "fiction:B@1"}]
        for request in (first, second):
            self.assertEqual(evaluate(request)["certificate"]["status"], "certified")
        first["extension"]["dependencies"] = [{"ref": second["extension"]["ref"], "sha256": digest(second["extension"])}]
        first["dependency_packages"] = [second["extension"]]
        self.assertEqual(evaluate(first)["reason_codes"], ["predicate_owner_conflict"])

    def test_hidden_dependency_inclusion_is_checked(self):
        request = fixture("definition-extension")
        hidden = {"ref": "fiction:hidden@1", "profile": "p0-positive-1", "predicates": [],
                  "definitions": [], "inclusions": [{"sub": "fiction:A@1", "super": "fiction:B@1"}], "dependencies": []}
        request["extension"]["dependencies"] = [{"ref": hidden["ref"], "sha256": digest(hidden)}]
        request["dependency_packages"] = [hidden]
        result = evaluate(request)["certificate"]
        self.assertEqual(result["status"], "not_certified")
        self.assertEqual(result["reason_codes"], ["additional_inclusions"])
        self.assertIsNone(result["scope"]["guarantee"])

    def test_dependency_new_symbols_are_not_skipped(self):
        request = fixture("definition-extension")
        hidden = {"ref": "fiction:hidden@1", "profile": "p0-positive-1", "predicates": [predicate("M")],
                  "definitions": [], "inclusions": [], "dependencies": []}
        request["extension"]["dependencies"] = [{"ref": hidden["ref"], "sha256": digest(hidden)}]
        request["dependency_packages"] = [hidden]
        result = evaluate(request)["certificate"]
        self.assertEqual(result["introduced"], ["fiction:M@1", "fiction:N@1"])
        self.assertEqual(result["reason_codes"], ["missing_definition"])

    def test_dependency_hash_cannot_be_changed(self):
        request = fixture("definition-extension")
        base = request["base_package"]
        request["extension"]["dependencies"] = [{"ref": base["ref"], "sha256": "0" * 64}]
        self.assertEqual(evaluate(request)["reason_codes"], ["dependency_hash_mismatch"])
        request["extension"]["dependencies"][0]["sha256"] = digest(base)
        self.assertEqual(evaluate(request)["certificate"]["status"], "certified")

    def test_base_is_resolved_without_future_vocabulary(self):
        request = fixture("definition-extension")
        request["base_package"]["inclusions"] = [{"sub": "fiction:A@1", "super": "fiction:N@1"}]
        self.assertEqual(evaluate(request)["reason_codes"], ["unresolved_predicate"])

    def test_old_dependency_symbols_cannot_be_reintroduced(self):
        request = fixture("definition-extension")
        base = deepcopy(request["base_package"])
        base["ref"] = "fiction:old-dependency@1"
        request["base_package"]["predicates"] = []
        request["base_package"]["dependencies"] = [{"ref": base["ref"], "sha256": digest(base)}]
        request["dependency_packages"] = [base]
        request["extension"]["predicates"].append(predicate("A"))
        self.assertEqual(evaluate(request)["reason_codes"], ["predicate_owner_conflict"])

    def test_roles_and_unresolved_definition_are_invalid(self):
        request = fixture("definition-extension")
        request["extension"]["predicates"][0]["roles"] = ["other"]
        self.assertEqual(evaluate(request)["reason_codes"], ["invalid_definition_roles"])
        request = fixture("definition-extension")
        request["extension"]["definitions"][0]["all_of"] = ["fiction:missing@1"]
        self.assertEqual(evaluate(request)["reason_codes"], ["unresolved_predicate"])

    def test_certification_budget_zero_and_mid_graph_never_issue_certificate(self):
        for limit in (0, 1, 2):
            with self.subTest(limit=limit):
                request = fixture("definition-extension")
                request["budget"]["max_steps"] = limit
                result = evaluate(request)
                self.assertEqual(result["status"], "resource_limit")
                self.assertNotIn("certificate", result)

    def test_certified_extensions_preserve_all_old_models_on_two_individuals(self):
        # 独立参照: Horn 閉包を使わず、全解釈の真理値でモデルを列挙。
        for kind in ("defined", "subtype", "mixed"):
            request = fixture("subtype-extension")
            if kind != "subtype":
                request["extension"]["definitions"] = [{"kind": "defined", "symbol": "fiction:N@1", "all_of": ["fiction:A@1", "fiction:B@1"]}]
            if kind == "mixed":
                request["extension"]["predicates"].append(predicate("M"))
                request["extension"]["definitions"].append({"kind": "subtype", "symbol": "fiction:M@1", "parent": "fiction:N@1"})
            self.assertEqual(evaluate(request)["certificate"]["status"], "certified")
            old = sorted(p["ref"] for p in request["base_package"]["predicates"])
            new = sorted(p["ref"] for p in request["extension"]["predicates"])
            all_names = old + new
            def interpretations(names):
                slots = list(itertools.product(names, ("a", "b")))
                for bits in itertools.product((False, True), repeat=len(slots)):
                    yield dict(zip(slots, bits))
            def satisfies(model, packages):
                for package in packages:
                    for person in ("a", "b"):
                        for inc in package["inclusions"]:
                            if model[inc["sub"], person] and not model[inc["super"], person]:
                                return False
                        for d in package["definitions"]:
                            lhs = model[d["symbol"], person]
                            if d["kind"] == "defined":
                                if lhs != all(model[r, person] for r in d["all_of"]):
                                    return False
                            elif lhs and not model[d["parent"], person]:
                                return False
                return True
            def projection(model):
                return tuple(model[name, person] for name in old for person in ("a", "b"))
            old_models = {projection(m) for m in interpretations(old) if satisfies(m, [request["base_package"]])}
            extended = {projection(m) for m in interpretations(all_names) if satisfies(m, [request["base_package"], request["extension"]])}
            self.assertEqual(old_models, extended, kind)


class DefinitionQueryTests(unittest.TestCase):
    def test_query_uses_hashed_dependency_closure_and_resolvable_rule_sources(self):
        certificate_request = fixture("definition-extension")
        base, extension = certificate_request["base_package"], certificate_request["extension"]
        extension["dependencies"] = [{"ref": base["ref"], "sha256": digest(base)}]
        request = fixture("definition-entailment")
        request["package"] = extension
        request["dependency_packages"] = [base]
        result = evaluate(request)
        self.assertEqual(result["results"][0]["status"], "supported")
        sources = {item["ref"]: item for item in result["definition_sources"]}
        for ref in result["results"][0]["evidence"][0]["definition_refs"]:
            source = sources[ref]
            self.assertEqual(source["package_ref"], extension["ref"])
            self.assertEqual(source["package_sha256"], digest(extension))
            self.assertEqual(source["pointer"], "/definitions/0")

    def test_positive_answers_match_all_models_reference(self):
        # 閉包アルゴリズムとは独立に、有限領域の全モデル共通の肯定を求める。
        for fixture_name in ("definition-entailment", "subtype-entailment", "unsafe-entailment"):
            request = fixture(fixture_name)
            names = ["fiction:A@1", "fiction:B@1", "fiction:N@1"]
            package = request["package"]
            for seed_bits in itertools.product((False, True), repeat=3):
                request["ledger"].update(assertions=[], reviews=[])
                for name, present in zip(("A", "B", "N"), seed_bits):
                    if present:
                        add_fact(request, name)
                ask(request, "A", "B", "N")
                models = []
                for bits in itertools.product((False, True), repeat=3):
                    model = dict(zip(names, bits))
                    if any(seed and not value for seed, value in zip(seed_bits, bits)):
                        continue
                    if any(model[i["sub"]] and not model[i["super"]] for i in package["inclusions"]):
                        continue
                    valid = True
                    for d in package["definitions"]:
                        if d["kind"] == "defined":
                            valid &= model[d["symbol"]] == all(model[r] for r in d["all_of"])
                        else:
                            valid &= not model[d["symbol"]] or model[d["parent"]]
                    if valid:
                        models.append(model)
                expected = ["supported" if all(m[name] for m in models) else "undetermined" for name in names]
                result = evaluate(request)
                self.assertEqual(result["status"], "ok")
                self.assertEqual([r["status"] for r in result["results"]], expected, (fixture_name, seed_bits))

    def test_defined_symbol_implies_every_conjunct_with_source(self):
        request = fixture("definition-entailment")
        request["ledger"].update(assertions=[], reviews=[])
        add_fact(request, "N")
        ask(request, "A", "B", "N")
        result = evaluate(request)
        self.assertEqual([r["status"] for r in result["results"]], ["supported"] * 3)
        for row in result["results"][:2]:
            self.assertEqual(row["evidence"][0]["assertion_refs"], ["h1"])
            self.assertEqual(row["evidence"][0]["definition_refs"], [request["package"]["ref"] + "#/definitions/0"])
        self.assertEqual(result["results"][2]["evidence"][0]["definition_refs"], [])
        self.assertEqual(result["definition_sources"][0]["package_sha256"], digest(request["package"]))

    def test_conjunction_requires_same_subject(self):
        request = fixture("definition-entailment")
        request["ledger"]["assertions"][1]["atom"]["args"] = ["fiction:b"]
        self.assertEqual(evaluate(request)["results"][0]["status"], "undetermined")

    def test_conjunction_requires_same_context(self):
        request = fixture("definition-entailment")
        context = deepcopy(request["contexts"][0]); context["ref"] += ":other"
        request["contexts"].append(context)
        request["ledger"]["assertions"][1]["context_ref"] = context["ref"]
        self.assertEqual(evaluate(request)["results"][0]["status"], "undetermined")

    def test_negative_defined_symbol_does_not_trigger_contraposition(self):
        request = fixture("definition-entailment")
        request["ledger"].update(assertions=[], reviews=[])
        add_fact(request, "N", polarity="negative")
        ask(request, "N", "A", "B")
        rows = evaluate(request)["results"]
        self.assertEqual([r["status"] for r in rows], ["opposed", "undetermined", "undetermined"])
        self.assertEqual(rows[0]["evidence"][0]["definition_refs"], [])

    def test_derived_conflict_blocks_whole_context_and_has_both_proofs(self):
        request = fixture("definition-entailment")
        add_fact(request, "N", polarity="negative")
        ask(request, "N", "A")
        rows = evaluate(request)["results"]
        self.assertEqual([r["status"] for r in rows], ["conflict", "conflict"])
        self.assertEqual(rows[0]["evidence"][0]["assertion_refs"], ["h1", "h2", "h3"])
        self.assertEqual(rows[0]["evidence"][0]["review_refs"], ["r1", "r2", "r3"])
        self.assertEqual(len(rows[0]["evidence"][0]["definition_refs"]), 1)

    def test_cyclic_inclusions_terminate_without_circular_evidence(self):
        request = fixture("subtype-entailment")
        request["package"]["inclusions"].append({"sub": "fiction:B@1", "super": "fiction:A@1"})
        ask(request, "A", "B")
        result = evaluate(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"][0]["evidence"][0]["definition_refs"], [])
        self.assertEqual(result["results"][1]["evidence"][0]["definition_refs"], [request["package"]["ref"] + "#/inclusions/0"])

    def test_cyclic_definitions_can_reason_without_being_certified(self):
        request = fixture("definition-entailment")
        cycle = fixture("cyclic-definitions")["extension"]
        request["package"] = cycle
        request["ledger"].update(assertions=[], reviews=[])
        add_fact(request, "N")
        ask(request, "M")
        self.assertEqual(evaluate(request)["results"][0]["status"], "supported")

    def test_unknown_capability_stops_before_definition_inference(self):
        request = fixture("definition-entailment")
        request["ledger"]["assertions"][0]["required_capabilities"] = ["fiction:future@1"]
        request["budget"]["max_steps"] = 1
        result = evaluate(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"][0]["reason_codes"], ["unknown_capability"])
        self.assertEqual(result["retained_assertions"], ["h1", "h2"])

    def test_unconfirmed_and_future_memberships_cannot_trigger_rules(self):
        for change in ("reviews", "recorded_at"):
            request = fixture("membership-added")
            if change == "reviews":
                request["ledger"]["reviews"] = []
            else:
                request["ledger"]["assertions"][0]["recorded_at"] = "2027-01-01T00:00:00Z"
                for review in request["ledger"]["reviews"]:
                    review["recorded_at"] = "2027-01-01T01:00:00Z"
            self.assertEqual([r["status"] for r in evaluate(request)["results"]], ["undetermined"] * 2)

    def test_budget_aborts_incomplete_closure_for_every_query_in_context(self):
        request = fixture("definition-entailment")
        ask(request, "A", "N")
        request["budget"]["max_steps"] = 1
        result = evaluate(request)
        self.assertEqual(result["status"], "resource_limit")
        for row in result["results"]:
            self.assertEqual(row["status"], "unassessed")
            self.assertEqual(row["bindings"], [])
            self.assertEqual(row["evidence"], [])

    def test_exact_closure_plus_query_budget_boundary(self):
        request = fixture("subtype-entailment")
        request["queries"] = request["queries"][:1]
        # A→B の二走査で固定点を確認し、B(a) の照合が一回。
        request["budget"]["max_steps"] = 3
        self.assertEqual(evaluate(request)["results"][0]["status"], "supported")
        request["budget"]["max_steps"] = 2
        self.assertEqual(evaluate(request)["results"][0]["status"], "unassessed")

    def test_multiple_derivations_choose_deterministic_finite_proof(self):
        request = fixture("subtype-entailment")
        request["package"]["inclusions"].append({"sub": "fiction:N@1", "super": "fiction:B@1"})
        add_fact(request, "N")
        ask(request, "B")
        result = evaluate(request)
        evidence = result["results"][0]["evidence"][0]
        self.assertEqual(evidence["assertion_refs"], ["h1"])
        original = deepcopy(request)
        for field in ("assertions", "reviews"):
            request["ledger"][field].reverse()
        repeated = evaluate(request)
        result.pop("input_sha256"); repeated.pop("input_sha256")
        self.assertEqual(result, repeated)
        self.assertEqual(evaluate(original), evaluate(original))


if __name__ == "__main__":
    unittest.main()
