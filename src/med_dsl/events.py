"""四項関係の可逆な事象化と、役割表を使う有限の支持計算。"""

from copy import deepcopy
import hashlib
from pathlib import Path
import re

from .definitions import compile_rules, positive_closure
from .ledger import select_view
from .model import Atom, Budget, PROFILE, Proof, Problem, atom
from .query import _match, _pattern_key, run_query
from .validation import (check_json, digest, fields, indexed, string, strings,
                         validate_query, values)

EVENT_PROFILE = "p1-events-draft-1"
EVENT_SPEC_SHA256 = "0fd014dd4904b2773839a8577675a59f7386ef2ea81ddb00c0def2ebbdf99cf3"
OPERATIONS = {"reify_events", "restore_events", "query_events", "compare_event_handover"}
ROLES = ("key", "specimen", "method", "value")
ACTIVE = "urn:med-dsl:events:active"
ROLE_REFS = {r: "urn:med-dsl:events:role:" + r for r in ROLES}
ENVELOPE = ("id", "context_ref", "polarity", "certainty", "recorded_at", "origin",
            "supersedes", "required_capabilities")


def _hash(value, path):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise Problem("invalid_sha256", path)


def _all_strings(value):
    if type(value) is str:
        return {value}
    if type(value) is list:
        return set().union(set(), *(_all_strings(v) for v in value))
    if type(value) is dict:
        return set().union(set(), *(_all_strings(v) for v in value.values()))
    return set()


def _p0_request(source, views, queries, maximum):
    return {"schema_version": "p0-request-draft-1", "operation": "query", **source,
            "views": views, "queries": queries, "budget": {"max_steps": maximum}}


def _source(source, relation_ref):
    fields(source, ("package", "dependency_packages", "contexts", "ledger"), path="source")
    string(relation_ref, "relation_ref")
    ordered = validate_query(_p0_request(source, [], [], 100000))
    signature = {p["ref"]: p for package in ordered for p in package["predicates"]}
    if relation_ref not in signature or len(signature[relation_ref]["roles"]) != 4:
        raise Problem("expected_four_ary_relation", "relation_ref")
    if ({ACTIVE, *ROLE_REFS.values()} & set(signature)):
        raise Problem("native_predicate_collision", "package")
    return ordered


def _restore(target):
    check_json(target)
    fields(target, ("schema_version", "profile", "profile_spec_sha256", "source_sha256",
                    "source_ledger_ref", "relation_ref", "package", "dependency_packages",
                    "contexts", "ledger"), path="target")
    if target["schema_version"] != "p1-event-snapshot-draft-1":
        raise Problem("unsupported_snapshot_schema", "target.schema_version")
    if target["profile"] != EVENT_PROFILE:
        raise Problem("unsupported_profile", "target.profile", "unsupported_profile")
    _hash(target["profile_spec_sha256"], "target.profile_spec_sha256")
    if target["profile_spec_sha256"] != EVENT_SPEC_SHA256:
        raise Problem("profile_spec_mismatch", "target.profile_spec_sha256")
    _hash(target["source_sha256"], "target.source_sha256")
    string(target["source_ledger_ref"], "target.source_ledger_ref")
    ledger = target["ledger"]
    fields(ledger, ("ref", "assertions", "reviews"), path="target.ledger")
    string(ledger["ref"], "target.ledger.ref")
    if ledger["ref"] == target["source_ledger_ref"]:
        raise Problem("ledger_reference_collision", "target.ledger.ref")
    assertions, event_refs = [], set()
    for item in values(ledger["assertions"], 1000, "target.assertions"):
        fields(item, (*ENVELOPE, "statement"), ("change_reason",), "target.assertion")
        statement = item["statement"]
        if type(statement) is not dict:
            raise Problem("expected_object", "statement")
        if statement.get("kind") == "event_tuple":
            fields(statement, ("kind", "event_ref", "source_assertion", "roles"), path="statement")
            string(statement["event_ref"], "statement.event_ref")
            if statement["event_ref"] in event_refs:
                raise Problem("event_reference_collision", "statement.event_ref")
            event_refs.add(statement["event_ref"])
            fields(statement["source_assertion"], ("ledger_ref", "id"), path="source_assertion")
            if statement["source_assertion"] != {"ledger_ref": target["source_ledger_ref"], "id": item["id"]}:
                raise Problem("source_assertion_mismatch", "statement.source_assertion")
            fields(statement["roles"], ROLES, path="statement.roles")
            for role in ROLES:
                string(statement["roles"][role], "statement.roles." + role)
            old_atom = {"predicate": target["relation_ref"],
                        "args": [statement["roles"][r] for r in ROLES]}
        elif statement.get("kind") == "unchanged_atom":
            fields(statement, ("kind", "atom"), path="statement")
            old_atom = statement["atom"]
            if type(old_atom) is dict and old_atom.get("predicate") == target["relation_ref"]:
                raise Problem("unreified_relation", "statement.atom")
        else:
            raise Problem("unsupported_statement", "statement.kind")
        assertions.append({**{k: v for k, v in item.items() if k != "statement"}, "atom": old_atom})
    source = {k: target[k] for k in ("package", "dependency_packages", "contexts")}
    source["ledger"] = {"ref": target["source_ledger_ref"], "assertions": assertions,
                        "reviews": ledger["reviews"]}
    ordered = _source(source, target["relation_ref"])
    if event_refs & (_all_strings(source) | {ledger["ref"]}):
        raise Problem("event_reference_collision", "statement.event_ref")
    if digest(source) != target["source_sha256"]:
        raise Problem("source_hash_mismatch", "target.source_sha256")
    return source, ordered


