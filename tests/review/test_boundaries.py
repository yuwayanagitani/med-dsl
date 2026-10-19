"""レビュー AI-001 の RV-07：境界値・小さな負例・到達不能な上限。

固定した231テスト・P1の20条件とは別の分母（レビュー系列）。実行は
`python3 -m unittest discover -s tests/review -v`。期待結果は契約・仕様の文言から手で指定した。
"""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.events import EVENT_PROFILE, EVENT_SPEC_SHA256
from med_dsl.handover import HANDOVER_PROFILE, HANDOVER_SPEC_SHA256
from med_dsl.validation import digest

POLICY = "fiction:confirmed-explicit-revision@1"
REL, UNARY = "fiction:O@1", "fiction:U@1"


def request(suite, name):
    return json.loads((ROOT / "examples" / suite / (name + ".json")).read_text())["request"]


def view(as_of="2026-01-02T00:00:00Z"):
    return [{"id": "v1", "as_of": as_of, "policy_ref": POLICY}]


def assertion(i, atom):
    return {"id": f"h{i}", "context_ref": "fiction:c1", "atom": atom, "polarity": "positive", "certainty": "confirmed",
            "recorded_at": "2026-01-01T01:00:00Z", "origin": {"kind": "observed", "ref": f"fiction:o{i}"},
            "supersedes": [], "required_capabilities": []}


def review(i):
    return {"id": f"r{i}", "assertion_ref": f"h{i}", "reviewer_ref": "fiction:rev", "reviewer_kind": "human",
            "recorded_at": "2026-01-01T02:00:00Z", "outcome": "confirmed"}


def source(n_events, n_unary, with_relation=True):
    predicates = [{"ref": UNARY, "roles": ["x"]}]
    atoms = [{"predicate": UNARY, "args": [f"y{j}"]} for j in range(n_unary)]
    if with_relation:
        predicates.insert(0, {"ref": REL, "roles": ["k", "s", "m", "v"]})
        atoms = [{"predicate": REL, "args": [f"k{i}", "s", "m", "v"]} for i in range(n_events)] + atoms
    return {"package": {"ref": "fiction:pkg@1", "profile": "p0-positive-1", "predicates": predicates, "definitions": [],
                        "inclusions": [], "dependencies": []},
            "dependency_packages": [],
            "contexts": [{"ref": "fiction:c1", "subject_ref": "fiction:p1", "effective_at": "2026-01-01T00:00:00Z", "purpose": "fiction:r"}],
            "ledger": {"ref": "fiction:L0", "assertions": [assertion(i, a) for i, a in enumerate(atoms)],
                       "reviews": [review(i) for i in range(len(atoms))]}}


def p0_query(n_a, n_b):
    """A(x) と B(y) の積。binding 数は n_a × n_b。"""
    atoms = [{"predicate": "fiction:A@1", "args": [f"a{i}"]} for i in range(n_a)] + [{"predicate": "fiction:B@1", "args": [f"b{j}"]} for j in range(n_b)]
    data = source(0, 0, with_relation=False)
    data["package"]["predicates"] = [{"ref": "fiction:A@1", "roles": ["x"]}, {"ref": "fiction:B@1", "roles": ["x"]}]
    data["ledger"]["assertions"] = [assertion(i, a) for i, a in enumerate(atoms)]
    data["ledger"]["reviews"] = [review(i) for i in range(len(atoms))]
    return {"schema_version": "p0-request-draft-1", "operation": "query", **data, "views": view(),
            "queries": [{"id": "q1", "context_ref": "fiction:c1", "required": False,
                         "atoms": [{"predicate": "fiction:A@1", "args": [{"var": "x"}]}, {"predicate": "fiction:B@1", "args": [{"var": "y"}]}]}],
            "budget": {"max_steps": 100000}}


def events_consumer(*operations):
    return {"profile": EVENT_PROFILE, "profile_spec_sha256": EVENT_SPEC_SHA256, "operations": list(operations)}


