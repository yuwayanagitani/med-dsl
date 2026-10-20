"""P2-d：共通予算の不変条件（X12、C-stop・I5）。

全要求（P0・P1・レビュー系列・P2 の例）を、予算 0 から完了に要る steps+2 まで掃引し、型によらない不変条件を確かめる：
完了した結果は予算を増やしても同じ／止まった結果に認定票がない／完了済みの行は無制限と同一／打切りの行は値を持たない／
入力不正・未対応は予算に依らない（仕様が課金を明記した一件を除く）。検査器自体も、壊れた評価を渡して違反を検出できることを確かめる。
"""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))
sys.path.insert(0, str(Path(__file__).parent))

import p2_checks as checks
import support
from med_dsl import evaluate
from med_dsl.extensions import standard_registry

STOPPED_ROWS = "p2-split/views-over-time.json"          # 予算 10：一行は完了、一行は打切り
OTHER_ROWS = "p2-splits/query-base-unchanged-by-the-combination.json"
RESOURCE_FULL = "p0/binding-limit.json"                 # 無制限でも資源の上限で止まる
BUDGET_DEPENDENT = "p1-a/unnormalized.json"


class BudgetContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = checks.load_requests()
        cls.by_name = dict(cls.requests)
        cls.registry = standard_registry(ROOT, evaluate=evaluate)

    def test_every_request_satisfies_the_budget_contract(self):
        report = checks.budget_report(self.requests, evaluate)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["requests"], len(self.requests))      # 予算を持たず検査されない要求がない
        self.assertGreater(report["evaluations"], 2000)

    def test_the_budget_dependent_refusal_is_one_documented_exception(self):
        self.assertEqual(set(checks.BUDGET_DEPENDENT_REFUSALS), {BUDGET_DEPENDENT})
        request = self.by_name[BUDGET_DEPENDENT]
        full = evaluate(deepcopy(request))
        self.assertEqual(full["status"], "invalid_input")
        low = deepcopy(request)
        low["budget"] = {"max_steps": 0}
        stopped = evaluate(low)
        self.assertEqual((stopped["status"], stopped["reason_codes"]), ("resource_limit", ["step_limit"]))
        # 仕様が、この検査を steps に含めると書いている
        spec = (ROOT / "src/med_dsl/forecast_spec.json").read_text(encoding="utf-8")
        self.assertIn("one for normalization comparison", spec)
        # 例外は、この要求だけ。ほかの入力不正は、予算 0 でも同じ結果
        for name, other in self.requests:
            if name == BUDGET_DEPENDENT or evaluate(deepcopy(other))["status"] != "invalid_input":
                continue
            zero = deepcopy(other)
            zero["budget"] = {"max_steps": 0}
            self.assertEqual(checks.without_input_hash(evaluate(zero)), checks.without_input_hash(evaluate(deepcopy(other))), name)

    def test_every_extension_that_declares_a_budget_sweep_has_requests_that_actually_stop(self):
        """宣言した予算の掃引が空振りでない：その拡張の要求に、無制限では完了し、予算 0 では止まるものがある。"""
        stoppable = {}
        for name, request in self.requests:
            owner = support.owner_of(self.registry, request)
            full = evaluate(deepcopy(request))
            zero = deepcopy(request)
            zero["budget"] = {"max_steps": 0}
            if full["status"] == "ok" and evaluate(zero)["status"] == "resource_limit":
                stoppable.setdefault(owner, []).append(name)
        for manifest in self.registry:
            if not manifest["evaluation"]["budget_sweep"]:
                continue
            ident = manifest["id"]
            if manifest["class"] == "HOST":
                # 共有の前段は操作を所有しない。引き継ぎの要求はすべてこの前段を通るので、そのうち止まるものを数える
                handover = [n for n, r in self.requests if r.get("schema_version") == "p1-handover-request-draft-1" and n in sum(stoppable.values(), [])]
                self.assertTrue(handover, ident)
            else:
                self.assertTrue(stoppable.get(ident), ident)

    def test_the_mixed_stop_request_has_both_a_finished_and_a_stopped_row(self):
        """検査器の負例が使う要求の前提：打切りの行と完了の行が同居する。"""
        request = deepcopy(self.by_name[STOPPED_ROWS])
        request["budget"] = {"max_steps": 10}
        result = evaluate(request)
        self.assertEqual(result["status"], "resource_limit")
        statuses = [(row["status"], row["reason_codes"]) for row in result["results"]]
        self.assertEqual(statuses, [("computed", []), ("blocked", ["step_limit"])])

    def test_requests_without_steps_used_are_still_swept_to_completion(self):
        """P0 の結果は steps_used を持たない。掃引の範囲は完了する予算から決め、0〜2 で打ち切らない。"""
        name = "p0/reproducibility-original.json"
        self.assertNotIn("steps_used", evaluate(deepcopy(self.by_name[name])))
        _, count = checks.budget_violations(name, self.by_name[name], evaluate)
        self.assertGreater(count, 10)
        self.assertLess(count, 40)               # 完了する予算（10）の少し先で止まる。上限（300）まで回さない
        for budget in range(0, 3):                          # 0〜2 のうちで完了するものはない（掃引が空振りでない）
            request = deepcopy(self.by_name[name])
            request["budget"] = {"max_steps": budget}
            self.assertEqual(evaluate(request)["status"], "resource_limit")

    def test_a_resource_limit_in_the_full_run_stays_a_resource_limit_without_a_certificate(self):
        request = self.by_name[RESOURCE_FULL]
        self.assertEqual(evaluate(deepcopy(request))["status"], "resource_limit")
        problems, _ = checks.budget_violations(RESOURCE_FULL, request, evaluate)
        self.assertEqual(problems, [])


