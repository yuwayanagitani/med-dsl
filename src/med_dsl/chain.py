"""事象化＋改名の鎖：端点・範囲の合成を実体から再計算して認定する（既知テンプレート）。"""

from copy import deepcopy

from .events import (EVENT_PROFILE, EVENT_SPEC_SHA256, _compare, _expand, _hash,
                     _queries, _restore, _source)
from .handover_common import CHAIN_FIELDS, Operation, P0_SPEC_SHA256
from .model import POLICY, PROFILE, Problem
from .validation import canonical_bytes, digest, fields, indexed, string, values


def _renaming(target, renames, target_ref):
    source, ordered = _restore(target)
    string(target_ref, "target_ledger_ref")
    if target_ref == target["ledger"]["ref"]:
        raise Problem("ledger_reference_redefined", "target_ledger_ref")
    entries = indexed(renames, "from_ref", 1000, "renames")
    old = {h["statement"]["event_ref"] for h in target["ledger"]["assertions"] if h["statement"]["kind"] == "event_tuple"}
    mapped = {}
    for entry in entries.values():
        fields(entry, ("from_ref", "to_ref"), path="rename")
        string(entry["to_ref"], "rename.to_ref")
        mapped[entry["from_ref"]] = entry["to_ref"]
    if set(mapped) != old or len(set(mapped.values())) != len(mapped):
        raise Problem("renaming_not_total_injective", "renames")
    if any(new in old and new != old_ref for old_ref, new in mapped.items()):
        raise Problem("renaming_capture", "renames")
    renamed = deepcopy(target)
    renamed["ledger"]["ref"] = target_ref
    for h in renamed["ledger"]["assertions"]:
        if h["statement"]["kind"] == "event_tuple":
            h["statement"]["event_ref"] = mapped[h["statement"]["event_ref"]]
    _restore(renamed)
    return renamed, source, ordered


def endpoint(snapshot, source, ordered, event=False):
    return {"profile": EVENT_PROFILE if event else PROFILE,
            "profile_spec_sha256": EVENT_SPEC_SHA256 if event else P0_SPEC_SHA256,
            "snapshot_sha256": digest(snapshot), "policy_ref": POLICY,
            "dependencies": [{"ref": p["ref"], "sha256": digest(p)} for p in sorted(ordered, key=lambda p: p["ref"])]}


def scope_hashes(views, queries, relation_ref):
    translated = []
    for q in sorted(queries, key=lambda q: q["id"]):
        if q["kind"] != "legacy_positive":
            translated.append({"id": q["id"], "kind": "out_of_scope", "source_kind": q["kind"]})
        else:
            patterns, public = _expand(q, relation_ref, "shared_event")
            translated.append({"id": q["id"], "context_ref": q["context_ref"], "atoms": patterns, "project": sorted(public)})
    return digest({"views": views, "queries": queries}), digest({"views": views, "queries": translated})


def validate_chain(request):
    source, ordered = request["source"], _source(request["source"], request["relation_ref"])
    middle_source, middle_ordered = _restore(request["intermediate"])
    final_source, final_ordered = _restore(request["target"])
    if any(t["relation_ref"] != request["relation_ref"] for t in (request["intermediate"], request["target"])):
        raise Problem("relation_mismatch")
    _queries(source, request["views"], request["queries"])
    legacy = _queries(middle_source, request["views"], request["queries"])
    _queries(final_source, request["views"], request["queries"])
    renamed, _, _ = _renaming(request["intermediate"], request["renames"], request["target"]["ledger"]["ref"])
    if len(values(request["stages"], 2, "stages")) != 2:
        raise Problem("expected_two_stages")
    for step in request["stages"]:
        fields(step, ("kind", "source", "target", "source_scope_sha256", "target_scope_sha256"), path="stage")
        string(step["kind"], "stage.kind")
        for key in ("source_scope_sha256", "target_scope_sha256"):
            _hash(step[key], "stage." + key)
        for key in ("source", "target"):
            e = step[key]
            fields(e, ("profile", "profile_spec_sha256", "snapshot_sha256", "dependencies", "policy_ref"), path="endpoint")
            for name in ("profile", "policy_ref"):
                string(e[name], "endpoint." + name)
            for name in ("profile_spec_sha256", "snapshot_sha256"):
                _hash(e[name], "endpoint." + name)
            for dep in values(e["dependencies"], 64, "endpoint.dependencies"):
                fields(dep, ("ref", "sha256"), path="dependency")
                string(dep["ref"], "dependency.ref")
                _hash(dep["sha256"], "dependency.sha256")
    return ordered, middle_source, middle_ordered, final_source, final_ordered, renamed, legacy


