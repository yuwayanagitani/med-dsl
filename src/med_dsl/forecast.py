"""固定した有限モデルを読む。確率を臨床上の事実へ変換する規則は持たない。"""

from fractions import Fraction
import hashlib
from pathlib import Path
import re

from .ledger import select_view
from .model import Atom, Budget, PROFILE, Problem
from .validation import (digest, fields, indexed, string, strings, timestamp,
                         validate_query, values)

FORECAST_PROFILE = "p1-finite-forecast-draft-1"
SPEC_SHA256 = "a918397c96ba9f6035b81c1d20839a544058f12adfbcb41f27df4328b9ad2704"
REPORT_PREDICATE = "fiction:forecast_reported@1"
REPORT_PURPOSE = "fiction:forecast-reporting@1"


def _sha(value, path):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise Problem("invalid_sha256", path)


def _profile(value, path):
    if value != FORECAST_PROFILE:
        raise Problem("unsupported_profile", path, "unsupported_profile")


def _spec(value, path):
    _sha(value, path)
    if value != SPEC_SHA256:
        raise Problem("profile_spec_mismatch", path)


def _nonempty_index(items, key, maximum, path):
    result = indexed(items, key, maximum, path)
    if not result:
        raise Problem("empty_collection", path)
    return result


def _rational(value):
    fields(value, ("numerator", "denominator"), path="weight")
    n, d = value["numerator"], value["denominator"]
    if type(n) is not int or type(d) is not int or d <= 0 or not 0 <= n <= d:
        raise Problem("invalid_rational", "weight")
    if max(n.bit_length(), d.bit_length()) > 63:
        raise Problem("rational_integer_limit", "weight", "resource_limit")


def _add(left, right, budget):
    budget.tick()
    # 約分前の演算も制限する。入力上限の下では積も有限で、丸めない。
    a = left.numerator * right.denominator
    b = right.numerator * left.denominator
    d = left.denominator * right.denominator
    n = a + b
    if max(a.bit_length(), b.bit_length(), n.bit_length(), d.bit_length()) > 4096:
        raise Problem("rational_intermediate_limit", status="resource_limit")
    return Fraction(n, d)


