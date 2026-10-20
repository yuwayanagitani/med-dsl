"""P2-a：拡張契約の宣言・登録・非干渉・再検証範囲の列挙（X01〜X03、X06、X07、X13）。

固定した231テスト・P1の20条件・レビュー系列とは別の分母（P2 系列）。実行は
`python3 -m unittest discover -s tests/p2 -v`。宣言は意味の正しさを検査するものではない。
"""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import support
from med_dsl import evaluate
from med_dsl.extensions import (CLASSES, COMMON, EVIDENCE, LOCK, OWN_KINDS, REQUIRED, TOP_LEVEL, Refused, Registry, affected,
                                guard_gaps, independent_pairs, load_manifests, module_graph, overlaps, standard_registry, validate, weakest_evidence)
from med_dsl.model import Problem
from med_dsl.validation import canonical_bytes, decode_json, digest

IDS = ["p0-positive", "p0-definitions", "p1-finite-forecast", "p1-events", "p1-handover-host", "p1-event-chain",
       "p1-projection", "p1-reference", "p1-absence", "p1-replay", "p2-concept-split", "p2-split-combination", "p2-temporal-assertion", "p2-quantity-literal", "p2-measurement-binding"]
# 防護例のない義務（理由は宣言の guard_gap）。増やすときはここも更新して、検査の見逃しが黙って増えないようにする。
# 残る 3 件は、拒否する入力を構成できない（構文の十分条件による保証・手作業の導出・損失のある段がない）
KNOWN_GAPS = {
    "p0-definitions": ["R1-3"],
    "p1-events": ["R3-3"],
    "p1-event-chain": ["COMP-3"],
}


def shipped():
    return {m["id"]: m for m in load_manifests(ROOT / "extensions")}


def base_registry(*ids):
    registry = Registry(ROOT, evaluate)
    for ident in ids:
        registry.register(shipped()[ident])
    return registry


def refused_codes(registry, manifest):
    try:
        registry.register(manifest)
    except Refused as error:
        return error.codes
    return None


class ShippedDeclarationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = standard_registry(ROOT, evaluate=evaluate)

    def test_all_shipped_declarations_register_in_dependency_order_and_guards_hold(self):
        self.assertEqual(sorted(m["id"] for m in self.registry), sorted(IDS))
        self.assertEqual(next(iter(self.registry))["class"], "BASE")

    def test_the_index_lists_every_declaration_with_its_hash(self):
        index = decode_json((ROOT / "extensions/index.json").read_bytes())
        self.assertEqual(index["schema_version"], "p2-extension-index-draft-1")
        self.assertFalse(index["independent_review"])
        listed = {e["id"]: e for e in index["extensions"]}
        self.assertEqual(sorted(listed), sorted(IDS))
        files = {p.name for p in (ROOT / "extensions").glob("*.json")} - {"index.json"}
        self.assertEqual(files, {e["path"] for e in index["extensions"]})
        for entry in index["extensions"]:
            self.assertEqual(hashlib.sha256((ROOT / "extensions" / entry["path"]).read_bytes()).hexdigest(), entry["sha256"], entry["id"])
            self.assertEqual(entry["class"], self.registry.get(entry["id"])["class"])

    def test_each_class_declares_every_required_obligation(self):
        for manifest in self.registry:
            with self.subTest(extension=manifest["id"]):
                declared = {o["id"] for o in manifest["obligations"]}
                self.assertTrue(set(REQUIRED[manifest["class"]]) <= declared)
                self.assertTrue(set(COMMON) <= declared)

    def test_guard_gaps_are_exactly_the_known_ones_and_each_has_a_reason(self):
        found = {m["id"]: guard_gaps(m) for m in self.registry if guard_gaps(m)}
        self.assertEqual(found, KNOWN_GAPS)
        for manifest in self.registry:
            for item in manifest["obligations"]:
                if not item["guards"]:
                    self.assertTrue(len(item["guard_gap"]) >= 10, (manifest["id"], item["id"]))

    def test_owned_names_are_disjoint_and_namespaces_do_not_overlap_names(self):
        owners = self.registry.owners()
        seen = list(owners)
        for i, (kind_a, token_a) in enumerate(seen):
            for kind_b, token_b in seen[i + 1:]:
                if kind_a == kind_b:
                    self.assertFalse(overlaps(token_a, token_b), (token_a, token_b))
        # 名前の種別のうち、実際に所有されているものが少なくとも四つある
        self.assertGreaterEqual(len({kind for kind, _ in owners}), 4)
        self.assertTrue(set(kind for kind, _ in owners) <= set(OWN_KINDS))

    def test_weakest_evidence_is_computed_and_never_stronger_than_any_obligation(self):
        for manifest in self.registry:
            weakest = weakest_evidence(manifest)
            self.assertTrue(all(EVIDENCE.index(o["evidence"]) >= EVIDENCE.index(weakest) for o in manifest["obligations"]))
        self.assertEqual(weakest_evidence(self.registry.get("p1-event-chain")), "hand_derivation")
        self.assertEqual(weakest_evidence(self.registry.get("p1-events")), "finite_check")

    def test_no_declaration_claims_an_independent_review(self):
        for manifest in self.registry:
            self.assertEqual(manifest["status"], {"review_state": "author_draft", "independent_review": False})

    def cited_files(self):
        """宣言と、宣言が根拠として引く実体（実装・仕様・契約・pin・防護例・検査・オラクル・評価の例）。"""
        cited = {"extensions/index.json"}
        for manifest in self.registry:
            cited.add(f"extensions/{manifest['id']}.json")
            cited.add(manifest["contract_doc"])
            if manifest["spec"] is not None:
                cited.add(manifest["spec"]["path"])
            cited.update(manifest["implementation"]["modules"])
            cited.update(pin["path"] for pin in manifest["pins"])
            for pattern in manifest["evaluation"]["examples"]:
                cited.update(str(path.relative_to(ROOT)) for path in ROOT.glob(pattern))
            cited.update(manifest["evaluation"]["tests"])
            if manifest["evaluation"].get("oracle"):
                cited.add(manifest["evaluation"]["oracle"])
            for obligation in manifest["obligations"]:
                cited.update(check.split("::")[0] for check in obligation["checks"])
                cited.update(guard["example"] for guard in obligation["guards"])
        return cited

    def test_the_lock_pins_the_declarations_and_everything_they_cite(self):
        """宣言を変えたり、宣言が根拠として引く実体を差し替えたりすると、共通 manifest（lock）の再固定が要る。
        例外は audit-preservation.py だけ：lock の hash を定数に持つので、載せると循環する。"""
        listed = set(decode_json((ROOT / LOCK).read_bytes())["files"])
        self.assertEqual(sorted(self.cited_files() - listed), ["scripts/research/audit-preservation.py"])
        self.assertTrue({"extensions/index.json", "scripts/research/check-extensions.py"} <= listed)

    def test_the_audit_script_is_outside_the_lock_because_it_holds_the_lock_hash(self):
        """例外の理由が今も成り立つこと：audit-preservation.py は lock 自身の sha256 を含む（載せると循環する）。"""
        lock_sha = hashlib.sha256((ROOT / LOCK).read_bytes()).hexdigest()
        self.assertIn(lock_sha, (ROOT / "scripts/research/audit-preservation.py").read_text(encoding="utf-8"))

    def test_embedded_in_covers_every_artifact_that_embeds_a_pinned_hash(self):
        """pin の hash を実際に埋め込んでいる実体（src／examples）が、その pin を宣言した拡張の embedded_in の和に含まれる。
        dispatcher と hand_specified_expectations は hash を埋め込まれない再検証依存。後者はlockで固定する。"""
        declared, values = {}, {}
        runtime = {}
        for manifest in self.registry:
            files = set()
            for pattern in manifest["embedded_in"]:
                files.update(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())
            for pin in manifest["pins"]:
                if pin["role"] == "dispatcher":
                    continue
                if pin["role"] == "hand_specified_expectations":
                    lock = decode_json((ROOT / LOCK).read_bytes())
                    self.assertIn(pin["path"], lock["files"])
                    self.assertEqual(hashlib.sha256((ROOT / pin["path"]).read_bytes()).hexdigest(),
                                     lock["files"][pin["path"]]["sha256"])
                    continue
                digest_ = hashlib.sha256((ROOT / pin["path"]).read_bytes()).hexdigest()
                if pin["role"] == "p0_runtime":
                    runtime[Path(pin["path"]).name] = digest_
                    key = "(P0 の5ファイルの束)"
                else:
                    key, values[pin["path"]] = pin["path"], digest_
                declared.setdefault(key, set()).update(files)
        values["(P0 の5ファイルの束)"] = digest(runtime)
        self.assertEqual(len(runtime), 5)
        pinned_paths = {p["path"] for m in self.registry for p in m["pins"]}
        for name, value in values.items():
            holders = set()
            for top in ("src", "examples"):
                for path in (ROOT / top).rglob("*"):
                    if path.is_file() and path.suffix in (".py", ".json") and "__pycache__" not in path.parts and value in path.read_text(encoding="utf-8"):
                        holders.add(str(path.relative_to(ROOT)))
            holders -= {name, LOCK}
            with self.subTest(pinned=name):
                self.assertTrue(holders, "宣言した pin の hash がどこにも埋め込まれていない（宣言が古い）")
                self.assertEqual(sorted(holders - declared[name]), [], "embedded_in に漏れ")


class OverlapTests(unittest.TestCase):
    def test_a_trailing_colon_makes_a_namespace_that_owns_everything_below_it(self):
        self.assertTrue(overlaps("a", "a"))
        self.assertTrue(overlaps("urn:x:", "urn:x:role:key"))
        self.assertTrue(overlaps("urn:x:role:key", "urn:x:"))
        self.assertFalse(overlaps("urn:x:role:", "urn:x:active"))
        self.assertFalse(overlaps("urn:x:", "urn:y:"))
        self.assertFalse(overlaps("abc", "abcd"))