def _header(request):
    operation = request.get("operation")
    if type(operation) is not str or operation not in OPERATIONS:
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    extra = {"reify_events": ("source", "relation_ref", "target_ledger_ref"),
             "restore_events": ("target",),
             "query_events": ("target", "views", "queries"),
             "compare_event_handover": ("source", "relation_ref", "target", "views", "queries", "translation")}[operation]
    fields(request, ("schema_version", "operation", "consumer", "budget", *extra))
    try:
        raw = Path(__file__).with_name("events_spec.json").read_bytes()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if hashlib.sha256(raw).hexdigest() != EVENT_SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    if consumer["profile"] != EVENT_PROFILE:
        raise Problem("unsupported_profile", "consumer.profile", "unsupported_profile")
    _hash(consumer["profile_spec_sha256"], "consumer.profile_spec_sha256")
    if consumer["profile_spec_sha256"] != EVENT_SPEC_SHA256:
        raise Problem("profile_spec_mismatch", "consumer.profile_spec_sha256")
    strings(consumer["operations"], 4, "consumer.operations")
    if operation not in consumer["operations"] or set(consumer["operations"]) - OPERATIONS:
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")
    return Budget(maximum)


def _queries(source, views, queries):
    indexed(queries, "id", 64, "queries")
    if not queries or not values(views, 64, "views"):
        raise Problem("empty_collection", "queries_or_views")
    contexts = {c["ref"] for c in source["contexts"]}
    legacy = []
    for q in queries:
        fields(q, ("id", "context_ref", "kind", "required"), ("atoms",), "query")
        string(q["kind"], "query.kind")
        string(q["context_ref"], "query.context_ref")
        if q["context_ref"] not in contexts:
            raise Problem("unresolved_context", "query.context_ref")
        if type(q["required"]) is not bool:
            raise Problem("expected_boolean", "query.required")
        if q["kind"] == "legacy_positive":
            if "atoms" not in q:
                raise Problem("missing_field", "query.atoms")
            legacy.append({k: v for k, v in q.items() if k != "kind"})
        elif "atoms" in q:
            raise Problem("unknown_field", "query.atoms")
    validate_query(_p0_request(source, views, legacy, 100000))
    return legacy


def _reify(source, relation_ref, target_ref, budget):
    string(target_ref, "target_ledger_ref")
    if target_ref == source["ledger"]["ref"]:
        raise Problem("ledger_reference_collision", "target_ledger_ref")
    assertions = []
    for old in source["ledger"]["assertions"]:
        budget.tick()
        if old["atom"]["predicate"] == relation_ref:
            reference = {"ledger_ref": source["ledger"]["ref"], "id": old["id"]}
            statement = {"kind": "event_tuple", "event_ref": "urn:med-dsl:event:" + digest(reference),
                         "source_assertion": reference, "roles": dict(zip(ROLES, old["atom"]["args"]))}
        else:
            statement = {"kind": "unchanged_atom", "atom": deepcopy(old["atom"])}
        assertions.append({**deepcopy({k: v for k, v in old.items() if k != "atom"}), "statement": statement})
    for _ in source["ledger"]["reviews"]:
        budget.tick()
    target = {"schema_version": "p1-event-snapshot-draft-1", "profile": EVENT_PROFILE,
              "profile_spec_sha256": EVENT_SPEC_SHA256, "source_sha256": digest(source),
              "source_ledger_ref": source["ledger"]["ref"], "relation_ref": relation_ref,
              **deepcopy({k: source[k] for k in ("package", "dependency_packages", "contexts")}),
              "ledger": {"ref": target_ref, "assertions": assertions, "reviews": deepcopy(source["ledger"]["reviews"])}}
    readback, _ = _restore(target)
    budget.tick()
    return {"status": "ok", "target": target, "target_sha256": digest(target),
            "roundtrip": {"status": "matched", "source_sha256": digest(source), "readback_sha256": digest(readback)},
            "reason_codes": [], "incomplete": [], "steps_used": budget.used}


