"""引き継ぎ操作のホスト：consumer・仕様 hash・実体の確認と予算の検証を行い、登録された操作へ振り分ける。
操作の実装は持たない（鎖と改名は chain.py、欠落の診断は absence.py、再生の点検は replay.py、
参考意味は reference.py、射影は projection.py）。"""

import hashlib
from pathlib import Path

from .absence import CHECK_ABSENCE_POLICY
from .chain import CHECK_EVENT_CHAIN, RENAME_EVENTS, endpoint, scope_hashes  # noqa: F401  （endpoint・scope_hashes はテストの入口）
from .events import EVENT_SPEC_SHA256, _hash
from .handover_common import P0_RUNTIME_SHA256, P0_SPEC_SHA256
from .model import Budget, Problem
from .projection import CHECK_PROJECTION_CHAIN
from .reference import CHECK_REFERENCE_CHANGE
from .replay import AUDIT_REPLAY
from .validation import digest, fields, strings

HANDOVER_PROFILE = "p1-handover-draft-1"
HANDOVER_SPEC_SHA256 = "f5b1709c8c538ede98dd58b0eea79a6c4b4a145d6b7248daaa586cffe660a54d"
P0_FILES = ("model.py", "validation.py", "definitions.py", "ledger.py", "query.py")
OPERATIONS = {op.name: op for op in (CHECK_REFERENCE_CHANGE, CHECK_ABSENCE_POLICY, RENAME_EVENTS, CHECK_EVENT_CHAIN,
                                     CHECK_PROJECTION_CHAIN, AUDIT_REPLAY)}


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
    if type(op) is not str or op not in OPERATIONS:
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    fields(request, ("schema_version", "operation", "consumer", "budget", *OPERATIONS[op].fields))
    _native_integrity(OPERATIONS[op].needs_p0)
    c = request["consumer"]
    fields(c, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    if c["profile"] != HANDOVER_PROFILE:
        raise Problem("unsupported_profile", "consumer.profile", "unsupported_profile")
    _hash(c["profile_spec_sha256"], "consumer.profile_spec_sha256")
    if c["profile_spec_sha256"] != HANDOVER_SPEC_SHA256:
        raise Problem("profile_spec_mismatch", "consumer.profile_spec_sha256")
    strings(c["operations"], len(OPERATIONS), "consumer.operations")
    if op not in c["operations"] or set(c["operations"]) - set(OPERATIONS):
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget")
    if maximum > 100000:
        raise Problem("step_budget_limit", status="resource_limit")
    return Budget(maximum)


def run_handover(request):
    budget = _header(request)
    operation = OPERATIONS[request["operation"]]
    validated = operation.validate(request, budget)
    budget.tick()
    response = operation.run(request, validated, budget)
    response["steps_used"] = budget.used
    return response