def events_query(n_events, n_unary):
    data = source(n_events, n_unary)
    reified = evaluate({"schema_version": "p1-events-request-draft-1", "operation": "reify_events", "consumer": events_consumer("reify_events"),
                        "budget": {"max_steps": 100000}, "source": data, "relation_ref": REL, "target_ledger_ref": "fiction:L1"})
    assert reified["status"] == "ok", reified
    return {"schema_version": "p1-events-request-draft-1", "operation": "query_events", "consumer": events_consumer("query_events"),
            "budget": {"max_steps": 100000}, "target": reified["target"], "views": view(),
            "queries": [{"id": "q1", "context_ref": "fiction:c1", "kind": "legacy_positive", "required": False,
                         "atoms": [{"predicate": REL, "args": [{"var": "k"}, "s", "m", "v"]}, {"predicate": UNARY, "args": [{"var": "y"}]}]}]}


class P0LimitTests(unittest.TestCase):
    def test_binding_limit_is_exactly_1000(self):
        ok = evaluate(p0_query(8, 125))
        self.assertEqual((ok["status"], ok["results"][0]["status"], len(ok["results"][0]["bindings"])), ("ok", "supported", 1000))
        over = evaluate(p0_query(7, 143))                       # 1001 binding
        self.assertEqual((over["status"], over["reason_codes"], over["results"][0]["status"], over["results"][0]["bindings"]),
                         ("resource_limit", ["binding_limit"], "unassessed", []))

    def test_an_answer_needs_one_step_after_the_closure_even_without_candidates(self):
        data = request("p0", "subtype-entailment")               # A→B の固定点確認に2 step。N には事実がない
        data["queries"] = [q for q in data["queries"] if q["id"] == "q2"]
        data["budget"]["max_steps"] = 2
        short = evaluate(data)
        self.assertEqual((short["status"], short["results"][0]["status"], short["results"][0]["reason_codes"]),
                         ("resource_limit", "unassessed", ["step_limit"]))
        data["budget"]["max_steps"] = 3
        self.assertEqual(evaluate(data)["results"][0]["status"], "undetermined")

    def test_zero_budget_stops_before_start_even_for_an_unknown_capability_context(self):
        data = request("p0", "unknown-capability")
        self.assertEqual(evaluate(deepcopy(data))["results"][0]["reason_codes"], ["unknown_capability"])
        data["budget"]["max_steps"] = 0
        result = evaluate(data)
        self.assertEqual((result["status"], result["results"][0]["status"], result["results"][0]["reason_codes"]),
                         ("resource_limit", "unassessed", ["step_limit"]))

    def test_extension_certification_costs_one_step_even_when_nothing_is_added(self):
        data = request("p0", "definition-extension")
        data["extension"].update(predicates=[], definitions=[])
        data["budget"]["max_steps"] = 0
        zero = evaluate(deepcopy(data))
        self.assertEqual((zero["status"], zero["reason_codes"]), ("resource_limit", ["step_limit"]))
        self.assertNotIn("certificate", zero)
        data["budget"]["max_steps"] = 1
        self.assertEqual(evaluate(data)["certificate"]["status"], "certified")

    def test_a_shorter_derivation_is_preferred_even_when_the_longer_one_is_found_first(self):
        data = source(0, 0, with_relation=False)
        names = ["fiction:A@1", "fiction:B@1", "fiction:H@1", "fiction:Z@1"]
        data["package"]["predicates"] = [{"ref": n, "roles": ["x"]} for n in names]
        data["package"]["inclusions"] = [{"sub": "fiction:A@1", "super": "fiction:B@1"}, {"sub": "fiction:B@1", "super": "fiction:H@1"},
                                         {"sub": "fiction:Z@1", "super": "fiction:H@1"}]
        atoms = [{"predicate": "fiction:A@1", "args": ["a"]}, {"predicate": "fiction:Z@1", "args": ["a"]}]
        data["ledger"]["assertions"] = [assertion(1, atoms[0]), assertion(2, atoms[1])]
        data["ledger"]["reviews"] = [review(1), review(2)]
        asked = {"schema_version": "p0-request-draft-1", "operation": "query", **data, "views": view(), "budget": {"max_steps": 1000},
                 "queries": [{"id": "q1", "context_ref": "fiction:c1", "required": False, "atoms": [{"predicate": "fiction:H@1", "args": ["a"]}]}]}
        evidence = evaluate(asked)["results"][0]["evidence"][0]
        self.assertEqual(evidence["assertion_refs"], ["h2"])
        self.assertEqual(evidence["definition_refs"], ["fiction:pkg@1#/inclusions/2"])

    def test_a_correction_recorded_at_the_same_time_as_its_target_is_invalid(self):
        data = request("p0", "assertion-revision")
        revising = next(a for a in data["ledger"]["assertions"] if a["supersedes"])
        target = next(a for a in data["ledger"]["assertions"] if a["id"] == revising["supersedes"][0])
        revising["recorded_at"] = target["recorded_at"]
        result = evaluate(data)
        self.assertEqual((result["status"], result["reason_codes"]), ("invalid_input", ["invalid_revision"]))


