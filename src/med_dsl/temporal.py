"""有効期間と参照時点を分ける、R5の方針診断。旧P0の採用経路を変更しない。"""

from copy import deepcopy
import hashlib
from pathlib import Path

from .model import Budget, PROFILE, Problem
from .validation import _atom, _contexts, _package, fields, indexed, string, strings, timestamp

TEMPORAL_PROFILE = "p2-temporal-assertion-draft-1"
TEMPORAL_POLICY = "fiction:confirmed-scoped-revision@1"
SPEC_SHA256 = "f6c5b4d93a887592f1d1e15b4f72ab5e8b51e8f2db0783e91ff7eb333baa7ba0"
OPERATION = "probe_temporal_literal"
ANSWER_KIND = "temporal_literal_probe"
ASSUMPTIONS = ["explicit_interval_uniformity", "scoped_revision"]


def _unsupported(code, path):
    raise Problem(code, path, "unsupported_profile")


def _validity(value, path):
    fields(value, ("kind",), ("start", "end"), path)
    string(value["kind"], path + ".kind")
    kind = value["kind"]
    if kind == "bounded":
        fields(value, ("kind", "start", "end"), path=path)
        timestamp(value["start"], path + ".start")
        timestamp(value["end"], path + ".end")
        if value["start"] >= value["end"]:
            raise Problem("invalid_validity_interval", path)
    elif kind in ("unknown", "unspecified"):
        fields(value, ("kind",), path=path)
    elif kind == "open_end":
        fields(value, ("kind", "start"), path=path)
        timestamp(value["start"], path + ".start")
        _unsupported("unsupported_validity", path)
    else:
        _unsupported("unsupported_validity", path)


