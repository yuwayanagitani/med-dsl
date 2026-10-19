"""概念の分割：旧い概念 P が部分 Q1…Qk に分かれたとき、旧い記録に区別がない個体の候補集合と情報要求を返す。

基底の状態を読むだけで書き換えない。結論は候補集合の状態で、基底の `supported` などへ変換しない。
公理（包含・被覆・排他）は仕様に固定され、要求は変更できない。
"""

import hashlib
from pathlib import Path

from .definitions import compile_rules
from .ledger import select_view
from .model import Atom, Budget, PROFILE, Problem
from .validation import digest, fields, indexed, string, strings, validate_query, values

SPLIT_PROFILE = "p2-concept-split-draft-1"
SPEC_SHA256 = "30326bd7b99cb4ccff8287b31a249fdda1bcd4d4e83620b6c7bb72eb45bd46e8"
AXIOMS = ("A1_subsumption", "A2_coverage", "A3_exclusivity")
SATISFIED_BY = "human_confirmed_assertion_of_one_candidate_or_human_confirmed_negation_of_all_others"


def _profile(value, path):
    if value != SPLIT_PROFILE:
        raise Problem("unsupported_profile", path, "unsupported_profile")


def _spec(value, path):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise Problem("invalid_sha256", path)
    if value != SPEC_SHA256:
        raise Problem("profile_spec_mismatch", path)


def _validate(request):
    fields(request, ("schema_version", "operation", "consumer", "source", "views", "split", "queries", "budget"))
    if request["operation"] != "query_split":
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    try:
        actual = hashlib.sha256(Path(__file__).with_name("split_spec.json").read_bytes()).hexdigest()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if actual != SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    _profile(consumer["profile"], "consumer.profile")
    _spec(consumer["profile_spec_sha256"], "consumer.profile_spec_sha256")
    strings(consumer["operations"], 64, "consumer.operations")
    if consumer["operations"] != ["query_split"]:
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")

    source = request["source"]
    fields(source, ("package", "contexts", "ledger"), ("dependency_packages",), path="source")
    p0 = {"schema_version": "p0-request-draft-1", "operation": "query", "package": source["package"],
          "contexts": source["contexts"], "ledger": source["ledger"], "views": request["views"],
          "queries": [], "budget": request["budget"]}
    if "dependency_packages" in source:
        p0["dependency_packages"] = source["dependency_packages"]
    ordered = validate_query(p0)

    split = request["split"]
    fields(split, ("parent", "parts"), path="split")
    parent = split["parent"]
    string(parent, "split.parent")
    parts = values(split["parts"], 8, "split.parts")
    for part in parts:
        string(part, "split.parts")
    if len(parts) < 2:
        raise Problem("too_few_parts", "split.parts")
    if len(set(parts)) != len(parts):
        raise Problem("duplicate_reference", "split.parts")
    if parent in parts:
        raise Problem("parent_among_parts", "split")
    roles = {p["ref"]: p["roles"] for package in ordered for p in package["predicates"]}
    for name in (parent, *parts):
        if name not in roles:
            raise Problem("undeclared_predicate", "split")
        if len(roles[name]) != 1:
            raise Problem("split_predicate_not_unary", "split")
    mentioned = {parent, *parts}
    rules, _ = compile_rules(ordered)
    if any(rule.head in mentioned or mentioned & set(rule.body) for rule in rules):
        raise Problem("split_symbol_has_rules", "split")

    contexts = {c["ref"] for c in source["contexts"]}
    queries = indexed(request["queries"], "id", 64, "queries")
    if not queries:
        raise Problem("empty_collection", "queries")
    for query in queries.values():
        fields(query, ("id", "context_ref", "subject", "required"), path="query")
        if type(query["context_ref"]) is not str or query["context_ref"] not in contexts:
            raise Problem("unresolved_context", "query.context_ref")
        string(query["subject"], "query.subject")
        if type(query["required"]) is not bool:
            raise Problem("expected_boolean", "query.required")
    views = indexed(request["views"], "id", 64, "views")
    if not views:
        raise Problem("empty_collection", "views")
    return parent, sorted(parts), views, queries


def classify(parent, parts, positive_parent, negative_parent, positive_parts, negative_parts):
    """個体一つの採用された肯定・否定から、候補集合の状態を規則で求める。

    positive_parts / negative_parts は部分の集合。戻り値は (status, candidates, excluded, parent_derived)。
    excluded は 部分 -> 理由の並び。除外の規則：その部分の否定、別の部分の肯定、親の否定。
    """
    excluded = {}
    for part in parts:
        reasons = []
        if part in negative_parts:
            reasons.append("adopted_negative")
        if positive_parts - {part}:
            reasons.append("other_part_asserted")
        if negative_parent:
            reasons.append("parent_opposed")
        if reasons:
            excluded[part] = reasons
    candidates = [part for part in parts if part not in excluded]
    parent_forced = positive_parent or bool(positive_parts)
    if parent_forced and not candidates:
        return "inconsistent", [], excluded, False
    if not parent_forced:
        # すべて偽の割り当てが残る。候補が残るなら親は未決、残らないなら親は成り立たない。
        if not candidates:
            return "parent_opposed", [], excluded, False
        return "no_parent", [], excluded, False
    derived = not positive_parent
    if len(candidates) == 1:
        return ("asserted" if candidates[0] in positive_parts else "single"), candidates, excluded, derived
    return ("open" if len(candidates) == len(parts) else "narrowed"), candidates, excluded, derived


