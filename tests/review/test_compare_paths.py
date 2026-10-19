"""P0 の compare 経路（喪失・追加・共通・比較不能・根拠・予算の共有）を独立オラクルで検査する。

固定した231テスト・P1の20条件とは別の分母（レビュー系列）。実行は
`python3 -m unittest discover -s tests/review -v`。乱数は seed 固定で、再現できる。
"""

from copy import deepcopy
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from med_dsl import evaluate
from med_dsl.validation import canonical_bytes, digest
from reference_oracle import CONSTS, CTX, REL, TIMES, UNARY, adopted, bindings_of, evaluate_source, generate, var

CASES = 400


def key(binding):
    return tuple(sorted(binding.items()))


def edited(rng, ledger):
    """前の台帳に、削除・確度や符号の変更・新規の追加を加えた後の台帳（前後で支持が重なるようにする）。"""
    kept = [deepcopy(a) for a in ledger["assertions"] if rng.random() > 0.2]
    ids = {a["id"] for a in kept}
    for a in kept:
        a["supersedes"] = [t for t in a["supersedes"] if t in ids]
        if rng.random() < 0.1:
            a["certainty"] = "suspected" if a["certainty"] == "confirmed" else "confirmed"
        if rng.random() < 0.1:
            a["polarity"] = "negative" if a["polarity"] == "positive" else "positive"
    for i in range(rng.randint(0, 2)):
        atom = ({"predicate": REL, "args": [rng.choice(CONSTS[:2]), rng.choice(CONSTS), rng.choice(CONSTS[:2]), rng.choice(CONSTS)]}
                if rng.random() < 0.6 else {"predicate": rng.choice(UNARY), "args": [rng.choice(CONSTS)]})
        kept.append({"id": f"n{i}", "context_ref": rng.choice(CTX), "atom": atom, "polarity": "positive", "certainty": "confirmed",
                     "recorded_at": rng.choice(TIMES[:5]), "origin": {"kind": "observed", "ref": f"fiction:n{i}"},
                     "supersedes": [], "required_capabilities": []})
    ids = {a["id"] for a in kept}
    when = {a["id"]: a["recorded_at"] for a in kept}
    reviews = [deepcopy(r) for r in ledger["reviews"] if r["assertion_ref"] in ids]
    for a in kept:
        if a["id"].startswith("n"):
            reviews.append({"id": f"rn-{a['id']}", "assertion_ref": a["id"], "reviewer_ref": "fiction:rev", "reviewer_kind": "human",
                            "recorded_at": rng.choice([t for t in TIMES if t >= when[a["id"]]]), "outcome": "confirmed"})
    return {"ref": ledger["ref"], "assertions": kept, "reviews": reviews}


def with_conflict(rng, ledger):
    """同じ文脈・同じ atom に、確認済みの肯定と否定を共存させる（衝突の経路を通す）。"""
    ledger = deepcopy(ledger)
    atom = {"predicate": rng.choice(UNARY[:3]), "args": [rng.choice(CONSTS)]}
    ctx = rng.choice(CTX)
    for tag, polarity in (("p", "positive"), ("n", "negative")):
        ident = f"x{tag}{len(ledger['assertions'])}"
        ledger["assertions"].append({"id": ident, "context_ref": ctx, "atom": atom, "polarity": polarity, "certainty": "confirmed",
                                     "recorded_at": TIMES[0], "origin": {"kind": "observed", "ref": "fiction:" + ident},
                                     "supersedes": [], "required_capabilities": []})
        ledger["reviews"].append({"id": "r" + ident, "assertion_ref": ident, "reviewer_ref": "fiction:rev", "reviewer_kind": "human",
                                  "recorded_at": TIMES[1], "outcome": "confirmed"})
    return ledger