def _expand(query, relation_ref, translation):
    public = {t["var"] for a in query["atoms"] for t in a["args"] if type(t) is dict}
    used, patterns = set(public), []

    def fresh():
        name = "_event_" + str(len(used))
        while name in used:
            name += "_"
        used.add(name)
        return {"var": name}

    for old in query["atoms"]:
        if old["predicate"] != relation_ref:
            patterns.append(old)
            continue
        shared = fresh() if translation == "shared_event" else None
        if translation == "shared_event":
            patterns.append({"predicate": ACTIVE, "args": [shared]})
        for role, term in zip(ROLES, old["args"]):
            z = shared if translation == "shared_event" else fresh()
            if translation == "split_roles":
                patterns.append({"predicate": ACTIVE, "args": [z]})
            patterns.append({"predicate": ROLE_REFS[role], "args": [z, term]})
    return patterns, public


def _bindings(patterns, public, facts, budget):
    rows = {(): Proof()}
    for pattern in sorted(patterns, key=_pattern_key):
        candidates = sorted(f for f in facts if f.predicate == pattern["predicate"])
        joined = {}
        for binding, proof in sorted(rows.items()):
            for fact in candidates:
                budget.tick()
                merged = _match(pattern, fact, binding)
                if merged is not None:
                    joined[merged] = joined.get(merged, Proof()).merge(proof.merge(facts[fact]))
                    if len(joined) > 4096:
                        raise Problem("intermediate_binding_limit", status="resource_limit")
        rows = joined
        if not rows:
            break
    projected = {}
    for binding, proof in sorted(rows.items()):
        budget.tick()
        key = tuple((k, v) for k, v in binding if k in public)
        projected[key] = projected.get(key, Proof()).merge(proof)
        if len(projected) > 1000:
            raise Problem("binding_limit", status="resource_limit")
    return projected


def _event_facts(target, adopted, as_of, context):
    reviews = {}
    for r in target["ledger"]["reviews"]:
        if r["recorded_at"] <= as_of:
            reviews.setdefault(r["assertion_ref"], set()).add(r["id"])
    facts = {}
    for item in target["ledger"]["assertions"]:
        s = item["statement"]
        if (item["id"] not in adopted or item["context_ref"] != context
                or item["polarity"] != "positive" or s["kind"] != "event_tuple"):
            continue
        proof = Proof(frozenset({item["id"]}), frozenset(reviews[item["id"]]))
        facts[Atom(ACTIVE, (s["event_ref"],))] = proof
        for role in ROLES:
            facts[Atom(ROLE_REFS[role], (s["event_ref"], s["roles"][role]))] = proof
    return facts