def _validate(request):
    fields(request, ("schema_version", "operation", "consumer", "artifacts",
                     "report_snapshot", "views", "queries", "budget"))
    if request["operation"] != "query_forecast":
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    try:
        actual = hashlib.sha256(Path(__file__).with_name("forecast_spec.json").read_bytes()).hexdigest()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if actual != SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    _profile(consumer["profile"], "consumer.profile")
    _spec(consumer["profile_spec_sha256"], "consumer.profile_spec_sha256")
    strings(consumer["operations"], 64, "consumer.operations")
    if consumer["operations"] != ["query_forecast"]:
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")

    artifacts, hashes = {}, {}
    for entry in values(request["artifacts"], 64, "artifacts"):
        fields(entry, ("artifact", "sha256"), path="artifacts")
        a = entry["artifact"]
        fields(a, ("ref", "profile", "profile_spec_sha256", "subject_ref", "context_ref",
                   "interval", "model_ref", "sample_space_ref", "worlds", "events"), path="artifact")
        for key in ("ref", "subject_ref", "context_ref", "model_ref", "sample_space_ref"):
            string(a[key], "artifact." + key)
        if a["ref"] in artifacts:
            raise Problem("duplicate_identifier", "artifacts")
        _profile(a["profile"], "artifact.profile")
        _spec(a["profile_spec_sha256"], "artifact.profile_spec_sha256")
        _sha(entry["sha256"], "artifact.sha256")
        if digest(a) != entry["sha256"]:
            raise Problem("artifact_hash_mismatch", "artifact.sha256")
        fields(a["interval"], ("start", "end"), path="artifact.interval")
        for key in ("start", "end"):
            timestamp(a["interval"][key], "artifact.interval." + key)
        if a["interval"]["start"] >= a["interval"]["end"]:
            raise Problem("invalid_interval", "artifact.interval")
        worlds = _nonempty_index(a["worlds"], "ref", 64, "worlds")
        for world in worlds.values():
            fields(world, ("ref", "weight"), path="world")
            _rational(world["weight"])
        events = _nonempty_index(a["events"], "ref", 64, "events")
        for event in events.values():
            fields(event, ("ref", "world_refs"), path="event")
            strings(event["world_refs"], 64, "event.world_refs")
            if set(event["world_refs"]) - set(worlds):
                raise Problem("unresolved_world", "event.world_refs")
        artifacts[a["ref"]], hashes[a["ref"]] = a, entry["sha256"]
    if not artifacts:
        raise Problem("empty_collection", "artifacts")

    snapshot = request["report_snapshot"]
    fields(snapshot, ("kind", "contexts", "ledger"), path="report_snapshot")
    if snapshot["kind"] != "forecast_reports":
        raise Problem("invalid_snapshot_kind", "report_snapshot.kind")
    package = {"ref": "fiction:native:forecast-reports@1", "profile": PROFILE,
               "predicates": [{"ref": REPORT_PREDICATE, "roles": ["subject", "forecast"]}],
               "definitions": [], "inclusions": [], "dependencies": []}
    # 検証のみを再利用する。P0 の規則推論や任意 package は実行しない。
    validate_query({"schema_version": "p0-request-draft-1", "operation": "query",
                    "package": package, "contexts": snapshot["contexts"],
                    "ledger": snapshot["ledger"], "views": request["views"],
                    "queries": [], "budget": request["budget"]})
    contexts = {c["ref"]: c for c in snapshot["contexts"]}
    for c in contexts.values():
        if c["purpose"] != REPORT_PURPOSE:
            raise Problem("invalid_report_purpose", "context.purpose")
    for a in artifacts.values():
        if a["context_ref"] not in contexts:
            raise Problem("unresolved_context", "artifact.context_ref")
        if contexts[a["context_ref"]]["subject_ref"] != a["subject_ref"]:
            raise Problem("forecast_subject_mismatch", "artifact.subject_ref")
    for assertion in snapshot["ledger"]["assertions"]:
        subject, ref = assertion["atom"]["args"]
        if ref not in artifacts:
            raise Problem("unresolved_forecast", "assertion.atom")
        a = artifacts[ref]
        if subject != a["subject_ref"] or assertion["context_ref"] != a["context_ref"]:
            raise Problem("forecast_report_mismatch", "assertion.atom")
    views = _nonempty_index(request["views"], "id", 64, "views")
    queries = _nonempty_index(request["queries"], "id", 64, "queries")
    for q in queries.values():
        fields(q, ("id", "forecast_ref", "all_of"), path="query")
        string(q["forecast_ref"], "query.forecast_ref")
        if q["forecast_ref"] not in artifacts:
            raise Problem("unresolved_forecast", "query.forecast_ref")
        strings(q["all_of"], 8, "query.all_of")
        if not q["all_of"]:
            raise Problem("empty_query", "query.all_of")
        if set(q["all_of"]) - {e["ref"] for e in artifacts[q["forecast_ref"]]["events"]}:
            raise Problem("unresolved_event", "query.all_of")
    return artifacts, hashes, views, queries