def _validate(request):
    fields(request, ("schema_version", "operation", "consumer", "source", "views", "queries", "budget"))
    if request["operation"] != OPERATION:
        _unsupported("unsupported_operation", "operation")
    try:
        actual = hashlib.sha256(Path(__file__).with_name("temporal_spec.json").read_bytes()).hexdigest()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if actual != SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    if consumer["profile"] != TEMPORAL_PROFILE:
        _unsupported("unsupported_profile", "consumer.profile")
    pin = consumer["profile_spec_sha256"]
    if type(pin) is not str or len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin):
        raise Problem("invalid_sha256", "consumer.profile_spec_sha256")
    if pin != SPEC_SHA256:
        _unsupported("profile_spec_mismatch", "consumer.profile_spec_sha256")
    strings(consumer["operations"], 64, "consumer.operations")
    if consumer["operations"] != [OPERATION]:
        _unsupported("unsupported_operation", "consumer.operations")
    fields(request["budget"], ("max_steps",), path="budget")
    maximum = request["budget"]["max_steps"]
    if type(maximum) is not int or maximum < 0:
        raise Problem("invalid_step_budget", "budget.max_steps")
    if maximum > 100000:
        raise Problem("step_budget_limit", "budget.max_steps", "resource_limit")

    source = request["source"]
    fields(source, ("package", "contexts", "ledger"), path="source")
    package = source["package"]
    _package(package)
    if (len(package["predicates"]) != 1 or len(package["predicates"][0]["roles"]) != 1
            or package["definitions"] or package["inclusions"] or package["dependencies"]):
        _unsupported("unsupported_temporal_package", "source.package")
    contexts = _contexts(source["contexts"])
    if len(contexts) != 1:
        _unsupported("unsupported_temporal_contexts", "source.contexts")
    context_ref, context = next(iter(contexts.items()))
    predicate = package["predicates"][0]
    predicates = {predicate["ref"]: predicate}
    expected_atom = {"predicate": predicate["ref"], "args": [context["subject_ref"]]}

    ledger = source["ledger"]
    fields(ledger, ("schema_version", "ref", "assertions", "reviews"), path="source.ledger")
    if ledger["schema_version"] != "p2-temporal-ledger-draft-1":
        _unsupported("unsupported_temporal_ledger", "source.ledger.schema_version")
    string(ledger["ref"], "ledger.ref")
    assertions = indexed(ledger["assertions"], "id", 1000, "assertions")
    for item in assertions.values():
        fields(item, ("id", "context_ref", "atom", "polarity", "certainty", "recorded_at", "origin",
                      "required_capabilities", "validity", "revises"), ("change_reason",), "assertion")
        if item["context_ref"] != context_ref:
            raise Problem("unresolved_context", "assertion.context_ref")
        _atom(item["atom"], predicates)
        if item["atom"] != expected_atom:
            raise Problem("temporal_atom_mismatch", "assertion.atom")
        if item["polarity"] not in ("positive", "negative"):
            raise Problem("invalid_polarity", "assertion.polarity")
        if item["certainty"] not in ("confirmed", "suspected"):
            raise Problem("invalid_certainty", "assertion.certainty")
        timestamp(item["recorded_at"], "assertion.recorded_at")
        fields(item["origin"], ("kind", "ref"), path="assertion.origin")
        if item["origin"]["kind"] not in ("observed", "judgment", "imported", "ai_candidate"):
            raise Problem("invalid_origin", "assertion.origin.kind")
        string(item["origin"]["ref"], "assertion.origin.ref")
        strings(item["required_capabilities"], 64, "assertion.required_capabilities")
        if TEMPORAL_PROFILE not in item["required_capabilities"]:
            raise Problem("missing_temporal_capability", "assertion.required_capabilities")
        _validity(item["validity"], "assertion.validity")
        strings(item["revises"], 1000, "assertion.revises")
        if item["revises"] or "change_reason" in item:
            string(item.get("change_reason"), "assertion.change_reason")
    for item in assertions.values():
        for target in item["revises"]:
            if target not in assertions:
                raise Problem("unresolved_revision", target)
            previous = assertions[target]
            if (item["context_ref"] != previous["context_ref"] or item["atom"] != previous["atom"]
                    or item["recorded_at"] <= previous["recorded_at"]):
                raise Problem("invalid_revision", target)
            current, old = item["validity"], previous["validity"]
            if current["kind"] != "bounded" or old["kind"] != "bounded":
                _unsupported("unsupported_revision_scope", "assertion.revises")
            if not (old["start"] <= current["start"] and current["end"] <= old["end"]):
                raise Problem("invalid_revision_interval", "assertion.revises")

    reviews = indexed(ledger["reviews"], "id", 1000, "reviews")
    for item in reviews.values():
        fields(item, ("id", "assertion_ref", "reviewer_ref", "reviewer_kind", "recorded_at", "outcome"), path="review")
        ref = item["assertion_ref"]
        if type(ref) is not str or ref not in assertions:
            raise Problem("unresolved_assertion", "review.assertion_ref")
        string(item["reviewer_ref"], "review.reviewer_ref")
        if item["reviewer_kind"] != "human" or item["outcome"] != "confirmed":
            raise Problem("invalid_review", "review")
        timestamp(item["recorded_at"], "review.recorded_at")
        if item["recorded_at"] < assertions[ref]["recorded_at"]:
            raise Problem("review_precedes_assertion", "review.recorded_at")
    views = indexed(request["views"], "id", 64, "views")
    queries = indexed(request["queries"], "id", 64, "queries")
    if not views or not queries:
        raise Problem("empty_collection", "views/queries")
    for view in views.values():
        fields(view, ("id", "as_of", "policy_ref"), path="view")
        timestamp(view["as_of"], "view.as_of")
        if view["policy_ref"] != TEMPORAL_POLICY:
            _unsupported("unsupported_policy", "view.policy_ref")
    for query in queries.values():
        fields(query, ("id", "context_ref", "atom", "target_at"), path="query")
        if query["context_ref"] != context_ref:
            raise Problem("unresolved_context", "query.context_ref")
        _atom(query["atom"], predicates)
        if query["atom"] != expected_atom:
            raise Problem("temporal_atom_mismatch", "query.atom")
        timestamp(query["target_at"], "query.target_at")
    return assertions, reviews, views, queries


def _select(assertions, reviews, as_of):
    """記録と人の確認の可視性だけを選ぶ。全体訂正の核は呼ばない。"""
    visible = {key: a for key, a in assertions.items() if a["recorded_at"] <= as_of}
    confirmations = {}
    for r in reviews.values():
        if r["assertion_ref"] in visible and r["recorded_at"] <= as_of:
            confirmations.setdefault(r["assertion_ref"], []).append(r["id"])
    eligible = {key for key, a in visible.items() if a["certainty"] == "confirmed" and key in confirmations}
    return visible, {key: sorted(refs) for key, refs in confirmations.items()}, eligible


