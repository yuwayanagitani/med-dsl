"""P2-c：独立な拡張の併用（L3、X08）。

拡張の独立は、依存・読み取り・順序・実装の import から機械的に判定する（`independent_pairs`）。
独立と判定された拡張の任意の部分集合を同時に載せ、登録と振り分けの順序を入れ替えても、全例の結果が
単独で載せたときと一致する。独立でない組は、片方を不活性にすると他方の結果が変わる（判定が実際の依存を捉える）。
"""

from contextlib import ExitStack
from copy import deepcopy
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import support
from med_dsl import evaluate, host
from med_dsl.extensions import independent_pairs, standard_registry
from med_dsl.validation import canonical_bytes


class IndependenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = standard_registry(ROOT, evaluate=evaluate)
        cls.pairs = independent_pairs(cls.registry)
        cls.requests = support.load_requests()
        cls.baseline = {name: canonical_bytes(evaluate(deepcopy(request))) for name, request in cls.requests}

    def related(self, a, b):
        return b in support.dependents(self.registry, a) or a in support.dependents(self.registry, b)

    def test_the_pairs_are_sorted_distinct_and_exclude_the_base(self):
        self.assertEqual(self.pairs, sorted(self.pairs))
        self.assertTrue(all(a < b for a, b in self.pairs))
        self.assertEqual(len(set(self.pairs)), len(self.pairs))
        self.assertNotIn("p0-positive", {x for pair in self.pairs for x in pair})

    def test_known_dependent_and_independent_pairs_are_classified_as_expected(self):
        pairs = set(self.pairs)
        for independent in (("p1-finite-forecast", "p2-concept-split"), ("p1-events", "p2-concept-split"), ("p1-events", "p1-finite-forecast"),
                            ("p1-absence", "p1-projection"), ("p1-finite-forecast", "p2-split-combination")):
            self.assertIn(tuple(sorted(independent)), pairs, independent)
        for dependent in (("p1-events", "p1-handover-host"), ("p1-event-chain", "p1-replay"), ("p2-concept-split", "p2-split-combination"),
                          ("p1-handover-host", "p1-reference")):
            self.assertNotIn(tuple(sorted(dependent)), pairs, dependent)

    def test_no_pair_that_depends_or_reads_is_called_independent(self):
        for a, b in self.pairs:
            self.assertFalse(self.related(a, b), (a, b))
            self.assertNotIn(b, self.registry.get(a)["composition"]["reads_extensions"])
            self.assertNotIn(a, self.registry.get(b)["composition"]["reads_extensions"])

    def test_every_independent_subset_gives_the_same_results_as_each_extension_alone(self):
        """X08：互いに独立な拡張の任意の部分集合を同時に載せ（残りは不活性）ても、載せた拡張と、不活性にした拡張に属さない要求の結果は、全部載せたときと同じ。"""
        group = ["p1-finite-forecast", "p1-events", "p2-concept-split"]
        for a, b in itertools.combinations(group, 2):
            self.assertIn(tuple(sorted((a, b))), set(self.pairs), (a, b))
        owners = {name: support.owner_of(self.registry, request) for name, request in self.requests}
        checked = 0
        for size in range(0, len(group) + 1):
            for active in itertools.combinations(group, size):
                inactive = [i for i in group if i not in active]
                with ExitStack() as stack:
                    for ident in inactive:
                        stack.enter_context(support.inert(self.registry, ident))
                    for name, request in self.requests:
                        if any(owners[name] in support.dependents(self.registry, i) for i in inactive):
                            continue                                    # 不活性にした拡張とその依存先の要求は対象外
                        with self.subTest(active=active, request=name):
                            self.assertEqual(canonical_bytes(evaluate(deepcopy(request))), self.baseline[name])
                        checked += 1
        self.assertGreater(checked, 400)

    def test_registration_and_dispatch_order_do_not_change_any_result(self):
        """X08：登録表（振り分け）の順序を入れ替えても、全例の結果は変わらない。"""
        reversed_surfaces = dict(reversed(list(host.SURFACES.items())))
        with patch.object(host, "SURFACES", reversed_surfaces):
            for name, request in self.requests:
                self.assertEqual(canonical_bytes(evaluate(deepcopy(request))), self.baseline[name], name)
        registry_forward = standard_registry(ROOT, evaluate=evaluate)
        self.assertEqual(sorted(m["id"] for m in registry_forward), sorted(m["id"] for m in self.registry))

    def test_a_dependent_pair_does_interfere_when_one_is_disabled(self):
        """独立でない組（併用は単独の分割を読む）は、片方を不活性にすると他方の結果が変わる：独立の判定が実際の依存を捉える。"""
        owners = {name: support.owner_of(self.registry, request) for name, request in self.requests}
        combination = [(n, r) for n, r in self.requests if owners[n] == "p2-split-combination"]
        self.assertTrue(combination)
        with support.inert(self.registry, "p2-concept-split"):
            changed = [n for n, r in combination if canonical_bytes(evaluate(deepcopy(r))) != self.baseline[n]]
        self.assertTrue(changed, "依存が宣言どおりに観測できなかった")
        # 逆向きは影響しない（分割は併用を読まない）
        splits = [(n, r) for n, r in self.requests if owners[n] == "p2-concept-split"]
        with support.inert(self.registry, "p2-split-combination"):
            self.assertTrue(all(canonical_bytes(evaluate(deepcopy(r))) == self.baseline[n] for n, r in splits))


if __name__ == "__main__":
    unittest.main()