def targeted_queries(rng, ledgers, count):
    """台帳にある atom を元に、引数の一部を変数にした問い合わせ（支持される問いが十分に出るように）。"""
    atoms = [a["atom"] for ledger in ledgers for a in ledger["assertions"]]
    names = ["x", "y", "z", "w"]
    queries = []
    for i in range(count):
        chosen = [deepcopy(rng.choice(atoms)) for _ in range(rng.randint(1, 2))]
        for atom in chosen:
            atom["args"] = [var(rng.choice(names)) if rng.random() < 0.5 else value for value in atom["args"]]
        queries.append({"id": f"t{i}", "context_ref": rng.choice(CTX), "atoms": chosen, "required": rng.random() < 0.5})
    return queries


def build(rng, rename_probability=0.3):
    """前後の台帳が異なる比較 request と、各側の（source, queries）。後側は文脈の別名と context_map を持つことがある。"""
    first, views, queries = generate(rng)
    queries = queries + targeted_queries(rng, [first["ledger"]], rng.randint(2, 4))
    second = {"ledger": edited(rng, first["ledger"])} if rng.random() < 0.85 else {"ledger": generate(rng)[0]["ledger"]}
    rename = {c: c + "b" for c in CTX if rng.random() < rename_probability}
    first["ledger"] = with_conflict(rng, first["ledger"]) if rng.random() < 0.15 else first["ledger"]
    second["ledger"] = with_conflict(rng, second["ledger"]) if rng.random() < 0.15 else second["ledger"]
    after_ledger = deepcopy(second["ledger"])
    after_ledger["ref"] = "fiction:L1"
    for item in after_ledger["assertions"]:
        item["context_ref"] = rename.get(item["context_ref"], item["context_ref"])
    after_contexts = [{**c, "ref": rename.get(c["ref"], c["ref"])} for c in first["contexts"]]
    before = {"package": first["package"], "contexts": first["contexts"], "ledger": first["ledger"]}
    after = {"package": first["package"], "contexts": after_contexts, "ledger": after_ledger}
    shuffled = deepcopy(queries)
    rng.shuffle(shuffled)      # 入力の順序に依らず、結果は query ID の順
    request = {"schema_version": "p0-request-draft-1", "operation": "compare", "before": before, "after": after,
               "view": views[0], "queries": shuffled, "budget": {"max_steps": 100000}}
    if rename:
        request["context_map"] = [{"before_ref": k, "after_ref": v} for k, v in rename.items()]
    after_queries = [{**q, "context_ref": rename.get(q["context_ref"], q["context_ref"])} for q in queries]
    return request, (before, queries), (after, after_queries)


def supports(side, view, query, binding, evidence):
    """証拠として挙がった主張・確認だけで、その binding が支持されるか（証拠の十分性）。"""
    chosen = set(evidence["assertion_refs"])
    reviews = set(evidence["review_refs"])
    mini = {"package": side["package"],
            "ledger": {"ref": "fiction:mini",
                       "assertions": [{**a, "supersedes": [], "certainty": "confirmed"} for a in side["ledger"]["assertions"] if a["id"] in chosen],
                       "reviews": [r for r in side["ledger"]["reviews"] if r["id"] in reviews]}}
    answer = evaluate_source(mini, [view], [query])[(view["id"], query["id"])]
    return answer[0] == "supported" and key(binding) in answer[1]


