"""P2-k：手指定期待、精密化を含む区間差引きとの比較、停止、根拠、予算、入力・旧経路の保存。"""

from copy import deepcopy
import hashlib
import importlib.util
import inspect
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/research"), str(ROOT / "scripts/research/p2"), str(Path(__file__).parent)]

from med_dsl import evaluate
from med_dsl.refinement import REFINEMENT_PROFILE, SPEC_SHA256
import gen_refinement_fixtures as make
import p2_checks
import refinement_oracle as oracle
import test_temporal

DIRECTORY = ROOT / "examples/p2-refinement"
WINDOWS = [(10, 14), (12, 16), (14, 18)]


def fixture(name):
    return json.loads((DIRECTORY / (name.lower() + ".json")).read_text(encoding="utf-8"))["request"]


def project(row):
    return {key: row[key] for key in ("literal_state", "positive_assertion_refs", "negative_assertion_refs", "masked_assertion_refs", "reason_codes")}


def comparisons(request):
    result = evaluate(request)
    if result["status"] != "ok":
        raise AssertionError(result)
    views = {v["id"]: v for v in request["views"]}
    queries = {q["id"]: q for q in request["queries"]}
    for row in result["results"]:
        expected = oracle.answer(request, views[row["view"]], queries[row["query"]])
        if project(row) != expected:
            raise AssertionError((request, row, expected))
    return len(result["results"])


def grid(request, knowledge=(3, 6, 9, 12), targets=(9, 10, 12, 14, 17, 18)):
    request["views"] = [{"id": f"v{i}", "as_of": make.day(k), "policy_ref": make.POLICY} for i, k in enumerate(knowledge)]
    request["queries"] = [{"id": f"q{i}", "context_ref": make.CONTEXT, "atom": deepcopy(make.ATOM), "target_at": make.day(t)}
                          for i, t in enumerate(targets)]
    return request


def refinement_choices(target, name, rec):
    """窓3通り×確認状態4通り（なし／同時／遅延／suspected）。"""
    for window in WINDOWS:
        for mode in range(4):
            review = None if mode == 0 else (rec if mode in (1, 3) else rec + 3)
            yield make.refinement(name, target, window, rec, review, "suspected" if mode == 3 else "confirmed")


def finite_histories():
    """未確定の記録1件（種類2×極性2）、精密化0〜2件、bounded な訂正の有無（窓3×極性2）。"""
    for kind, polarity in itertools.product(("unknown", "unspecified"), ("positive", "negative")):
        target = make.assertion("A", polarity, kind)
        configs = [()]
        configs += [(f,) for f in refinement_choices(target, "F1", 5)]
        configs += list(itertools.product(refinement_choices(target, "F1", 5), refinement_choices(target, "F2", 7)))
        revisers = [None] + [make.assertion("B", pol, window, 4, 4, ("A",)) for window in WINDOWS for pol in ("positive", "negative")]
        for config in configs:
            for reviser in revisers:
                records = [target] + ([reviser] if reviser else [])
                yield grid(make.request(records, list(config)))


def random_history(rng):
    records, refinements, previous = [], [], []
    for i in range(rng.randrange(1, 5)):
        kind = rng.choice(("bounded", "unknown", "unspecified", "unknown"))
        start = rng.randrange(8, 15)
        validity = (start, rng.randrange(start + 1, 19)) if kind == "bounded" else kind
        revises = []
        if kind == "bounded":
            for earlier in previous:
                old = earlier[0]["validity"]
                if old["kind"] != "bounded" or (old["start"] <= make.day(validity[0]) and make.day(validity[1]) <= old["end"]):
                    if rng.random() < 0.35:
                        revises.append(earlier[0]["id"])
        a = make.assertion(f"A{i}", rng.choice(("positive", "negative")), validity, i + 2, rng.choice((None, i + 2, i + 5)), revises,
                           rng.choice(("confirmed", "confirmed", "confirmed", "suspected")))
        if rng.random() < 0.08:
            a[0]["required_capabilities"].append("fiction:unknown")
        previous.append(a)
        records.append(a)
    for a, _ in records:
        if a["validity"]["kind"] != "bounded":
            for j in range(rng.choice((0, 0, 1, 1, 2, 3))):
                rec = int(a["recorded_at"][8:10]) + 1 + rng.randrange(0, 5)
                start = rng.randrange(8, 15)
                f = make.refinement(f"F{a['id']}-{j}", (a, []), (start, rng.randrange(start + 1, 19)), rec,
                                    rng.choice((None, rec, rec + 3)), rng.choice(("confirmed", "confirmed", "suspected")))
                if rng.random() < 0.08:
                    f[0]["required_capabilities"].append("fiction:unknown")
                    f = (f[0], [make.seal(f[0], "FR" + f[0]["id"][1:], rec)] if f[1] else [])
                refinements.append(f)
    return grid(make.request(records, refinements), (4, 8, 12), (9, 11, 13, 15, 17, 18))