class EventLimitTests(unittest.TestCase):
    def test_projected_binding_limit_is_exactly_1000(self):
        ok = evaluate(events_query(8, 125))
        self.assertEqual((ok["status"], ok["results"][0]["status"], len(ok["results"][0]["bindings"])), ("ok", "supported", 1000))
        over = evaluate(events_query(7, 143))                   # 1001 binding
        self.assertEqual((over["status"], over["reason_codes"], over["results"][0]["status"]), ("resource_limit", ["binding_limit"], "unassessed"))

    def test_intermediate_binding_limit_is_exactly_4096(self):
        over = evaluate(events_query(17, 241))                  # 17 × 241 = 4097 行
        self.assertEqual((over["status"], over["reason_codes"]), ("resource_limit", ["intermediate_binding_limit"]))
        inside = evaluate(events_query(16, 256))                # 16 × 256 = 4096 行は上限内。以後は共通予算が先に尽きる
        self.assertEqual((inside["status"], inside["reason_codes"]), ("resource_limit", ["step_limit"]))

    def test_a_changed_review_time_is_reported_as_history_and_adoption_not_preserved(self):
        data = request("p1-b", "confirmation-times")
        target = data["target"]
        target["ledger"]["reviews"][0]["recorded_at"] = "2026-01-10T10:05:30Z"      # v1（10:05:00）では保留になる
        assertions = []
        for item in target["ledger"]["assertions"]:
            statement = item["statement"]
            atom = ({"predicate": target["relation_ref"], "args": [statement["roles"][r] for r in ("key", "specimen", "method", "value")]}
                    if statement["kind"] == "event_tuple" else statement["atom"])
            assertions.append({**{k: v for k, v in item.items() if k != "statement"}, "atom": atom})
        rebuilt = {k: target[k] for k in ("package", "dependency_packages", "contexts")}
        rebuilt["ledger"] = {"ref": target["source_ledger_ref"], "assertions": assertions, "reviews": target["ledger"]["reviews"]}
        target["source_sha256"] = digest(rebuilt)
        result = evaluate(data)
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["comparison"]["history_matches"], result["comparison"]["adoption_matches"]), (False, False))
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertEqual(result["certificate"]["reason_codes"], ["template_obligations_pending", "history_not_preserved", "adoption_not_preserved"])