class CompareAgainstOracleTests(unittest.TestCase):
    def check(self, request, before, after):
        result = evaluate(deepcopy(request))
        self.assertEqual(result["status"], "ok", result.get("reason_codes"))
        view = request["view"]
        expected = {"before": evaluate_source(before[0], [view], before[1]), "after": evaluate_source(after[0], [view], after[1])}
        self.assertEqual(result["scope"], "positive_query_bindings")
        self.assertEqual(result["view"], view)
        for side, (snapshot, _) in (("before", before), ("after", after)):
            self.assertEqual(result[side]["snapshot_sha256"], digest(request[side]))
            self.assertEqual(result[side]["ledger_ref"], snapshot["ledger"]["ref"])
            self.assertEqual(result[side]["package_ref"], snapshot["package"]["ref"])
        rows = {r["query"]: r for r in result["results"]}
        self.assertEqual(list(rows), sorted(q["id"] for q in request["queries"]))
        incomparable = []
        after_by_id = {q["id"]: q for q in after[1]}
        for query in request["queries"]:
            after_query = after_by_id[query["id"]]
            row, name = rows[query["id"]], (view["id"], query["id"])
            left, right = expected["before"][name], expected["after"][name]
            self.assertEqual((row["before_status"], row["after_status"]), (left[0], right[0]))
            self.assertEqual((row["before_context_ref"], row["after_context_ref"]), (query["context_ref"], after_query["context_ref"]))
            open_sides = [(s, st) for s, st in (("before", left[0]), ("after", right[0])) if st in ("conflict", "unassessed")]
            if open_sides:
                incomparable.append(query["id"])
                self.assertEqual(row["status"], "incomparable")
                for field in ("lost", "added", "unchanged", "lost_evidence", "added_evidence"):
                    self.assertIsNone(row[field], field)
                for side, status in open_sides:
                    self.assertIn(f"{side}_{status}", row["reason_codes"])
                self.assertEqual(row["reason_codes"], sorted(set(row["reason_codes"])))
                continue
            self.assertEqual(row["status"], "compared")
            self.assertEqual(row["reason_codes"], [])
            old, new = bindings_of(left), bindings_of(right)
            self.assertEqual([key(b) for b in row["lost"]], sorted(old - new))
            self.assertEqual([key(b) for b in row["added"]], sorted(new - old))
            self.assertEqual([key(b) for b in row["unchanged"]], sorted(old & new))
            for field, side, chosen, bindings in (("lost_evidence", "before", before, row["lost"]), ("added_evidence", "after", after, row["added"])):
                self.assertEqual(len(row[field]), len(bindings))
                for entry, binding in zip(row[field], bindings):
                    self.assertEqual(entry["binding"], binding)
                    self.assertEqual(entry["ledger_ref"], chosen[0]["ledger"]["ref"])
                    _, chosen_ids, _ = adopted(chosen[0], view["as_of"])
                    self.assertTrue(set(entry["assertion_refs"]) <= chosen_ids and entry["assertion_refs"], entry)
                    query_for_side = query if side == "before" else after_query
                    self.assertTrue(supports(chosen[0], view, query_for_side, binding, entry), (side, binding, entry))
        self.assertEqual([i["query"] for i in result["incomplete"]], sorted(incomparable))
        return result

    def test_random_histories_give_the_expected_loss_gain_and_incomparability(self):
        rng = random.Random(20261019)
        seen = {"incomparable": 0, "lost": 0, "added": 0, "unchanged": 0, "mapped": 0}
        for _ in range(CASES):
            request, before, after = build(rng)
            result = self.check(request, before, after)
            seen["mapped"] += "context_map" in request
            for row in result["results"]:
                seen["incomparable"] += row["status"] == "incomparable"
                for field in ("lost", "added", "unchanged"):
                    seen[field] += bool(row[field])
        # 生成器が各分岐を実際に通ること（空振りの照合にしない）
        for name, count in seen.items():
            self.assertGreater(count, 5, name)

    def test_swapping_before_and_after_swaps_loss_and_gain(self):
        rng = random.Random(7)
        checked = 0
        for _ in range(60):
            request, _, _ = build(rng, rename_probability=0)
            forward = evaluate(deepcopy(request))
            swapped = deepcopy(request)
            swapped["before"], swapped["after"] = request["after"], request["before"]
            backward = evaluate(swapped)
            for f, b in zip(forward["results"], backward["results"]):
                if f["status"] == "compared":
                    checked += 1
                    self.assertEqual((f["lost"], f["added"], f["unchanged"]), (b["added"], b["lost"], b["unchanged"]))
                else:
                    self.assertEqual(b["status"], "incomparable")
        self.assertGreater(checked, 40)

    def test_the_same_snapshot_on_both_sides_has_no_loss_or_gain(self):
        rng = random.Random(11)
        for _ in range(60):
            request, _, _ = build(rng, rename_probability=0)
            request["after"] = deepcopy(request["before"])
            for row in evaluate(request)["results"]:
                if row["status"] == "compared":
                    self.assertEqual((row["lost"], row["added"]), ([], []))
                else:
                    self.assertEqual(row["status"], "incomparable")