def broken(mutate):
    """評価を包み、予算に応じて結果を壊す。検査器が違反を見つけられるかを調べる。"""
    def evaluate_with_defect(request):
        return mutate(request["budget"]["max_steps"], evaluate(request))
    return evaluate_with_defect


class CheckerDetectsDefectsTests(unittest.TestCase):
    """検査器の検出力：壊した評価（実装の退行を模したもの）で、期待した種類の違反が報告される。"""

    @classmethod
    def setUpClass(cls):
        cls.by_name = dict(checks.load_requests())

    def kinds(self, name, mutate):
        problems, _ = checks.budget_violations(name, self.by_name[name], broken(mutate))
        return {problem[2] for problem in problems}

    def test_the_unbroken_evaluation_has_no_violations(self):
        for name in (STOPPED_ROWS, OTHER_ROWS, RESOURCE_FULL, BUDGET_DEPENDENT, "p0/reproducibility-original.json"):
            self.assertEqual(self.kinds(name, lambda budget, result: result), set(), name)

    def test_a_certificate_on_a_stopped_result_is_found(self):
        def mutate(budget, result):
            if result["status"] == "resource_limit":
                result = {**result, "certificate": {"status": "certified"}}
            return result
        self.assertIn("certificate_on_stop", self.kinds(STOPPED_ROWS, mutate))

    def test_a_value_on_a_stopped_row_is_found(self):
        def mutate(budget, result):
            if result["status"] == "resource_limit":
                result = deepcopy(result)
                for row in result["results"]:
                    if row["status"] == "blocked":
                        row["split"] = {"status": "open", "candidates": ["fiction:P1@1"]}
            return result
        self.assertIn("value_on_stopped_row", self.kinds(STOPPED_ROWS, mutate))

    def test_a_stopped_row_that_asks_for_information_is_found(self):
        def mutate(budget, result):
            if result["status"] == "resource_limit":
                result = deepcopy(result)
                for row in result["results"]:
                    if row["status"] == "blocked":
                        row["information_requests"] = [{"kind": "confirm_part"}]
            return result
        self.assertIn("value_on_stopped_row", self.kinds(STOPPED_ROWS, mutate))

    def test_a_completed_row_that_changes_when_the_run_stops_is_found(self):
        def mutate(budget, result):
            if result["status"] == "resource_limit":
                result = deepcopy(result)
                for row in result["results"]:
                    if row["status"] == "computed":
                        row["split"]["candidates"] = []
            return result
        self.assertIn("completed_row_changed", self.kinds(STOPPED_ROWS, mutate))

    def test_a_completed_result_that_depends_on_the_budget_is_found(self):
        def mutate(budget, result):
            if result["status"] == "ok" and budget < 100000:
                result = {**result, "extra": budget}
            return result
        self.assertIn("completed_result_changed", self.kinds(OTHER_ROWS, mutate))

    def test_a_result_that_completes_and_then_stops_again_is_found(self):
        name = OTHER_ROWS
        done = next(b for b in range(300) if evaluate({**deepcopy(self.by_name[name]), "budget": {"max_steps": b}})["status"] == "ok")

        def mutate(budget, result):
            if budget == done + 1:                               # 完了した次の予算で、また打切りに戻る
                return {**result, "status": "resource_limit", "reason_codes": ["step_limit"]}
            return result
        self.assertIn("completed_then_stopped", self.kinds(name, mutate))

    def test_an_unexpected_stop_status_is_found(self):
        def mutate(budget, result):
            return {**result, "status": "invalid_input"} if result["status"] == "resource_limit" else result
        self.assertTrue(any(k.startswith("unexpected_status:") for k in self.kinds(OTHER_ROWS, mutate)))

    def test_a_refusal_that_becomes_a_different_answer_at_low_budget_is_found(self):
        refusal = next(n for n in self.by_name if n.startswith("p2-split/") and evaluate(deepcopy(self.by_name[n]))["status"] == "invalid_input")

        def mutate(budget, result):
            if result["status"] == "invalid_input" and budget < 5:
                return {**result, "status": "resource_limit", "reason_codes": ["step_limit"]}
            return result
        self.assertIn("refusal_depends_on_budget", self.kinds(refusal, mutate))

    def test_the_documented_exception_does_not_excuse_any_other_difference(self):
        def mutate(budget, result):
            return {**result, "status": "ok"} if result["status"] == "resource_limit" and budget < 5 else result
        self.assertIn("refusal_depends_on_budget", self.kinds(BUDGET_DEPENDENT, mutate))

    def test_a_full_resource_stop_that_turns_into_a_certificate_is_found(self):
        def mutate(budget, result):
            if budget == 0:
                return {**result, "certificate": {"status": "certified"}}
            return result
        self.assertIn("resource_stop_not_honest", self.kinds(RESOURCE_FULL, mutate))


if __name__ == "__main__":
    unittest.main()
