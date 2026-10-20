"""P2-e：手指定期待、区間差分との比較、停止、根拠、予算、入力・旧経路の保存。"""

from copy import deepcopy
import hashlib
import importlib.util
import itertools
import inspect
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
from med_dsl.temporal import SPEC_SHA256, TEMPORAL_PROFILE
import gen_temporal_fixtures as make
import p2_checks
import temporal_oracle as oracle
import support

DIRECTORY = ROOT / "examples/p2-temporal"


def fixture(name):
    return json.loads((DIRECTORY / (name.lower() + ".json")).read_text())["request"]


def project(row):
    return {key: row[key] for key in ("literal_state", "positive_assertion_refs", "negative_assertion_refs", "masked_assertion_refs", "reason_codes")}


def comparisons(request):
    result = evaluate(request)
    if result["status"] != "ok":
        raise AssertionError(result)
    views = {v["id"]: v for v in request["views"]}
    queries = {q["id"]: q for q in request["queries"]}
    for row in result["results"]:
        if project(row) != oracle.answer(request, views[row["view"]], queries[row["query"]]):
            raise AssertionError((request, row))
    return len(result["results"])


def grid(request, knowledge=(4,5,6)):
    request["views"] = [{"id":f"v{i}", "as_of":make.day(k), "policy_ref":make.POLICY} for i,k in enumerate(knowledge)]
    points = ["2026-09-30T23:59:59Z", make.day(1), "2026-10-01T12:00:00Z", make.day(2), "2026-10-02T12:00:00Z", make.day(3)]
    request["queries"] = [{**deepcopy(request["queries"][0]), "id":f"q{i}", "target_at":t} for i,t in enumerate(points)]
    return request


def finite_histories():
    """二区間、極性、四確認状態、包含可能な訂正辺を列挙。"""
    periods = [(1,2),(1,3),(2,3)]
    for p0,p1 in itertools.product(periods, repeat=2):
        edges = [(), ("A",)] if p0[0] <= p1[0] and p1[1] <= p0[1] else [()]
        for polarities, modes, edge in itertools.product(itertools.product(("positive","negative"),repeat=2),
                                                         itertools.product(range(4),repeat=2), edges):
            records=[]
            for i, (name,period) in enumerate((("A",p0),("B",p1))):
                review = None if modes[i]==0 else (6 if modes[i]==2 else 4+i)
                a,r = make.record(name,polarities[i],period,4+i,review,edge if i else ())
                if modes[i]==3: a["certainty"]="suspected"
                records.append((a,r))
            yield grid(make.request(records))


def chain_histories():
    for periods in (((1,3),(1,2),(1,2)), ((1,3),(1,3),(2,3)), ((1,3),(2,3),(2,3))):
        for polarity in itertools.product(("positive","negative"),repeat=3):
            for mask in range(8):
                edges=[[],[],[]]
                for bit,(child,parent) in enumerate(((1,0),(2,0),(2,1))):
                    if mask & (1<<bit): edges[child].append("ABC"[parent])
                records=[make.record("ABC"[i],polarity[i],periods[i],4+i,4+i,edges[i]) for i in range(3)]
                yield grid(make.request(records), (3,4,5,6,7))


