"""P2-a の防護例（examples/p2/）：宣言の guards が引く拒否・境界の例を、実際に評価して期待と照合する。

期待結果はゲートの意味から手で指定した（予算の境界の n だけは無制限の実行から測った）。このテストは、
(1) 例が期待どおりの結果を返すこと、(2) 台帳の hash と派生元が実体と合うこと、(3) 境界の例が派生元の入力を
予算だけ変えたものであること、(4) どの例も宣言の防護例として引かれていること、を検査する。
実装のゲートを壊したとき例が失敗するか（検出力）は、変異検査で別に確かめる。
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.extensions import load_manifests
from med_dsl.validation import canonical_bytes, decode_json

DIRECTORY = ROOT / "examples/p2"


def fixtures():
    manifest = decode_json((DIRECTORY / "manifest.json").read_bytes())
    return manifest, [(entry, decode_json((DIRECTORY / entry["path"]).read_bytes())) for entry in manifest["files"]]


def lookup(result, path):
    for key in path:
        if type(result) is dict and type(key) is str and key in result:
            result = result[key]
        elif type(result) is list and type(key) is int and 0 <= key < len(result):
            result = result[key]
        else:
            return False, None
    return True, result


class GuardExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.items = fixtures()
        cls.declarations = {m["id"]: m for m in load_manifests(ROOT / "extensions")}

    def test_the_manifest_matches_the_files_and_marks_the_series_as_draft(self):
        self.assertEqual(self.manifest["schema_version"], "p2-guard-examples-manifest-draft-1")
        self.assertEqual((self.manifest["status"], self.manifest["independent_review"], self.manifest["evaluation_frozen"]),
                         ("author_draft", False, False))
        listed = {entry["path"] for entry in self.manifest["files"]}
        self.assertEqual(listed, {p.name for p in DIRECTORY.glob("*.json")} - {"manifest.json"})
        ids = [entry["fixture_id"] for entry in self.manifest["files"]]
        self.assertEqual(ids, [f"GD{i:02}" for i in range(1, len(ids) + 1)])
        for entry, data in self.items:
            raw = (DIRECTORY / entry["path"]).read_bytes()
            with self.subTest(fixture=entry["fixture_id"]):
                self.assertEqual((entry["bytes"], entry["sha256"]), (len(raw), hashlib.sha256(raw).hexdigest()))
                self.assertEqual((data["fixture_id"], data["fictional"], data["review_state"]), (entry["fixture_id"], True, "author_draft"))
                self.assertTrue(data["gate"] and entry["gate"] == data["gate"])
                self.assertIn(data["kind"], ("refusal", "non_conversion", "boundary"))

    def test_every_example_returns_its_hand_specified_expectation(self):
        for entry, data in self.items:
            result = evaluate(deepcopy(data["request"]))
            for check in data["expected"]["checks"]:
                found, actual = lookup(result, check["path"])
                with self.subTest(fixture=entry["fixture_id"], path=check["path"]):
                    self.assertTrue(found, "期待した位置が結果にない")
                    self.assertEqual(canonical_bytes(actual), canonical_bytes(check["equals"]))

    def test_each_example_names_a_real_extension_and_obligation_and_a_real_origin(self):
        for entry, data in self.items:
            with self.subTest(fixture=entry["fixture_id"]):
                ids = {o["id"] for o in self.declarations[data["extension"]]["obligations"]}
                self.assertIn(data["obligation"], ids)
                suite, name = data["derived_from"].split("/")
                self.assertTrue((ROOT / "examples" / suite / (name + ".json")).is_file())

    def test_budget_examples_differ_from_their_origin_only_in_the_budget(self):
        measured = self.manifest["measured_budgets"]
        for entry, data in self.items:
            slug = entry["path"].removesuffix(".json")
            if not slug.startswith(("budget-below-", "budget-exact-")):
                continue
            name = slug.split("-", 2)[2]
            suite, base = data["derived_from"].split("/")
            origin = decode_json((ROOT / "examples" / suite / (base + ".json")).read_bytes())["request"]
            mine = deepcopy(data["request"])
            budget = mine.pop("budget")["max_steps"]
            origin.pop("budget")
            with self.subTest(fixture=entry["fixture_id"]):
                self.assertEqual(canonical_bytes(mine), canonical_bytes(origin))
                self.assertEqual(budget, measured[name] - (1 if slug.startswith("budget-below-") else 0))

    def test_the_measured_budget_is_the_smallest_that_completes(self):
        """n は無制限の実行から測った値。n で完了し n-1 で完了しないことを、派生元の入力で再確認する。"""
        for name, n in self.manifest["measured_budgets"].items():
            entry = next(e for e in self.manifest["files"] if e["path"] == f"budget-exact-{name}.json")
            request = decode_json((DIRECTORY / entry["path"]).read_bytes())["request"]
            for budget, expected in ((n, "ok"), (n - 1, "resource_limit")):
                request["budget"] = {"max_steps": budget}
                with self.subTest(example=name, budget=budget):
                    self.assertEqual(evaluate(deepcopy(request))["status"], expected)

    def test_every_example_is_cited_by_some_declaration_as_a_guard(self):
        cited = {Path(g["example"]).name for m in self.declarations.values() for o in m["obligations"] for g in o["guards"]
                 if g["example"].startswith("examples/p2/")}
        self.assertEqual({e["path"] for e in self.manifest["files"]} - cited, set())

    def test_guards_cite_the_obligation_of_the_extension_that_declared_them(self):
        for ident, manifest in self.declarations.items():
            for obligation in manifest["obligations"]:
                for guard in obligation["guards"]:
                    if not guard["example"].startswith("examples/p2/"):
                        continue
                    data = decode_json((ROOT / guard["example"]).read_bytes())
                    with self.subTest(extension=ident, obligation=obligation["id"], example=guard["example"]):
                        self.assertEqual((data["extension"], data["obligation"]), (ident, obligation["id"]))


if __name__ == "__main__":
    unittest.main()
