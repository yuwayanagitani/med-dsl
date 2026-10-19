"""既知の射影と、その実際の出力だけを保存する符号化の合成。"""

import base64
import json

from .handover_common import Operation
from .model import Problem
from .validation import canonical_bytes, digest, fields, indexed, string, values


def relation(rows):
    seen = set()
    for row in values(rows, 64, "relation"):
        if len(values(row, 4, "tuple")) != 4:
            raise Problem("arity_mismatch")
        for value in row:
            string(value, "tuple")
        if tuple(row) in seen:
            raise Problem("duplicate_tuple")
        seen.add(tuple(row))
    return sorted(seen)


def _position(value):
    if type(value) is not int or not 0 <= value < 4:
        raise Problem("invalid_position")


def validate_projection(request):
    relation(request["source_a"])
    relation(request["source_b"])
    p = request["projection"]
    if type(p) is not dict:
        raise Problem("expected_object", "projection")
    if p.get("kind") == "value_set":
        fields(p, ("kind",), path="projection")
    elif p.get("kind") == "columns":
        fields(p, ("kind", "positions"), path="projection")
        for pos in values(p["positions"], 4, "positions"):
            _position(pos)
        if not p["positions"] or len(set(p["positions"])) != len(p["positions"]):
            raise Problem("invalid_positions")
    else:
        raise Problem("unsupported_projection", status="unsupported_profile")
    queries = indexed(request["queries"], "id", 16, "queries")
    if not queries:
        raise Problem("empty_collection", "queries")
    for q in queries.values():
        fields(q, ("id", "where", "select"), path="query")
        positions, variables = set(), set()
        for condition in values(q["where"], 4, "query.where"):
            fields(condition, ("position", "value"))
            _position(condition["position"])
            string(condition["value"], "query.where.value")
            if condition["position"] in positions:
                raise Problem("duplicate_position")
            positions.add(condition["position"])
        positions = set()
        for item in values(q["select"], 4, "query.select"):
            fields(item, ("position", "var"))
            _position(item["position"])
            string(item["var"], "query.select.var")
            if item["position"] in positions or item["var"] in variables:
                raise Problem("duplicate_selection")
            positions.add(item["position"])
            variables.add(item["var"])
    if request["source_sidecar"] is not None:
        fields(request["source_sidecar"], ("relation", "sha256"), path="source_sidecar")
        sidecar = request["source_sidecar"]
        if digest(sidecar["relation"]) != sidecar["sha256"] or relation(sidecar["relation"]) != relation(request["source_a"]):
            raise Problem("sidecar_mismatch")


def _answers(rows, q, budget):
    found = {}
    for row in rows:
        budget.tick()
        if all(row[c["position"]] == c["value"] for c in q["where"]):
            binding = {v["var"]: row[v["position"]] for v in q["select"]}
            found[tuple(sorted(binding.items()))] = binding
    return sorted(found.values(), key=lambda b: tuple(sorted(b.items())))


def run_projection(request, budget):
    projected, encodings = {}, {}
    columns = request["projection"].get("positions", [])
    for side in ("source_a", "source_b"):
        out = set()
        for row in relation(request[side]):
            budget.tick()
            if request["projection"]["kind"] == "columns":
                out.add(tuple(row[pos] for pos in columns))
            else:
                out.update(row)
        projected[side] = [list(r) for r in sorted(out)] if columns else sorted(out)
        encoded = canonical_bytes(projected[side])
        decoded = json.loads(encoded)
        budget.tick()
        if decoded != projected[side]:
            raise Problem("encoding_roundtrip_failed")
        encodings[side] = {"bytes_base64": base64.b64encode(encoded).decode("ascii"),
                           "sha256": digest(projected[side]), "roundtrip_matches": True}
    results, counterexamples, covered = [], [], []
    for q in sorted(request["queries"], key=lambda q: q["id"]):
        a = _answers(relation(request["source_a"]), q, budget)
        b = _answers(relation(request["source_b"]), q, budget)
        budget.tick()
        required = {c["position"] for c in q["where"]} | {v["position"] for v in q["select"]}
        in_scope = bool(columns) and required <= set(columns)
        target = None
        if in_scope:
            rows = [dict(zip(columns, r)) for r in projected["source_a"]]
            target = _answers(rows, q, budget)
            covered.append(q["id"])
        row = {"query_id": q["id"], "source_a_bindings": a, "source_b_bindings": b,
               "target_bindings": target, "status": "preserved" if in_scope else "out_of_scope"}
        if not in_scope and request["source_sidecar"] is not None:
            row["sidecar_answer"] = {"mode": "sidecar_replay", "bindings": _answers(relation(request["source_sidecar"]["relation"]), q, budget)}
        results.append(row)
        if projected["source_a"] == projected["source_b"] and a != b:
            counterexamples.append({"query_id": q["id"], "reason": "intermediate_projection_lost_query_distinction",
                                    "source_a_bindings": a, "source_b_bindings": b})
    certified = len(covered) == len(results)
    budget.tick()
    return {"status": "ok", "meaning_mode": "finite_relation_projection", "projected": projected,
            "encodings": encodings, "projected_value_sets_equal": projected["source_a"] == projected["source_b"],
            "second_step_certificate": {"status": "certified", "evidence_level": "checked_native_template", "scope": "canonical_json_value_identity"},
            "certificate": {"status": "certified" if certified else "not_certified", "evidence_level": "checked_native_template" if certified else "verified_collision" if counterexamples else "lossy_template",
                            "scope": {"query_ids": covered, "excludes": ["discarded_fields", "source_history"]},
                            "reason_codes": [] if certified else ["intermediate_projection_lost_query_distinction"] if counterexamples else ["query_out_of_scope"]},
            "results": results, "counterexamples": counterexamples,
            "full_difference_status": "compared" if certified else "incomparable",
            "source_sidecar_available": request["source_sidecar"] is not None,
            "additional_source_used": any("sidecar_answer" in row for row in results),
            "reason_codes": [], "incomplete": []}


def _validate(request, budget):
    return validate_projection(request)


def _run(request, validated, budget):
    return run_projection(request, budget)


CHECK_PROJECTION_CHAIN = Operation("check_projection_chain", ("source_a", "source_b", "projection", "queries", "source_sidecar"), False, _validate, _run)
