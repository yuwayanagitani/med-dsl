"""事象化の native 経路、`split_roles`（役割を別々の事象から取る既知の誤訳）、鎖の認定を独立オラクルで検査する。

固定した231テスト・P1の20条件とは別の分母（レビュー系列）。実行は
`python3 -m unittest discover -s tests/review -v`。乱数は seed 固定。
"""

from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from med_dsl import evaluate
from med_dsl.events import EVENT_PROFILE, EVENT_SPEC_SHA256, _expand, _restore, _source
from med_dsl.handover import HANDOVER_PROFILE, HANDOVER_SPEC_SHA256, endpoint, scope_hashes
from med_dsl.validation import digest
from reference_oracle import POLICY, REL, bindings_of, evaluate_source, generate, var

CASES = 200


def key(binding):
    return tuple(sorted(binding.items()))


def events_consumer(*operations):
    return {"profile": EVENT_PROFILE, "profile_spec_sha256": EVENT_SPEC_SHA256, "operations": list(operations)}


def handover_consumer(operation):
    return {"profile": HANDOVER_PROFILE, "profile_spec_sha256": HANDOVER_SPEC_SHA256, "operations": [operation]}


def reify(source, ledger_ref="fiction:L1"):
    result = evaluate({"schema_version": "p1-events-request-draft-1", "operation": "reify_events", "consumer": events_consumer("reify_events"),
                       "budget": {"max_steps": 100000}, "source": source, "relation_ref": REL, "target_ledger_ref": ledger_ref})
    assert result["status"] == "ok", result
    return result["target"]


def native(queries):
    return [{**q, "kind": "legacy_positive"} for q in queries]


def generate_mixing(rng):
    """複数の確認済みの四つ組を持ち、別々の四つ組の値を混ぜた問い合わせを含む履歴。役割の取り違えが起きる入力。"""
    source, views, queries = generate(rng)
    ledger = source["ledger"]
    for item in ledger["assertions"]:
        if item["atom"]["predicate"] == REL and rng.random() < 0.9:
            item.update(certainty="confirmed", polarity="positive", context_ref="fiction:c1", required_capabilities=[])
            if not any(r["assertion_ref"] == item["id"] for r in ledger["reviews"]):
                ledger["reviews"].append({"id": f"rx-{item['id']}", "assertion_ref": item["id"], "reviewer_ref": "fiction:rev", "reviewer_kind": "human",
                                          "recorded_at": item["recorded_at"], "outcome": "confirmed"})
    views = [{"id": "v9", "as_of": "2026-01-06T00:00:00Z", "policy_ref": POLICY}] + views
    tuples = [a["atom"]["args"] for a in ledger["assertions"] if a["atom"]["predicate"] == REL]
    if len(tuples) >= 2:
        for i in range(rng.randint(2, 4)):
            first, second = rng.sample(tuples, 2)
            names = iter(["x", "y", "z", "w"])
            args = [var(next(names)) if rng.random() < 0.35 else rng.choice([first[r], second[r]]) for r in range(4)]
            queries.append({"id": f"m{i}", "context_ref": "fiction:c1", "required": False, "atoms": [{"predicate": REL, "args": args}]})
    return source, views, queries


def event_rows(result):
    return {(r["view"], r["query"]): r for r in result["results"]}


class NativeEventQueryTests(unittest.TestCase):
    def test_native_event_answers_equal_the_independent_oracle(self):
        rng = random.Random(1019)
        for _ in range(CASES):
            source, views, queries = generate(rng)
            result = evaluate({"schema_version": "p1-events-request-draft-1", "operation": "query_events", "consumer": events_consumer("query_events"),
                               "budget": {"max_steps": 100000}, "target": reify(source), "views": views, "queries": native(queries)})
            self.assertEqual(result["status"], "ok")
            expected = evaluate_source(source, views, queries)
            for name, row in event_rows(result).items():
                self.assertEqual(row["status"], expected[name][0], name)
                if row["status"] == "supported":
                    self.assertEqual({key(b) for b in row["bindings"]}, expected[name][1], name)
                else:
                    self.assertEqual(row["bindings"], [])


