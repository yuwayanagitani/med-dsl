"""欠落を否定に変える方針変更の診断（閉世界の仮定）。認定は出さない。"""

from copy import deepcopy

from .handover_common import Operation, p0_request
from .model import Problem
from .query import run_query
from .validation import validate_query


def _validate_absence(request, budget):
    p0 = p0_request(request["source"], request["views"], request["queries"], budget)
    ordered = validate_query(p0)
    if not request["views"] or not request["queries"]:
        raise Problem("empty_collection")
    for q in request["queries"]:
        if len(q["atoms"]) != 1 or any(type(t) is not str for t in q["atoms"][0]["args"]):
            raise Problem("unsupported_absence_query", status="unsupported_profile")
    return p0, ordered


def _run_absence(p0, ordered, budget):
    before = run_query(p0, ordered, budget)
    if before["status"] == "resource_limit":
        raise Problem(before["reason_codes"][0], status="resource_limit")
    rows = []
    for r in before["results"]:
        budget.tick()
        new = "opposed" if r["status"] == "undetermined" else r["status"]
        negated = lambda s: {"supported": "opposed", "opposed": "supported"}.get(s, s)
        rows.append({"view": r["view"], "query": r["query"], "before_status": r["status"], "after_status": new,
                     "before_negative_literal_status": negated(r["status"]), "after_negative_literal_status": negated(new),
                     "assumptions": ["closed_world_assumption"] if new != r["status"] else [],
                     "difference": None if r["status"] in ("unassessed", "conflict") else {"status_changed": new != r["status"]}})
    budget.tick()
    return {"status": "ok", "meaning_mode": "support_policy_probe", "source_result": before, "results": rows,
            "certificate": {"status": "not_certified", "evidence_level": "known_policy_change", "reason_codes": ["negation_semantics_changed"], "scope": None},
            "clinical_assertions_added": [], "reason_codes": [], "incomplete": deepcopy(before["incomplete"])}


def _validate(request, budget):
    return _validate_absence(request, budget)


def _run(request, validated, budget):
    return _run_absence(*validated, budget)


CHECK_ABSENCE_POLICY = Operation("check_absence_policy", ("source", "views", "queries"), True, _validate, _run)
