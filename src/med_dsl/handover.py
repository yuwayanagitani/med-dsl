"""既知テンプレートの条件、端点・範囲の合成、旧処理系の可用性を分離する。"""

import base64
import binascii
from copy import deepcopy
import hashlib
from pathlib import Path

from .events import (EVENT_PROFILE, EVENT_SPEC_SHA256, _compare, _expand, _hash,
                     _queries, _restore, _source)
from .model import Budget, POLICY, PROFILE, Problem
from .projection import run_projection, validate_projection
from .query import run_query
from .reference import run_reference, validate_reference
from .validation import (canonical_bytes, check_json, decode_json, digest, fields, indexed,
                         string, strings, validate_query, values)

HANDOVER_PROFILE = "p1-handover-draft-1"
HANDOVER_SPEC_SHA256 = "f5b1709c8c538ede98dd58b0eea79a6c4b4a145d6b7248daaa586cffe660a54d"
P0_SPEC_SHA256 = "3ae222d252a46ad6a1cf2221a230a5218170ed13f8ccf645c22249e957c3ac72"
P0_RUNTIME_SHA256 = "2d30169e3d12cb005cc74e152012afffae4e8ae0eec78bd4452f9fc168966e27"
P0_RUNTIME_REF = "med-dsl:p0-native@1"
P0_FILES = ("model.py", "validation.py", "definitions.py", "ledger.py", "query.py")
CHAIN_FIELDS = ("source", "relation_ref", "intermediate", "target", "renames", "stages", "views", "queries")
EXTRA = {
    "check_reference_change": ("signature", "source", "target", "queries", "models", "finite_domain_sizes"),
    "check_absence_policy": ("source", "views", "queries"),
    "rename_events": ("target", "renames", "target_ledger_ref"),
    "check_event_chain": CHAIN_FIELDS,
    "check_projection_chain": ("source_a", "source_b", "projection", "queries", "source_sidecar"),
    "audit_replay": ("archive", "available_resources", "semantic_chain"),
}


def _native_integrity(needs_p0):
    directory = Path(__file__).parent
    try:
        if hashlib.sha256((directory / "handover_spec.json").read_bytes()).hexdigest() != HANDOVER_SPEC_SHA256:
            raise Problem("native_spec_mismatch")
        if hashlib.sha256((directory / "events_spec.json").read_bytes()).hexdigest() != EVENT_SPEC_SHA256:
            raise Problem("event_spec_mismatch")
        if needs_p0:
            hashes = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in P0_FILES}
            if digest(hashes) != P0_RUNTIME_SHA256:
                raise Problem("native_runtime_mismatch")
            contract = directory.parent.parent / "docs/research/06-p0-contract.md"
            if hashlib.sha256(contract.read_bytes()).hexdigest() != P0_SPEC_SHA256:
                raise Problem("p0_spec_mismatch")
    except OSError as error:
        raise Problem("native_spec_unavailable") from error