class RefinementTests(unittest.TestCase):
    def test_hand_expectations_and_manifest_integrity(self):
        manifest = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
        declaration = json.loads((ROOT / "extensions/p2-validity-refinement.json").read_text(encoding="utf-8"))
        self.assertEqual({o["id"] for o in declaration["obligations"]},
                         {"K-ID", "K-STOP", "K-INV", "K-RES", "R5-1", "R5-2", "R5-3"} | {f"RF-{n}" for n in range(1, 13)})
        self.assertEqual(manifest["conditions"], {"U": 25, "N": 20, "B": 5})
        self.assertEqual({e["condition"] for e in manifest["files"]}, {f"{p}{n:02}" for p, c in (("U", 25), ("N", 20), ("B", 5)) for n in range(1, c + 1)})
        self.assertEqual({p.name for p in DIRECTORY.glob("*.json")}, {e["path"] for e in manifest["files"]} | {"manifest.json"})
        for entry in manifest["files"]:
            raw = (DIRECTORY / entry["path"]).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (entry["bytes"], entry["sha256"]))
            data = json.loads(raw)
            done = subprocess.run([sys.executable, "-B", "-m", "med_dsl", "--fixture", str(DIRECTORY / entry["path"])],
                                  cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True, timeout=30)
            result = json.loads(done.stdout)
            self.assertEqual(done.returncode, {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}[result["status"]], done.stderr)
            self.assertEqual(p2_checks.failed_checks(result, data["expected"]["checks"]), [], entry["path"])
        report = p2_checks.suite_report("p2-refinement", evaluate)
        self.assertEqual((report["examples"], report["checks"], report["failures"]), (66, 721, []))

    def test_finite_histories_with_refinements_agree_with_interval_subtraction(self):
        histories = rows = 0
        for request in finite_histories():
            rows += comparisons(request)
            histories += 1
        self.assertEqual((histories, rows), (4396, 105504))

    def test_seeded_histories_with_unknowns_conflicts_and_future_records(self):
        rng = random.Random(20261020)
        rows = stopped = 0
        states = set()
        for _ in range(300):
            request = random_history(rng)
            rows += comparisons(request)
            results = evaluate(request)["results"]
            stopped += sum(r["status"] != "ok" for r in results)
            states |= {r["literal_state"] for r in results}
        self.assertEqual(rows, 5400)
        self.assertGreater(stopped, 300)                                   # 阻害・競合・矛盾・未知能力の行が実際に現れている
        self.assertTrue({"positive_only", "negative_only", "both", "neither", None} <= states, states)     # 列挙で現れない both もここで現れる

    def test_every_final_state_of_the_semantics_occurs_in_the_enumeration(self):
        seen = set()
        for request in finite_histories():
            result = evaluate(request)
            for row in result["results"]:
                seen.add((row["literal_state"], tuple(row["reason_codes"])))
        for wanted in ((None, ("validity_unknown",)), (None, ("validity_unspecified",)), (None, ("validity_refinement_conflict",)),
                       (None, ("revision_outside_refined_validity",)), ("positive_only", ()), ("negative_only", ()), ("neither", ())):
            self.assertIn(wanted, seen)

    def test_budget_sweep_has_no_partial_values_or_changed_finished_rows(self):
        requests = [(n, r) for n, r in p2_checks.load_requests(("p2-refinement",)) if r["schema_version"] == "p2-refinement-request-draft-1"]
        report = p2_checks.budget_report(requests, evaluate)
        self.assertEqual(report["violations"], [])
        for _, req in requests:
            full = evaluate(req)
            if "steps_used" not in full:
                continue
            for n in range(full["steps_used"] + 2):
                copied = deepcopy(req)
                copied["budget"]["max_steps"] = n
                result = evaluate(copied)
                self.assertLessEqual(result["steps_used"], n)
                for row in result["results"]:
                    if row["status"] == "unassessed" and row["reason_codes"] == ["step_limit"]:
                        for key in ("literal_state", "positive_assertion_refs", "negative_assertion_refs", "masked_assertion_refs",
                                    "assertion_evidence", "revision_evidence", "refinement_evidence", "pending_refinement_refs"):
                            self.assertIsNone(row[key], (n, key))

    def test_the_cost_formula_matches_the_measured_steps(self):
        """設計50の§8の式を、台帳の件数から別に計算して、実装の steps_used と比べる。"""
        def expected(request):
            ledger = request["source"]["ledger"]
            total = 1
            for view in request["views"]:
                k = view["as_of"]
                total += sum(len(ledger[key]) for key in ("assertions", "reviews", "refinements", "refinement_reviews"))
                visible = [a for a in ledger["assertions"] if a["recorded_at"] <= k]
                reviewed = {r["assertion_ref"] for r in ledger["reviews"] if r["recorded_at"] <= k}
                edges = sum(len(a["revises"]) for a in visible if a["certainty"] == "confirmed" and a["id"] in reviewed)
                seen = sum(f["recorded_at"] <= k for f in ledger["refinements"])
                total += len(request["queries"]) * (2 + len(visible) + seen + edges)
            return total
        for name in ("U02", "U06", "U14", "U15", "U16", "U22", "U25", "B04-13"):
            request = fixture(name)
            self.assertEqual(evaluate(request)["steps_used"], expected(request), name)
        for request in itertools.islice(finite_histories(), 0, 4396, 97):
            self.assertEqual(evaluate(request)["steps_used"], expected(request))

    def test_semantics_are_inherited_from_p2_e_on_ledgers_without_refinements(self):
        """RF-D10：意味の継承と実装の共有を区別する。P2-e の全ての完了した例と有限列挙を、精密化のない P2-k の要求へ写し、
        P2-e の実装の結果と行ごとに比べる（理由コード・採用集合・除去集合）。実装は共有していないので、一致は継承の検査になる。"""
        def translate(old):
            new = deepcopy(old)
            new["schema_version"] = "p2-refinement-request-draft-1"
            new["operation"] = "probe_refined_temporal_literal"
            new["consumer"] = {"profile": REFINEMENT_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": ["probe_refined_temporal_literal"]}
            ledger = new["source"]["ledger"]
            ledger["schema_version"] = "p2-refinement-ledger-draft-1"
            ledger["refinements"], ledger["refinement_reviews"] = [], []
            for a in ledger["assertions"]:
                a["required_capabilities"] = [REFINEMENT_PROFILE if c == "p2-temporal-assertion-draft-1" else c for c in a["required_capabilities"]]
            for view in new["views"]:
                view["policy_ref"] = make.POLICY
            return new

        compared = 0
        sources = [r for _, r in p2_checks.load_requests(("p2-temporal",)) if r["schema_version"] == "p2-temporal-request-draft-1"]
        sources += list(test_temporal.finite_histories()) + list(test_temporal.chain_histories())
        for old in sources:
            before = evaluate(deepcopy(old))
            if before["status"] != "ok":
                continue
            after = evaluate(translate(old))
            self.assertEqual(after["status"], "ok")
            self.assertEqual([project(r) for r in before["results"]], [project(r) for r in after["results"]])
            compared += len(before["results"])
        self.assertEqual(compared, 21920)                                   # P2-e の完了した例 29 件の 32 行 ＋ 二記録 16,128 ＋ 三記録 5,760

    def test_pending_and_ineligible_refinements_never_change_a_result(self):
        """Y2・I3：可視の主張・適格な主張・適格な精密化が同じなら、参照時点が違っても結果は同じ。
        確認前・suspected の精密化（AI 由来の候補を含む）が可視になっても、完了した行も阻害した行も変わらない。"""
        rows = groups = witnesses = 0
        for request in itertools.islice(finite_histories(), 0, 4396, 3):
            result = evaluate(request)
            views = {v["id"]: v for v in result["views"]}
            seen, shown = {}, {}
            for row in result["results"]:
                v = views[row["view"]]
                key = (row["query"], tuple(v["visible_assertions"]), tuple(v["eligible_assertions"]), tuple(v["eligible_refinements"]))
                self.assertEqual(seen.setdefault(key, project(row)), project(row), key)
                shown.setdefault(key, set()).add(tuple(v["visible_refinements"]))
                rows += 1
            groups += len(seen)
            witnesses += sum(len(sets) > 1 for sets in shown.values())
        self.assertLess(groups, rows)                                      # 同じ状態の参照時点が実際に複数ある
        self.assertGreater(witnesses, 1000)                                # 可視の精密化だけが違う（確認前・suspected が加わる）組が実際にある

    def test_input_immutability_and_permutation_including_evidence(self):
        for name in ("U12", "U14", "U15", "U16", "U13"):
            req = fixture(name)
            original = deepcopy(req)
            full = evaluate(req)
            self.assertEqual(req, original)
            for key in ("assertions", "reviews", "refinements", "refinement_reviews"):
                req["source"]["ledger"][key].reverse()
            for key in ("views", "queries"):
                req[key].reverse()
            self.assertEqual({k: v for k, v in evaluate(req).items() if k != "input_sha256"},
                             {k: v for k, v in full.items() if k != "input_sha256"}, name)

    def test_refinement_evidence_lists_only_visible_confirmations(self):
        req = fixture("U12")
        req["source"]["ledger"]["refinement_reviews"].append(make.seal(req["source"]["ledger"]["refinements"][0], "FR1-late", 10))
        req["source"]["ledger"]["refinement_reviews"].append(make.seal(req["source"]["ledger"]["refinements"][0], "FR1-early", 7))
        row = evaluate(req)["results"][0]
        refs = {item["refinement_ref"]: item["review_refs"] for item in row["refinement_evidence"][0]["refinements"]}
        self.assertEqual(refs, {"F1": ["FR1", "FR1-early"], "F2": ["FR2"]})
        self.assertNotIn("FR1-late", json.dumps(row))

    def test_information_requests_offer_a_resolution_only_where_one_exists(self):
        unresolved = evaluate(fixture("U01"))["results"][0]["information_requests"][0]
        self.assertTrue(unresolved["resolution_supported"])
        conflict = evaluate(fixture("U08"))["results"][0]["information_requests"][0]
        self.assertFalse(conflict["resolution_supported"])
        old = evaluate(fixture("N01"))["results"][0]["information_requests"][0]
        self.assertFalse(old["resolution_supported"])                # 旧い P2-e の応答は変わらない

    def test_native_identity_and_spec_mismatch_fail_closed(self):
        self.assertEqual(hashlib.sha256((ROOT / "src/med_dsl/refinement_spec.json").read_bytes()).hexdigest(), SPEC_SHA256)
        with patch("med_dsl.refinement.SPEC_SHA256", "0" * 64):
            self.assertEqual(evaluate(fixture("U02"))["reason_codes"], ["native_spec_mismatch"])

    def test_review_order_human_requirement_and_confirmed_certainty(self):
        for mode in ("early", "nonhuman", "suspected"):
            req = fixture("U02")
            f = req["source"]["ledger"]["refinements"][0]
            if mode == "early":
                req["source"]["ledger"]["refinement_reviews"][0]["recorded_at"] = make.day(4)
            elif mode == "nonhuman":
                req["source"]["ledger"]["refinement_reviews"][0]["reviewer_kind"] = "ai"
            else:
                f["certainty"] = "suspected"
                req["source"]["ledger"]["refinement_reviews"][0] = make.seal(f, "FR1", 6)
            result = evaluate(req)
            self.assertEqual(result["status"], "ok" if mode == "suspected" else "invalid_input")
            if mode == "suspected":
                self.assertEqual(result["results"][0]["reason_codes"], ["validity_unknown"])

    def test_a_confirmation_of_a_changed_refinement_or_target_is_refused(self):
        """確認が内容 hash を拘束する：精密化の期間、対象の極性、対象の期間のいずれを変えても、変更前の確認は流用できない。"""
        for change, code in ((lambda l: l["refinements"][0]["validity"].__setitem__("end", make.day(21)), "refinement_review_hash_mismatch"),
                             (lambda l: l["assertions"][0].__setitem__("polarity", "negative"), "refinement_target_hash_mismatch"),
                             (lambda l: l["assertions"][0].__setitem__("origin", {"kind": "judgment", "ref": "fiction:refinement:other"}),
                              "refinement_target_hash_mismatch")):
            req = fixture("U02")
            change(req["source"]["ledger"])
            result = evaluate(req)
            self.assertEqual((result["status"], result["reason_codes"]), ("invalid_input", [code]))

    def test_structural_refusals_are_budget_independent(self):
        for name, req in p2_checks.load_requests(("p2-refinement",)):
            full = evaluate(req)
            if full["status"] not in ("invalid_input", "unsupported_profile"):
                continue
            for n in (0, 1, 100000):
                copied = deepcopy(req)
                copied["budget"]["max_steps"] = n
                self.assertEqual(p2_checks.without_input_hash(evaluate(copied)), p2_checks.without_input_hash(full), name)

    def test_schema_corruption_never_raises_or_changes_input(self):
        source = fixture("U14")

        def paths(value, prefix=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield prefix + (key,)
                    yield from paths(child, prefix + (key,))
            elif isinstance(value, list):
                for key, child in enumerate(value):
                    yield prefix + (key,)
                    yield from paths(child, prefix + (key,))
        for path in paths(source):
            for value in (None, True, 0, [], {}):
                req = deepcopy(source)
                parent = req
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                before = deepcopy(req)
                result = evaluate(req)
                self.assertIn(result["status"], ("ok", "invalid_input", "unsupported_profile", "resource_limit"))
                self.assertEqual(req, before)

    def test_old_route_and_new_route_are_separate_implementations(self):
        with patch("med_dsl.refinement._probe", side_effect=AssertionError("old route entered refinement")):
            self.assertEqual(evaluate(fixture("N01"))["status"], "ok")
        with patch("med_dsl.temporal._probe", side_effect=AssertionError("new route entered the P2-e probe")):
            self.assertEqual(evaluate(fixture("U02"))["status"], "ok")
        result = evaluate(fixture("U02"))
        self.assertFalse(result["converted_to_base"])
        self.assertEqual(result["clinical_assertions_added"], [])
        self.assertEqual(result["certificate"]["status"], "not_certified")
        self.assertNotIn("supported", json.dumps(result))

    def test_future_records_do_not_change_completed_semantic_result(self):
        before = fixture("U02")
        after = deepcopy(before)
        future = make.refinement("F9", (make.assertion("A")[0], []), (12, 22), 12, 13)
        future[0]["required_capabilities"].append("fiction:unknown")
        future = (future[0], [make.seal(future[0], "FR9", 13)])
        after["source"]["ledger"]["refinements"].append(future[0])
        after["source"]["ledger"]["refinement_reviews"].extend(future[1])
        self.assertEqual(evaluate(before)["results"], evaluate(after)["results"])

    def test_an_earlier_view_reproduces_the_result_before_the_refinement(self):
        """Y3：同じ台帳で、精密化の前の参照時点は精密化の前の結果、後の参照時点は後の結果を返し、互いに影響しない。"""
        request = fixture("U06")
        both = evaluate(request)["results"]
        for index, name in enumerate(("v04", "v06")):
            single = deepcopy(request)
            single["views"] = [v for v in single["views"] if v["id"] == name]
            self.assertEqual(evaluate(single)["results"][0], both[index * 2 if name == "v06" else 0])

    def test_arrival_order_of_refinements_and_corrections_does_not_change_a_view(self):
        """Y4：精密化・確認・訂正の記録時刻を入れ替えても、全てが可視な参照時点の結果は同じ。"""
        for name_a, name_b in (("U14", "U15"),):
            first, second = evaluate(fixture(name_a))["results"], evaluate(fixture(name_b))["results"]
            self.assertEqual([project(r) for r in first], [project(r) for r in second[3:]])
        one, other = evaluate(fixture("U08"))["results"], evaluate(fixture("U09"))["results"]
        self.assertEqual([project(r) for r in one], [project(r) for r in other])

    def test_each_of_the_semantic_mutants_is_detected_by_its_guard(self):
        from med_dsl import refinement
        mutants = [
            ("unreviewed_effective", "_select", 'f["certainty"] == "confirmed" and key in refinement_confirmations}', 'f["certainty"] == "confirmed"}', "U05"),
            ("suspected_effective", "_select", 'f["certainty"] == "confirmed" and key in refinement_confirmations}', 'key in refinement_confirmations}', "U10"),
            ("future_refinement_visible", "_select", 'seen = {key: f for key, f in refinements.items() if f["recorded_at"] <= as_of}',
             'seen = {key: f for key, f in refinements.items()}', "U25"),
            ("review_time_ignored", "_select", 'if r["refinement_ref"] in seen and r["recorded_at"] <= as_of:', 'if r["refinement_ref"] in seen:', "U05"),
            ("latest_wins", "_probe", '''    for key in effective:
        f = seen[key]
        groups.setdefault(f["assertion_ref"], {}).setdefault(_interval(f["validity"]), []).append(key)''',
             '''    for key in sorted(effective, key=lambda ref: seen[ref]["recorded_at"]):
        f = seen[key]
        latest = groups.setdefault(f["assertion_ref"], {})
        latest.clear()
        latest.setdefault(_interval(f["validity"]), []).append(key)''', "U08"),
            ("identical_intervals_conflict", "_probe", 'setdefault(_interval(f["validity"]), []).append(key)',
             'setdefault((_interval(f["validity"]), key), []).append(key)', "U12"),
            ("end_inclusive", "_probe", '<= target < effective_validity(key)["end"]', '<= target <= effective_validity(key)["end"]', "U03"),
            ("keep_block_after_refinement", "_probe", 'if unresolved(key) and len(groups.get(key, {})) != 1:', 'if unresolved(key):', "U02"),
            ("outside_is_negative", "_probe", '"negative_only" if negative else "neither"', '"negative_only" if negative else "negative_only"', "U03"),
            ("pending_capability_ignored", "_probe", 'unknown_refinements = {key: set(f["required_capabilities"]) - CAPABILITIES for key, f in seen.items()}',
             'unknown_refinements = {}', "U17"),
            ("containment_skipped", "_probe", '    if outside:', '    if False:', "U16"),
            ("target_hash_unchecked", "_validate", 'if item["target_sha256"] != digest(target):', 'if False:', "N04"),
            ("review_hash_unchecked", "_validate", 'if item["refinement_sha256"] != digest(refinements[ref]):', 'if False:', "N08"),
            ("bounded_target_accepted", "_validate", 'if target["validity"]["kind"] == "bounded":', 'if False:', "N02"),
            ("open_end_refinement_accepted", "_refinement_validity", 'if value["kind"] != "bounded":', 'if False:', "N06A"),
        ]
        for ident, name, old, new, case in mutants:
            source = inspect.getsource(getattr(refinement, name))
            self.assertEqual(source.count(old), 1, ident)
            namespace = dict(vars(refinement))
            exec(compile(source.replace(old, new), f"<refinement-mutant:{ident}>", "exec"), namespace)
            data = json.loads((DIRECTORY / (case.lower() + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(p2_checks.failed_checks(evaluate(deepcopy(data["request"])), data["expected"]["checks"]), [], ident)
            with patch.object(refinement, name, namespace[name]):
                try:
                    bad = p2_checks.failed_checks(evaluate(deepcopy(data["request"])), data["expected"]["checks"])
                except Exception as error:                      # 変異で内部の前提が崩れて例外になることも、検出に数える
                    bad = [repr(error)]
            self.assertTrue(bad, ident)


if __name__ == "__main__":
    unittest.main()