class SplitRolesTests(unittest.TestCase):
    """split_roles は、四役割を別々の事象から取る。正しい翻訳より多くの binding を返し、反例として検出される。"""

    def compare(self, source, views, queries, kind="split_roles"):
        return evaluate({"schema_version": "p1-events-request-draft-1", "operation": "compare_event_handover", "consumer": events_consumer("compare_event_handover"),
                         "budget": {"max_steps": 100000}, "source": source, "relation_ref": REL, "target": reify(source),
                         "views": views, "queries": native(queries), "translation": {"kind": kind}})

    def test_wrong_role_joins_are_found_and_the_result_is_never_certified(self):
        rng = random.Random(2026)
        mixing_cases = counterexamples_seen = limited = 0
        for _ in range(CASES):
            source, views, queries = generate_mixing(rng)
            result = self.compare(source, views, queries)
            if result["status"] == "resource_limit":
                # 四役割を別々の事象にすると行が積で増える。打切りでは認定も反例の断定も出さない
                limited += 1
                self.assertIsNone(result["certificate"])
                self.assertEqual(result["comparison"]["status"], "unassessed")
                continue
            self.assertEqual(result["status"], "ok")
            shared = evaluate_source(source, views, queries)
            split = evaluate_source(source, views, queries, split_roles=True)
            self.assertEqual(result["certificate"]["status"], "not_certified")
            self.assertEqual(result["certificate"]["evidence_level"], "finite_execution_check")
            # 三つの結果が、それぞれ独立オラクルと一致する
            for field, expected in (("source_result", shared), ("correct_target_result", shared), ("target_result", split)):
                for name, row in event_rows(result[field]).items():
                    self.assertEqual(row["status"], expected[name][0], (field, name))
                    self.assertEqual({key(b) for b in row["bindings"]}, bindings_of(expected[name]) if row["status"] == "supported" else set(), (field, name))
            expected_counter = set()
            rows = {(r["view"], r["query"]): r for r in result["comparison"]["results"]}
            for name, row in rows.items():
                old, new = shared[name], split[name]
                if old[0] in ("unassessed", "conflict") or new[0] in ("unassessed", "conflict"):
                    self.assertEqual((row["status"], row["reason_codes"]), ("unassessed", ["incomparable_answers"]))
                    continue
                before, after = bindings_of(old), bindings_of(new)
                self.assertTrue(before <= after, "正しい翻訳の binding は split に残る")
                self.assertEqual({key(b) for b in row["difference"]["added_bindings"]}, after - before)
                self.assertEqual(row["difference"]["removed_bindings"], [])
                if after - before:
                    self.assertEqual(row["status"], "mismatch")
                    expected_counter |= {(name, b) for b in after - before}
            found = {((c["view"], c["query"]), key(c["binding"])) for c in result["comparison"]["counterexamples"]}
            self.assertEqual(found, expected_counter)
            for counter in result["comparison"]["counterexamples"]:
                self.assertEqual((counter["meaning_mode"], counter["source_truth"], counter["correct_target_truth"], counter["incorrect_target_truth"]),
                                 ("truth_in_listed_model", False, False, True))
            self.assertEqual(result["certificate"]["reason_codes"][0], "satisfaction_condition_failed" if found else "unsupported_translation")
            if found:
                mixing_cases += 1
                counterexamples_seen += len(found)
                self.assertEqual(result["comparison"]["status"], "mismatch")
        # 生成器が誤った役割結合を実際に起こしている（検出能力を試している）こと
        self.assertGreater(mixing_cases, 25)
        self.assertGreater(counterexamples_seen, mixing_cases)
        self.assertLess(limited, CASES // 3)

    def test_one_event_cannot_mix_roles_so_split_roles_gives_no_counterexample(self):
        rng = random.Random(8)
        checked = 0
        while checked < 30:
            source, views, queries = generate(rng)
            tuples = [a for a in source["ledger"]["assertions"] if a["atom"]["predicate"] == REL]
            if len(tuples) != 1:
                continue
            result = self.compare(source, views, queries)
            self.assertEqual(result["comparison"]["counterexamples"], [])
            self.assertEqual(result["certificate"]["reason_codes"][0], "unsupported_translation")
            self.assertEqual(result["certificate"]["status"], "not_certified")
            checked += 1

    def test_the_correct_translation_is_never_reported_as_a_counterexample(self):
        rng = random.Random(77)
        for _ in range(80):
            source, views, queries = generate(rng)
            result = self.compare(source, views, queries, kind="shared_event")
            self.assertEqual(result["comparison"]["counterexamples"], [])
            self.assertEqual(result["certificate"]["status"], "not_certified")
            self.assertEqual(result["certificate"]["reason_codes"][0], "template_obligations_pending")
            self.assertNotIn("satisfaction_condition_failed", result["certificate"]["reason_codes"])


class ChainCertificationTests(unittest.TestCase):
    def chain(self, source, views, queries):
        target = reify(source)
        renames = [{"from_ref": h["statement"]["event_ref"], "to_ref": f"urn:test:renamed:{i}"}
                   for i, h in enumerate(h for h in target["ledger"]["assertions"] if h["statement"]["kind"] == "event_tuple")]
        renamed = evaluate({"schema_version": "p1-handover-request-draft-1", "operation": "rename_events", "consumer": handover_consumer("rename_events"),
                            "budget": {"max_steps": 100000}, "target": target, "renames": renames, "target_ledger_ref": "fiction:L2"})
        assert renamed["status"] == "ok", renamed
        final = renamed["target"]
        mid_source, mid_packages = _restore(target)
        end_source, end_packages = _restore(final)
        legacy = native(queries)
        source_scope, event_scope = scope_hashes(views, legacy, REL)
        stages = [{"kind": "event_reification", "source": endpoint(source, source, _source(source, REL)), "target": endpoint(target, mid_source, mid_packages, True),
                   "source_scope_sha256": source_scope, "target_scope_sha256": event_scope},
                  {"kind": "event_rename", "source": endpoint(target, mid_source, mid_packages, True), "target": endpoint(final, end_source, end_packages, True),
                   "source_scope_sha256": event_scope, "target_scope_sha256": event_scope}]
        return {"schema_version": "p1-handover-request-draft-1", "operation": "check_event_chain", "consumer": handover_consumer("check_event_chain"),
                "budget": {"max_steps": 100000}, "source": source, "relation_ref": REL, "intermediate": target, "target": final,
                "renames": renames, "stages": stages, "views": views, "queries": legacy}

    def test_certified_exactly_when_every_answer_is_complete(self):
        rng = random.Random(4242)
        certified = refused = 0
        for _ in range(CASES):
            source, views, queries = generate(rng)
            result = evaluate(self.chain(source, views, queries))
            self.assertEqual(result["status"], "ok")
            statuses = [status for status, _ in evaluate_source(source, views, queries).values()]
            complete = all(s in ("supported", "undetermined", "opposed") for s in statuses)
            self.assertEqual(result["certificate"]["status"], "certified" if complete else "not_certified")
            certified += complete
            refused += not complete
        self.assertGreater(certified, 100)
        self.assertGreater(refused, 10)

    def test_a_voucher_that_claims_the_split_translation_is_refused_even_when_consistent(self):
        rng = random.Random(31)
        source, views, queries = generate(rng)
        request = self.chain(source, views, queries)
        self.assertEqual(evaluate(deepcopy(request))["certificate"]["status"] in ("certified", "not_certified"), True)
        translated = []
        for q in sorted(native(queries), key=lambda q: q["id"]):
            patterns, public = _expand(q, REL, "split_roles")
            translated.append({"id": q["id"], "context_ref": q["context_ref"], "atoms": patterns, "project": sorted(public)})
        forged = digest({"views": views, "queries": translated})
        honest = request["stages"][0]["target_scope_sha256"]
        self.assertNotEqual(forged, honest)
        request["stages"][0]["target_scope_sha256"] = forged
        request["stages"][1]["source_scope_sha256"] = forged
        result = evaluate(request)
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertEqual(result["certificate"]["reason_codes"], ["chain_obligation_failed"])
        failed = [o["name"] for o in result["obligations"] if not o["passed"]]
        self.assertEqual(failed, ["stage_1.target_scope_sha256", "stage_2.source_scope_sha256"])


if __name__ == "__main__":
    unittest.main()
