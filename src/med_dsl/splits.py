"""概念の分割の併用：複数の分割（記号を共有し得る）の保存性の判定と、併用での候補集合。

個別に保存的な分割でも、記号を共有する併用は保存的とは限らない。併用全体の公理の下で、旧記号の
すべての割り当てが拡張できるかを全数で判定し、個別の認定を根拠にしない。基底の状態は読むだけで、
結論を基底の状態へ変換しない。
"""

import hashlib
import itertools
from pathlib import Path

from .ledger import select_view
from .model import Atom, Budget, PROFILE, Problem
from .split import SPLIT_PROFILE, check_split, classify
from .validation import digest, fields, indexed, packages, string, strings, validate_query, values

SPLITS_PROFILE = "p2-split-combination-draft-1"
SPEC_SHA256 = "73e4f4823ef3bb843023de617e0c6c0b594785ad8cb4921898a858f9d86382fc"
OPERATIONS = ("check_split_combination", "query_split_combination")
METHOD = "monadic-extension-exhaustive-1"
MAX_SPLITS, MAX_SYMBOLS = 4, 10


def _profile(value, path):
    if value != SPLITS_PROFILE:
        raise Problem("unsupported_profile", path, "unsupported_profile")


def _spec(value, path):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise Problem("invalid_sha256", path)
    if value != SPEC_SHA256:
        raise Problem("profile_spec_mismatch", path)