def run_forecast(request):
    artifacts, hashes, views, queries = _validate(request)
    snapshot = request["report_snapshot"]
    snapshot_hash = digest(snapshot)
    ledger = snapshot["ledger"]
    budget = Budget(request["budget"]["max_steps"])
    rows = [{"view_id": v, "query_id": q, "status": "unassessed", "answer": None,
             "reason_codes": ["step_limit"], "evidence": [], "information_requests": []}
            for v in sorted(views) for q in sorted(queries)]
    metadata = []
    response = {"status": "ok", "reason_codes": [], "results": rows, "views": metadata,
                "report_snapshot_sha256": snapshot_hash,
                "artifact_hashes": dict(sorted(hashes.items())), "incomplete": []}

    def evidence(proof):
        return {"ledger_ref": ledger["ref"], "snapshot_sha256": snapshot_hash,
                **proof.evidence({})}

    try:
        budget.tick()
        for ref in sorted(artifacts):
            total = Fraction(0)
            for world in sorted(artifacts[ref]["worlds"], key=lambda w: w["ref"]):
                total = _add(total, Fraction(**world["weight"]), budget)
            budget.tick()
            if total != 1:
                raise Problem("weights_not_normalized", ref)
        row_index = 0
        for view_id in sorted(views):
            for _ in ledger["assertions"]:
                budget.tick()
            for _ in ledger["reviews"]:
                budget.tick()
            meta, positive, negative, unknown = select_view(
                ledger, views[view_id], known_capabilities={PROFILE, FORECAST_PROFILE})
            metadata.append(meta)
            for query_id in sorted(queries):
                row = rows[row_index]
                row_index += 1
                budget.tick()
                q = queries[query_id]
                a = artifacts[q["forecast_ref"]]
                ctx = a["context_ref"]
                fact = Atom(REPORT_PREDICATE, (a["subject_ref"], a["ref"]))
                pos, neg = positive.get(ctx, {}), negative.get(ctx, {})
                if ctx in unknown:
                    blockers = unknown[ctx]
                    row.update(status="unassessed", reason_codes=["unknown_capability"],
                               missing_capabilities=sorted(blockers),
                               blocking_assertion_refs=sorted(set().union(*blockers.values())))
                    continue
                collisions = sorted(set(pos) & set(neg))
                if collisions:
                    row.update(status="conflict", reason_codes=["unresolved_conflict"],
                               conflicts=[{"atom": {"predicate": f.predicate, "args": list(f.args)},
                                           "positive": evidence(pos[f]), "negative": evidence(neg[f])}
                                          for f in collisions])
                    continue
                if fact not in pos:
                    if fact in neg:
                        row.update(status="opposed", reason_codes=["negative_forecast_report"],
                                   evidence=[evidence(neg[fact])])
                    else:
                        row.update(status="undetermined", reason_codes=["no_adopted_report"],
                                   information_requests=[{"kind": "forecast_report_confirmation",
                                                          "forecast_ref": a["ref"], "context_ref": ctx}])
                    continue
                events = {e["ref"]: set(e["world_refs"]) for e in a["events"]}
                selected, probability = [], Fraction(0)
                for world in sorted(a["worlds"], key=lambda w: w["ref"]):
                    included = True
                    for event_ref in sorted(q["all_of"]):
                        budget.tick()
                        included = (world["ref"] in events[event_ref]) and included
                    if included:
                        selected.append(world)
                for world in selected:
                    probability = _add(probability, Fraction(**world["weight"]), budget)
                budget.tick()
                row.update(status="computed", reason_codes=[], evidence=[evidence(pos[fact])],
                           answer={"kind": "forecast_probability",
                                   "probability": {"numerator": probability.numerator,
                                                   "denominator": probability.denominator},
                                   **{k: a[k] for k in ("subject_ref", "context_ref",
                                                       "model_ref", "sample_space_ref")},
                                   "interval": dict(a["interval"]),
                                   "forecast_ref": a["ref"], "artifact_sha256": hashes[a["ref"]],
                                   "event_refs": sorted(q["all_of"])})
    except Problem as problem:
        if problem.status != "resource_limit":
            raise
        response.update(status="resource_limit", reason_codes=[problem.code])
        # 完了した別の回答を消さず、打切られた一問の値は公開しない。
        for row in rows:
            if row["reason_codes"] == ["step_limit"]:
                row["reason_codes"] = [problem.code]
    # 未評価の行（未知能力・打切り）は、P0 の query／P1-b と同じく incomplete に列挙する。
    response["incomplete"] = [{"view_id": r["view_id"], "query_id": r["query_id"]} for r in rows if r["status"] == "unassessed"]
    response["steps_used"] = budget.used
    return response
