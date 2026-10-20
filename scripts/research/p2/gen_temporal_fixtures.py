#!/usr/bin/env python3
"""文書31/32の手指定期待を実行例へ展開する。runtimeを呼ばず、出力から期待を生成しない。"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
DIRECTORY = ROOT / "examples/p2-temporal"
PROFILE = "p2-temporal-assertion-draft-1"
POLICY = "fiction:confirmed-scoped-revision@1"
SPEC = hashlib.sha256((ROOT / "src/med_dsl/temporal_spec.json").read_bytes()).hexdigest()
ATOM = {"predicate": "fiction:temporal:P@1", "args": ["fiction:temporal:u"]}
CONTEXT = "fiction:temporal:context@1"


def day(n):
    return f"2026-10-{n:02}T00:00:00Z"


def record(name, polarity="positive", period=(1, 10), rec=2, review=2, revises=()):
    validity = ({"kind": "bounded", "start": day(period[0]), "end": day(period[1])}
                if isinstance(period, tuple) else {"kind": period})
    a = {"id": name, "context_ref": CONTEXT, "atom": deepcopy(ATOM), "polarity": polarity,
         "certainty": "confirmed", "recorded_at": day(rec), "origin": {"kind": "observed", "ref": f"fiction:temporal:source:{name}"},
         "required_capabilities": ["p0-positive-1", PROFILE], "validity": validity, "revises": list(revises)}
    if revises:
        a["change_reason"] = "架空の期間限定の訂正"
    r = [] if review is None else [{"id": "review-" + name, "assertion_ref": name, "reviewer_ref": "fiction:temporal:human",
                                    "reviewer_kind": "human", "recorded_at": day(review), "outcome": "confirmed"}]
    return a, r


def request(records, k=9, t=5):
    records = deepcopy(records)
    return {"schema_version": "p2-temporal-request-draft-1", "operation": "probe_temporal_literal",
            "consumer": {"profile": PROFILE, "profile_spec_sha256": SPEC, "operations": ["probe_temporal_literal"]},
            "source": {"package": {"ref": "fiction:temporal:package@1", "profile": "p0-positive-1",
                                   "predicates": [{"ref": ATOM["predicate"], "roles": ["subject"]}],
                                   "definitions": [], "inclusions": [], "dependencies": []},
                       "contexts": [{"ref": CONTEXT, "subject_ref": ATOM["args"][0], "effective_at": day(1), "purpose": "fiction:research"}],
                       "ledger": {"schema_version": "p2-temporal-ledger-draft-1", "ref": "fiction:temporal:ledger@1",
                                  "assertions": [a for a, _ in records], "reviews": [r for _, rs in records for r in rs]}},
            "views": [{"id": "v", "as_of": day(k), "policy_ref": POLICY}],
            "queries": [{"id": "q", "context_ref": CONTEXT, "atom": deepcopy(ATOM), "target_at": day(t)}],
            "budget": {"max_steps": 100000}}


def check(path, value):
    return {"path": path, "equals": value}


def row(state, pos=(), neg=(), masked=(), reasons=(), index=0):
    prefix = ["results", index]
    stopped = state is None
    return [check(prefix + ["status"], "unassessed" if stopped else "ok"),
            check(prefix + ["literal_state"], state), check(prefix + ["reason_codes"], list(reasons)),
            check(prefix + ["positive_assertion_refs"], None if stopped else list(pos)),
            check(prefix + ["negative_assertion_refs"], None if stopped else list(neg)),
            check(prefix + ["masked_assertion_refs"], None if stopped else list(masked))]


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, condition, req, checks, temporal=True):
        if temporal:
            checks += [check(["meaning_mode"], "temporal_literal_probe"), check(["converted_to_base"], False),
                       check(["clinical_assertions_added"], []), check(["certificate", "status"], "not_certified"),
                       check(["retained_assertions"], sorted(a["id"] for a in req["source"]["ledger"]["assertions"]))]
        value = {"schema_version": "p1-fixture-draft-1", "fixture_version": 1,
                 "fixture_id": name, "condition": condition, "fictional": True, "review_state": "author_draft",
                 "request": req, "expected": {"comparison": "required_paths", "checks": checks}}
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
        filename = name.lower() + ".json"
        (DIRECTORY / filename).write_bytes(raw)
        entries.append({"fixture_id": name, "condition": condition, "path": filename, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

    def good(name, req, state, pos=(), neg=(), masked=(), reasons=(), extra=()):
        emit(name, name[:3], req, [check(["status"], "ok"), *row(state, pos, neg, masked, reasons), *extra])

    late = [record("A", period=(1, 5), rec=8, review=9)]
    for number, k, t, state, pos in [(1,6,3,"neither",()), (2,8,3,"neither",()), (3,9,3,"positive_only",("A",)),
                                     (4,9,1,"positive_only",("A",)), (5,9,5,"neither",()), (6,9,6,"neither",())]:
        good(f"T{number:02}", request(late, k, t), state, pos)
    revised = [record("A"), record("B", "negative", (4,6), 7,8,("A",))]
    chain = [*revised, record("C", "positive", (5,6), 9,9,("B",))]
    good("T07", request(revised,8,3), "positive_only",("A",))
    good("T08", request(revised,8,4), "negative_only",neg=("B",),masked=("A",))
    good("T09", request(chain), "positive_only",("C",),masked=("A","B"),extra=[check(["results",0,"revision_evidence"], [
        {"assertion_ref":"B", "target_ref":"A", "review_refs":["review-B"]},
        {"assertion_ref":"C", "target_ref":"B", "review_refs":["review-C"]}])])
    good("T09-start", request(chain,9,4), "negative_only",neg=("B",),masked=("A",))
    good("T09-end", request(chain,9,6), "positive_only",("A",))
    good("T10", request([record("A",period=(1,5),rec=1,review=1),record("B","negative",(5,8))]), "negative_only",neg=("B",))
    overlap = [record("A",period=(1,6),rec=1,review=1),record("B","negative",(5,8))]
    good("T11", request(overlap), "both",("A",),("B",))
    good("T12", request(overlap,t=6), "negative_only",neg=("B",))
    good("T13", request([record("A",period="unknown")]), None,reasons=("validity_unknown",))
    good("T14", request([record("A",period="unspecified"),record("B",rec=3,review=3)]), None,reasons=("validity_unspecified",))
    ai = record("A",period="unknown",review=None)
    ai[0]["origin"]["kind"] = "ai_candidate"
    good("T15", request([ai,record("B",rec=3,review=3)]), "positive_only",("B",))
    r16 = request([record("A",review=9),revised[1]],8)
    r16["views"].append({"id":"v2", "as_of":day(9), "policy_ref":POLICY})
    good("T16", r16, "negative_only",neg=("B",),masked=("A",), extra=row("negative_only",neg=("B",),masked=("A",),index=1))
    good("T17", request([record("A"),record("B","negative",(4,6),7,9,("A",))],8), "positive_only",("A",))
    x = record("X","negative",(7,8),3,None)
    x[0]["required_capabilities"].append("fiction:unknown-capability")
    good("T18", request([record("A"),x]), None,reasons=("unknown_capability",))
    future = deepcopy(x); future[0]["recorded_at"] = day(10)
    good("T19", request([record("A"),future]), "positive_only",("A",))
    unknown = deepcopy(revised); unknown[0][0]["required_capabilities"].append("fiction:unknown-capability")
    good("T20", request(unknown), None,reasons=("unknown_capability",))

    def refusal(name, req, status="invalid_input", reason=None):
        checks = [check(["status"],status)]
        if reason:
            checks.append(check(["reason_codes"],[reason]))
        emit(name,name[:3],req,checks,False)

    old = json.loads((ROOT / "examples/p0/assertion-revision.json").read_text())["request"]
    emit("N01", "N01", old, [check(["results",0,"status"],"undetermined"),check(["results",1,"status"],"opposed")],False)
    seed = request(late, t=3)
    for key in ("validity", "required_capabilities"):
        r=deepcopy(seed); del r["source"]["ledger"]["assertions"][0][key]
        refusal("N02-"+key,r)
    r=deepcopy(seed); r["source"]["ledger"]["assertions"][0]["required_capabilities"] = []
    refusal("N02-capability",r,reason="missing_temporal_capability")
    r=deepcopy(seed); r["source"]["ledger"]["assertions"][0]["validity"]["kind"]="unknown"
    refusal("N02-mixed",r)
    for name, validity in {"empty":{"kind":"bounded","start":day(5),"end":day(5)},
                           "reversed":{"kind":"bounded","start":day(6),"end":day(5)},
                           "missing":{"kind":"bounded","start":day(1)},
                           "date":{"kind":"bounded","start":"2026-02-30T00:00:00Z","end":day(5)},
                           "precision":{"kind":"bounded","start":"2026-10-01T00:00:00.1Z","end":day(5)},
                           "zone":{"kind":"bounded","start":"2026-10-01T00:00:00+00:00","end":day(5)},
                           "null":None}.items():
        r=deepcopy(seed); r["source"]["ledger"]["assertions"][0]["validity"]=validity
        refusal("N03-"+name,r)
    r=deepcopy(seed); r["source"]["ledger"]["assertions"][0]["validity"]={"kind":"open_end","start":day(1)}
    refusal("N04",r,"unsupported_profile","unsupported_validity")
    for name in ("interval","atom","context","same-time","earlier","target","reason"):
        r=request(revised); a,b=r["source"]["ledger"]["assertions"]
        if name=="interval": b["validity"]={"kind":"bounded","start":day(3),"end":day(11)}
        elif name=="atom": b["atom"]["args"]=["fiction:other-subject"]
        elif name=="context": b["context_ref"]="fiction:other-context"
        elif name=="same-time": b["recorded_at"]=a["recorded_at"]
        elif name=="earlier": b["recorded_at"]=day(1)
        elif name=="target": b["revises"]=["absent"]
        else: del b["change_reason"]
        refusal("N05-"+name,r)
    for index in (0,1):
        r=request(revised);r["source"]["ledger"]["assertions"][index]["validity"]={"kind":"unknown"}
        refusal(f"N06-{index}",r,"unsupported_profile","unsupported_revision_scope")
    for name in ("policy","profile","operation","consumer-operation","hash","ledger"):
        r=deepcopy(seed)
        if name=="policy":r["views"][0]["policy_ref"]="fiction:confirmed-explicit-revision@1"
        elif name=="profile":r["consumer"]["profile"]="unknown"
        elif name=="operation":r["operation"]="unknown"
        elif name=="consumer-operation":r["consumer"]["operations"]=["unknown"]
        elif name=="hash":r["consumer"]["profile_spec_sha256"]="0"*64
        else:r["source"]["ledger"]["schema_version"]="unknown"
        refusal("N07-"+name,r,"unsupported_profile")
    reversed_request=request(chain)
    for key in ("assertions","reviews"): reversed_request["source"]["ledger"][key].reverse()
    good("N08",reversed_request,"positive_only",("C",),masked=("A","B"))
    mixed=request([record("A"),x]);mixed["views"].append({"id":"v2","as_of":day(2),"policy_ref":POLICY})
    good("N09",mixed,None,reasons=("unknown_capability",),extra=row("positive_only",("A",),index=1))
    good("N10",seed,"positive_only",("A",))
    for name, req, maximum, used, complete in [
        ("B01",seed,0,0,False),("B02-below",seed,5,5,False),("B02-exact",seed,6,6,True),("B02-above",seed,7,6,True),
        ("B03-below",request(chain),13,13,False),("B03-exact",request(chain),14,14,True)]:
        r=deepcopy(req);r["budget"]["max_steps"]=maximum
        checks=[check(["status"],"ok" if complete else "resource_limit"),check(["steps_used"],used)]
        checks+=row("positive_only",("C",) if name.startswith("B03") else ("A",),masked=("A","B") if name.startswith("B03") else ()) if complete else row(None,reasons=("step_limit",))
        emit(name,name[:3],r,checks)
    for maximum in (6,9):
        r=deepcopy(seed);r["queries"].append({**deepcopy(r["queries"][0]),"id":"q2"});r["budget"]["max_steps"]=maximum
        checks=[check(["status"],"ok" if maximum==9 else "resource_limit"),check(["steps_used"],maximum),*row("positive_only",("A",))]
        checks+=row("positive_only",("A",),index=1) if maximum==9 else row(None,reasons=("step_limit",),index=1)
        emit(f"B04-{maximum}","B04",r,checks)
    manifest={"schema_version":"p2-temporal-manifest-draft-1","status":"author_draft","independent_review":False,"evaluation_frozen":False,
              "expectations_source":"docs/research/32-p2-e-cases.md","profile_spec_sha256":SPEC,"conditions":{"T":20,"N":10,"B":4},"files":entries}
    (DIRECTORY/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"files":len(entries),"checks":sum(len(json.loads((DIRECTORY/e['path']).read_text())["expected"]["checks"]) for e in entries),"spec_sha256":SPEC}))


if __name__ == "__main__":
    main()