def _probe(visible, confirmations, eligible, target):
    unknown = {}
    for key, a in visible.items():
        for cap in set(a["required_capabilities"]) - {PROFILE, TEMPORAL_PROFILE}:
            unknown.setdefault(cap, []).append(key)
    if unknown:
        return {"reason_codes": ["unknown_capability"], "missing_capabilities": sorted(unknown),
                "blocking_assertion_refs": sorted({key for refs in unknown.values() for key in refs})}
    blockers = {key: "validity_" + visible[key]["validity"]["kind"] for key in eligible
                if visible[key]["validity"]["kind"] != "bounded"}
    if blockers:
        return {"reason_codes": sorted(set(blockers.values())), "blocking_assertion_refs": sorted(blockers),
                "information_requests": [{"kind": blockers[key], "assertion_ref": key,
                                           "requires": ["validity", "evidence", "human_confirmation"],
                                           "resolution_supported": False} for key in sorted(blockers)]}
    applicable = {key for key in eligible
                  if visible[key]["validity"]["start"] <= target < visible[key]["validity"]["end"]}
    edges = [(key, other) for key in sorted(applicable) for other in sorted(visible[key]["revises"])]
    masked = {other for _, other in edges}
    adopted = applicable - masked
    positive = sorted(key for key in adopted if visible[key]["polarity"] == "positive")
    negative = sorted(adopted - set(positive))
    state = ("both" if negative else "positive_only") if positive else ("negative_only" if negative else "neither")
    return {"status": "ok", "literal_state": state, "reason_codes": [],
            "positive_assertion_refs": positive, "negative_assertion_refs": negative,
            "masked_assertion_refs": sorted(masked), "assumptions": list(ASSUMPTIONS),
            "assertion_evidence": [{"assertion_ref": key, "polarity": visible[key]["polarity"],
                                    "validity": deepcopy(visible[key]["validity"]), "review_refs": confirmations[key]}
                                   for key in sorted(adopted)],
            "revision_evidence": [{"assertion_ref": key, "target_ref": other, "review_refs": confirmations[key]} for key, other in edges]}


def run_temporal(request):
    assertions, reviews, views, queries = _validate(request)
    budget = Budget(request["budget"]["max_steps"])
    rows = [{"view": v, "query": q, "as_of": views[v]["as_of"], "target_at": queries[q]["target_at"],
             "context_ref": queries[q]["context_ref"], "policy_ref": TEMPORAL_POLICY,
             "status": "unassessed", "literal_state": None, "positive_assertion_refs": None,
             "negative_assertion_refs": None, "masked_assertion_refs": None, "assertion_evidence": None,
             "revision_evidence": None, "assumptions": [], "information_requests": [],
             "reason_codes": ["step_limit"]} for v in sorted(views) for q in sorted(queries)]
    result = {"status": "ok", "meaning_mode": ANSWER_KIND, "converted_to_base": False, "clinical_assertions_added": [],
              "certificate": {"status": "not_certified", "evidence_level": "known_policy_change",
                              "reason_codes": ["scoped_revision_policy"], "scope": None},
              "retained_assertions": sorted(assertions), "retained_reviews": sorted(reviews),
              "views": [], "results": rows, "reason_codes": []}
    row_index = 0
    try:
        budget.tick()
        for view in sorted(views):
            for _ in range(len(assertions) + len(reviews)):
                budget.tick()
            visible, confirmations, eligible = _select(assertions, reviews, views[view]["as_of"])
            result["views"].append({"id": view, "as_of": views[view]["as_of"], "visible_assertions": sorted(visible),
                                    "eligible_assertions": sorted(eligible), "pending_assertions": sorted(set(visible) - eligible)})
            for query in sorted(queries):
                budget.tick()
                for _ in visible:
                    budget.tick()
                for key in eligible:
                    for _ in assertions[key]["revises"]:
                        budget.tick()
                value = _probe(visible, confirmations, eligible, queries[query]["target_at"])
                budget.tick()
                rows[row_index].update(value)
                row_index += 1
    except Problem as problem:
        if problem.status != "resource_limit":
            raise
        result.update(status="resource_limit", reason_codes=[problem.code])
    result["steps_used"] = budget.used
    result["incomplete"] = [{"view": r["view"], "query": r["query"], "reason_codes": r["reason_codes"]}
                            for r in rows if r["status"] == "unassessed"]
    return result
