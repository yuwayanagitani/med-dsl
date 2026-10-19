"""小さな一階参考意味。有限モデルの反例と既知の導出だけを返す。"""

from .model import Problem
from .validation import canonical_bytes, digest, fields, indexed, string, strings, values


def validate_reference(request):
    signature = request["signature"]
    fields(signature, ("predicates", "constants"), path="signature")
    predicates = indexed(signature["predicates"], "ref", 8, "signature.predicates")
    strings(signature["constants"], 8, "signature.constants")
    for p in predicates.values():
        fields(p, ("ref", "arity"), path="predicate")
        if type(p["arity"]) is not int or not 1 <= p["arity"] <= 4:
            raise Problem("invalid_arity", "predicate.arity")
    count = 0

    def term(t, scope):
        if type(t) is not dict or len(t) != 1 or next(iter(t)) not in ("var", "const"):
            raise Problem("invalid_term")
        kind, name = next(iter(t.items()))
        string(name, "term")
        if name not in (scope if kind == "var" else signature["constants"]):
            raise Problem("unbound_variable" if kind == "var" else "undeclared_constant")

    def formula(f, scope=frozenset(), depth=0):
        nonlocal count
        count += 1
        if count > 512 or depth > 16:
            raise Problem("formula_limit", status="resource_limit")
        if type(f) is not dict:
            raise Problem("expected_object", "formula")
        kind = f.get("kind")
        if kind == "atom":
            fields(f, ("kind", "predicate", "args"), path="formula")
            string(f["predicate"], "formula.predicate")
            if f["predicate"] not in predicates:
                raise Problem("undeclared_predicate")
            if len(values(f["args"], 4, "formula.args")) != predicates[f["predicate"]]["arity"]:
                raise Problem("arity_mismatch")
            for t in f["args"]:
                term(t, scope)
        elif kind in ("forall", "exists"):
            fields(f, ("kind", "var", "body"), path="formula")
            string(f["var"], "formula.var")
            if f["var"] in scope:
                raise Problem("shadowed_variable")
            formula(f["body"], scope | {f["var"]}, depth + 1)
        elif kind == "not":
            fields(f, ("kind", "body"), path="formula")
            formula(f["body"], scope, depth + 1)
        elif kind in ("and", "or"):
            fields(f, ("kind", "items"), path="formula")
            if not values(f["items"], 8, "formula.items"):
                raise Problem("empty_connective")
            for item in f["items"]:
                formula(item, scope, depth + 1)
        elif kind in ("implies", "eq"):
            fields(f, ("kind", "left", "right"), path="formula")
            for key in ("left", "right"):
                if kind == "eq":
                    term(f[key], scope)
                else:
                    formula(f[key], scope, depth + 1)
        else:
            raise Problem("unsupported_formula", "formula.kind", "unsupported_profile")

    for side in ("source", "target"):
        fields(request[side], ("theory", "data"), path=side)
        for f in values(request[side]["theory"], 16, side + ".theory"):
            formula(f)
        for f in values(request[side]["data"], 16, side + ".data"):
            formula(f)
            if f["kind"] != "atom":
                raise Problem("expected_ground_atom", side + ".data")
    queries = indexed(request["queries"], "id", 16, "queries")
    if not queries:
        raise Problem("empty_collection", "queries")
    for q in queries.values():
        fields(q, ("id", "formula"), path="query")
        formula(q["formula"])
    models = indexed(request["models"], "id", 16, "models")
    for entry in models.values():
        fields(entry, ("id", "model"), path="model_entry")
        m = entry["model"]
        fields(m, ("domain", "constants", "predicates"), path="model")
        strings(m["domain"], 8, "model.domain")
        if not m["domain"]:
            raise Problem("empty_domain")
        fields(m["constants"], signature["constants"], path="model.constants")
        for value in m["constants"].values():
            string(value, "model.constant")
            if value not in m["domain"]:
                raise Problem("unresolved_domain_element")
        fields(m["predicates"], predicates, path="model.predicates")
        for ref, tuples in m["predicates"].items():
            seen = set()
            for row in values(tuples, 64, "model.relation"):
                values(row, 4, "model.tuple")
                if len(row) != predicates[ref]["arity"]:
                    raise Problem("arity_mismatch")
                for value in row:
                    string(value, "model.tuple")
                    if value not in m["domain"]:
                        raise Problem("unresolved_domain_element")
                if tuple(row) in seen:
                    raise Problem("duplicate_tuple")
                seen.add(tuple(row))
    sizes = values(request["finite_domain_sizes"], 8, "finite_domain_sizes")
    if any(type(n) is not int or not 1 <= n <= 8 for n in sizes) or len(set(sizes)) != len(sizes):
        raise Problem("invalid_domain_sizes")
    if sizes and (predicates or signature["constants"]):
        raise Problem("unsupported_finite_probe", status="unsupported_profile")


