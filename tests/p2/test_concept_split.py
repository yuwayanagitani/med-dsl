"""P2-b：概念の分割（候補集合と情報要求）。X04・X05・X14 と、R6 の義務の検査。

固定した231テスト・P1の20条件・レビュー系列・防護例（p2）とは別の分母（P2-b 系列）。実行は
`python3 -m unittest discover -s tests/p2 -v`。期待は split_oracle.py（個体ごとの k+1 個のモデルの全数列挙）と、
examples/p2-split/ の手で指定した期待。意味の導出は docs/research/23-p2-b-design.md。
"""

from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from med_dsl import evaluate
from med_dsl.split import AXIOMS, SPEC_SHA256, SPLIT_PROFILE, classify
from med_dsl.validation import canonical_bytes, decode_json, digest
import split_oracle as oracle

DIRECTORY = ROOT / "examples/p2-split"
SPLIT_STATUSES = {"inconsistent", "parent_opposed", "no_parent", "open", "narrowed", "single", "asserted"}


def request_of(source, views, split, queries, budget=100000):
    return {"schema_version": "p2-split-request-draft-1", "operation": "query_split",
            "consumer": {"profile": SPLIT_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": ["query_split"]},
            "budget": {"max_steps": budget}, "source": source, "views": views, "split": split, "queries": queries}


def lookup(result, path):
    for key in path:
        if type(result) is dict and type(key) is str and key in result:
            result = result[key]
        elif type(result) is list and type(key) is int and 0 <= key < len(result):
            result = result[key]
        else:
            return False, None
    return True, result


def strip_split_capability(source):
    stripped = deepcopy(source)
    for item in stripped["ledger"]["assertions"]:
        item["required_capabilities"] = [c for c in item["required_capabilities"] if c != oracle.SPLIT_CAPABILITY]
    return stripped


def base_statuses(source, views, vocabulary, context, subject):
    """分割を知らない消費側（P0 の query）が、同じ原子に返す状態。"""
    queries = [{"id": f"q{i}", "context_ref": context, "atoms": [{"predicate": name, "args": [subject]}], "required": False}
               for i, name in enumerate(vocabulary)]
    result = evaluate({"schema_version": "p0-request-draft-1", "operation": "query", **deepcopy(source), "views": views,
                       "queries": queries, "budget": {"max_steps": 100000}})
    return result


class ExhaustiveRuleTests(unittest.TestCase):
    """R6-3：規則による計算（split.classify）と、モデルの全数列挙（オラクル）の一致。各原子が {なし, 肯定, 否定} の全組。"""

    def test_rules_agree_with_the_enumeration_for_every_assignment(self):
        counts = {}
        for k in (2, 3, 4, 5):
            parts = oracle.parts_of(k)
            names = [oracle.PARENT, *parts]
            for marks in itertools.product(("none", "pos", "neg"), repeat=len(names)):
                pos = {n for n, m in zip(names, marks) if m == "pos"}
                neg = {n for n, m in zip(names, marks) if m == "neg"}
                status, candidates, excluded, derived = classify(oracle.PARENT, parts, oracle.PARENT in pos, oracle.PARENT in neg,
                                                                 pos & set(parts), neg & set(parts))
                found = oracle.models(oracle.PARENT, parts, pos, neg)
                if not found:
                    want = ("inconsistent", [], False)
                elif found == [None]:
                    want = ("parent_opposed", [], False)
                elif None in found:
                    want = ("no_parent", [], False)
                elif len(found) == 1:
                    want = ("asserted" if found[0] in pos else "single", list(found), oracle.PARENT not in pos)
                else:
                    want = ("open" if len(found) == k else "narrowed", list(found), False)
                with self.subTest(k=k, marks=marks):
                    self.assertEqual((status, candidates, derived), want)
                counts[status] = counts.get(status, 0) + 1
        # 七つの状態がすべて実際に現れる（空振りでない）
        self.assertEqual(set(counts), SPLIT_STATUSES)

    def test_old_data_never_makes_the_split_inconsistent(self):
        """R6-2：部分の原子を含まない状態（旧データ）は、公理を加えても矛盾しない。"""
        for k in (2, 3, 4, 5):
            parts = oracle.parts_of(k)
            for parent_mark in ("none", "pos", "neg"):
                pos = {oracle.PARENT} if parent_mark == "pos" else set()
                neg = {oracle.PARENT} if parent_mark == "neg" else set()
                status = classify(oracle.PARENT, parts, bool(pos), bool(neg), set(), set())[0]
                with self.subTest(k=k, parent=parent_mark):
                    self.assertIn(status, {"open", "parent_opposed", "no_parent"})

    def test_every_small_old_model_expands_to_a_model_of_the_axioms(self):
        """R6-2：旧い任意のモデル（P の解釈）は、Q1 := P、他 := ∅ で公理を満たす拡張を持つ。台集合 3 個までを全数検査する。"""
        for size in range(0, 4):
            domain = list(range(size))
            for bits in itertools.product((False, True), repeat=size):
                parent = {x for x, b in zip(domain, bits) if b}
                for k in (2, 3, 4):
                    parts = [parent] + [set() for _ in range(k - 1)]
                    for x in domain:
                        true = [x in q for q in parts]
                        self.assertTrue(all(not t or x in parent for t in true))          # A1
                        self.assertTrue(x not in parent or any(true))                      # A2
                        self.assertLessEqual(sum(true), 1)                                  # A3


class DifferentialTests(unittest.TestCase):
    """乱数で作った台帳（確認の有無・疑い・AI 候補・訂正・能力・複数の参照時点・文脈）で、実装とオラクルを照合する。"""

    CASES = 600

    @classmethod
    def setUpClass(cls):
        rng = random.Random(20260519)
        cls.cases = [oracle.generate(rng) for _ in range(cls.CASES)]
        cls.rows = []
        for source, views, split, queries in cls.cases:
            result = evaluate(request_of(deepcopy(source), views, split, queries))
            cls.rows.append(result)

    def test_every_row_equals_the_enumeration_oracle(self):
        seen = {"blocked": 0, "computed": 0}
        statuses, reasons = set(), set()
        for (source, views, split, queries), result in zip(self.cases, self.rows):
            self.assertEqual(result["status"], "ok", result)
            ordered = [(v, q) for v in sorted(views, key=lambda x: x["id"]) for q in sorted(queries, key=lambda x: x["id"])]
            self.assertEqual(len(result["results"]), len(ordered))
            for row, (view, query) in zip(result["results"], ordered):
                want = oracle.expected_row(source, view, split, query)
                seen[want[0]] += 1
                with self.subTest(view=view["id"], query=query["id"]):
                    self.assertEqual((row["view"], row["query"]), (view["id"], query["id"]))
                    if want[0] == "blocked":
                        self.assertEqual((row["status"], row["reason_codes"]), ("blocked", [want[1]]))
                        self.assertIsNone(row["split"])
                        reasons.add(want[1])
                        if want[1] == "unknown_capability":
                            self.assertEqual(row["blocking_assertion_refs"], want[2])
                        continue
                    _, status, candidates, derived, base = want
                    self.assertEqual(row["status"], "computed")
                    self.assertEqual(row["split"]["status"], status)
                    self.assertEqual(row["split"]["candidates"], candidates)
                    self.assertEqual(row["split"]["parent_derived"], derived)
                    self.assertEqual(row["base"]["parent"], base[split["parent"]])
                    self.assertEqual(row["base"]["parts"], {q: base[q] for q in split["parts"]})
                    statuses.add(status)
        # 分母が空振りでない：両方の行と、七つの状態が実際に現れる
        self.assertGreater(seen["blocked"], 50)
        self.assertGreater(seen["computed"], 1000)
        self.assertEqual(statuses, SPLIT_STATUSES)
        self.assertEqual(reasons, {"unknown_capability", "unresolved_conflict"})

    def test_base_block_equals_the_p0_query_on_a_ledger_without_the_split_capability(self):
        """X05：行の `base` は、分割を知らない消費側（P0 の query）が同じ原子に返す状態と一致する。"""
        compared = 0
        for (source, views, split, queries), result in zip(self.cases, self.rows):
            stripped = strip_split_capability(source)
            vocabulary = [split["parent"], *sorted(split["parts"])]
            for row in result["results"]:
                if row["status"] != "computed":
                    continue
                view = next(v for v in views if v["id"] == row["view"])
                base = base_statuses(stripped, [view], vocabulary, row["context_ref"], row["subject"])
                got = {r["query"]: r["status"] for r in base["results"]}
                with self.subTest(view=row["view"], query=row["query"]):
                    self.assertEqual([got[f"q{i}"] for i in range(len(vocabulary))],
                                     [row["base"]["parent"], *(row["base"]["parts"][q] for q in sorted(split["parts"]))])
                compared += 1
        self.assertGreater(compared, 1000)

    def test_no_split_status_is_ever_a_base_status_and_nothing_is_converted(self):
        """X05：split.status の語彙は基底の状態の語彙と互いに素。基底の状態の語は `base` の下にしか現れない。converted_to_base は常に偽。"""
        self.assertTrue(SPLIT_STATUSES.isdisjoint(oracle.BASE_STATUSES))

        def walk(value, path):
            if isinstance(value, dict):
                for key, item in value.items():
                    yield from walk(item, path + (key,))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from walk(item, path + (index,))
            else:
                yield path, value

        for result in self.rows:
            for row in result["results"]:
                self.assertIs(row["converted_to_base"], False)
                self.assertEqual(row["answer_kind"], "candidate_set")
            for path, value in walk(result, ()):
                if value in oracle.BASE_STATUSES and path[0] == "results":
                    self.assertEqual(path[2], "base", path)

    def test_the_input_is_preserved_and_the_result_is_deterministic(self):
        """I6・I7：入力は変更されず、同じ入力から同じ結果（正規化 hash が同じ）。"""
        for source, views, split, queries in self.cases[:200]:
            request = request_of(source, views, split, queries)
            before = canonical_bytes(request)
            first = canonical_bytes(evaluate(request))
            self.assertEqual(canonical_bytes(request), before)
            self.assertEqual(canonical_bytes(evaluate(deepcopy(request))), first)

    def test_part_order_and_query_order_do_not_change_the_result(self):
        for source, views, split, queries in self.cases[:150]:
            plain = evaluate(request_of(deepcopy(source), views, split, queries))
            shuffled_split = {"parent": split["parent"], "parts": list(reversed(split["parts"]))}
            other = evaluate(request_of(deepcopy(source), list(reversed(views)), shuffled_split, list(reversed(queries))))
            for result in (plain, other):
                result.pop("input_sha256")                                                  # 入力の並びが違えば入力の hash は違う
            self.assertEqual(canonical_bytes(plain), canonical_bytes(other))

    def test_every_candidate_offered_in_a_request_can_actually_be_asserted(self):
        """R6-6：情報要求が求める候補は、その部分が肯定されたとき `asserted` になる（実現しない主張を求めない）。"""
        checked = 0
        for (source, views, split, queries), result in zip(self.cases, self.rows):
            for row in result["results"]:
                for request in row["information_requests"]:
                    if request["kind"] != "confirm_part":
                        continue
                    for part in request["candidate_parts"]:
                        view = next(v for v in views if v["id"] == row["view"])
                        _, _, adopted = oracle.adoption(source, view)
                        items = {h["id"]: h for h in source["ledger"]["assertions"]}
                        vocabulary = {split["parent"], *split["parts"]}
                        pos = {items[k]["atom"]["predicate"] for k in adopted if items[k]["context_ref"] == row["context_ref"]
                               and items[k]["polarity"] == "positive" and items[k]["atom"]["args"] == [row["subject"]]} & vocabulary
                        neg = {items[k]["atom"]["predicate"] for k in adopted if items[k]["context_ref"] == row["context_ref"]
                               and items[k]["polarity"] == "negative" and items[k]["atom"]["args"] == [row["subject"]]} & vocabulary
                        found = oracle.models(split["parent"], sorted(split["parts"]), pos | {part}, neg)
                        self.assertEqual(found, [part])
                        checked += 1
        self.assertGreater(checked, 200)

    def test_conclusions_name_the_axioms_they_rely_on(self):
        """R6-4：公理に頼る結論は、頼る公理を挙げる。採用された主張だけで言える状態（no_parent）は挙げない。"""
        for result in self.rows:
            for row in result["results"]:
                if row["status"] != "computed":
                    continue
                derivation = row["split"]["derivation"]
                self.assertTrue(set(derivation) <= set(AXIOMS))
                if row["split"]["status"] == "no_parent":
                    self.assertEqual(derivation, [])
                if row["split"]["status"] in ("open", "narrowed", "single"):
                    self.assertIn("A2_coverage", derivation)
                if row["split"]["parent_derived"]:
                    self.assertIn("A1_subsumption", derivation)

    def test_old_data_only_ledgers_never_produce_a_violation(self):
        """R6-2：部分の原子を含まない台帳（旧データ）では、`inconsistent` は現れない。"""
        rng = random.Random(77)
        total = 0
        for _ in range(300):
            source, views, split, queries = oracle.generate(rng, with_parts=False)
            result = evaluate(request_of(source, views, split, queries))
            for row in result["results"]:
                if row["status"] == "computed":
                    total += 1
                    self.assertIn(row["split"]["status"], {"open", "parent_opposed", "no_parent"})
        self.assertGreater(total, 300)


class DenseDifferentialTests(unittest.TestCase):
    """稀な状態（single・narrowed・inconsistent など）を採用との結合を通して十分な件数で照合する。"""

    def test_dense_ledgers_agree_with_the_oracle_and_reach_every_status_often(self):
        rng = random.Random(8128)
        counts = {}
        for _ in range(2500):
            source, views, split, queries = oracle.generate_dense(rng)
            result = evaluate(request_of(deepcopy(source), views, split, queries))
            row = result["results"][0]
            want = oracle.expected_row(source, views[0], split, queries[0])
            if want[0] == "blocked":
                self.assertEqual((row["status"], row["reason_codes"]), ("blocked", [want[1]]))
                counts[want[1]] = counts.get(want[1], 0) + 1
                continue
            _, status, candidates, derived, base = want
            self.assertEqual((row["split"]["status"], row["split"]["candidates"], row["split"]["parent_derived"]), (status, candidates, derived))
            self.assertEqual(row["base"]["parent"], base[split["parent"]])
            self.assertEqual(row["base"]["parts"], {q: base[q] for q in sorted(split["parts"])})
            counts[status] = counts.get(status, 0) + 1
        for name in SPLIT_STATUSES:
            self.assertGreaterEqual(counts.get(name, 0), 25, (name, counts))


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = decode_json((DIRECTORY / "manifest.json").read_bytes())
        cls.items = [(e, decode_json((DIRECTORY / e["path"]).read_bytes())) for e in cls.manifest["files"]]

    def test_the_manifest_matches_the_files(self):
        self.assertEqual((self.manifest["schema_version"], self.manifest["status"], self.manifest["independent_review"],
                          self.manifest["evaluation_frozen"]), ("p2-split-manifest-draft-1", "author_draft", False, False))
        self.assertEqual((self.manifest["profile"], self.manifest["profile_spec_sha256"]), (SPLIT_PROFILE, SPEC_SHA256))
        self.assertEqual({e["path"] for e in self.manifest["files"]}, {p.name for p in DIRECTORY.glob("*.json")} - {"manifest.json"})
        self.assertEqual([e["fixture_id"] for e in self.manifest["files"]], [f"SP{i:02}" for i in range(1, len(self.items) + 1)])
        for entry, data in self.items:
            raw = (DIRECTORY / entry["path"]).read_bytes()
            with self.subTest(fixture=entry["fixture_id"]):
                self.assertEqual((entry["bytes"], entry["sha256"]), (len(raw), hashlib.sha256(raw).hexdigest()))
                self.assertEqual((data["fixture_id"], data["fictional"], data["review_state"], data["extension"]),
                                 (entry["fixture_id"], True, "author_draft", "p2-concept-split"))
                self.assertIn(data["kind"], ("refusal", "non_conversion", "boundary"))

    def test_every_example_returns_its_hand_specified_expectation(self):
        for entry, data in self.items:
            result = evaluate(deepcopy(data["request"]))
            for check in data["expected"]["checks"]:
                found, actual = lookup(result, check["path"])
                with self.subTest(fixture=entry["fixture_id"], path=check["path"]):
                    self.assertTrue(found, "期待した位置が結果にない")
                    self.assertEqual(canonical_bytes(actual), canonical_bytes(check["equals"]))

    def test_the_measured_budget_is_the_smallest_that_completes(self):
        n = self.manifest["measured_budget"]
        exact = next(d for e, d in self.items if e["path"] == "budget-exact.json")
        for budget, status in ((n, "ok"), (n - 1, "resource_limit")):
            request = deepcopy(exact["request"])
            request["budget"] = {"max_steps": budget}
            self.assertEqual(evaluate(request)["status"], status)

    def test_consumer_hash_embedded_in_every_split_example_is_the_pinned_spec_hash(self):
        for entry, data in self.items:
            consumer = data["request"].get("consumer")
            if consumer and entry["path"] != "consumer-spec-hash.json":
                self.assertEqual(consumer["profile_spec_sha256"], SPEC_SHA256, entry["path"])


class ContractConditionTests(unittest.TestCase):
    """受入条件 X04・X05・X14 を、例で明示的に検査する。"""

    @staticmethod
    def fixture(name):
        return decode_json((DIRECTORY / f"{name}.json").read_bytes())["request"]

    def test_x04_an_unaware_consumer_stops_and_an_aware_consumer_reads(self):
        unaware = evaluate(self.fixture("base-unaware-consumer-stops"))
        row = unaware["results"][0]
        self.assertEqual((row["status"], row["reason_codes"]), ("unassessed", ["unknown_capability"]))
        self.assertEqual(row["missing_capabilities"], [SPLIT_PROFILE])
        self.assertEqual(row["blocking_assertion_refs"], ["h2", "h3", "h4"])      # 採用・訂正済み・保留のすべて
        aware = evaluate(self.fixture("aware-consumer-reads-the-same-ledger"))["results"][0]
        self.assertEqual((aware["status"], aware["split"]["status"]), ("computed", "single"))

    def test_x04_a_third_unknown_capability_still_blocks_the_aware_consumer(self):
        row = evaluate(self.fixture("unknown-capability-blocks"))["results"][0]
        self.assertEqual((row["status"], row["missing_capabilities"]), ("blocked", ["fiction:other-capability@1"]))

    def test_x05_the_single_candidate_is_not_a_base_support(self):
        row = evaluate(self.fixture("single-by-exclusion"))["results"][0]
        self.assertEqual(row["split"]["status"], "single")
        self.assertEqual(row["base"]["parts"]["fiction:P2@1"], "undetermined")
        source = strip_split_capability(self.fixture("single-by-exclusion")["source"])
        views = self.fixture("single-by-exclusion")["views"]
        base = base_statuses(source, views, ["fiction:P2@1"], row["context_ref"], row["subject"])
        self.assertEqual(base["results"][0]["status"], "undetermined")

    def test_x14_old_answers_are_reproduced_and_the_new_question_returns_candidates(self):
        request = self.fixture("old-record-only")
        old = base_statuses(request["source"], request["views"], ["fiction:P@1", "fiction:P1@1", "fiction:P2@1"], "fiction:context:old@1", "fiction:person:1")
        self.assertEqual([r["status"] for r in old["results"]], ["supported", "undetermined", "undetermined"])
        row = evaluate(deepcopy(request))["results"][0]
        self.assertEqual((row["split"]["status"], row["split"]["candidates"]), ("open", ["fiction:P1@1", "fiction:P2@1"]))
        # 旧参照は消えない：根拠は元の主張 h1、台帳と入力の hash は元のまま
        self.assertEqual(row["evidence"]["adopted"][0]["assertion_refs"], ["h1"])
        self.assertEqual(row["evidence"]["snapshot_sha256"], digest(request["source"]))

    def test_x14_a_rewritten_record_is_a_different_snapshot_and_changes_the_answer_honestly(self):
        """旧参照を消して任意の一方へ書き換えると別の snapshot になり、結果が変わる。拡張が黙って書き換えて確定することはない。"""
        request = self.fixture("old-record-only")
        rewritten = deepcopy(request)
        rewritten["source"]["ledger"]["assertions"][0]["atom"]["predicate"] = "fiction:P1@1"
        first = evaluate(deepcopy(request))
        second = evaluate(rewritten)
        self.assertNotEqual(first["snapshot_sha256"], second["snapshot_sha256"])
        self.assertEqual(first["results"][0]["split"]["status"], "open")
        self.assertEqual(second["results"][0]["split"]["status"], "asserted")


class BudgetTests(unittest.TestCase):
    def test_every_budget_gives_complete_rows_or_an_honest_stop(self):
        rng = random.Random(5150)
        checked = stopped = 0
        for _ in range(60):
            source, views, split, queries = oracle.generate(rng)
            full = evaluate(request_of(deepcopy(source), views, split, queries))
            used = full["steps_used"]
            for budget in range(0, used + 3):
                limited = evaluate(request_of(deepcopy(source), views, split, queries, budget))
                checked += 1
                if limited["status"] == "ok":
                    self.assertGreaterEqual(budget, used)
                    self.assertEqual(canonical_bytes(limited["results"]), canonical_bytes(full["results"]))
                    continue
                stopped += 1
                self.assertEqual((limited["status"], limited["reason_codes"]), ("resource_limit", ["step_limit"]))
                for a, b in zip(limited["results"], full["results"]):
                    if a["status"] == "computed":
                        self.assertEqual(canonical_bytes(a), canonical_bytes(b))           # 完了した行は汚れない
                    else:
                        self.assertEqual(a["status"], "blocked")
                        if a["reason_codes"] == ["step_limit"]:
                            self.assertIsNone(a["split"])                                  # 打切りの行は値を持たない
        self.assertGreater(stopped, 100)
        self.assertGreater(checked, 400)


class NativeSpecTests(unittest.TestCase):
    def test_the_actual_spec_file_is_checked_not_only_the_client_claim(self):
        request = decode_json((DIRECTORY / "old-record-only.json").read_bytes())["request"]
        with patch("med_dsl.split.Path.read_bytes", return_value=b"untrusted specification"):
            self.assertEqual(evaluate(deepcopy(request))["reason_codes"], ["native_spec_mismatch"])
        with patch("med_dsl.split.Path.read_bytes", side_effect=OSError):
            self.assertEqual(evaluate(deepcopy(request))["reason_codes"], ["native_spec_unavailable"])

    def test_the_pinned_hash_is_the_raw_hash_of_the_spec_file(self):
        self.assertEqual(hashlib.sha256((ROOT / "src/med_dsl/split_spec.json").read_bytes()).hexdigest(), SPEC_SHA256)
        spec = json.loads((ROOT / "src/med_dsl/split_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(set(spec["semantics"]["statuses"]), SPLIT_STATUSES)
        self.assertEqual(set(spec["split"]["axioms"]), set(AXIOMS))


if __name__ == "__main__":
    unittest.main()
