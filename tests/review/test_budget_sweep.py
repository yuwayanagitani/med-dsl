"""レビュー AI-001 の RV-01：予算の全値掃引による回帰検査。

固定した全 117 例（P0 37、P1 80）と負例系列 12 例の予算を 0 から steps+3 まで変え、次を確認する。
- 正常終了なら、無制限実行と steps_used・入力 hash を除いて同一。
- resource_limit なら、完了済みの行は無制限実行と同一、未完了の行は値を持たず、認定・回答・生成物を返さない。
- 必要十分な予算（steps_used）は正常終了し、その1少ない予算は resource_limit になる。
- 入力不正が予算不足で正常化されたり、別の状態へ変わったりしない。
`python3 -m unittest discover -s tests/review -v` で実行する（約15秒）。
"""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.validation import canonical_bytes, decode_json

SUITES = ("p0", "p1-a", "p1-b", "p1-c", "review")
FULL = 100000
OPEN_ROW_STATUS = ("unassessed", "incomparable")
FORBIDDEN_UNDER_LIMIT = ("certificate", "semantic_handover", "answer", "target", "probability")


def requests():
    for suite in SUITES:
        folder = ROOT / "examples" / suite
        manifest = decode_json((folder / "manifest.json").read_bytes())
        for entry in manifest["files"]:
            yield suite, entry["path"], decode_json((folder / entry["path"]).read_bytes())["request"]


def strip(result):
    result = deepcopy(result)
    for key in ("steps_used", "input_sha256"):
        result.pop(key, None)
    return canonical_bytes(result)


def row_key(row):
    return row.get("view") or row.get("view_id"), row.get("query") or row.get("query_id")


def budgets(steps):
    top = (steps if steps is not None else 400) + 3
    values = set(range(0, min(top, 300) + 1)) | set(range(300, top + 1, 7)) | {top, top + 1, top + 50}
    if steps is not None:
        values |= {steps - 1, steps, steps + 1}
    return sorted(v for v in values if v >= 0)


class BudgetSweepTests(unittest.TestCase):
    def test_every_budget_gives_the_full_answer_or_an_honest_stop(self):
        total = 0
        for suite, name, request in requests():
            full_request = deepcopy(request)
            full_request["budget"] = {"max_steps": FULL}
            full = evaluate(full_request)
            full_rows = ({row_key(r): r for r in full["results"] if type(r) is dict}
                         if type(full.get("results")) is list else {})
            for budget in budgets(full.get("steps_used")):
                total += 1
                limited = deepcopy(request)
                limited["budget"] = {"max_steps": budget}
                result = evaluate(limited)
                where = f"{suite}/{name} budget={budget}"
                if result["status"] == "ok":
                    self.assertEqual(full["status"], "ok", where)
                    self.assertEqual(strip(result), strip(full), where)
                    self.assertGreaterEqual(budget, result["steps_used"] if "steps_used" in result else 0, where)
                elif result["status"] == "resource_limit":
                    for row in result.get("results", []) if type(result.get("results")) is list else []:
                        if row["status"] in OPEN_ROW_STATUS:
                            self.assertFalse(row.get("bindings") or row.get("evidence") or row.get("answer"), where)
                        else:
                            self.assertIn(row_key(row), full_rows, where)
                            self.assertEqual(canonical_bytes(row), canonical_bytes(full_rows[row_key(row)]), where)
                    for key in FORBIDDEN_UNDER_LIMIT:
                        self.assertIn(result.get(key), (None, {}), f"{where}: {key}")
                else:
                    # 構造・参照の入力不正は予算に依らない。予算不足で別の状態へ変えない。
                    self.assertEqual(result["status"], full["status"], where)
                    self.assertEqual(result["reason_codes"], full["reason_codes"], where)
        self.assertGreater(total, 20000)

    def test_minimum_sufficient_budget_is_exact(self):
        checked = 0
        for suite, name, request in requests():
            full_request = deepcopy(request)
            full_request["budget"] = {"max_steps": FULL}
            full = evaluate(full_request)
            steps = full.get("steps_used")
            if full["status"] != "ok" or steps is None or steps < 1:
                continue
            exact, short = deepcopy(request), deepcopy(request)
            exact["budget"], short["budget"] = {"max_steps": steps}, {"max_steps": steps - 1}
            with self.subTest(fixture=f"{suite}/{name}"):
                self.assertEqual(strip(evaluate(exact)), strip(full))
                self.assertEqual(evaluate(short)["status"], "resource_limit")
            checked += 1
        self.assertGreater(checked, 40)


if __name__ == "__main__":
    unittest.main()