def _axioms(status, excluded, parent_derived):
    """結論が頼る公理。採用された主張だけで言える状態（no_parent）は空になる。"""
    used = set()
    if status == "inconsistent":
        return list(AXIOMS)
    if parent_derived:
        used.add("A1_subsumption")
    for reasons in excluded.values():
        if "other_part_asserted" in reasons:
            used.add("A3_exclusivity")
        if "parent_opposed" in reasons:
            used.add("A1_subsumption")
    if status in ("open", "narrowed", "single"):
        used.add("A2_coverage")
    if status == "parent_opposed" and not any("parent_opposed" in r for r in excluded.values()):
        used.add("A2_coverage")
    return sorted(used)


def run_split(request):
    parent, parts, views, queries = _validate(request)
    source = request["source"]
    ledger = source["ledger"]
    snapshot_hash = digest(source)
    budget = Budget(request["budget"]["max_steps"])
    vocabulary = (parent, *parts)
    rows = [{"view": v, "query": q, "subject": queries[q]["subject"], "context_ref": queries[q]["context_ref"],
             "status": "blocked", "reason_codes": ["step_limit"], "answer_kind": "candidate_set",
             "converted_to_base": False, "base": None, "split": None, "evidence": None,
             "information_requests": []}
            for v in sorted(views) for q in sorted(queries)]
    metadata = []
    response = {"status": "ok", "reason_codes": [], "results": rows, "views": metadata,
                "snapshot_sha256": snapshot_hash,
                "split": {"parent": parent, "parts": list(parts), "axioms": list(AXIOMS)}, "incomplete": []}

    def literal(atom, polarity, proof):
        return {"predicate": atom.predicate, "polarity": polarity, "assertion_refs": sorted(proof.assertions),
                "review_refs": sorted(proof.reviews)}

    try:
        budget.tick()
        row_index = 0
        for view_id in sorted(views):
            for _ in ledger["assertions"]:
                budget.tick()
            for _ in ledger["reviews"]:
                budget.tick()
            meta, positive, negative, unknown = select_view(
                ledger, views[view_id], known_capabilities={PROFILE, SPLIT_PROFILE})
            metadata.append(meta)
            pending_ids = set(meta["pending_assertions"])
            for query_id in sorted(queries):
                row = rows[row_index]
                row_index += 1
                budget.tick()
                query = queries[query_id]
                context, subject = query["context_ref"], query["subject"]
                pos, neg = positive.get(context, {}), negative.get(context, {})
                if context in unknown:
                    blockers = unknown[context]
                    row.update(status="blocked", reason_codes=["unknown_capability"],
                               missing_capabilities=sorted(blockers),
                               blocking_assertion_refs=sorted(set().union(*blockers.values())))
                    continue
                collisions = sorted(set(pos) & set(neg))
                if collisions:
                    row.update(status="blocked", reason_codes=["unresolved_conflict"],
                               conflicts=[{"atom": {"predicate": f.predicate, "args": list(f.args)},
                                           "positive": literal(f, "positive", pos[f]),
                                           "negative": literal(f, "negative", neg[f])} for f in collisions])
                    continue
                atoms = {name: Atom(name, (subject,)) for name in vocabulary}
                for _ in vocabulary:
                    budget.tick()
                positive_parts = {q for q in parts if atoms[q] in pos}
                negative_parts = {q for q in parts if atoms[q] in neg}
                status, candidates, excluded, derived = classify(
                    parent, parts, atoms[parent] in pos, atoms[parent] in neg, positive_parts, negative_parts)
                state = lambda name: "supported" if atoms[name] in pos else "opposed" if atoms[name] in neg else "undetermined"
                adopted = [literal(atoms[n], "positive", pos[atoms[n]]) for n in vocabulary if atoms[n] in pos]
                adopted += [literal(atoms[n], "negative", neg[atoms[n]]) for n in vocabulary if atoms[n] in neg]
                pending = [{"assertion_ref": a["id"], "predicate": a["atom"]["predicate"], "polarity": a["polarity"],
                            "origin_kind": a["origin"]["kind"]}
                           for a in sorted(ledger["assertions"], key=lambda x: x["id"])
                           if a["id"] in pending_ids and a["context_ref"] == context
                           and a["atom"]["predicate"] in vocabulary and a["atom"]["args"] == [subject]]
                requests = []
                if status in ("open", "narrowed", "single"):
                    requests.append({"kind": "confirm_part", "subject": subject, "context_ref": context, "parent": parent,
                                     "candidate_parts": list(candidates), "satisfied_by": SATISFIED_BY,
                                     "pending_assertion_refs": [p["assertion_ref"] for p in pending]})
                elif status == "inconsistent":
                    requests.append({"kind": "resolve_split_violation", "subject": subject, "context_ref": context,
                                     "assertion_refs": sorted({r for lit in adopted for r in lit["assertion_refs"]})})
                budget.tick()
                row.update(status="computed", reason_codes=[],
                           base={"parent": state(parent), "parts": {q: state(q) for q in parts}},
                           split={"status": status, "candidates": list(candidates),
                                  "excluded": [{"part": q, "reasons": excluded[q]} for q in parts if q in excluded],
                                  "parent_derived": derived,
                                  "derivation": _axioms(status, excluded, derived)},
                           evidence={"ledger_ref": ledger["ref"], "snapshot_sha256": snapshot_hash,
                                     "adopted": adopted, "pending": pending},
                           information_requests=requests)
    except Problem as problem:
        if problem.status != "resource_limit":
            raise
        response.update(status="resource_limit", reason_codes=[problem.code])
        for row in rows:
            if row["reason_codes"] == ["step_limit"]:
                row["reason_codes"] = [problem.code]
    response["incomplete"] = [{"view": r["view"], "query": r["query"]} for r in rows if r["status"] == "blocked"]
    response["steps_used"] = budget.used
    return response