class RefusalTests(unittest.TestCase):
    """X01（欠落）・X02（衝突）・X06（クラス別の義務）・X07（防護例）：拒否は全か無か。"""

    def check_refusal(self, mutate, code, base=("p0-positive",), target="p1-finite-forecast"):
        registry = base_registry(*base)
        manifest = deepcopy(shipped()[target])
        mutate(manifest)
        before = [m["id"] for m in registry]
        codes = refused_codes(registry, manifest)
        self.assertIsNotNone(codes, f"{code} が拒否されなかった")
        self.assertIn(code, codes)
        self.assertEqual([m["id"] for m in registry], before, "拒否したのに登録が変わった")

    def test_an_obligation_of_the_r6_class_declared_by_another_class_is_refused(self):
        """R6（公理つき読み取りモジュール）の義務を、R2 の拡張が宣言することは認めない。"""
        self.check_refusal(lambda m: m["obligations"].append({**deepcopy(m["obligations"][0]), "id": "R6-1"}), "obligation_of_another_class")

    def test_an_obligation_of_the_joint_class_declared_by_another_class_is_refused(self):
        self.check_refusal(lambda m: m["obligations"].append({**deepcopy(m["obligations"][0]), "id": "JOINT-1"}), "obligation_of_another_class")

    def test_class_joint_requires_the_r2_and_r6_obligations_and_its_own(self):
        self.assertTrue({f"R2-{i}" for i in range(1, 6)} | {f"R6-{i}" for i in range(1, 7)} | {f"JOINT-{i}" for i in range(1, 7)} | set(COMMON) <= set(REQUIRED["JOINT"]))
        self.assertEqual(len(REQUIRED["JOINT"]), len(set(REQUIRED["JOINT"])))

    def test_class_r6_requires_the_r2_obligations_and_its_own(self):
        self.assertTrue({f"R2-{i}" for i in range(1, 6)} | {f"R6-{i}" for i in range(1, 7)} | set(COMMON) <= set(REQUIRED["R6"]))
        self.assertEqual(len(REQUIRED["R6"]), len(set(REQUIRED["R6"])))

    def test_every_missing_top_level_field_is_refused(self):
        for key in TOP_LEVEL:
            with self.subTest(field=key):
                self.check_refusal(lambda m, k=key: m.pop(k), "missing_field")

    def test_unknown_field_class_schema_and_review_claim_are_refused(self):
        self.check_refusal(lambda m: m.update(extra=1), "unknown_field")
        self.check_refusal(lambda m: m.update({"class": "R9"}), "unknown_class")
        self.check_refusal(lambda m: m.update(schema_version="x"), "unsupported_manifest_schema")
        self.check_refusal(lambda m: m["status"].update(independent_review=True), "independent_review_claim_without_record")

    def test_removing_any_class_required_obligation_is_refused(self):
        for ident, manifest in shipped().items():
            if ident == "p0-positive":
                continue
            for need in REQUIRED[manifest["class"]]:
                with self.subTest(extension=ident, missing=need):
                    chain = {"p0-definitions": ("p0-positive",), "p1-finite-forecast": ("p0-positive",), "p1-events": ("p0-positive",),
                             "p1-handover-host": ("p0-positive", "p1-events"),
                             "p1-event-chain": ("p0-positive", "p1-events", "p1-handover-host"),
                             "p1-projection": ("p0-positive", "p1-events", "p1-handover-host"),
                             "p1-reference": ("p0-positive", "p1-events", "p1-handover-host"),
                             "p1-absence": ("p0-positive", "p1-events", "p1-handover-host"),
                             "p1-replay": ("p0-positive", "p1-events", "p1-handover-host", "p1-event-chain"),
                             "p2-concept-split": ("p0-positive",),
                             "p2-temporal-assertion": ("p0-positive",),
                             "p2-quantity-literal": ("p0-positive",),
                             "p2-measurement-binding": ("p0-positive", "p2-quantity-literal"),
                             "p2-split-combination": ("p0-positive", "p2-concept-split")}[ident]
                    self.check_refusal(lambda m, n=need: m["obligations"].__delitem__([o["id"] for o in m["obligations"]].index(n)),
                                       "missing_obligation", chain, ident)

    def test_an_obligation_of_another_class_is_refused(self):
        self.check_refusal(lambda m: m["obligations"].append({"id": "R3-1", "statement": "x", "evidence": "self_declared", "checks": [], "guards": [], "guard_gap": "理由を書いた"}),
                           "obligation_of_another_class")

    def test_guard_rules(self):
        def no_reason(m):
            m["obligations"][0]["guards"] = []
            m["obligations"][0].pop("guard_gap", None)
        self.check_refusal(no_reason, "unexplained_guard_gap")
        def both(m):
            m["obligations"][0]["guard_gap"] = "防護例もあるのに欠落の理由を書く"
        self.check_refusal(both, "guard_gap_with_guards")
        def wrong_outcome(m):
            m["obligations"][0]["guards"][0]["equals"] = ["unexpected"]
        self.check_refusal(wrong_outcome, "guard_outcome_mismatch")
        def missing_example(m):
            m["obligations"][0]["guards"][0]["example"] = "examples/p1-a/no-such-example.json"
        self.check_refusal(missing_example, "missing_guard_example")
        def bad_kind(m):
            m["obligations"][0]["guards"][0]["kind"] = "decoration"
        self.check_refusal(bad_kind, "invalid_guards")

    def test_evidence_and_checks_are_verified(self):
        self.check_refusal(lambda m: m["obligations"][0].update(evidence="trust_me"), "unknown_evidence")
        self.check_refusal(lambda m: m["obligations"][0]["checks"].append("tests/no_such_test.py"), "missing_check_file")
        self.check_refusal(lambda m: m["obligations"][0]["checks"].append("tests/test_p1_forecast.py::test_no_such_name"), "missing_check_name")

    def test_declaration_must_match_the_actual_files(self):
        self.check_refusal(lambda m: m["spec"].update(sha256="0" * 64), "spec_hash_mismatch")
        self.check_refusal(lambda m: m["owns"]["answer_kinds"].append("a_kind_the_code_never_mentions"), "owned_name_not_found")
        self.check_refusal(lambda m: m["implementation"]["modules"].append("scripts/research/evaluate-p0.py"), "implementation_outside_package")
        self.check_refusal(lambda m: m["implementation"]["modules"].append("src/med_dsl/no_such_module.py"), "missing_module")
        self.check_refusal(lambda m: m.update(contract_doc="docs/research/no-such.md"), "missing_contract_doc")

    def test_malformed_fields_are_refused_with_their_own_codes(self):
        cases = [
            (lambda m: m.update(id=""), "expected_nonempty_string"),
            (lambda m: m.update(status={"review_state": "author_draft"}), "invalid_status"),
            (lambda m: m.update(spec={"path": "x", "sha256": "short"}), "invalid_spec"),
            (lambda m: m["implementation"].update(modules=[]), "invalid_implementation"),
            (lambda m: m.update(pins=[{"path": "x"}]), "invalid_pin"),
            (lambda m: m.update(pins="x"), "expected_array"),
            (lambda m: m.update(embedded_in=[""]), "invalid_embedded_in"),
            (lambda m: m.update(depends_on=[{"id": "p0-positive"}]), "invalid_dependency"),
            (lambda m: m["owns"].pop("operations"), "invalid_owns"),
            (lambda m: m["owns"].update(operations=["a", "a"]), "invalid_owns"),
            (lambda m: m.update(scope={}), "invalid_scope"),
            (lambda m: m["stops"].pop("resource"), "invalid_stops"),
            (lambda m: m["composition"].update(order_dependent="no"), "invalid_composition"),
            (lambda m: m["evaluation"].update(budget_sweep="yes"), "invalid_evaluation"),
            (lambda m: m["obligations"].append("x"), "invalid_obligation"),
            (lambda m: m["obligations"].append(deepcopy(m["obligations"][0])), "invalid_or_duplicate_obligation_id"),
            (lambda m: m["obligations"][0].update(checks="x"), "invalid_checks"),
            (lambda m: m["obligations"][0].update(statement=""), "expected_nonempty_string"),
            (lambda m: m["obligations"][0].update(derivation=""), "invalid_derivation"),
        ]
        for mutate, code in cases:
            with self.subTest(expected=code):
                self.check_refusal(mutate, code)

    def test_missing_files_named_by_a_declaration_are_refused(self):
        self.check_refusal(lambda m: m["spec"].update(path="src/med_dsl/no_such_spec.json"), "missing_spec")
        self.check_refusal(lambda m: m["pins"].append({"path": "src/med_dsl/no_such_pin.json", "role": "native_spec"}), "missing_pin")
        self.check_refusal(lambda m: m["evaluation"]["examples"].append("examples/no-such-folder/*.json"), "evaluation_examples_not_found")
        self.check_refusal(lambda m: m["evaluation"]["tests"].append("tests/no_such_test_file.py"), "missing_test_file")

    def test_registry_rules_duplicate_unresolved_dependency_and_base(self):
        registry = base_registry("p0-positive", "p1-finite-forecast")
        self.assertIn("duplicate_extension", refused_codes(registry, shipped()["p1-finite-forecast"]))
        self.check_refusal(lambda m: m["depends_on"].__setitem__(0, {"id": "p0-positive", "version": "draft-1"}), "unresolved_dependency")
        self.check_refusal(lambda m: m["depends_on"].clear(), "must_depend_on_base")
        self.assertIn("base_not_registered", refused_codes(Registry(ROOT, evaluate), shipped()["p1-finite-forecast"]))
        second_base = deepcopy(shipped()["p0-positive"])
        second_base["id"] = "another-base"
        self.assertIn("base_must_be_first", refused_codes(base_registry("p0-positive"), second_base))

    def test_owner_conflicts_for_every_kind_including_namespaces(self):
        samples = {"operations": "reify_events", "schema_versions": "p1-events-request-draft-1", "profiles": "p1-events-draft-1",
                   "answer_kinds": "native_event_roles", "predicates": "urn:med-dsl:events:", "capabilities": "p0-positive-1"}
        for kind, token in samples.items():
            with self.subTest(kind=kind, token=token):
                def take(m, k=kind, t=token):
                    m["owns"][k].append(t)
                registry = base_registry("p0-positive", "p1-events")
                manifest = deepcopy(shipped()["p1-finite-forecast"])
                take(manifest)
                # 実装に現れる名前にして、所有の衝突だけを検査する
                manifest["implementation"]["modules"] = ["src/med_dsl/forecast.py", "src/med_dsl/events.py", "src/med_dsl/model.py", "src/med_dsl/host.py"]
                self.assertIn("owner_conflict", refused_codes(registry, manifest))

    def test_shared_names_and_undeclared_reads_are_refused(self):
        self.check_refusal(lambda m: m["composition"].update(shares_names_with=["p0-positive"]), "shared_names_need_joint_check")
        self.check_refusal(lambda m: m["composition"].update(reads_extensions=["p1-events"]), "undeclared_read")

    def test_refusal_is_atomic_for_a_whole_batch(self):
        registry = base_registry("p0-positive")
        good = shipped()["p1-finite-forecast"]
        bad = deepcopy(good)
        bad["id"] = "p1-broken"
        bad.pop("owns")
        registry.register(good)
        with self.assertRaises(Refused):
            registry.register(bad)
        self.assertEqual([m["id"] for m in registry], ["p0-positive", "p1-finite-forecast"])