def truth(formula, model, budget, env=None):
    budget.tick()
    env = {} if env is None else env
    term = lambda t: env[t["var"]] if "var" in t else model["constants"][t["const"]]
    kind = formula["kind"]
    if kind == "atom":
        return [term(t) for t in formula["args"]] in model["predicates"][formula["predicate"]]
    if kind == "eq":
        return term(formula["left"]) == term(formula["right"])
    if kind == "not":
        return not truth(formula["body"], model, budget, env)
    if kind == "and":
        return all(truth(f, model, budget, env) for f in formula["items"])
    if kind == "or":
        return any(truth(f, model, budget, env) for f in formula["items"])
    if kind == "implies":
        return not truth(formula["left"], model, budget, env) or truth(formula["right"], model, budget, env)
    for value in model["domain"]:
        budget.tick()
        result = truth(formula["body"], model, budget, {**env, formula["var"]: value})
        if kind == "forall" and not result:
            return False
        if kind == "exists" and result:
            return True
    return kind == "forall"


def _unary_variable(f, variable):
    return f["kind"] == "atom" and f["args"] == [{"var": variable}]


def _proof(side, query, budget):
    sentences = side["theory"] + side["data"]
    facts, rules = {}, []
    for i, f in enumerate(sentences):
        budget.tick()
        if canonical_bytes(f) == canonical_bytes(query):
            return {"kind": "asserted_sentence", "sentence_indices": [i]}
        if f["kind"] == "atom" and len(f["args"]) == 1:
            facts[(f["predicate"], f["args"][0]["const"])] = {i}
        if f["kind"] == "forall" and f["body"]["kind"] == "implies":
            body = f["body"]
            if _unary_variable(body["left"], f["var"]) and _unary_variable(body["right"], f["var"]):
                rules.append((body["left"]["predicate"], body["right"]["predicate"], i))
    changed = True
    while changed:
        changed = False
        for a, b, index in rules:
            for (pred, constant), refs in sorted(list(facts.items())):
                budget.tick()
                if pred == a and (b, constant) not in facts:
                    facts[(b, constant)] = refs | {index}
                    changed = True
    if query["kind"] == "atom" and len(query["args"]) == 1:
        key = query["predicate"], query["args"][0]["const"]
        if key in facts:
            return {"kind": "unary_horn", "sentence_indices": sorted(facts[key])}
    if query["kind"] != "exists" or not _unary_variable(query["body"], query["var"]):
        return None
    wanted = query["body"]["predicate"]
    for (pred, constant), refs in sorted(facts.items()):
        budget.tick()
        if pred == wanted:
            return {"kind": "existing_ground_witness", "constant": constant, "sentence_indices": sorted(refs)}
    for index, f in enumerate(side["theory"]):
        budget.tick()
        if f["kind"] != "forall" or f["body"]["kind"] != "implies":
            continue
        premise, conclusion = f["body"]["left"], f["body"]["right"]
        if not _unary_variable(premise, f["var"]) or conclusion["kind"] != "exists" or conclusion["body"]["kind"] != "and":
            continue
        items = conclusion["body"]["items"]
        witness = {"kind": "atom", "predicate": wanted, "args": [{"var": conclusion["var"]}]}
        relations = [x for x in items if x["kind"] == "atom" and x["args"] == [{"var": f["var"]}, {"var": conclusion["var"]}]]
        if len(items) == 2 and witness in items and len(relations) == 1:
            for (pred, constant), refs in sorted(facts.items()):
                budget.tick()
                if pred == premise["predicate"]:
                    return {"kind": "existential_rule_consequence", "sentence_indices": sorted(refs | {index}), "named_witness": None}
    return None