class HandoverBoundaryTests(unittest.TestCase):
    def test_a_relation_that_differs_from_the_reified_snapshots_is_refused(self):
        data = request("p1-c", "event-renaming-chain")
        data["source"]["package"]["predicates"].append({"ref": "fiction:other@1", "roles": ["a", "b", "c", "d"]})
        data["relation_ref"] = "fiction:other@1"
        result = evaluate(data)
        self.assertEqual((result["status"], result["reason_codes"]), ("invalid_input", ["relation_mismatch"]))

    def test_reference_scope_is_the_narrow_two_conjunct_existential_rule_only(self):
        # 現行の推論範囲の固定：前提の述語に事実があっても、3連言や関係なしの形は導かない（拡張は別の判断）
        def reference(items):
            rule = {"kind": "forall", "var": "x", "body": {"kind": "implies", "left": {"kind": "atom", "predicate": "A", "args": [{"var": "x"}]},
                    "right": {"kind": "exists", "var": "y", "body": {"kind": "and", "items": items}}}}
            atom = lambda p, *a: {"kind": "atom", "predicate": p, "args": list(a)}
            return {"schema_version": "p1-handover-request-draft-1", "operation": "check_reference_change",
                    "consumer": {"profile": HANDOVER_PROFILE, "profile_spec_sha256": HANDOVER_SPEC_SHA256, "operations": ["check_reference_change"]},
                    "budget": {"max_steps": 100000},
                    "signature": {"predicates": [{"ref": "A", "arity": 1}, {"ref": "B", "arity": 1}, {"ref": "C", "arity": 1}, {"ref": "r", "arity": 2}], "constants": ["a"]},
                    "source": {"theory": [rule], "data": [atom("A", {"const": "a"})]}, "target": {"theory": [rule], "data": [atom("A", {"const": "a"})]},
                    "queries": [{"id": "q1", "formula": {"kind": "exists", "var": "z", "body": atom("B", {"var": "z"})}}],
                    "models": [], "finite_domain_sizes": []}
        atom = lambda p, *a: {"kind": "atom", "predicate": p, "args": list(a)}
        two = [atom("r", {"var": "x"}, {"var": "y"}), atom("B", {"var": "y"})]
        three = two + [atom("C", {"var": "y"})]
        self.assertEqual(evaluate(reference(two))["results"][0]["source"]["status"], "entailed")
        # 前提の述語（A）に事実がなく、別の述語（C）の事実だけがある場合は導かない
        wrong_premise = reference(two)
        wrong_premise["source"]["data"] = [atom("C", {"const": "a"})]
        wrong_premise["target"]["data"] = [atom("C", {"const": "a"})]
        row = evaluate(wrong_premise)["results"][0]["source"]
        self.assertEqual((row["status"], row["entails"], row["proof"]), ("unassessed", None, None))
        row = evaluate(reference(three))["results"][0]["source"]
        self.assertEqual((row["status"], row["entails"], row["proof"]), ("unassessed", None, None))


class ForecastBoundaryTests(unittest.TestCase):
    def test_artifact_subject_must_match_the_report_context_subject(self):
        data = request("p1-a", "finite-forecast")
        entry = data["artifacts"][0]
        entry["artifact"]["subject_ref"] = "fiction:subject:other"
        entry["sha256"] = digest(entry["artifact"])
        result = evaluate(data)
        self.assertEqual((result["status"], result["reason_codes"], result["error_path"]),
                         ("invalid_input", ["forecast_subject_mismatch"], "artifact.subject_ref"))

    def test_the_4096_bit_intermediate_limit_is_unreachable_under_the_input_limits(self):
        def prime(n):
            if n < 2 or n % 2 == 0:
                return n == 2
            d, s = n - 1, 0
            while d % 2 == 0:
                d, s = d // 2, s + 1
            for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
                x = pow(a, d, n)
                if x in (1, n - 1):
                    continue
                for _ in range(s - 1):
                    x = x * x % n
                    if x == n - 1:
                        break
                else:
                    return False
            return True
        primes, candidate = [], (1 << 63) - 1
        while len(primes) < 64:
            if prime(candidate):
                primes.append(candidate)
            candidate -= 2
        worlds = [{"ref": f"w{i}", "weight": {"numerator": 1, "denominator": p}} for i, p in enumerate(primes)]
        # 独立に、1/p の逐次和の最大ビット長を計算する（約分後の分母は素数の積）
        from fractions import Fraction
        total, widest = Fraction(0), 0
        for p in primes:
            total += Fraction(1, p)
            widest = max(widest, total.denominator.bit_length(), (total.numerator * p).bit_length(), (total.denominator * p).bit_length())
        self.assertLess(widest, 4096)
        data = request("p1-a", "finite-forecast")
        artifact = data["artifacts"][0]["artifact"]
        artifact["worlds"] = worlds
        artifact["events"] = [{"ref": "fiction:event:X@1", "world_refs": ["w0"]}]
        data["artifacts"][0]["sha256"] = digest(artifact)
        result = evaluate(data)
        self.assertEqual((result["status"], result["reason_codes"]), ("invalid_input", ["weights_not_normalized"]))


if __name__ == "__main__":
    unittest.main()