class NonInterferenceTests(unittest.TestCase):
    """X03：ある拡張を無効にしても、その拡張とそれに依存する拡張に属さない全例の結果は変わらない。"""

    DISABLED = support.DISABLABLE

    @classmethod
    def setUpClass(cls):
        cls.registry = standard_registry(ROOT, evaluate=evaluate)
        cls.requests = support.load_requests()
        cls.baseline = {name: canonical_bytes(evaluate(deepcopy(request))) for name, request in cls.requests}

    def functions_of(self, ident):
        return support.functions_of(self.registry, ident)

    def inert(self, ident):
        return support.inert(self.registry, ident)

    def dependents(self, ident):
        return support.dependents(self.registry, ident)

    def owner_of(self, request):
        return support.owner_of(self.registry, request)

    def test_disabling_each_extension_changes_nothing_outside_it_and_its_dependents(self):
        for ident in self.DISABLED:
            excluded = self.dependents(ident)
            inside, outside = [], []
            for name, request in self.requests:
                (inside if self.owner_of(request) in excluded else outside).append((name, request))
            self.assertTrue(inside and outside, ident)
            with self.inert(ident):
                changed_inside = [n for n, r in inside if canonical_bytes(evaluate(deepcopy(r))) != self.baseline[n]]
                changed_outside = [n for n, r in outside if canonical_bytes(evaluate(deepcopy(r))) != self.baseline[n]]
            with self.subTest(extension=ident):
                self.assertEqual(changed_outside, [], "無効にした拡張の外の結果が変わった（非干渉の破れ）")
                self.assertTrue(changed_inside, "無効化が効いていない（検査が空振り）")

    def test_the_inert_switch_is_restored_afterwards(self):
        with self.inert("p1-event-chain"):
            pass
        after = {name: canonical_bytes(evaluate(deepcopy(request))) for name, request in self.requests}
        self.assertEqual(after, self.baseline)

    def test_an_undeclared_read_is_exposed_by_disabling_the_extension_that_is_read(self):
        """p1-replay は archive の意味引き継ぎで鎖の認定（run_chain）を呼ぶ。この読み取りを宣言から落とすと、
        鎖を無効にしたときに replay の結果が変わり、非干渉の検査が破れを報告する（宣言の誤りを検出できる）。"""
        manifests = {m["id"]: deepcopy(m) for m in self.registry}
        manifests["p1-replay"]["depends_on"] = [d for d in manifests["p1-replay"]["depends_on"] if d["id"] != "p1-event-chain"]
        manifests["p1-replay"]["composition"]["reads_extensions"] = []
        flawed = Registry(ROOT, evaluate)
        for ident in IDS:
            flawed.register(manifests[ident])
        original, self.registry = self.registry, flawed
        try:
            excluded = self.dependents("p1-event-chain")
            outside = [(n, r) for n, r in self.requests if self.owner_of(r) not in excluded]
        finally:
            self.registry = original
        self.assertNotIn("p1-replay", excluded)

        with self.inert("p1-event-chain"):
            changed = [n for n, r in outside if canonical_bytes(evaluate(deepcopy(r))) != self.baseline[n]]
        self.assertTrue(any("p1-c/" in n for n in changed), "宣言の誤りが非干渉の検査で見つからなかった")

    def test_every_example_has_an_owner_and_the_base_owns_the_p0_requests(self):
        owners = {name: self.owner_of(request) for name, request in self.requests}
        self.assertNotIn(None, owners.values())
        for name, owner in owners.items():
            if name.startswith("p0/"):
                operation = dict(self.requests)[name]["operation"]
                self.assertEqual(owner, "p0-definitions" if operation == "check_extension" else "p0-positive", name)