class CompareBudgetTests(unittest.TestCase):
    def test_a_limit_never_turns_into_a_difference_and_completed_rows_stay_exact(self):
        rng = random.Random(99)
        for _ in range(25):
            request, _, _ = build(rng, rename_probability=0)
            full_request = deepcopy(request)
            full_request["budget"]["max_steps"] = 100000
            full = evaluate(full_request)
            full_rows = {r["query"]: r for r in full["results"]}
            for budget in list(range(0, 41)) + [60, 100, 400, 3000]:
                limited = deepcopy(request)
                limited["budget"]["max_steps"] = budget
                result = evaluate(limited)
                self.assertIn(result["status"], ("ok", "resource_limit"))
                for row in result["results"]:
                    if row["status"] == "compared":
                        self.assertEqual(canonical_bytes(row), canonical_bytes(full_rows[row["query"]]), (budget, row["query"]))
                    elif full_rows[row["query"]]["status"] == "compared":
                        # 完全には比較できなかった行は、差分なしにせず、打切りを理由に挙げる
                        self.assertEqual((row["status"], row["lost"], row["added"]), ("incomparable", None, None))
                        self.assertTrue(any("step_limit" in code for code in row["reason_codes"]), (budget, row))
                if result["status"] == "ok":
                    self.assertEqual(canonical_bytes({k: v for k, v in result.items() if k != "input_sha256"}),
                                     canonical_bytes({k: v for k, v in full.items() if k != "input_sha256"}))

    def test_the_budget_is_shared_by_both_sides(self):
        # 左右を別々に数える実装なら、必要な予算は片側の最大に近づく。共有なら両側の合計に近い。
        def minimal(make):
            for budget in range(0, 2000):
                if evaluate(make(budget))["status"] == "ok":
                    return budget
            self.fail("no sufficient budget")

        rng = random.Random(5)
        strict = 0
        for _ in range(100):
            request, before, after = build(rng, rename_probability=0)
            both = minimal(lambda b: {**deepcopy(request), "budget": {"max_steps": b}})
            alone = []
            for side, queries in (before, after):
                alone.append(minimal(lambda b: {"schema_version": "p0-request-draft-1", "operation": "query", "package": side["package"],
                                                "contexts": side["contexts"], "ledger": side["ledger"], "views": [request["view"]],
                                                "queries": queries, "budget": {"max_steps": b}}))
            self.assertGreaterEqual(both, max(alone))
            self.assertLessEqual(both, sum(alone))
            if min(alone) >= 3:
                strict += 1
                self.assertGreater(both, max(alone), alone)
        self.assertGreater(strict, 10)


class CompareInputTests(unittest.TestCase):
    def base(self):
        return build(random.Random(3), rename_probability=0)[0]

    def test_inconsistent_inputs_are_refused_not_compared(self):
        data = self.base()
        data["after"]["ledger"]["ref"] = data["before"]["ledger"]["ref"]
        data["after"]["ledger"]["assertions"].append(deepcopy(data["after"]["ledger"]["assertions"][0]))
        self.assertIn(evaluate(data)["status"], ("invalid_input",))
        data = self.base()
        data["after"]["contexts"][0] = {**data["after"]["contexts"][0], "purpose": "fiction:other"}
        self.assertEqual(evaluate(data)["reason_codes"], ["context_redefined"])
        data = self.base()
        data["after"]["ledger"]["ref"] = data["before"]["ledger"]["ref"]
        if canonical_bytes(data["after"]["ledger"]) != canonical_bytes(data["before"]["ledger"]):
            self.assertEqual(evaluate(data)["reason_codes"], ["ledger_reference_redefined"])


if __name__ == "__main__":
    unittest.main()