def _run_target(target, source, ordered, views, queries, budget, translation="shared_event"):
    rows = [{"view": v["id"], "query": q["id"], "status": "unassessed", "bindings": [],
             "evidence": [], "reason_codes": ["step_limit"]}
            for v in sorted(views, key=lambda v: v["id"]) for q in sorted(queries, key=lambda q: q["id"])]
    result = {"status": "ok", "evaluation_mode": "native_event_roles", "results": rows,
              "views": [], "reason_codes": [], "incomplete": [],
              "ledger_ref": target["ledger"]["ref"], "source_ledger_ref": target["source_ledger_ref"],
              "target_sha256": digest(target), "retained_assertions": sorted(a["id"] for a in source["ledger"]["assertions"])}
    rules, sources = compile_rules(ordered)
    if sources:
        result["definition_sources"] = sources
    index = 0
    try:
        for view in sorted(views, key=lambda v: v["id"]):
            for _ in (*source["ledger"]["assertions"], *source["ledger"]["reviews"]):
                budget.tick()
            metadata, positive, negative, unknown = select_view(source["ledger"], view)
            result["views"].append(metadata)
            closures, native = {}, {}
            for query in sorted(queries, key=lambda q: q["id"]):
                row = rows[index]
                index += 1
                budget.tick()
                context = query["context_ref"]
                out = {"status": "unassessed", "bindings": [], "evidence": [], "reason_codes": []}
                if query["kind"] != "legacy_positive":
                    out["reason_codes"] = ["query_out_of_scope"]
                elif context in unknown:
                    out.update(reason_codes=["unknown_capability"], missing_capabilities=sorted(unknown[context]),
                               blocking_assertion_refs=sorted(set().union(*unknown[context].values())))
                else:
                    if context not in closures:
                        closures[context] = positive_closure(positive.get(context, {}), rules, budget)
                        native[context] = {f: p for f, p in closures[context].items() if f.predicate != target["relation_ref"]}
                        native[context].update(_event_facts(target, set(metadata["adopted_assertions"]), view["as_of"], context))
                    facts, denials = closures[context], negative.get(context, {})
                    collisions = sorted(set(facts) & set(denials))
                    if collisions:
                        proof = Proof()
                        conflicts = []
                        for f in collisions:
                            proof = proof.merge(facts[f]).merge(denials[f])
                            conflicts.append({"atom": {"predicate": f.predicate, "args": list(f.args)},
                                              "positive_evidence": facts[f].evidence(()),
                                              "negative_evidence": denials[f].evidence(())})
                        out.update(status="conflict", evidence=[proof.evidence(())], conflicts=conflicts,
                                   reason_codes=["conflicting_assertions"])
                    else:
                        patterns, public = _expand(query, target["relation_ref"], translation)
                        answers = _bindings(patterns, public, native[context], budget)
                        if answers:
                            out.update(status="supported", bindings=[dict(b) for b in sorted(answers)],
                                       evidence=[answers[b].evidence(b) for b in sorted(answers)])
                        elif (len(query["atoms"]) == 1 and all(type(t) is str for t in query["atoms"][0]["args"])
                              and atom(query["atoms"][0]) in denials):
                            out.update(status="opposed", evidence=[denials[atom(query["atoms"][0])].evidence(())])
                        else:
                            out["status"] = "undetermined"
                budget.tick()
                if query["required"] and out["status"] != "supported":
                    out["information_request"] = {"undetermined": "needs_information", "opposed": "needs_information",
                                                  "conflict": "needs_resolution", "unassessed": "needs_capability_or_completion"}[out["status"]]
                row.update(out)
    except Problem as problem:
        if problem.status != "resource_limit":
            raise
        result.update(status="resource_limit", reason_codes=[problem.code])
        for row in rows:
            if row["reason_codes"] == ["step_limit"]:
                row["reason_codes"] = [problem.code]
    result["incomplete"] = [{"view": r["view"], "query": r["query"], "reason_codes": r["reason_codes"]}
                            for r in rows if r["status"] == "unassessed"]
    return result


def _answer_signature(row):
    return {k: row[k] for k in ("status", "bindings", "evidence")}


