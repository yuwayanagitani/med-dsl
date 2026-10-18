"""文脈ごとの正の閉包と、有限の役割付き事実への問い合わせ。"""

from .definitions import compile_rules, positive_closure
from .ledger import select_view
from .model import Budget, Proof, Problem, atom


def _pattern_key(pattern):
    return (pattern["predicate"], tuple((1, value["var"]) if type(value) is dict
                                      else (0, value) for value in pattern["args"]))


def _match(pattern, fact, binding):
    merged = dict(binding)
    for term, value in zip(pattern["args"], fact.args):
        if type(term) is dict:
            key = term["var"]
            if key in merged and merged[key] != value:
                return None
            merged[key] = value
        elif term != value:
            return None
    return tuple(sorted(merged.items()))


def bindings_for(query, facts, budget):
    rows = {(): Proof()}
    patterns = sorted(query["atoms"], key=_pattern_key)
    for index, pattern in enumerate(patterns):
        candidates = sorted(fact for fact in facts if fact.predicate == pattern["predicate"])
        joined = {}
        for binding, proof in sorted(rows.items()):
            for fact in candidates:
                budget.tick()
                merged = _match(pattern, fact, binding)
                if merged is not None:
                    joined[merged] = joined.get(merged, Proof()).merge(proof.merge(facts[fact]))
                    if index == len(patterns) - 1 and len(joined) > 1000:
                        raise Problem("binding_limit", status="resource_limit")
        rows = joined
        if not rows:
            break
    return rows


def _answer(query, facts, negative, budget):
    if budget.maximum == 0 or budget.used >= budget.maximum:
        raise Problem("step_limit", status="resource_limit")
    rows = bindings_for(query, facts, budget)
    if rows:
        ordered = sorted(rows.items())
        return "supported", [dict(binding) for binding, _ in ordered], [
            proof.evidence(binding) for binding, proof in ordered]
    if len(query["atoms"]) == 1 and all(type(x) is str for x in query["atoms"][0]["args"]):
        denied = atom(query["atoms"][0])
        if denied in negative:
            return "opposed", [], [negative[denied].evidence(())]
    return "undetermined", [], []


def run_query(request, ordered_packages, budget=None):
    if budget is None:
        budget = Budget(request["budget"]["max_steps"])
    result = {"status": "ok", "views": [], "results": [], "reason_codes": [],
              "retained_assertions": sorted(x["id"] for x in request["ledger"]["assertions"]),
              "incomplete": []}
    rules, sources = compile_rules(ordered_packages)
    if sources:
        result["definition_sources"] = sources
    for view in sorted(request["views"], key=lambda x: x["id"]):
        metadata, positive, negative, unknown = select_view(request["ledger"], view)
        result["views"].append(metadata)
        closures, failures = {}, {}
        for query in sorted(request["queries"], key=lambda x: x["id"]):
            context = query["context_ref"]
            facts, denials = positive.get(context, {}), negative.get(context, {})
            row = {"view": view["id"], "query": query["id"], "status": "unassessed",
                   "bindings": [], "evidence": [], "reason_codes": []}
            try:
                if budget.maximum == 0:
                    raise Problem("step_limit", status="resource_limit")
                if context in unknown:
                    row["reason_codes"] = ["unknown_capability"]
                    row["missing_capabilities"] = sorted(unknown[context])
                    row["blocking_assertion_refs"] = sorted({
                        ref for refs in unknown[context].values() for ref in refs})
                else:
                    if context in failures:
                        raise Problem(failures[context], status="resource_limit")
                    if context not in closures:
                        try:
                            closures[context] = positive_closure(facts, rules, budget)
                        except Problem as problem:
                            failures[context] = problem.code
                            raise
                    facts = closures[context]
                    collisions = sorted(set(facts) & set(denials))
                    if collisions:
                        proof = Proof()
                        conflicts = []
                        for fact in collisions:
                            proof = proof.merge(facts[fact]).merge(denials[fact])
                            conflicts.append({"atom": {"predicate": fact.predicate, "args": list(fact.args)},
                                              "positive_evidence": facts[fact].evidence(()),
                                              "negative_evidence": denials[fact].evidence(())})
                        row.update(status="conflict", evidence=[proof.evidence(())],
                                   conflicts=conflicts,
                                   reason_codes=["conflicting_assertions"])
                    else:
                        status, bindings, evidence = _answer(query, facts, denials, budget)
                        row.update(status=status, bindings=bindings, evidence=evidence)
            except Problem as problem:
                if problem.status != "resource_limit":
                    raise
                result["status"] = "resource_limit"
                row["reason_codes"] = [problem.code]
                result["reason_codes"] = sorted(set(result["reason_codes"]) | {problem.code})
            if row["status"] == "unassessed":
                result["incomplete"].append({"view": view["id"], "query": query["id"],
                                             "reason_codes": row["reason_codes"]})
            if query["required"] and row["status"] != "supported":
                row["information_request"] = {
                    "undetermined": "needs_information", "opposed": "needs_information",
                    "conflict": "needs_resolution", "unassessed": "needs_capability_or_completion",
                }[row["status"]]
            result["results"].append(row)
    return result