def _components(splits):
    """記号を共有する分割の連結成分（分割の添字の整列した並びの並び）。"""
    parent = list(range(len(splits)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for index, (head, parts) in enumerate(splits):
        for symbol in (head, *parts):
            if symbol in owner:
                parent[find(index)] = find(owner[symbol])
            else:
                owner[symbol] = index
    groups = {}
    for index in range(len(splits)):
        groups.setdefault(find(index), []).append(index)
    return sorted(groups.values())


def _acyclic(splits):
    """「部分→親」の辺が閉路を持たないか。"""
    edges = {}
    for head, parts in splits:
        for part in parts:
            edges.setdefault(part, set()).add(head)
    state = {}

    def visit(node):
        if state.get(node) == 1:
            return False
        if state.get(node) == 2:
            return True
        state[node] = 1
        ok = all(visit(next_node) for next_node in sorted(edges.get(node, ())))
        state[node] = 2
        return ok

    return all(visit(node) for node in sorted(edges))


def structure_of(splits):
    """併用の構造を、宣言した分割から再計算する。"""
    parts_of = [set(parts) for _, parts in splits]
    symbols = [{head, *parts} for head, parts in splits]
    all_parts = [q for _, parts in splits for q in parts]
    heads = {head for head, _ in splits}
    if len(splits) == 1:
        kind = "single"
    elif all(symbols[i].isdisjoint(symbols[j]) for i in range(len(splits)) for j in range(i)):
        kind = "disjoint"
    elif not _acyclic(splits):
        kind = "cyclic"
    elif len(set(all_parts)) != len(all_parts):
        kind = "shared_parts"
    else:
        kind = "forest"
    vocabulary = sorted(set().union(*symbols))
    old = sorted(set(vocabulary) - set(all_parts))
    new = sorted(set(all_parts))
    leaves = sorted(set(all_parts) - heads)
    return {"kind": kind, "chain": any(head in set(all_parts) for head in heads),
            "components": _components(splits), "vocabulary": vocabulary, "old_symbols": old, "new_symbols": new,
            "leaves": leaves, "forest_condition": kind in ("single", "disjoint", "forest")}


def _assignments(symbols, member_splits):
    """成分の公理を満たす割り当て。各分割の記号への制限が、すべて偽、または親と一つの部分だけ真、の枠に入るもの。"""
    index = {s: i for i, s in enumerate(symbols)}
    found = []
    for bits in itertools.product((0, 1), repeat=len(symbols)):
        ok = True
        for head, parts in member_splits:
            ones = sum(bits[index[q]] for q in parts)
            if not ((bits[index[head]] == 0 and ones == 0) or (bits[index[head]] == 1 and ones == 1)):
                ok = False
                break
        if ok:
            found.append(bits)
    return index, found


def _plan(splits):
    """成分ごとの語彙・割り当ての列挙（要求の検証の一部。課金しない）。"""
    structure = structure_of(splits)
    old = set(structure["old_symbols"])
    plan = []
    for members in structure["components"]:
        member_splits = [splits[i] for i in members]
        symbols = sorted({s for head, parts in member_splits for s in (head, *parts)})
        index, valid = _assignments(symbols, member_splits)
        plan.append({"members": members, "symbols": symbols, "index": index, "valid": valid,
                     "old": [s for s in symbols if s in old]})
    return structure, plan


def _judge(component, budget):
    """成分の保存性。旧記号の割り当てを辞書順に調べ、拡張できない最初のものを返す（なければ None）。"""
    extendable = {tuple(bits[component["index"][s]] for s in component["old"]) for bits in component["valid"]}
    for valuation in itertools.product((0, 1), repeat=len(component["old"])):
        budget.tick()
        if valuation not in extendable:
            return dict(zip(component["old"], valuation))
    return None


def _validate(request):
    op = request.get("operation")
    if type(op) is not str or op not in OPERATIONS:
        raise Problem("unsupported_operation", "operation", "unsupported_profile")
    extra = {"check_split_combination": ("source", "splits"),
             "query_split_combination": ("source", "views", "splits", "queries")}[op]
    fields(request, ("schema_version", "operation", "consumer", "budget", *extra))
    try:
        actual = hashlib.sha256(Path(__file__).with_name("splits_spec.json").read_bytes()).hexdigest()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if actual != SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    _profile(consumer["profile"], "consumer.profile")
    _spec(consumer["profile_spec_sha256"], "consumer.profile_spec_sha256")
    strings(consumer["operations"], len(OPERATIONS), "consumer.operations")
    if op not in consumer["operations"] or set(consumer["operations"]) - set(OPERATIONS):
        raise Problem("unsupported_operation", "consumer.operations", "unsupported_profile")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")

    source = request["source"]
    if op == "check_split_combination":
        fields(source, ("package",), ("dependency_packages",), path="source")
        ordered, _ = packages(source["package"], source.get("dependency_packages", []))
        views = queries = None
    else:
        fields(source, ("package", "contexts", "ledger"), ("dependency_packages",), path="source")
        p0 = {"schema_version": "p0-request-draft-1", "operation": "query", "package": source["package"],
              "contexts": source["contexts"], "ledger": source["ledger"], "views": request["views"],
              "queries": [], "budget": request["budget"]}
        if "dependency_packages" in source:
            p0["dependency_packages"] = source["dependency_packages"]
        ordered = validate_query(p0)
    raw = values(request["splits"], MAX_SPLITS, "splits")
    if not raw:
        raise Problem("empty_collection", "splits")
    splits, seen = [], set()
    for position, item in enumerate(raw):
        head, parts = check_split(ordered, item, f"splits[{position}]")
        if (head, tuple(parts)) in seen:
            raise Problem("duplicate_split", "splits")
        seen.add((head, tuple(parts)))
        splits.append((head, parts))
    if len({s for head, parts in splits for s in (head, *parts)}) > MAX_SYMBOLS:
        raise Problem("vocabulary_limit", "splits", "resource_limit")
    if op == "query_split_combination":
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
    return op, splits, views, queries


def _status_from_found(head, parts, found, positive):
    """併用の枠（None は親が偽）から、P2-b の状態表で状態を決める。"""
    if not found:
        return "inconsistent", [], False
    if found == {None}:
        return "parent_opposed", [], False
    if None in found:
        return "no_parent", [], False
    candidates = [q for q in parts if q in found]
    if len(candidates) == 1:
        return ("asserted" if candidates[0] in positive else "single"), candidates, head not in positive
    return ("open" if len(candidates) == len(parts) else "narrowed"), candidates, False


def _check(request, splits, budget):
    structure, plan = _plan(splits)
    budget.tick()
    counterexample = None
    for position, component in enumerate(plan):
        failed = _judge(component, budget)
        if failed is not None:
            counterexample = {"component": position, "splits": component["members"],
                              "old_valuation": {s: v for s, v in sorted(failed.items())}}
            break
    individual = []
    for position, split in enumerate(splits):
        _, single_plan = _plan([split])
        single = _judge(single_plan[0], budget)
        individual.append({"split": position, "parent": split[0], "parts": list(split[1]),
                           "certificate": "certified" if single is None else "not_certified"})
    budget.tick()
    certified = counterexample is None
    return {"status": "ok", "structure": structure,
            "certificate": {"status": "certified" if certified else "not_certified", "method": METHOD,
                            "evidence_level": "exhaustive_monadic_decision", "basis": "recomputed_from_the_combination",
                            "reason_codes": [] if certified else ["not_conservative_over_old_symbols"],
                            "counterexample": counterexample,
                            "scope": {"axioms": "p2-concept-split-draft-1", "splits": len(splits),
                                      "old_symbols": structure["old_symbols"]} if certified else None},
            "individual": individual, "reason_codes": [], "incomplete": []}


def _query(request, splits, views, queries, budget):
    structure, plan = _plan(splits)
    source = request["source"]
    ledger = source["ledger"]
    snapshot_hash = digest(source)
    vocabulary = structure["vocabulary"]
    leaves = set(structure["leaves"])
    rows = [{"view": v, "query": q, "subject": queries[q]["subject"], "context_ref": queries[q]["context_ref"],
             "status": "blocked", "reason_codes": ["step_limit"], "answer_kind": "joint_candidate_set",
             "converted_to_base": False, "base": None, "splits": None, "leaf_candidates": None,
             "interaction_violation": None, "evidence": None, "information_requests": []}
            for v in sorted(views) for q in sorted(queries)]
    metadata = []
    response = {"status": "ok", "reason_codes": [], "results": rows, "views": metadata, "snapshot_sha256": snapshot_hash,
                "structure": structure, "incomplete": []}

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
                ledger, views[view_id], known_capabilities={PROFILE, SPLIT_PROFILE, SPLITS_PROFILE})
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
                    row.update(status="blocked", reason_codes=["unknown_capability"], missing_capabilities=sorted(blockers),
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
                positive_set = {n for n in vocabulary if atoms[n] in pos}
                negative_set = {n for n in vocabulary if atoms[n] in neg}
                joint = [None] * len(splits)
                violated, possible = [], set()
                for component in plan:
                    index = component["index"]
                    models = []
                    for bits in component["valid"]:
                        budget.tick()
                        if all(bits[index[s]] == 1 for s in component["symbols"] if s in positive_set) \
                                and all(bits[index[s]] == 0 for s in component["symbols"] if s in negative_set):
                            models.append(bits)
                    for position in component["members"]:
                        head, parts = splits[position]
                        found = {None if bits[index[head]] == 0 else next(q for q in parts if bits[index[q]] == 1) for bits in models}
                        joint[position] = _status_from_found(head, parts, found, positive_set)
                    possible |= {s for bits in models for s in component["symbols"] if s in leaves and bits[index[s]] == 1}
                    if not models:
                        violated.append(component)
                entries, requests = [], []
                for position, (head, parts) in enumerate(splits):
                    status, candidates, derived = joint[position]
                    single = classify(head, parts, head in positive_set, head in negative_set,
                                      positive_set & set(parts), negative_set & set(parts))
                    own = next(c for c in plan if position in c["members"])
                    entries.append({"index": position, "parent": head, "parts": list(parts),
                                    "individual": {"status": single[0], "candidates": list(single[1])},
                                    "joint": {"status": status, "candidates": list(candidates), "parent_derived": derived},
                                    "differs": (status, candidates) != (single[0], single[1]),
                                    "axioms_of_splits": list(own["members"])})
                    if status in ("open", "narrowed", "single"):
                        requests.append({"kind": "confirm_part", "split": position, "subject": subject, "context_ref": context,
                                         "parent": head, "candidate_parts": list(candidates)})
                adopted = [literal(atoms[n], "positive", pos[atoms[n]]) for n in vocabulary if atoms[n] in pos]
                adopted += [literal(atoms[n], "negative", neg[atoms[n]]) for n in vocabulary if atoms[n] in neg]
                for component in violated:
                    symbols = set(component["symbols"])
                    requests.append({"kind": "resolve_split_violation", "splits": list(component["members"]), "subject": subject,
                                     "context_ref": context,
                                     "assertion_refs": sorted({r for lit in adopted if lit["predicate"] in symbols for r in lit["assertion_refs"]})})
                interaction = any(all(entries[p]["individual"]["status"] != "inconsistent" for p in c["members"]) for c in violated)
                pending = [{"assertion_ref": a["id"], "predicate": a["atom"]["predicate"], "polarity": a["polarity"],
                            "origin_kind": a["origin"]["kind"]}
                           for a in sorted(ledger["assertions"], key=lambda x: x["id"])
                           if a["id"] in pending_ids and a["context_ref"] == context
                           and a["atom"]["predicate"] in vocabulary and a["atom"]["args"] == [subject]]
                state = lambda name: "supported" if atoms[name] in pos else "opposed" if atoms[name] in neg else "undetermined"
                budget.tick()
                row.update(status="computed", reason_codes=[], base={n: state(n) for n in vocabulary}, splits=entries,
                           leaf_candidates=sorted(possible), interaction_violation=interaction,
                           evidence={"ledger_ref": ledger["ref"], "snapshot_sha256": snapshot_hash, "adopted": adopted, "pending": pending},
                           information_requests=requests)
    except Problem as problem:
        if problem.status != "resource_limit":
            raise
        response.update(status="resource_limit", reason_codes=[problem.code])
        for row in rows:
            if row["reason_codes"] == ["step_limit"]:
                row["reason_codes"] = [problem.code]
    response["incomplete"] = [{"view": r["view"], "query": r["query"]} for r in rows if r["status"] == "blocked"]
    return response


def run_splits(request):
    op, splits, views, queries = _validate(request)
    budget = Budget(request["budget"]["max_steps"])
    if op == "check_split_combination":
        response = _check(request, splits, budget)
    else:
        response = _query(request, splits, views, queries, budget)
    response["steps_used"] = budget.used
    return response
