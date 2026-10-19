"""原保存と旧処理系の可用性の点検。新側の保証（鎖の認定）とは分けて返す。"""

import base64
import binascii
import hashlib

from .chain import run_chain, validate_chain
from .events import _hash
from .handover_common import CHAIN_FIELDS, Operation, P0_RUNTIME_REF, P0_RUNTIME_SHA256, P0_SPEC_SHA256, p0_request
from .model import Budget, PROFILE, Problem
from .validation import canonical_bytes, check_json, decode_json, fields, string, validate_query, values


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
        validate_query(p0_request(payload, [], [], Budget(0)))
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


def _validate(request, budget):
    return _validate_archive(request)


def _run(request, validated, budget):
    return _run_archive(request, *validated, budget)


AUDIT_REPLAY = Operation("audit_replay", ("archive", "available_resources", "semantic_chain"), True, _validate, _run)
