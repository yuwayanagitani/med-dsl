"""固定した Q の支持 binding を比較する。比較不能を空の差分にしない。"""

from .model import Budget
from .query import run_query
from .validation import digest


def _binding_key(binding):
    return tuple(sorted(binding.items()))


def run_compare(request, inputs, closures):
    budget = Budget(request["budget"]["max_steps"])
    sides = {}
    for side in ("before", "after"):
        snapshot = request[side]
        sides[side] = {"snapshot_sha256": digest(snapshot),
                       "package_ref": snapshot["package"]["ref"],
                       "ledger_ref": snapshot["ledger"]["ref"],
                       **run_query(inputs[side], closures[side], budget)}
    result = {"status": "resource_limit" if any(s["status"] == "resource_limit" for s in sides.values()) else "ok",
              "view": dict(request["view"]), "scope": "positive_query_bindings",
              **sides, "results": [], "incomplete": [],
              "reason_codes": sorted(set(sides["before"]["reason_codes"]) | set(sides["after"]["reason_codes"]))}
    after_queries = {q["id"]: q for q in inputs["after"]["queries"]}
    before_rows = {r["query"]: r for r in sides["before"]["results"]}
    after_rows = {r["query"]: r for r in sides["after"]["results"]}
    for query in sorted(request["queries"], key=lambda q: q["id"]):
        key = query["id"]
        before, after = before_rows[key], after_rows[key]
        row = {"view": request["view"]["id"], "query": key,
               "before_context_ref": query["context_ref"], "after_context_ref": after_queries[key]["context_ref"],
               "before_status": before["status"], "after_status": after["status"],
               "status": "incomparable", "lost": None, "added": None, "unchanged": None,
               "lost_evidence": None, "added_evidence": None, "reason_codes": []}
        for side, answer in (("before", before), ("after", after)):
            if answer["status"] in ("conflict", "unassessed"):
                row["reason_codes"].extend([side + "_" + answer["status"],
                                            *(side + "_" + code for code in answer["reason_codes"])])
        if row["reason_codes"]:
            row["reason_codes"] = sorted(set(row["reason_codes"]))
            result["incomplete"].append({"query": key, "reason_codes": row["reason_codes"]})
        else:
            left = {_binding_key(b) for b in before["bindings"]}
            right = {_binding_key(b) for b in after["bindings"]}
            lost, added = sorted(left - right), sorted(right - left)
            row.update(status="compared", lost=[dict(b) for b in lost], added=[dict(b) for b in added],
                       unchanged=[dict(b) for b in sorted(left & right)])
            for side, answer, field, selected in (("before", before, "lost_evidence", lost),
                                                   ("after", after, "added_evidence", added)):
                evidence = {_binding_key(e["binding"]): e for e in answer["evidence"]}
                row[field] = [{"ledger_ref": sides[side]["ledger_ref"], **evidence[b]} for b in selected]
        result["results"].append(row)
    return result
