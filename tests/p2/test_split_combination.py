"""P2-c：概念の分割の併用（保存性の判定と、併用での候補集合）。X09・X10 と、JOINT の義務の検査。

固定した231テスト・P1の20条件・レビュー系列・防護例（p2）・概念の分割（p2-split）とは別の分母（P2-c 系列）。
期待は splits_oracle.py（公理の式の直接評価と記号のグラフによる成分）と、examples/p2-splits/ の手で導いた期待。
意味の導出は docs/research/25-p2-c-design.md。
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
from med_dsl.split import SPEC_SHA256 as SPLIT_SPEC_SHA256, SPLIT_PROFILE
from med_dsl.splits import SPEC_SHA256, SPLITS_PROFILE, structure_of
from med_dsl.validation import canonical_bytes, decode_json
import split_oracle as base
import splits_oracle as oracle

DIRECTORY = ROOT / "examples/p2-splits"
STATUSES = {"inconsistent", "parent_opposed", "no_parent", "open", "narrowed", "single", "asserted"}


def check_request(splits, pool=oracle.POOL, budget=100000):
    return {"schema_version": "p2-splits-request-draft-1", "operation": "check_split_combination",
            "consumer": {"profile": SPLITS_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": ["check_split_combination"]},
            "budget": {"max_steps": budget},
            "source": {"package": {"ref": "fiction:package:splits@1", "profile": "p0-positive-1", "predicates": [{"ref": n, "roles": ["subject"]} for n in pool],
                                   "definitions": [], "inclusions": [], "dependencies": []}},
            "splits": [{"parent": h, "parts": list(ps)} for h, ps in splits]}


def query_request(source, views, splits, queries, budget=100000):
    return {"schema_version": "p2-splits-request-draft-1", "operation": "query_split_combination",
            "consumer": {"profile": SPLITS_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": ["query_split_combination"]},
            "budget": {"max_steps": budget}, "source": source, "views": views,
            "splits": [{"parent": h, "parts": list(ps)} for h, ps in splits], "queries": queries}


def lookup(result, path):
    for key in path:
        if type(result) is dict and type(key) is str and key in result:
            result = result[key]
        elif type(result) is list and type(key) is int and 0 <= key < len(result):
            result = result[key]
        else:
            return False, None
    return True, result


def strip_capabilities(source):
    stripped = deepcopy(source)
    for item in stripped["ledger"]["assertions"]:
        item["required_capabilities"] = []
    return stripped


def all_pair_combinations(pool):
    """部分が 2 個の分割を、親ごとに全部作り、1 個と 2 個の全組み合わせ。"""
    splits = [(head, sorted(pair)) for head in pool for pair in itertools.combinations([s for s in pool if s != head], 2)]
    yield from ([s] for s in splits)
    yield from ([a, b] for a, b in itertools.combinations(splits, 2))


class JudgmentTests(unittest.TestCase):
    """JOINT-3・JOINT-1：保存性の判定は、実装（枠の結合）とオラクル（式の直接評価・全語彙の全数）で一致する。"""

    def assert_counterexample(self, splits, certificate):
        """反例は、保存的でない成分の旧記号の割り当てで、(1) 本当に拡張できず、(2) 辞書順（記号名の整列順）で最初のもの。"""
        example = certificate["counterexample"]
        member_splits = [splits[i] for i in example["splits"]]
        old = sorted(oracle.old_symbols(member_splits))
        self.assertEqual(sorted(example["old_valuation"]), old)
        models = oracle.models_of(member_splits)

        def extends(valuation):
            return any(all(int(v[s]) == valuation[s] for s in old) for v in models)

        self.assertFalse(extends(example["old_valuation"]))
        earlier = [dict(zip(old, bits)) for bits in itertools.product((0, 1), repeat=len(old)) if list(bits) < [example["old_valuation"][s] for s in old]]
        self.assertTrue(all(extends(valuation) for valuation in earlier))

    def test_the_judgment_agrees_with_the_oracle_for_every_one_and_two_split_combination_over_four_symbols(self):
        pool = oracle.POOL[:4]
        counts = {"certified": 0, "not_certified": 0}
        for splits in all_pair_combinations(pool):
            result = evaluate(check_request(splits, pool))
            want, counterexample = oracle.conservative(splits)
            certificate = result["certificate"]
            with self.subTest(splits=splits):
                self.assertEqual(certificate["status"], "certified" if want else "not_certified")
                if want:
                    self.assertIsNone(certificate["counterexample"])
                else:
                    self.assert_counterexample(splits, certificate)
                self.assertEqual(result["structure"]["old_symbols"], oracle.old_symbols(splits))
                self.assertEqual(result["structure"]["components"], oracle.components(splits))
                for entry in result["individual"]:
                    self.assertEqual(entry["certificate"], "certified")        # 単独の分割は、いつも保存的
            counts[certificate["status"]] += 1
        # 空振りでない：保存的でない併用（K04 型）が実際にある
        self.assertGreaterEqual(counts["not_certified"], 3)
        self.assertGreater(counts["certified"], 50)

    def test_random_combinations_with_more_splits_and_parts_agree_with_the_oracle(self):
        rng = random.Random(25)
        verdicts = set()
        for _ in range(400):
            splits = oracle.generate_splits(rng, max_splits=4)
            symbols = oracle.symbols_of(splits)
            if len(symbols) > 10:
                continue
            result = evaluate(check_request(splits))
            want, counterexample = oracle.conservative(splits)
            self.assertEqual(result["certificate"]["status"], "certified" if want else "not_certified", splits)
            if not want:
                self.assert_counterexample(splits, result["certificate"])
            verdicts.add(want)
        self.assertEqual(verdicts, {True, False})

    def test_the_forest_condition_implies_certification_and_the_converse_does_not_hold(self):
        """J4：構造が single・disjoint・forest なら保存的。保存的でも、森の十分条件の外（部分を共有）にある併用がある。"""
        rng = random.Random(26)
        forest = outside = 0
        for _ in range(400):
            splits = oracle.generate_splits(rng, max_splits=3)
            result = evaluate(check_request(splits))
            if result["structure"]["forest_condition"]:
                forest += 1
                self.assertEqual(result["certificate"]["status"], "certified", splits)
            elif result["certificate"]["status"] == "certified":
                outside += 1
        self.assertGreater(forest, 100)
        self.assertGreater(outside, 5)

    def test_structure_is_recomputed_from_the_splits_and_matches_the_definitions(self):
        P, R, A, B, C, D = oracle.POOL[:6]
        cases = [([(P, [A, B])], "single", False), ([(P, [A, B]), (R, [C, D])], "disjoint", False),
                 ([(P, [A, B]), (A, [C, D])], "forest", True), ([(P, [A, B]), (P, [C, D])], "forest", False),
                 ([(P, [A, B]), (R, [A, C])], "shared_parts", False), ([(P, [A, B]), (A, [P, C])], "cyclic", True)]
        for splits, kind, chain in cases:
            with self.subTest(kind=kind):
                structure = structure_of(splits)
                self.assertEqual((structure["kind"], structure["chain"]), (kind, chain))

    def test_certification_agrees_with_the_data_level_old_only_states(self):
        """J5：保存的 ⟺ 旧記号だけで定まる（採用された）状態が矛盾にならない。静的な判定と、データでの結果の一致。"""
        pool = oracle.POOL[:4]
        compared = 0
        for splits in all_pair_combinations(pool):
            old = oracle.old_symbols(splits)
            result = evaluate(check_request(splits, pool))
            conservative = result["certificate"]["status"] == "certified"
            inconsistent_states = 0
            for valuation in itertools.product((True, False), repeat=len(old)):
                assertions = [{"id": f"h{i}", "context_ref": base.CONTEXTS[0], "atom": {"predicate": s, "args": [base.SUBJECTS[0]]},
                               "polarity": "positive" if v else "negative", "certainty": "confirmed", "recorded_at": base.TIMES[0],
                               "origin": {"kind": "observed", "ref": f"fiction:source:{i}"}, "supersedes": [], "required_capabilities": []}
                              for i, (s, v) in enumerate(zip(old, valuation))]
                reviews = [{"id": f"r{a['id']}", "assertion_ref": a["id"], "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
                            "recorded_at": base.TIMES[1], "outcome": "confirmed"} for a in assertions]
                source = {"package": {"ref": "fiction:package:splits@1", "profile": base.P0_CAPABILITY,
                                      "predicates": [{"ref": n, "roles": ["subject"]} for n in pool], "definitions": [], "inclusions": [], "dependencies": []},
                          "contexts": [{"ref": base.CONTEXTS[0], "subject_ref": base.SUBJECTS[0], "effective_at": "2019-12-01T00:00:00Z", "purpose": "fiction:research"}],
                          "ledger": {"ref": "fiction:ledger:old@1", "assertions": assertions, "reviews": reviews}}
                row = evaluate(query_request(source, [{"id": "v0", "as_of": base.TIMES[5], "policy_ref": base.POLICY}], splits,
                                             [{"id": "q0", "context_ref": base.CONTEXTS[0], "subject": base.SUBJECTS[0], "required": False}]))["results"][0]
                self.assertEqual(row["status"], "computed")
                if any(entry["joint"]["status"] == "inconsistent" for entry in row["splits"]):
                    inconsistent_states += 1
                compared += 1
            with self.subTest(splits=splits):
                self.assertEqual(conservative, inconsistent_states == 0)
        self.assertGreater(compared, 100)


class DifferentialTests(unittest.TestCase):
    """乱数の併用と台帳で、実装とオラクルを照合する。"""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(20260619)
        cls.cases = []
        for i in range(500):
            splits = oracle.generate_splits(rng)
            source, views, queries = oracle.generate_state(rng, splits, dense=(i % 2 == 0))      # 密な台帳と疎な台帳を交互に（矛盾への偏りを避ける）
            cls.cases.append((splits, source, views, queries, evaluate(query_request(deepcopy(source), views, splits, queries))))

    def test_every_row_equals_the_oracle(self):
        statuses, blocked, interactions, differs = set(), 0, 0, 0
        for splits, source, views, queries, result in self.cases:
            self.assertEqual(result["status"], "ok", result)
            row = result["results"][0]
            want = oracle.expected_row(source, views[0], splits, queries[0])
            with self.subTest(splits=splits):
                if want[0] == "blocked":
                    self.assertEqual((row["status"], row["reason_codes"]), ("blocked", [want[1]]))
                    blocked += 1
                    continue
                _, per_split, possible, interaction, state = want
                self.assertEqual(row["status"], "computed")
                self.assertEqual(row["leaf_candidates"], possible)
                self.assertEqual(row["interaction_violation"], interaction)
                self.assertEqual(row["base"], state)
                for entry, ((status, candidates, derived), (single_status, single_candidates, _)) in zip(row["splits"], per_split):
                    self.assertEqual((entry["joint"]["status"], entry["joint"]["candidates"], entry["joint"]["parent_derived"]), (status, candidates, derived))
                    self.assertEqual((entry["individual"]["status"], entry["individual"]["candidates"]), (single_status, single_candidates))
                    self.assertEqual(entry["differs"], (status, candidates) != (single_status, single_candidates))
                    statuses.add(status)
                    differs += entry["differs"]
                interactions += interaction
        self.assertGreater(blocked, 10)
        self.assertGreater(differs, 20)
        self.assertGreater(interactions, 5)
        self.assertGreaterEqual(len(statuses), 5)
        self.assertTrue(statuses <= STATUSES)

    def test_a_split_alone_in_its_component_has_the_same_joint_and_individual_result(self):
        """J1・JOINT-2：他の分割と記号を共有しない分割は、併用での結果が単独の結果と同じ。"""
        alone = 0
        for splits, source, views, queries, result in self.cases:
            row = result["results"][0]
            if row["status"] != "computed":
                continue
            components = oracle.components(splits)
            for entry in row["splits"]:
                if [entry["index"]] in components:
                    alone += 1
                    self.assertFalse(entry["differs"], (splits, entry))
                    self.assertEqual(entry["axioms_of_splits"], [entry["index"]])
        self.assertGreater(alone, 100)

    def test_the_individual_result_equals_the_p2_b_query_split_for_the_same_split(self):
        """JOINT-6：`individual` は、p2-concept-split の query_split が同じ分割に返す結果そのもの。"""
        compared = 0
        for splits, source, views, queries, result in self.cases[:150]:
            row = result["results"][0]
            if row["status"] != "computed":
                continue
            for entry in row["splits"]:
                single = {"schema_version": "p2-split-request-draft-1", "operation": "query_split",
                          "consumer": {"profile": SPLIT_PROFILE, "profile_spec_sha256": SPLIT_SPEC_SHA256, "operations": ["query_split"]},
                          "budget": {"max_steps": 100000}, "source": deepcopy(source), "views": views, "split": {"parent": entry["parent"], "parts": entry["parts"]},
                          "queries": queries}
                alone = evaluate(single)["results"][0]
                if alone["status"] != "computed":
                    continue
                self.assertEqual((entry["individual"]["status"], entry["individual"]["candidates"]), (alone["split"]["status"], alone["split"]["candidates"]))
                compared += 1
        self.assertGreater(compared, 100)

    def test_base_block_equals_the_p0_query_on_a_ledger_without_the_capabilities(self):
        """X05：行の `base` は、併用を知らない消費側（P0 の query）が同じ原子に返す状態と一致する。"""
        compared = 0
        for splits, source, views, queries, result in self.cases:
            row = result["results"][0]
            if row["status"] != "computed":
                continue
            vocabulary = oracle.symbols_of(splits)
            p0 = {"schema_version": "p0-request-draft-1", "operation": "query", **deepcopy(strip_capabilities(source)), "views": views,
                  "queries": [{"id": f"q{i}", "context_ref": row["context_ref"], "atoms": [{"predicate": s, "args": [row["subject"]]}], "required": False}
                              for i, s in enumerate(vocabulary)], "budget": {"max_steps": 100000}}
            got = {r["query"]: r["status"] for r in evaluate(p0)["results"]}
            self.assertEqual([got[f"q{i}"] for i in range(len(vocabulary))], [row["base"][s] for s in vocabulary])
            compared += 1
        self.assertGreater(compared, 300)

    def test_statuses_are_disjoint_from_base_statuses_and_nothing_is_converted(self):
        self.assertTrue(STATUSES.isdisjoint(base.BASE_STATUSES))

        def walk(value, path):
            if isinstance(value, dict):
                for key, item in value.items():
                    yield from walk(item, path + (key,))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from walk(item, path + (index,))
            else:
                yield path, value

        for *_, result in self.cases:
            for row in result["results"]:
                self.assertIs(row["converted_to_base"], False)
                self.assertEqual(row["answer_kind"], "joint_candidate_set")
            for path, value in walk(result, ()):
                if value in base.BASE_STATUSES and path[0] == "results":
                    self.assertEqual(path[2], "base", path)

    def test_the_input_is_preserved_and_the_result_is_deterministic(self):
        for splits, source, views, queries, _ in self.cases[:150]:
            request = query_request(source, views, splits, queries)
            before = canonical_bytes(request)
            first = canonical_bytes(evaluate(request))
            self.assertEqual(canonical_bytes(request), before)
            self.assertEqual(canonical_bytes(evaluate(deepcopy(request))), first)

    def test_every_offered_candidate_can_actually_be_asserted(self):
        """R6-6・JOINT-6：情報要求の候補は、その部分が肯定されたとき、その分割の併用での状態が `asserted` になる。"""
        checked = 0
        for splits, source, views, queries, result in self.cases:
            row = result["results"][0]
            if row["status"] != "computed":
                continue
            for request in row["information_requests"]:
                if request["kind"] != "confirm_part":
                    continue
                head, parts = splits[request["split"]]
                for candidate in request["candidate_parts"]:
                    extra = deepcopy(source)
                    extra["ledger"]["assertions"].append({"id": "hnew", "context_ref": row["context_ref"], "atom": {"predicate": candidate, "args": [row["subject"]]},
                                                          "polarity": "positive", "certainty": "confirmed", "recorded_at": base.TIMES[0],
                                                          "origin": {"kind": "observed", "ref": "fiction:source:new"}, "supersedes": [], "required_capabilities": []})
                    extra["ledger"]["reviews"].append({"id": "rnew", "assertion_ref": "hnew", "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
                                                       "recorded_at": base.TIMES[1], "outcome": "confirmed"})
                    after = evaluate(query_request(extra, views, splits, queries))["results"][0]
                    if after["status"] == "computed" and after["splits"][request["split"]]["joint"]["status"] != "inconsistent":
                        self.assertEqual(after["splits"][request["split"]]["joint"]["candidates"], [candidate])
                        checked += 1
        self.assertGreater(checked, 60)


class ConstructedStructureTests(unittest.TestCase):
    """乱数の併用は共有・閉路に偏る（互いに素・入れ子は 400 件中 9 件だった）。互いに素な併用と入れ子の併用を直接作って、判定と結果をオラクルと照合する。"""

    def check_against_the_oracle(self, rng, make, kind, chain):
        compared = 0
        for _ in range(150):
            splits = make(rng)
            if len(splits) < 2:
                continue
            result = evaluate(check_request(splits, oracle.POOL10))
            self.assertEqual((result["structure"]["kind"], result["structure"]["chain"]), (kind, chain), splits)
            self.assertEqual(result["certificate"]["status"], "certified", splits)
            self.assertTrue(oracle.conservative(splits)[0])
            source, views, queries = oracle.generate_state(rng, splits, pool=oracle.POOL10, dense=True)
            row = evaluate(query_request(source, views, splits, queries))["results"][0]
            want = oracle.expected_row(source, views[0], splits, queries[0])
            if want[0] == "blocked":
                self.assertEqual(row["reason_codes"], [want[1]])
                continue
            for entry, ((status, candidates, derived), (single_status, single_candidates, _)) in zip(row["splits"], want[1]):
                self.assertEqual((entry["joint"]["status"], entry["joint"]["candidates"], entry["joint"]["parent_derived"]), (status, candidates, derived))
                self.assertEqual((entry["individual"]["status"], entry["individual"]["candidates"]), (single_status, single_candidates))
                if kind == "disjoint":
                    self.assertFalse(entry["differs"])                 # 互いに素：併用は単独の結果に分解できる
            self.assertEqual(row["leaf_candidates"], want[2])
            compared += 1
        return compared

    def test_disjoint_combinations_are_certified_and_decompose(self):
        self.assertGreater(self.check_against_the_oracle(random.Random(31), oracle.generate_disjoint, "disjoint", False), 60)

    def test_nested_combinations_are_forests_certified_and_agree_with_the_oracle(self):
        compared = self.check_against_the_oracle(random.Random(32), oracle.generate_nested, "forest", True)
        self.assertGreater(compared, 60)


class DenseTests(unittest.TestCase):
    def test_dense_states_reach_every_status_often_and_agree_with_the_oracle(self):
        rng = random.Random(9090)
        counts = {}
        for _ in range(2500):
            splits = oracle.generate_splits(rng, max_splits=3)
            source, views, queries = oracle.generate_state(rng, splits, dense=True)
            row = evaluate(query_request(source, views, splits, queries))["results"][0]
            want = oracle.expected_row(source, views[0], splits, queries[0])
            if want[0] == "blocked":
                self.assertEqual(row["reason_codes"], [want[1]])
                continue
            for entry, ((status, candidates, derived), _) in zip(row["splits"], want[1]):
                self.assertEqual((entry["joint"]["status"], entry["joint"]["candidates"], entry["joint"]["parent_derived"]), (status, candidates, derived))
                counts[status] = counts.get(status, 0) + 1
        for name in STATUSES:
            self.assertGreaterEqual(counts.get(name, 0), 25, (name, counts))


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = decode_json((DIRECTORY / "manifest.json").read_bytes())
        cls.items = [(e, decode_json((DIRECTORY / e["path"]).read_bytes())) for e in cls.manifest["files"]]

    def test_the_manifest_matches_the_files(self):
        self.assertEqual((self.manifest["schema_version"], self.manifest["status"], self.manifest["independent_review"], self.manifest["evaluation_frozen"]),
                         ("p2-splits-manifest-draft-1", "author_draft", False, False))
        self.assertEqual((self.manifest["profile"], self.manifest["profile_spec_sha256"]), (SPLITS_PROFILE, SPEC_SHA256))
        self.assertEqual({e["path"] for e in self.manifest["files"]}, {p.name for p in DIRECTORY.glob("*.json")} - {"manifest.json"})
        self.assertEqual([e["fixture_id"] for e in self.manifest["files"]], [f"SC{i:02}" for i in range(1, len(self.items) + 1)])
        for entry, data in self.items:
            raw = (DIRECTORY / entry["path"]).read_bytes()
            with self.subTest(fixture=entry["fixture_id"]):
                self.assertEqual((entry["bytes"], entry["sha256"]), (len(raw), hashlib.sha256(raw).hexdigest()))
                self.assertEqual((data["fixture_id"], data["fictional"], data["review_state"], data["extension"]), (entry["fixture_id"], True, "author_draft", "p2-split-combination"))
                self.assertIn(data["kind"], ("refusal", "non_conversion", "boundary"))

    def test_every_example_returns_its_hand_derived_expectation(self):
        for entry, data in self.items:
            result = evaluate(deepcopy(data["request"]))
            for check in data["expected"]["checks"]:
                found, actual = lookup(result, check["path"])
                with self.subTest(fixture=entry["fixture_id"], path=check["path"]):
                    self.assertTrue(found, "期待した位置が結果にない")
                    self.assertEqual(canonical_bytes(actual), canonical_bytes(check["equals"]))

    def test_the_measured_budgets_are_the_smallest_that_complete(self):
        for name, exact in (("check", "check-budget-exact.json"), ("query", "query-budget-exact.json")):
            n = self.manifest["measured_budgets"][name]
            request = decode_json((DIRECTORY / exact).read_bytes())["request"]
            for budget, status in ((n, "ok"), (n - 1, "resource_limit")):
                request["budget"] = {"max_steps": budget}
                self.assertEqual(evaluate(deepcopy(request))["status"], status)

    def test_consumer_hash_embedded_in_every_example_is_the_pinned_spec_hash(self):
        for entry, data in self.items:
            consumer = data["request"].get("consumer")
            if consumer and entry["path"] != "check-consumer-spec-hash.json" and data["request"].get("schema_version") == "p2-splits-request-draft-1":
                self.assertEqual(consumer["profile_spec_sha256"], SPEC_SHA256, entry["path"])


class ContractConditionTests(unittest.TestCase):
    """受入条件 X09・X10 を例で明示的に検査する。"""

    @staticmethod
    def fixture(name):
        return decode_json((DIRECTORY / f"{name}.json").read_bytes())["request"]

    def test_x09_individually_conservative_splits_are_not_conservative_together(self):
        result = evaluate(self.fixture("check-k04-shared-parts"))
        self.assertEqual([e["certificate"] for e in result["individual"]], ["certified", "certified"])
        self.assertEqual(result["certificate"]["status"], "not_certified")
        # 個別の認定票を併用の根拠として受け付けない
        request = self.fixture("check-k04-shared-parts")
        request["individual_certificates"] = ["certified", "certified"]
        self.assertEqual(evaluate(request)["reason_codes"], ["unknown_field"])

    def test_x10_the_later_stage_is_decided_only_when_the_earlier_stage_decides_the_individual(self):
        undecided = evaluate(self.fixture("query-chain-loss-not-recovered"))["results"][0]
        self.assertEqual([e["joint"]["status"] for e in undecided["splits"]], ["open", "no_parent"])
        self.assertEqual(undecided["leaf_candidates"], ["fiction:B@1", "fiction:C@1", "fiction:D@1"])
        decided = evaluate(self.fixture("query-chain-exclusion-flows"))["results"][0]
        self.assertEqual([e["joint"]["status"] for e in decided["splits"]], ["single", "open"])
        self.assertEqual([e["individual"]["status"] for e in decided["splits"]], ["single", "no_parent"])

    def test_x10_the_chain_result_differs_from_composing_the_stages_one_after_the_other(self):
        row = evaluate(self.fixture("query-chain-exclusion-flows"))["results"][0]
        self.assertTrue(row["splits"][1]["differs"])
        row = evaluate(self.fixture("query-chain-later-info-flows-back"))["results"][0]
        self.assertTrue(row["splits"][0]["differs"])


class BudgetTests(unittest.TestCase):
    def test_every_query_budget_gives_complete_rows_or_an_honest_stop(self):
        rng = random.Random(7771)
        stopped = checked = 0
        for _ in range(40):
            splits = oracle.generate_splits(rng)
            source, views, queries = oracle.generate_state(rng, splits)
            full = evaluate(query_request(deepcopy(source), views, splits, queries))
            for budget in range(0, full["steps_used"] + 3):
                limited = evaluate(query_request(deepcopy(source), views, splits, queries, budget))
                checked += 1
                if limited["status"] == "ok":
                    self.assertGreaterEqual(budget, full["steps_used"])
                    self.assertEqual(canonical_bytes(limited["results"]), canonical_bytes(full["results"]))
                    continue
                stopped += 1
                self.assertEqual((limited["status"], limited["reason_codes"]), ("resource_limit", ["step_limit"]))
                for a, b in zip(limited["results"], full["results"]):
                    if a["status"] == "computed":
                        self.assertEqual(canonical_bytes(a), canonical_bytes(b))
                    elif a["reason_codes"] == ["step_limit"]:
                        self.assertIsNone(a["splits"])
        self.assertGreater(stopped, 100)

    def test_a_check_is_either_complete_or_has_no_certificate(self):
        combinations = [[(oracle.POOL[0], oracle.POOL[1:3])], [(oracle.POOL[0], oracle.POOL[2:4]), (oracle.POOL[1], oracle.POOL[2:4])]]
        for splits in combinations:
            full = evaluate(check_request(splits))
            for budget in range(0, full["steps_used"] + 2):
                limited = evaluate(check_request(splits, budget=budget))
                if limited["status"] == "ok":
                    self.assertEqual(limited["certificate"]["status"], full["certificate"]["status"])
                else:
                    self.assertNotIn("certificate", limited)


class NativeSpecTests(unittest.TestCase):
    def test_the_actual_spec_file_is_checked_not_only_the_client_claim(self):
        request = decode_json((DIRECTORY / "check-k04-shared-parts.json").read_bytes())["request"]
        with patch("med_dsl.splits.Path.read_bytes", return_value=b"untrusted specification"):
            self.assertEqual(evaluate(deepcopy(request))["reason_codes"], ["native_spec_mismatch"])
        with patch("med_dsl.splits.Path.read_bytes", side_effect=OSError):
            self.assertEqual(evaluate(deepcopy(request))["reason_codes"], ["native_spec_unavailable"])

    def test_the_pinned_hash_is_the_raw_hash_of_the_spec_file(self):
        self.assertEqual(hashlib.sha256((ROOT / "src/med_dsl/splits_spec.json").read_bytes()).hexdigest(), SPEC_SHA256)
        spec = json.loads((ROOT / "src/med_dsl/splits_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["operations"], ["check_split_combination", "query_split_combination"])


if __name__ == "__main__":
    unittest.main()