def run_chain(request, validated, budget):
    ordered, middle_source, middle_ordered, final_source, final_ordered, renamed, legacy = validated
    source_scope, event_scope = scope_hashes(request["views"], request["queries"], request["relation_ref"])
    start = endpoint(request["source"], request["source"], ordered)
    mid = endpoint(request["intermediate"], middle_source, middle_ordered, True)
    end = endpoint(request["target"], final_source, final_ordered, True)
    expected = [{"kind": "event_reification", "source": start, "target": mid,
                 "source_scope_sha256": source_scope, "target_scope_sha256": event_scope},
                {"kind": "event_rename", "source": mid, "target": end,
                 "source_scope_sha256": event_scope, "target_scope_sha256": event_scope}]
    obligations = []

    def check(name, ok):
        budget.tick()
        obligations.append({"name": name, "passed": ok})

    for i, (actual, wanted) in enumerate(zip(request["stages"], expected)):
        for key in wanted:
            check(f"stage_{i + 1}.{key}", canonical_bytes(actual[key]) == canonical_bytes(wanted[key]))
    check("intermediate_history_roundtrip", canonical_bytes(request["source"]) == canonical_bytes(middle_source))
    check("final_history_roundtrip", canonical_bytes(request["source"]) == canonical_bytes(final_source))
    check("actual_second_step_is_only_renaming", canonical_bytes(renamed) == canonical_bytes(request["target"]))
    check("stage_endpoints_compose", request["stages"][0]["target"] == request["stages"][1]["source"])
    check("translated_query_scopes_compose", request["stages"][0]["target_scope_sha256"] == request["stages"][1]["source_scope_sha256"])
    covered = [q["id"] for q in request["queries"] if q["kind"] == "legacy_positive"]
    outside = [q["id"] for q in request["queries"] if q["kind"] != "legacy_positive"]
    if not all(o["passed"] for o in obligations):
        budget.tick()
        return {"status": "ok", "certificate": {"status": "not_certified", "evidence_level": "checked_native_template",
                "reason_codes": ["chain_obligation_failed"], "scope": None}, "obligations": obligations,
                "source_scope_sha256": source_scope, "translated_scope_sha256": event_scope,
                "reason_codes": [], "incomplete": []}
    checks = []
    for target, restored, packages in ((request["intermediate"], middle_source, middle_ordered), (request["target"], final_source, final_ordered)):
        probe = {"source": request["source"], "target": target, "views": request["views"], "queries": request["queries"], "translation": {"kind": "shared_event"}}
        evidence = _compare(probe, request["source"], ordered, restored, packages, legacy, budget)
        if evidence["status"] == "resource_limit":
            raise Problem(evidence["reason_codes"][0], status="resource_limit")
        checks.append(evidence)
    complete = all(c["comparison"]["status"] == "matched" for c in checks)
    certified = complete and not outside
    incomplete = [{"check_index": i, "view": r["view"], "query": r["query"]}
                  for i, c in enumerate(checks) for r in c["comparison"]["results"]
                  if r["status"] == "unassessed"]
    budget.tick()
    return {"status": "ok", "certificate": {"status": "certified" if certified else "not_certified",
                "evidence_level": "checked_native_template", "method": "four-role-history-and-bijective-renaming-1",
                "scope": {"query_ids": sorted(covered), "guarantee": "source_history_and_completed_p0_positive_support",
                          "source_sha256": digest(request["source"]), "target_sha256": digest(request["target"]),
                          "excludes": ["event_identity", "event_count", "general_first_order_inference", "policy_changes", "new_membership_data", "execution_completion"]},
                "reason_codes": [] if certified else ["query_out_of_scope"] if outside
                else ["answers_mismatch"] if any(c["comparison"]["status"] == "mismatch" for c in checks) else ["incomparable_execution"]},
            "obligations": obligations, "finite_checks": checks, "out_of_scope_query_ids": sorted(outside),
            "source_scope_sha256": source_scope, "translated_scope_sha256": event_scope,
            "reason_codes": [], "incomplete": incomplete}


def _validate_chain(request, budget):
    return validate_chain(request)


def _validate_rename(request, budget):
    return _renaming(request["target"], request["renames"], request["target_ledger_ref"])


def _run_rename(request, validated, budget):
    renamed, source, _ = validated
    for _ in (*source["ledger"]["assertions"], *source["ledger"]["reviews"]):
        budget.tick()
    budget.tick()
    return {"status": "ok", "target": renamed, "target_sha256": digest(renamed), "source_sha256": digest(source), "reason_codes": [], "incomplete": []}


CHECK_EVENT_CHAIN = Operation("check_event_chain", CHAIN_FIELDS, True, _validate_chain, run_chain)
RENAME_EVENTS = Operation("rename_events", ("target", "renames", "target_ledger_ref"), False, _validate_rename, _run_rename)