class TemporalTests(unittest.TestCase):
    def test_hand_expectations_and_manifest_integrity(self):
        manifest=json.loads((DIRECTORY/"manifest.json").read_text())
        declaration=json.loads((ROOT/"extensions/p2-temporal-assertion.json").read_text())
        self.assertEqual({o["id"] for o in declaration["obligations"]},
                         {"K-ID","K-STOP","K-INV","K-RES","R5-1","R5-2","R5-3"}|{f"TE-{n}" for n in range(1,9)})
        self.assertEqual(manifest["conditions"],{"T":20,"N":10,"B":4})
        self.assertEqual({e["condition"] for e in manifest["files"]}, {f"{p}{n:02}" for p,c in (("T",20),("N",10),("B",4)) for n in range(1,c+1)})
        self.assertEqual({p.name for p in DIRECTORY.glob("*.json")}, {e["path"] for e in manifest["files"]}|{"manifest.json"})
        for entry in manifest["files"]:
            raw=(DIRECTORY/entry["path"]).read_bytes()
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(entry["bytes"],entry["sha256"]))
            data=json.loads(raw)
            done=subprocess.run([sys.executable,"-B","-m","med_dsl","--fixture",str(DIRECTORY/entry["path"])],
                                cwd=ROOT,env={**os.environ,"PYTHONPATH":str(ROOT/"src")},capture_output=True,text=True,timeout=30)
            result=json.loads(done.stdout)
            self.assertEqual(done.returncode,{"ok":0,"invalid_input":2,"unsupported_profile":3,"resource_limit":4}[result["status"]],done.stderr)
            self.assertEqual(p2_checks.failed_checks(result,data["expected"]["checks"]),[],entry["path"])
        report=p2_checks.suite_report("p2-temporal",evaluate)
        self.assertEqual((report["examples"],report["checks"],report["failures"]),(61,462,[]))

    def test_two_record_finite_histories_agree_with_interval_subtraction(self):
        histories=rows=0
        for req in finite_histories():
            rows+=comparisons(req); histories+=1
        self.assertEqual((histories,rows),(896,16128))

    def test_three_record_chains_and_branches_agree_with_interval_subtraction(self):
        histories=rows=0
        for req in chain_histories():
            rows+=comparisons(req); histories+=1
        self.assertEqual((histories,rows),(192,5760))

    def test_seeded_histories_with_unknowns_and_delayed_reviews(self):
        rng=random.Random(20261020)
        rows=0
        for _ in range(200):
            records=[]
            for i in range(rng.randrange(1,7)):
                start=rng.randrange(1,8); period=(start,rng.randrange(start+1,10))
                edges=[a["id"] for a,_ in records if a["validity"]["kind"]=="bounded" and a["validity"]["start"]<=make.day(period[0]) and make.day(period[1])<=a["validity"]["end"] and rng.random()<0.4]
                a,r=make.record(f"A{i}",rng.choice(("positive","negative")),period,i+2,rng.choice((None,i+2,i+5)),edges)
                if rng.random()<0.2:a["certainty"]="suspected"
                if not edges and not any(a["id"] in b["revises"] for b,_ in records) and rng.random()<0.15:
                    a["validity"]={"kind":rng.choice(("unknown","unspecified"))}
                if rng.random()<0.1:a["required_capabilities"].append("fiction:unknown")
                records.append((a,r))
            rows+=comparisons(grid(make.request(records),(3,6,10)))
        self.assertEqual(rows,3600)

    def test_budget_sweep_has_no_partial_values_or_changed_finished_rows(self):
        requests=[(n,r) for n,r in p2_checks.load_requests(("p2-temporal",)) if r["schema_version"]=="p2-temporal-request-draft-1"]
        report=p2_checks.budget_report(requests,evaluate)
        self.assertEqual(report["violations"],[])
        for _,req in requests:
            full=evaluate(req)
            if "steps_used" not in full:continue
            for n in range(full["steps_used"]+2):
                copied=deepcopy(req);copied["budget"]["max_steps"]=n
                result=evaluate(copied)
                self.assertLessEqual(result["steps_used"],n)
                for row in result["results"]:
                    if row["status"]=="unassessed":
                        for key in ("literal_state","positive_assertion_refs","negative_assertion_refs","masked_assertion_refs","assertion_evidence","revision_evidence"):
                            self.assertIsNone(row[key],(n,key))

    def test_input_immutability_and_permutation_including_evidence(self):
        for name in ("T09","T16","N09","B04-6"):
            req=fixture(name);original=deepcopy(req);full=evaluate(req)
            self.assertEqual(req,original)
            for key in ("assertions","reviews"):req["source"]["ledger"][key].reverse()
            for key in ("views","queries"):req[key].reverse()
            self.assertEqual({k:v for k,v in evaluate(req).items() if k!="input_sha256"},{k:v for k,v in full.items() if k!="input_sha256"})

    def test_evidence_includes_masked_revisers_and_only_visible_reviews(self):
        req=fixture("T09")
        later={**req["source"]["ledger"]["reviews"][0],"id":"later-review","recorded_at":make.day(10)}
        req["source"]["ledger"]["reviews"].append(later)
        req["source"]["ledger"]["reviews"].append({**later,"id":"additional-review-C","assertion_ref":"C","recorded_at":make.day(9)})
        row=evaluate(req)["results"][0]
        self.assertEqual(row["revision_evidence"],[{"assertion_ref":"B","target_ref":"A","review_refs":["review-B"]},{"assertion_ref":"C","target_ref":"B","review_refs":["additional-review-C","review-C"]}])
        self.assertEqual(row["assertion_evidence"],[{"assertion_ref":"C","polarity":"positive","validity":{"kind":"bounded","start":make.day(5),"end":make.day(6)},"review_refs":["additional-review-C","review-C"]}])
        self.assertNotIn("later-review",json.dumps(row))

    def test_unknown_validity_information_requests_do_not_offer_an_implemented_resolution(self):
        row=evaluate(fixture("T13"))["results"][0]
        self.assertEqual(row["blocking_assertion_refs"],["A"])
        self.assertFalse(row["information_requests"][0]["resolution_supported"])
        self.assertIsNone(row["assertion_evidence"])

    def test_native_identity_and_spec_mismatch_fail_closed(self):
        self.assertEqual(hashlib.sha256((ROOT/"src/med_dsl/temporal_spec.json").read_bytes()).hexdigest(),SPEC_SHA256)
        with patch("med_dsl.temporal.SPEC_SHA256","0"*64):
            self.assertEqual(evaluate(fixture("T03"))["reason_codes"],["native_spec_mismatch"])

    def test_review_order_human_requirement_and_confirmed_certainty(self):
        for mode in ("early","nonhuman","suspected"):
            req=fixture("T03")
            if mode=="early":req["source"]["ledger"]["reviews"][0]["recorded_at"]=make.day(7)
            elif mode=="nonhuman":req["source"]["ledger"]["reviews"][0]["reviewer_kind"]="ai"
            else:req["source"]["ledger"]["assertions"][0]["certainty"]="suspected"
            result=evaluate(req)
            self.assertEqual(result["status"],"ok" if mode=="suspected" else "invalid_input")
            if mode=="suspected":self.assertEqual(result["results"][0]["literal_state"],"neither")

    def test_structural_refusals_are_budget_independent(self):
        for name,req in p2_checks.load_requests(("p2-temporal",)):
            full=evaluate(req)
            if full["status"] not in ("invalid_input","unsupported_profile"):continue
            for n in (0,1,100000):
                copied=deepcopy(req);copied["budget"]["max_steps"]=n
                self.assertEqual(p2_checks.without_input_hash(evaluate(copied)),p2_checks.without_input_hash(full),name)

    def test_schema_corruption_never_raises_or_changes_input(self):
        source=fixture("T09")
        def paths(value,prefix=()):
            if isinstance(value,dict):
                for key,child in value.items():
                    yield prefix+(key,)
                    yield from paths(child,prefix+(key,))
            elif isinstance(value,list):
                for key,child in enumerate(value):
                    yield prefix+(key,)
                    yield from paths(child,prefix+(key,))
        for path in paths(source):
            for value in (None,True,0,[],{}):
                req=deepcopy(source);parent=req
                for key in path[:-1]:parent=parent[key]
                parent[path[-1]]=value
                before=deepcopy(req)
                result=evaluate(req)
                self.assertIn(result["status"],("ok","invalid_input","unsupported_profile","resource_limit"))
                self.assertEqual(req,before)

    def test_no_base_conversion_and_old_route_does_not_call_temporal(self):
        with patch("med_dsl.temporal._probe",side_effect=AssertionError("old route entered temporal")):
            self.assertEqual(evaluate(fixture("N01"))["status"],"ok")
        result=evaluate(fixture("T03"))
        self.assertFalse(result["converted_to_base"])
        self.assertEqual(result["clinical_assertions_added"],[])
        self.assertEqual(result["certificate"]["status"],"not_certified")
        self.assertNotIn("supported",json.dumps(result))

    def test_future_records_do_not_change_completed_semantic_result(self):
        before=fixture("T03");after=deepcopy(before)
        a,r=make.record("future","negative",(1,5),10,11)
        a["required_capabilities"].append("fiction:unknown")
        after["source"]["ledger"]["assertions"].append(a)
        after["source"]["ledger"]["reviews"].extend(r)
        self.assertEqual(evaluate(before)["results"],evaluate(after)["results"])

    def test_each_of_the_five_semantic_mutants_is_detected_by_its_guard(self):
        from med_dsl import temporal
        mutants = [
            ("end_inclusive", "_probe", "<= target <", "<= target <=", "T05"),
            ("ignore_confirmation_time", "_select", 'r["recorded_at"] <= as_of', 'True', "T02"),
            ("resurrect_old", "_probe", 'masked = {other for _, other in edges}',
             'edges = [(a, b) for a, b in edges if a not in {y for _, y in edges}]\n    masked = {other for _, other in edges}', "T09"),
            ("ignore_outside_unknown", "_probe", 'for key, a in visible.items():',
             'for key, a in ((k, a) for k, a in visible.items() if a["validity"]["kind"] == "bounded" and a["validity"]["start"] <= target < a["validity"]["end"]):', "T18"),
            ("absence_negative", "_probe", '"negative_only" if negative else "neither"',
             '"negative_only" if negative else "negative_only"', "T06"),
        ]
        for ident, name, old, new, case in mutants:
            source=inspect.getsource(getattr(temporal,name))
            self.assertEqual(source.count(old),1,ident)
            namespace=dict(vars(temporal))
            exec(compile(source.replace(old,new),f"<temporal-mutant:{ident}>","exec"),namespace)
            data=json.loads((DIRECTORY/(case.lower()+".json")).read_text())
            self.assertEqual(p2_checks.failed_checks(evaluate(data["request"]),data["expected"]["checks"]),[])
            with patch.object(temporal,name,namespace[name]):
                bad=p2_checks.failed_checks(evaluate(data["request"]),data["expected"]["checks"])
            self.assertTrue(bad,ident)


if __name__ == "__main__":
    unittest.main()