def _compare(request, source, ordered, restored, target_ordered, legacy, budget):
    budget.tick()
    history_matches = digest(source) == digest(restored)
    before = run_query(_p0_request(source, request["views"], legacy, budget.maximum), ordered, budget)
    before.update(evaluation_mode="legacy_replay", ledger_ref=source["ledger"]["ref"], source_sha256=digest(source))
    correct = _run_target(request["target"], restored, target_ordered, request["views"], request["queries"], budget)
    split = request["translation"]["kind"] == "split_roles"
    after = (_run_target(request["target"], restored, target_ordered, request["views"], request["queries"], budget, "split_roles")
             if split else correct)
    resource = any(r["status"] == "resource_limit" for r in (before, correct, after))
    resource_reasons = {reason for r in (before, correct, after) if r["status"] == "resource_limit" for reason in r["reason_codes"]}
    adoption_matches = (before["views"] == after["views"]) if not resource else None
    old_rows = {(r["view"], r["query"]): r for r in before["results"]}
    correct_rows = {(r["view"], r["query"]): r for r in correct["results"]}
    rows, counterexamples = [], []
    for new in after["results"]:
        key = new["view"], new["query"]
        row = {"view": key[0], "query": key[1], "status": "unassessed", "difference": None}
        old = old_rows.get(key)
        if "query_out_of_scope" in new["reason_codes"]:
            row.update(status="out_of_scope", reason_codes=["query_out_of_scope"])
        elif (old is None or old["status"] in ("unassessed", "conflict")
              or new["status"] in ("unassessed", "conflict")):
            row["reason_codes"] = ["incomparable_answers"]
        else:
            try:
                budget.tick()
            except Problem:
                resource = True
                resource_reasons.add("step_limit")
                row["reason_codes"] = ["step_limit"]
                rows.append(row)
                continue
            left = {digest(b): b for b in old["bindings"]}
            right = {digest(b): b for b in new["bindings"]}
            added, removed = [right[k] for k in sorted(right.keys() - left.keys())], [left[k] for k in sorted(left.keys() - right.keys())]
            match = digest(_answer_signature(old)) == digest(_answer_signature(new))
            row.update(status="matched" if match else "mismatch", reason_codes=[],
                       difference={"added_bindings": added, "removed_bindings": removed,
                                   "before_status": old["status"], "after_status": new["status"],
                                   "evidence_matches": digest(old["evidence"]) == digest(new["evidence"])})
            good = correct_rows[key]
            if (split and history_matches and added and good["status"] in ("supported", "undetermined")
                    and old["status"] in ("supported", "undetermined")):
                good_bindings = {digest(b) for b in good["bindings"]}
                for binding in added:
                    if digest(binding) not in good_bindings:
                        counterexamples.append({"view": key[0], "query": key[1], "binding": binding,
                                                "meaning_mode": "truth_in_listed_model", "source_truth": False,
                                                "correct_target_truth": False, "incorrect_target_truth": True,
                                                "target_evidence": new["evidence"]})
        rows.append(row)
    if resource:
        status = "unassessed"
    elif not history_matches or adoption_matches is False or any(r["status"] == "mismatch" for r in rows):
        status = "mismatch"
    elif any(r["status"] == "unassessed" for r in rows):
        status = "unassessed"
    elif any(r["status"] == "out_of_scope" for r in rows):
        status = "partial"
    else:
        status = "matched"
    reasons = (["satisfaction_condition_failed"] if counterexamples else
               ["unsupported_translation"] if split else ["template_obligations_pending"])
    if not history_matches:
        reasons.append("history_not_preserved")
    if adoption_matches is False:
        reasons.append("adoption_not_preserved")
    if any(r["status"] == "out_of_scope" for r in rows):
        reasons.append("query_out_of_scope")
    if status == "unassessed":
        reasons.append("incomplete_execution")
    result = {"status": "resource_limit" if resource else "ok", "reason_codes": sorted(resource_reasons),
              "source_sha256": digest(source), "target_sha256": digest(request["target"]),
              "source_result": before, "target_result": after,
              "comparison": {"status": status, "mode": "semantic_handover", "history_matches": history_matches,
                             "adoption_matches": adoption_matches, "results": rows, "counterexamples": counterexamples},
              "certificate": None if resource else {"status": "not_certified", "evidence_level": "finite_execution_check",
                                                    "reason_codes": reasons},
              "incomplete": [{"view": r["view"], "query": r["query"]} for r in rows if r["status"] == "unassessed"]}
    if split:
        result["correct_target_result"] = correct
    return result


def run_events(request):
    budget = _header(request)
    operation = request["operation"]
    if operation == "reify_events":
        _source(request["source"], request["relation_ref"])
        string(request["target_ledger_ref"], "target_ledger_ref")
        if request["target_ledger_ref"] == request["source"]["ledger"]["ref"]:
            raise Problem("ledger_reference_collision", "target_ledger_ref")
        budget.tick()
        return _reify(request["source"], request["relation_ref"], request["target_ledger_ref"], budget)
    restored, target_ordered = _restore(request["target"])
    if operation == "restore_events":
        budget.tick()
        for _ in (*restored["ledger"]["assertions"], *restored["ledger"]["reviews"]):
            budget.tick()
        budget.tick()
        return {"status": "ok", "source": deepcopy(restored), "source_sha256": digest(restored),
                "target_sha256": digest(request["target"]), "reason_codes": [], "incomplete": [], "steps_used": budget.used}
    legacy = _queries(restored, request["views"], request["queries"])
    if operation == "query_events":
        budget.tick()
        response = _run_target(request["target"], restored, target_ordered, request["views"], request["queries"], budget)
    else:
        ordered = _source(request["source"], request["relation_ref"])
        _queries(request["source"], request["views"], request["queries"])
        if request["relation_ref"] != request["target"]["relation_ref"]:
            raise Problem("relation_mismatch", "relation_ref")
        fields(request["translation"], ("kind",), path="translation")
        if request["translation"]["kind"] not in ("shared_event", "split_roles"):
            raise Problem("unsupported_translation", "translation.kind", "unsupported_profile")
        budget.tick()
        response = _compare(request, request["source"], ordered, restored, target_ordered, legacy, budget)
    response["steps_used"] = budget.used
    return response