def _header(request):
    op = request.get("operation")
    if type(op) is not str or op not in EXTRA:
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    fields(request, ("schema_version", "operation", "consumer", "budget", *EXTRA[op]))
    _native_integrity(op in ("check_absence_policy", "check_event_chain", "audit_replay"))
    c = request["consumer"]
    fields(c, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    if c["profile"] != HANDOVER_PROFILE:
        raise Problem("unsupported_profile", "consumer.profile", "unsupported_profile")
    _hash(c["profile_spec_sha256"], "consumer.profile_spec_sha256")
    if c["profile_spec_sha256"] != HANDOVER_SPEC_SHA256:
        raise Problem("profile_spec_mismatch", "consumer.profile_spec_sha256")
    strings(c["operations"], len(EXTRA), "consumer.operations")
    if op not in c["operations"] or set(c["operations"]) - set(EXTRA):
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget")
    if maximum > 100000:
        raise Problem("step_budget_limit", status="resource_limit")
    return Budget(maximum)


def _p0(source, views, queries, budget):
    fields(source, ("package", "dependency_packages", "contexts", "ledger"), path="source")
    return {"schema_version": "p0-request-draft-1", "operation": "query", **source,
            "views": views, "queries": queries, "budget": {"max_steps": budget.maximum}}


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


def _validate_absence(request, budget):
    p0 = _p0(request["source"], request["views"], request["queries"], budget)
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


def _decode(value):
    string(value, "bytes_base64")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise Problem("invalid_base64") from error


def _validate_archive(request):
    a = request["archive"]
    fields(a, ("bytes_base64", "sha256", "profile", "profile_spec_sha256", "requirements"), path="archive")
    if a["profile"] != PROFILE:
        raise Problem("unsupported_profile", "archive.profile", "unsupported_profile")
    _hash(a["profile_spec_sha256"], "archive.profile_spec_sha256")
    if a["profile_spec_sha256"] != P0_SPEC_SHA256:
        raise Problem("profile_spec_mismatch", "archive.profile_spec_sha256")
    _hash(a["sha256"], "archive.sha256")
    raw = _decode(a["bytes_base64"])
    if hashlib.sha256(raw).hexdigest() != a["sha256"]:
        raise Problem("archive_hash_mismatch")
    inventory, seen = {}, set()
    for resource in values(request["available_resources"], 16, "available_resources"):
        fields(resource, ("kind", "ref", "sha256", "bytes_base64"), path="resource")
        _resource(resource)
        key = resource["kind"], resource["ref"]
        if key in inventory:
            raise Problem("duplicate_resource")
        if hashlib.sha256(_decode(resource["bytes_base64"])).hexdigest() != resource["sha256"]:
            raise Problem("resource_hash_mismatch")
        inventory[key] = resource
    requirements = values(a["requirements"], 16, "requirements")
    for requirement in requirements:
        fields(requirement, ("kind", "ref", "sha256"), path="requirement")
        _resource(requirement)
        key = requirement["kind"], requirement["ref"]
        if key in seen:
            raise Problem("duplicate_resource")
        seen.add(key)
    if sum(r["kind"] == "runtime" for r in requirements) != 1:
        raise Problem("expected_one_runtime_requirement")
    chain = request["semantic_chain"]
    validated = None
    payload, interpretation = None, {"status": "unassessed", "reason_codes": []}
    try:
        payload = decode_json(raw)
        check_json(payload)
        validate_query(_p0(payload, [], [], Budget(0)))
        interpretation = {"status": "validated_p0_snapshot", "reason_codes": []}
    except Problem as problem:
        if problem.status == "resource_limit":
            raise
        interpretation["reason_codes"] = [problem.code]
    if chain is not None:
        fields(chain, CHAIN_FIELDS, path="semantic_chain")
        if interpretation["status"] != "validated_p0_snapshot":
            raise Problem("archive_not_supported_json")
        if canonical_bytes(payload) != canonical_bytes(chain["source"]):
            raise Problem("archive_source_mismatch")
        validated = validate_chain(chain)
    return inventory, validated, interpretation


def _resource(value):
    if value["kind"] not in ("runtime", "runtime_dependency", "semantic_dependency"):
        raise Problem("invalid_resource_kind")
    string(value["ref"], "resource.ref")
    _hash(value["sha256"], "resource.sha256")


def _run_archive(request, inventory, validated, interpretation, budget):
    budget.tick()
    checked = []
    for r in request["archive"]["requirements"]:
        budget.tick()
        stored = inventory.get((r["kind"], r["ref"]))
        supplied = stored is not None and stored["sha256"] == r["sha256"]
        native = r["kind"] == "runtime" and r["ref"] == P0_RUNTIME_REF and r["sha256"] == P0_RUNTIME_SHA256
        ready = native if r["kind"] == "runtime" else supplied
        checked.append({"kind": r["kind"], "ref": r["ref"], "available": ready, "stored_bytes_verified": supplied,
                        "reason": None if ready else "unknown_runtime_handler" if r["kind"] == "runtime" else "required_resource_unavailable"})
    semantic = {"status": "unassessed", "certificate": None, "reason_codes": ["semantic_handover_not_checked"]}
    if validated is not None:
        result = run_chain(request["semantic_chain"], validated, budget)
        semantic = {"status": result["certificate"]["status"], "certificate": result["certificate"], "verification": result}
    budget.tick()
    return {"status": "ok", "archive_bytes_verified": True, "archive_sha256": request["archive"]["sha256"],
            "legacy_replay": {"status": "ready_to_replay" if all(r["available"] for r in checked) and interpretation["status"] == "validated_p0_snapshot" else "unavailable",
                              "availability_scope": "verified_supplied_inventory_and_native_registry", "executed": False,
                              "input_interpretation": interpretation, "requirements": checked},
            "semantic_handover": semantic, "reason_codes": [], "incomplete": []}


def run_handover(request):
    budget = _header(request)
    op = request["operation"]
    validated = None
    if op == "check_reference_change":
        validate_reference(request)
    elif op == "check_projection_chain":
        validate_projection(request)
    elif op == "check_event_chain":
        validated = validate_chain(request)
    elif op == "rename_events":
        validated = _renaming(request["target"], request["renames"], request["target_ledger_ref"])
    elif op == "check_absence_policy":
        validated = _validate_absence(request, budget)
    else:
        validated = _validate_archive(request)
    budget.tick()
    if op == "check_reference_change":
        response = run_reference(request, budget)
    elif op == "check_projection_chain":
        response = run_projection(request, budget)
    elif op == "check_event_chain":
        response = run_chain(request, validated, budget)
    elif op == "check_absence_policy":
        response = _run_absence(*validated, budget)
    elif op == "audit_replay":
        response = _run_archive(request, *validated, budget)
    else:
        renamed, source, _ = validated
        for _ in (*source["ledger"]["assertions"], *source["ledger"]["reviews"]):
            budget.tick()
        budget.tick()
        response = {"status": "ok", "target": renamed, "target_sha256": digest(renamed), "source_sha256": digest(source), "reason_codes": [], "incomplete": []}
    response["steps_used"] = budget.used
    return response
