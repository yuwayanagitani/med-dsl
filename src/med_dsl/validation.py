"""外部取得を行わない、厳格な JSON・参照検証。"""

from datetime import datetime
import hashlib
import json
import re

from .model import MAX_BYTES, POLICY, PROFILE, Problem


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Problem("duplicate_json_key")
        value[key] = item
    return value


def _number(_):
    raise Problem("unsupported_json_number")


def decode_json(raw):
    if len(raw) > MAX_BYTES:
        raise Problem("input_size_limit", status="resource_limit")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=_number, parse_constant=_number)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Problem("invalid_json") from error


def check_json(value):
    """Python API も、JSON デコーダを迂回して型を持ち込めない。"""
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 64:
            raise Problem("nesting_limit", status="resource_limit")
        if type(item) is dict:
            if not all(type(key) is str for key in item):
                raise Problem("invalid_json_key")
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (str, int, bool):
            raise Problem("unsupported_json_type")
    try:
        raw = canonical_bytes(value)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Problem("invalid_json") from error
    if len(raw) > MAX_BYTES:
        raise Problem("input_size_limit", status="resource_limit")
    return hashlib.sha256(raw).hexdigest()


def fields(value, required, optional=(), path="$"):
    if type(value) is not dict:
        raise Problem("expected_object", path)
    if set(value) - set(required) - set(optional):
        raise Problem("unknown_field", path)
    if set(required) - set(value):
        raise Problem("missing_field", path)


def string(value, path):
    if type(value) is not str or not value or value != value.strip():
        raise Problem("expected_nonempty_string", path)


def values(value, maximum, path):
    if type(value) is not list:
        raise Problem("expected_array", path)
    if len(value) > maximum:
        raise Problem("item_limit", path, "resource_limit")
    return value


def strings(value, maximum, path):
    for item in values(value, maximum, path):
        string(item, path)
    if len(set(value)) != len(value):
        raise Problem("duplicate_reference", path)


def timestamp(value, path):
    string(value, path)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise Problem("invalid_timestamp", path)
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise Problem("invalid_timestamp", path) from error


def indexed(items, key, maximum, path):
    result = {}
    for item in values(items, maximum, path):
        if type(item) is not dict or key not in item:
            raise Problem("missing_identifier", path)
        string(item[key], path)
        if item[key] in result:
            raise Problem("duplicate_identifier", path)
        result[item[key]] = item
    return result