class ReverificationTests(unittest.TestCase):
    """X13：宣言と import の関係から、再検証が要る拡張と、hash を埋め込んだため再生成が要る実体を列挙する。"""

    @classmethod
    def setUpClass(cls):
        cls.registry = standard_registry(ROOT, evaluate=evaluate)

    def test_module_graph_follows_relative_imports(self):
        graph = module_graph(ROOT)
        self.assertIn("validation", graph["forecast"])
        self.assertIn("events", graph["handover"])
        self.assertIn("projection", graph["handover"])
        self.assertNotIn("forecast", graph["handover"])
        self.assertEqual(graph["model"], set())

    def test_a_change_to_the_forecast_module_affects_only_forecast(self):
        result = affected(self.registry, ["src/med_dsl/forecast.py"])
        self.assertEqual(result["extensions"], ["p1-finite-forecast"])
        self.assertEqual(result["regenerate"], [])
        self.assertEqual(result["lock"], LOCK)

    def test_a_change_to_a_pinned_spec_also_lists_the_artifacts_that_embed_its_hash(self):
        result = affected(self.registry, ["src/med_dsl/forecast_spec.json"])
        self.assertEqual(result["extensions"], ["p1-finite-forecast"])
        self.assertIn("src/med_dsl/forecast.py", result["regenerate"])
        self.assertIn("examples/p1-a/finite-forecast.json", result["regenerate"])
        self.assertNotIn("examples/p1-b/native-query.json", result["regenerate"])

    def test_a_change_to_the_events_module_reaches_every_handover_extension_through_the_declared_dependencies(self):
        result = affected(self.registry, ["src/med_dsl/events.py"])
        self.assertEqual(result["extensions"], sorted(["p1-events", "p1-handover-host", "p1-event-chain", "p1-projection", "p1-reference", "p1-absence", "p1-replay"]))
        self.assertNotIn("p1-finite-forecast", result["extensions"])
        self.assertNotIn("p0-positive", result["extensions"])

    def test_an_unrelated_change_affects_nothing(self):
        result = affected(self.registry, ["docs/research/16-review-plan.md", "README.md"])
        self.assertEqual((result["extensions"], result["regenerate"], result["lock"]), ([], [], None))

    def test_the_kernel_change_of_draft_2_is_enumerated_and_covers_the_forced_repin(self):
        """draft-2 の RV-05（validation.py の確認の時刻順＋P0 契約）。実際に再固定が要った実体は、列挙に含まれる。"""
        changed = ["src/med_dsl/validation.py", "docs/research/06-p0-contract.md"]
        result = affected(self.registry, changed)
        self.assertEqual(result["extensions"], sorted(IDS))
        for expected in ("src/med_dsl/handover.py", "src/med_dsl/handover_spec.json", "examples/p1-c/event-renaming-chain.json",
                         "examples/p1-c/manifest.json", "examples/audits/existential-reversed.json"):
            self.assertIn(expected, result["regenerate"])
        self.assertEqual(result["lock"], LOCK)
        # 実際の履歴：e73d4ba（draft-1）から 2b501c1（draft-2）で、三つの hash の置換だけで変わったファイル
        try:
            for commit in ("e73d4ba", "2b501c1"):
                subprocess.run(["git", "cat-file", "-e", commit], cwd=ROOT, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("git の履歴（e73d4ba／2b501c1）がない")
        show = lambda commit, path: subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True).stdout
        names = subprocess.run(["git", "diff", "--name-only", "e73d4ba", "2b501c1"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        import re

        def constants(commit):
            text = show(commit, "src/med_dsl/handover.py").decode("utf-8")
            return {key: re.search(rf'^{name} = "([0-9a-f]{{64}})"', text, re.M).group(1)
                    for key, name in (("spec", "HANDOVER_SPEC_SHA256"), ("p0", "P0_SPEC_SHA256"), ("rt", "P0_RUNTIME_SHA256"))}
        old, new = constants("e73d4ba"), constants("2b501c1")
        self.assertTrue(all(old[k] != new[k] for k in old))
        pure, changed_files = set(), set(names)
        for name in names:
            before, after = show("e73d4ba", name), show("2b501c1", name)
            if before and after and before != after:
                restored = after.decode("utf-8", "replace")
                for key in new:
                    restored = restored.replace(new[key], old[key])
                if name.startswith(("examples/p1-c/", "examples/audits/")) and name != "examples/p1-c/manifest.json" and restored.encode() == before:
                    pure.add(name)
        self.assertGreaterEqual(len(pure), 27)              # p1-c の27例（PR01 は 559244d で追加されたので e73d4ba にはない）
        predicted = set(result["regenerate"])
        self.assertTrue(pure <= predicted, sorted(pure - predicted))                    # 漏れなし
        existed = {p for p in predicted if show("e73d4ba", p)}
        self.assertTrue(existed <= changed_files, sorted(existed - changed_files))     # 予測した実体はすべて実際に変わった


class FakeRegistry:
    def __init__(self, root, items):
        self.root = Path(root)
        self._items = {m["id"]: m for m in items}

    def __iter__(self):
        return iter(self._items.values())

    def get(self, ident):
        return self._items[ident]


def toy_manifest(ident, modules, **kwargs):
    base = {"id": ident, "implementation": {"modules": modules}, "spec": None, "contract_doc": f"docs/{ident}.md", "pins": [],
            "depends_on": [], "embedded_in": []}
    base.update(kwargs)
    return base


class AffectedLogicTests(unittest.TestCase):
    """列挙の各規則を、小さな人工の木で一つずつ確かめる（実際の宣言では他の規則と重なって見えない規則を含む）。"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        package = self.root / "src/med_dsl"
        package.mkdir(parents=True)
        (package / "a.py").write_text("from .b import x\n")
        (package / "b.py").write_text("from . import c\nx = 1\n")
        (package / "c.py").write_text("y = 2\n")
        (package / "d.py").write_text("z = 3\n")
        (self.root / "art").mkdir()
        for name in ("one", "two"):
            (self.root / "art" / f"{name}.json").write_text("{}")

    def tearDown(self):
        self.folder.cleanup()

    def run_affected(self, items, changed):
        return affected(FakeRegistry(self.root, items), changed)

    def test_an_import_chain_makes_a_transitive_module_change_affect_the_importer(self):
        items = [toy_manifest("A", ["src/med_dsl/a.py"]), toy_manifest("D", ["src/med_dsl/d.py"])]
        result = self.run_affected(items, ["src/med_dsl/c.py"])
        self.assertEqual(result["extensions"], ["A"])
        self.assertEqual(result["reasons"]["A"], ["src/med_dsl/c.py"])
        self.assertEqual(self.run_affected(items, ["src/med_dsl/d.py"])["extensions"], ["D"])

    def test_dependents_are_affected_even_when_their_own_files_are_not_touched(self):
        items = [toy_manifest("A", ["src/med_dsl/a.py"]), toy_manifest("B", ["src/med_dsl/d.py"], depends_on=[{"id": "A", "version": "v"}])]
        result = self.run_affected(items, ["src/med_dsl/b.py"])
        self.assertEqual(result["extensions"], ["A", "B"])
        self.assertTrue(result["reasons"]["B"][0].startswith("depends_on:A"))

    def test_spec_contract_and_pin_paths_each_affect_their_extension(self):
        items = [toy_manifest("E", ["src/med_dsl/d.py"], spec={"path": "spec_e.json", "sha256": "0" * 64}, contract_doc="doc_e.md",
                              pins=[{"path": "pin_e.txt", "role": "native_spec"}])]
        for path in ("spec_e.json", "doc_e.md", "pin_e.txt"):
            with self.subTest(path=path):
                self.assertEqual(self.run_affected(items, [path])["extensions"], ["E"])
        self.assertEqual(self.run_affected(items, ["elsewhere.txt"])["extensions"], [])

    def test_only_a_changed_pin_lists_the_artifacts_that_embed_its_hash(self):
        items = [toy_manifest("F", ["src/med_dsl/d.py"], pins=[{"path": "pin_f.txt", "role": "native_spec"}], embedded_in=["art/*.json"])]
        self.assertEqual(self.run_affected(items, ["pin_f.txt"])["regenerate"], ["art/one.json", "art/two.json"])
        self.assertEqual(self.run_affected(items, ["src/med_dsl/d.py"])["regenerate"], [])

    def test_a_registration_import_is_not_followed_but_an_ordinary_one_is(self):
        """host が登録のために member を import し、member の拡張が host の拡張に依存するとき、member の変更は host に及ばない。
        依存の宣言がなければ、同じ import は通常の辺として辿る（逆向きの読み取りを見逃さない）。"""
        package = self.root / "src/med_dsl"
        (package / "hub.py").write_text("from . import member\n")
        (package / "member.py").write_text("v = 1\n")
        hub = toy_manifest("H", ["src/med_dsl/hub.py"])
        member = toy_manifest("M", ["src/med_dsl/member.py"], depends_on=[{"id": "H", "version": "v"}])
        self.assertEqual(self.run_affected([hub, member], ["src/med_dsl/member.py"])["extensions"], ["M"])
        self.assertEqual(self.run_affected([hub, member], ["src/med_dsl/hub.py"])["extensions"], ["H", "M"])
        independent = toy_manifest("M", ["src/med_dsl/member.py"])
        self.assertEqual(self.run_affected([hub, independent], ["src/med_dsl/member.py"])["extensions"], ["H", "M"])
        indirect = toy_manifest("N", ["src/med_dsl/d.py"], depends_on=[{"id": "M", "version": "v"}])
        self.assertEqual(self.run_affected([hub, member, indirect], ["src/med_dsl/member.py"])["extensions"], ["M", "N"])

    def test_a_registration_import_reaches_through_a_chain_of_dependents(self):
        """host が import するモジュールの拡張が、host に直接ではなく、別の拡張を経由して依存するときも、登録の辺として辿らない。"""
        package = self.root / "src/med_dsl"
        (package / "hub.py").write_text("from . import member, deep\n")
        (package / "member.py").write_text("v = 1\n")
        (package / "deep.py").write_text("w = 1\n")
        hub = toy_manifest("H", ["src/med_dsl/hub.py"])
        member = toy_manifest("M", ["src/med_dsl/member.py"], depends_on=[{"id": "H", "version": "v"}])
        deep = toy_manifest("N", ["src/med_dsl/deep.py"], depends_on=[{"id": "M", "version": "v"}])
        self.assertEqual(self.run_affected([hub, member, deep], ["src/med_dsl/deep.py"])["extensions"], ["N"])
        self.assertEqual(self.run_affected([hub, member, deep], ["src/med_dsl/member.py"])["extensions"], ["M", "N"])
        self.assertEqual(self.run_affected([hub, member, deep], ["src/med_dsl/hub.py"])["extensions"], ["H", "M", "N"])

    def test_the_lock_is_listed_only_when_a_locked_file_changes(self):
        lock = self.root / LOCK
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"files": {"src/med_dsl/d.py": {}}}))
        items = [toy_manifest("D", ["src/med_dsl/d.py"])]
        self.assertEqual(self.run_affected(items, ["src/med_dsl/d.py"])["lock"], LOCK)
        self.assertIsNone(self.run_affected(items, ["notes.txt"])["lock"])


class IndependenceLogicTests(unittest.TestCase):
    """L3：独立の判定の各条件を、小さな人工の木で一つずつ確かめる。"""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        package = self.root / "src/med_dsl"
        package.mkdir(parents=True)
        (package / "kernel.py").write_text("k = 0\n")
        (package / "a.py").write_text("from . import kernel\n")
        (package / "b.py").write_text("from . import kernel\n")
        (package / "c.py").write_text("from . import a\n")

    def tearDown(self):
        self.folder.cleanup()

    def pairs(self, *items):
        base = toy_manifest("BASE", ["src/med_dsl/kernel.py"], **{"class": "BASE", "composition": {"shares_names_with": [], "reads_extensions": [], "order_dependent": False}})
        return independent_pairs(FakeRegistry(self.root, [base, *items]), self.root)

    @staticmethod
    def ext(ident, module, **kwargs):
        composition = {"shares_names_with": [], "reads_extensions": kwargs.pop("reads", []), "order_dependent": kwargs.pop("order", False)}
        return toy_manifest(ident, [f"src/med_dsl/{module}.py", *kwargs.pop("extra", [])], **{"class": "R2", "composition": composition}, **kwargs)

    def test_two_extensions_with_nothing_in_common_but_the_kernel_are_independent(self):
        self.assertEqual(self.pairs(self.ext("A", "a"), self.ext("B", "b")), [("A", "B")])

    def test_a_dependency_a_read_and_an_order_dependence_each_make_a_pair_dependent(self):
        self.assertEqual(self.pairs(self.ext("A", "a"), self.ext("B", "b", depends_on=[{"id": "A", "version": "v"}])), [])
        self.assertEqual(self.pairs(self.ext("A", "a", reads=["B"]), self.ext("B", "b")), [])
        self.assertEqual(self.pairs(self.ext("A", "a"), self.ext("B", "b", reads=["A"])), [])
        self.assertEqual(self.pairs(self.ext("A", "a", order=True), self.ext("B", "b")), [])
        self.assertEqual(self.pairs(self.ext("A", "a"), self.ext("B", "b", order=True)), [])

    def test_a_transitive_dependency_makes_a_pair_dependent(self):
        chain = self.pairs(self.ext("A", "a"), self.ext("B", "b", depends_on=[{"id": "A", "version": "v"}]),
                           self.ext("C", "c", depends_on=[{"id": "B", "version": "v"}]))
        self.assertNotIn(("A", "C"), chain)

    def test_importing_the_other_extensions_own_module_makes_a_pair_dependent_in_either_direction(self):
        self.assertEqual(self.pairs(self.ext("A", "a"), self.ext("C", "c")), [])
        self.assertEqual(self.pairs(self.ext("C", "c"), self.ext("A", "a")), [])

    def test_a_module_the_base_declared_is_the_kernel_and_does_not_make_a_pair_dependent(self):
        self.assertEqual(self.pairs(self.ext("A", "a", extra=["src/med_dsl/kernel.py"]), self.ext("B", "b")), [("A", "B")])

    def test_the_base_is_never_in_a_pair(self):
        self.assertTrue(all("BASE" not in pair for pair in self.pairs(self.ext("A", "a"), self.ext("B", "b"))))


class RealAffectedTests(unittest.TestCase):
    def test_contract_document_and_dispatcher_changes_are_enumerated(self):
        registry = standard_registry(ROOT, evaluate=evaluate)
        self.assertEqual(affected(registry, ["docs/research/12-p1-a-contract.md"])["extensions"], ["p1-finite-forecast"])
        self.assertEqual(affected(registry, ["src/med_dsl/__init__.py"])["extensions"], sorted(IDS))
        self.assertEqual(affected(registry, ["src/med_dsl/host.py"])["extensions"], sorted(IDS))

    def test_a_change_to_one_handover_operation_affects_only_that_extension_and_the_ones_that_read_it(self):
        """拡張ホストの分離（P2-a の後）の効果：引き継ぎの操作が一つのモジュールにあったとき、どの操作の変更も 6 件すべてを列挙していた。"""
        registry = standard_registry(ROOT, evaluate=evaluate)
        one = lambda stem: affected(registry, [f"src/med_dsl/{stem}.py"])["extensions"]
        self.assertEqual(one("absence"), ["p1-absence"])
        self.assertEqual(one("replay"), ["p1-replay"])
        self.assertEqual(one("projection"), ["p1-projection"])
        self.assertEqual(one("reference"), ["p1-reference"])
        self.assertEqual(one("chain"), ["p1-event-chain", "p1-replay"])      # replay は鎖の認定を読む（宣言済み）
        family = sorted(["p1-handover-host", "p1-event-chain", "p1-projection", "p1-reference", "p1-absence", "p1-replay"])
        self.assertEqual(one("handover"), family)
        self.assertEqual(one("handover_common"), family)
        self.assertEqual(one("forecast"), ["p1-finite-forecast"])


class CommandLineTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/research/check-extensions.py"), *args], cwd=ROOT, capture_output=True, text=True)

    def test_the_check_passes_on_the_shipped_declarations_and_strict_mode_reports_the_gaps(self):
        plain = self.run_script("--json")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        report = json.loads(plain.stdout)
        self.assertEqual((len(report["registered"]), report["refused"]), (15, []))
        self.assertEqual(report["guard_gaps"], sum(len(v) for v in KNOWN_GAPS.values()))
        self.assertEqual(self.run_script("--strict").returncode, 1)

    def test_a_broken_declaration_directory_fails_with_the_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            for path in (ROOT / "extensions").glob("*.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("id") == "p1-finite-forecast":
                    data["obligations"] = [o for o in data["obligations"] if o["id"] != "R2-4"]
                (Path(folder) / path.name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = self.run_script("--directory", folder, "--json")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertIn("p1-finite-forecast", [r["id"] for r in report["refused"]])
        self.assertTrue(any(f["code"] == "missing_obligation" for r in report["refused"] for f in r["findings"]))


if __name__ == "__main__":
    unittest.main()