def run_reference(request, budget):
    checked = []
    for entry in sorted(request["models"], key=lambda m: m["id"]):
        model = entry["model"]
        valid = {side: all(truth(f, model, budget) for f in request[side]["theory"] + request[side]["data"])
                 for side in ("source", "target")}
        checked.append({"model_id": entry["id"], "model_sha256": digest(model),
                        "source_model": valid["source"], "target_model": valid["target"],
                        "query_truth": {q["id"]: truth(q["formula"], model, budget) for q in sorted(request["queries"], key=lambda q: q["id"])}})
    sentences = {side: {canonical_bytes(f) for f in request[side]["theory"] + request[side]["data"]} for side in ("source", "target")}
    budget.tick()
    coverage_witness = next((r["model_id"] for r in checked if r["source_model"] and not r["target_model"]), None)
    reduct_witness = next((r["model_id"] for r in checked if r["target_model"] and not r["source_model"]), None)
    coverage = False if coverage_witness else True if sentences["target"] <= sentences["source"] else None
    budget.tick()
    reduct = False if reduct_witness else True if sentences["source"] <= sentences["target"] else None
    results = []
    for q in sorted(request["queries"], key=lambda q: q["id"]):
        row = {"query_id": q["id"]}
        for side in ("source", "target"):
            proof = _proof(request[side], q["formula"], budget)
            countermodel = next((r for r in checked if r[side + "_model"] and not r["query_truth"][q["id"]]), None)
            if proof and countermodel:
                raise Problem("inconsistent_entailment_evidence")
            row[side] = {"status": "entailed" if proof else "not_entailed" if countermodel else "unassessed",
                         "entails": True if proof else False if countermodel else None,
                         "proof": proof, "countermodel_id": countermodel["model_id"] if countermodel else None}
        results.append(row)
    probes = []
    for size in request["finite_domain_sizes"]:
        model = {"domain": [str(i) for i in range(size)], "constants": {}, "predicates": {}}
        satisfied = {side: all(truth(f, model, budget) for f in request[side]["theory"] + request[side]["data"]) for side in ("source", "target")}
        probes.append({"domain_size": size, "source_model": satisfied["source"], "target_model": satisfied["target"],
                       "query_truth": {q["id"]: truth(q["formula"], model, budget) for q in request["queries"]},
                       "agreement": satisfied["source"] == satisfied["target"]})
    identity = sentences["source"] == sentences["target"]
    budget.tick()
    if identity:
        reasons = []
    elif coverage_witness:
        reasons = ["old_model_not_liftable"]
    elif reduct_witness:
        reasons = ["new_model_reduct_invalid"]
    else:
        # 未証明の側だけを理由にする。coverage と reduct の両方が True なら文集合が等しく identity になる。
        reasons = [code for proven, code in ((coverage is True, "model_coverage_not_established"),
                                             (reduct is True, "model_reduct_not_established")) if not proven]
    return {"status": "ok", "meaning_mode": "first_order_reference", "results": results, "models": checked,
            "model_coverage": coverage, "model_reduct": reduct, "satisfaction_identity": True,
            "coverage_countermodel_id": coverage_witness, "reduct_countermodel_id": reduct_witness,
            "finite_probes": probes, "named_witness_assertions_added": [],
            "certificate": {"status": "certified" if identity else "not_certified",
                            "evidence_level": "checked_identity_template" if identity else "verified_countermodel" if coverage_witness or reduct_witness else "insufficient_conditions",
                            "reason_codes": reasons,
                            "scope": "same_signature_identity_first_order_sentences" if identity else None},
            "reason_codes": [], "incomplete": [{"query_id": r["query_id"], "side": side}
                for r in results for side in ("source", "target") if r[side]["status"] == "unassessed"]}