def _package(package):
    fields(package, ("ref", "profile", "predicates", "definitions", "inclusions", "dependencies"))
    string(package["ref"], "package.ref")
    string(package["profile"], "package.profile")
    if package["profile"] != PROFILE:
        raise Problem("unsupported_profile", "package.profile", "unsupported_profile")
    predicates = indexed(package["predicates"], "ref", 64, "predicates")
    for predicate in predicates.values():
        fields(predicate, ("ref", "roles"))
        strings(predicate["roles"], 8, "predicate.roles")
        if not predicate["roles"]:
            raise Problem("empty_roles", "predicate.roles")
    seen = set()
    for definition in values(package["definitions"], 64, "definitions"):
        if type(definition) is not dict:
            raise Problem("expected_object", "definition")
        if definition.get("kind") == "defined":
            fields(definition, ("kind", "symbol", "all_of"))
            strings(definition["all_of"], 64, "definition.all_of")
            if not definition["all_of"]:
                raise Problem("empty_definition", "definition")
        elif definition.get("kind") == "subtype":
            fields(definition, ("kind", "symbol", "parent"))
            string(definition["parent"], "definition.parent")
        else:
            raise Problem("invalid_definition_kind", "definition")
        string(definition["symbol"], "definition.symbol")
        if definition["symbol"] not in predicates:
            raise Problem("undeclared_definition", "definition.symbol")
        if definition["symbol"] in seen:
            raise Problem("duplicate_definition", "definition.symbol")
        seen.add(definition["symbol"])
    for inclusion in values(package["inclusions"], 64, "inclusions"):
        fields(inclusion, ("sub", "super"))
        string(inclusion["sub"], "inclusion.sub")
        string(inclusion["super"], "inclusion.super")
    dependencies = indexed(package["dependencies"], "ref", 64, "dependencies")
    for dependency in dependencies.values():
        fields(dependency, ("ref", "sha256"))
        if type(dependency["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", dependency["sha256"]):
            raise Problem("invalid_hash", "dependency.sha256")


def _registry(roots, supplied):
    registry = {}
    for package in [*roots, *values(supplied, 64, "dependency_packages")]:
        _package(package)
        ref = package["ref"]
        if ref in registry and digest(registry[ref]) != digest(package):
            raise Problem("reference_redefined", ref)
        registry[ref] = package
    if len(registry) > 64:
        raise Problem("package_limit", status="resource_limit")
    return registry


def _closure(roots, registry):
    ordered, seen, active = [], set(), set()

    def visit(ref):
        if ref in active:
            raise Problem("dependency_cycle", ref)
        if ref in seen:
            return
        active.add(ref)
        for dependency in sorted(registry[ref]["dependencies"], key=lambda x: x["ref"]):
            target = dependency["ref"]
            if target not in registry:
                raise Problem("unresolved_dependency", target)
            if digest(registry[target]) != dependency["sha256"]:
                raise Problem("dependency_hash_mismatch", target)
            visit(target)
        active.remove(ref)
        seen.add(ref)
        ordered.append(registry[ref])

    for root in roots:
        visit(root["ref"])
    return ordered


def _signature(ordered):
    predicates = {}
    definition_count = inclusion_count = 0
    for package in ordered:
        for predicate in package["predicates"]:
            if predicate["ref"] in predicates:
                raise Problem("predicate_owner_conflict", predicate["ref"])
            predicates[predicate["ref"]] = predicate
        definition_count += len(package["definitions"])
        inclusion_count += len(package["inclusions"])
    if len(predicates) > 64 or definition_count > 64 or inclusion_count > 64:
        raise Problem("definition_limit", status="resource_limit")
    for package in ordered:
        for definition in package["definitions"]:
            refs = [definition["symbol"], *(definition.get("all_of") or [definition["parent"]])]
            roles = []
            for ref in refs:
                if ref not in predicates:
                    raise Problem("unresolved_predicate", ref)
                roles.append(predicates[ref]["roles"])
            if any(len(role) != 1 or role != roles[0] for role in roles):
                raise Problem("invalid_definition_roles")
        for inclusion in package["inclusions"]:
            refs = [inclusion["sub"], inclusion["super"]]
            if any(ref not in predicates for ref in refs):
                raise Problem("unresolved_predicate", "inclusion")
            roles = [predicates[ref]["roles"] for ref in refs]
            if len(roles[0]) != 1 or roles[0] != roles[1]:
                raise Problem("invalid_inclusion_roles")
    return predicates


def packages(root, supplied):
    ordered = _closure([root], _registry([root], supplied))
    return ordered, _signature(ordered)


def validate_extension(request):
    base, extension = request["base_package"], request["extension"]
    registry = _registry([base, extension], request.get("dependency_packages", []))
    old = _closure([base], registry)
    # 旧側を単独検証し、追加語彙が旧側の未解決参照を埋めることを防ぐ。
    old_signature = _signature(old)
    combined = _closure([base, extension], registry)
    _signature(combined)
    return old, combined, old_signature


def _atom(value, predicates, pattern=False):
    fields(value, ("predicate", "args"), path="atom")
    string(value["predicate"], "atom.predicate")
    if value["predicate"] not in predicates:
        raise Problem("undeclared_predicate", "atom.predicate")
    args = values(value["args"], 8, "atom.args")
    if len(args) != len(predicates[value["predicate"]]["roles"]):
        raise Problem("arity_mismatch", "atom.args")
    variables = set()
    for term in args:
        if pattern and type(term) is dict:
            fields(term, ("var",), path="variable")
            string(term["var"], "variable.var")
            variables.add(term["var"])
        else:
            string(term, "atom.args")
    return variables


def _contexts(items):
    contexts = indexed(items, "ref", 1000, "contexts")
    for context in contexts.values():
        fields(context, ("ref", "subject_ref", "effective_at", "purpose"))
        for key in ("subject_ref", "purpose"):
            string(context[key], "context." + key)
        timestamp(context["effective_at"], "context.effective_at")
    return contexts


def validate_query(request):
    fields(request, ("schema_version", "operation", "package", "contexts", "ledger", "views", "queries", "budget"), ("dependency_packages",))
    ordered, predicates = packages(request["package"], request.get("dependency_packages", []))
    contexts = _contexts(request["contexts"])
    ledger = request["ledger"]
    fields(ledger, ("ref", "assertions", "reviews"), path="ledger")
    string(ledger["ref"], "ledger.ref")
    assertions = indexed(ledger["assertions"], "id", 1000, "assertions")
    for assertion in assertions.values():
        fields(assertion, ("id", "context_ref", "atom", "polarity", "certainty", "recorded_at", "origin", "supersedes", "required_capabilities"), ("change_reason",), "assertion")
        if type(assertion["context_ref"]) is not str or assertion["context_ref"] not in contexts:
            raise Problem("unresolved_context", "assertion.context_ref")
        _atom(assertion["atom"], predicates)
        if assertion["polarity"] not in ("positive", "negative"):
            raise Problem("invalid_polarity")
        if assertion["certainty"] not in ("confirmed", "suspected"):
            raise Problem("invalid_certainty")
        timestamp(assertion["recorded_at"], "assertion.recorded_at")
        fields(assertion["origin"], ("kind", "ref"), path="origin")
        if assertion["origin"]["kind"] not in ("observed", "judgment", "imported", "ai_candidate"):
            raise Problem("invalid_origin")
        string(assertion["origin"]["ref"], "origin.ref")
        strings(assertion["supersedes"], 1000, "assertion.supersedes")
        strings(assertion["required_capabilities"], 64, "assertion.required_capabilities")
        if assertion["supersedes"] or "change_reason" in assertion:
            string(assertion.get("change_reason"), "assertion.change_reason")
    for assertion in assertions.values():
        for target in assertion["supersedes"]:
            if target not in assertions:
                raise Problem("unresolved_revision", target)
            previous = assertions[target]
            if (previous["context_ref"] != assertion["context_ref"]
                    or previous["atom"] != assertion["atom"]
                    or previous["recorded_at"] >= assertion["recorded_at"]):
                raise Problem("invalid_revision", target)
    reviews = indexed(ledger["reviews"], "id", 1000, "reviews")
    for review in reviews.values():
        fields(review, ("id", "assertion_ref", "reviewer_ref", "reviewer_kind", "recorded_at", "outcome"))
        if type(review["assertion_ref"]) is not str or review["assertion_ref"] not in assertions:
            raise Problem("unresolved_assertion", "review.assertion_ref")
        string(review["reviewer_ref"], "review.reviewer_ref")
        if review["reviewer_kind"] != "human" or review["outcome"] != "confirmed":
            raise Problem("invalid_review")
        timestamp(review["recorded_at"], "review.recorded_at")
        # 確認は対象が台帳に記録された後にしか存在できない（等しい時刻は許す）。
        if review["recorded_at"] < assertions[review["assertion_ref"]]["recorded_at"]:
            raise Problem("review_precedes_assertion", "review.recorded_at")
    views = indexed(request["views"], "id", 64, "views")
    for view in views.values():
        fields(view, ("id", "as_of", "policy_ref"))
        timestamp(view["as_of"], "view.as_of")
        if view["policy_ref"] != POLICY:
            raise Problem("unsupported_policy", "view.policy_ref", "unsupported_profile")
    queries = indexed(request["queries"], "id", 64, "queries")
    for query in queries.values():
        fields(query, ("id", "context_ref", "atoms", "required"))
        if type(query["context_ref"]) is not str or query["context_ref"] not in contexts:
            raise Problem("unresolved_context", "query.context_ref")
        if type(query["required"]) is not bool:
            raise Problem("expected_boolean", "query.required")
        patterns = values(query["atoms"], 64, "query.atoms")
        if not patterns:
            raise Problem("empty_query")
        variables = set()
        for pattern in patterns:
            variables.update(_atom(pattern, predicates, pattern=True))
        if len(variables) > 4:
            raise Problem("variable_limit", status="resource_limit")
    return ordered


def validate_compare(request):
    before, after = request["before"], request["after"]
    for side in ("before", "after"):
        fields(request[side], ("package", "contexts", "ledger"), path=side)
    # 両側を一つの参照空間で検査するが、理論の閉包・所有者は各側で解決する。
    registry = _registry([before["package"], after["package"]], request.get("dependency_packages", []))
    contexts = {side: _contexts(request[side]["contexts"]) for side in ("before", "after")}
    left, right = contexts["before"], contexts["after"]
    for ref in sorted(set(left) & set(right)):
        if left[ref] != right[ref]:
            raise Problem("context_redefined", ref)
    mapping = {}
    for pair in values(request.get("context_map", []), 1000, "context_map"):
        fields(pair, ("before_ref", "after_ref"), path="context_map")
        for key in ("before_ref", "after_ref"):
            string(pair[key], "context_map." + key)
        source, target = pair["before_ref"], pair["after_ref"]
        if source in mapping:
            raise Problem("duplicate_context_mapping", source)
        if source not in left or target not in right:
            raise Problem("unresolved_context_mapping", source)
        if any(left[source][key] != right[target][key] for key in ("subject_ref", "effective_at", "purpose")):
            raise Problem("context_mismatch", source)
        mapping[source] = target
    resolved = {ref: mapping.get(ref, ref) for ref in left if mapping.get(ref, ref) in right}
    if len(set(resolved.values())) != len(resolved):
        raise Problem("noninjective_context_mapping", "context_map")
    inputs, closures = {}, {}
    for side in ("before", "after"):
        queries = request["queries"]
        if side == "after":
            # before 側で全 query の構文検証を完了してから複製する。
            queries = [{**q, "context_ref": mapping.get(q["context_ref"], q["context_ref"])} for q in queries]
        side_input = {"schema_version": request["schema_version"], "operation": "query",
                      **request[side], "views": [request["view"]], "queries": queries,
                      "dependency_packages": list(registry.values()), "budget": request["budget"]}
        try:
            closures[side] = validate_query(side_input)
        except Problem as problem:
            raise Problem(problem.code, side + "." + problem.path, problem.status) from problem
        inputs[side] = side_input
    if before["ledger"]["ref"] == after["ledger"]["ref"] and digest(before["ledger"]) != digest(after["ledger"]):
        raise Problem("ledger_reference_redefined", before["ledger"]["ref"])
    # 同じ述語参照の役割・明示定義は左右で不変。一般包含の版更新とは分ける。
    meanings, union = {}, {}
    for side in ("before", "after"):
        for package in closures[side]:
            union[package["ref"]] = package
            definitions = {d["symbol"]: d for d in package["definitions"]}
            for predicate in package["predicates"]:
                descriptor = (predicate, definitions.get(predicate["ref"]))
                ref = predicate["ref"]
                if ref in meanings and meanings[ref] != descriptor:
                    raise Problem("predicate_redefined", ref)
                meanings[ref] = descriptor
    if (len(meanings) > 64 or sum(len(p["definitions"]) for p in union.values()) > 64
            or sum(len(p["inclusions"]) for p in union.values()) > 64):
        raise Problem("definition_limit", status="resource_limit")
    return inputs, closures


def validate_header(request):
    if type(request) is not dict:
        raise Problem("expected_object")
    if request.get("schema_version") != "p0-request-draft-1":
        raise Problem("unsupported_schema_version")
    if request.get("operation") not in ("query", "check_extension", "compare"):
        raise Problem("unknown_operation")
    required = {
        "query": ("package", "contexts", "ledger", "views", "queries"),
        "check_extension": ("base_package", "extension"),
        "compare": ("before", "after", "view", "queries"),
    }[request["operation"]]
    optional = ("dependency_packages", "context_map") if request["operation"] == "compare" else ("dependency_packages",)
    fields(request, ("schema_version", "operation", "budget", *required), optional)
    fields(request.get("budget"), ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")
