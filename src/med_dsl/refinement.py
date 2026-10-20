"""確認済みの期間不明記録の精密化。意味は P2-e（temporal.py）を継承するが、実装は共有しない。旧 P0・P2-e の経路は変更しない。"""

from copy import deepcopy
import hashlib
from pathlib import Path

from .model import Budget, PROFILE, Problem
from .validation import _atom, _contexts, _package, digest, fields, indexed, string, strings, timestamp

REFINEMENT_PROFILE = "p2-validity-refinement-draft-1"
REFINEMENT_POLICY = "fiction:confirmed-validity-refinement@1"
SPEC_SHA256 = "66ff3f35cfee608b7a2dd7ff7d77a7ddb2506a17dafc5eaff705470b3644e124"
OPERATION = "probe_refined_temporal_literal"
ANSWER_KIND = "refined_temporal_literal_probe"
LEDGER_SCHEMA = "p2-refinement-ledger-draft-1"
ASSUMPTIONS = ["explicit_interval_uniformity", "scoped_revision", "validity_refinement"]
CAPABILITIES = {PROFILE, REFINEMENT_PROFILE}


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


def _refinement_validity(value, path):
    """精密化が述べる期間は bounded だけ。不明で不明を精密化しない。"""
    _validity(value, path)
    if value["kind"] != "bounded":
        raise Problem("invalid_refinement_validity", path)


def _digest_field(value, path):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise Problem("invalid_sha256", path)


def _origin(item, path):
    fields(item["origin"], ("kind", "ref"), path=path)
    if item["origin"]["kind"] not in ("observed", "judgment", "imported", "ai_candidate"):
        raise Problem("invalid_origin", path + ".kind")
    string(item["origin"]["ref"], path + ".ref")


def _validate(request):
    fields(request, ("schema_version", "operation", "consumer", "source", "views", "queries", "budget"))
    if request["operation"] != OPERATION:
        _unsupported("unsupported_operation", "operation")
    try:
        actual = hashlib.sha256(Path(__file__).with_name("refinement_spec.json").read_bytes()).hexdigest()
    except OSError as error:
        raise Problem("native_spec_unavailable", "native_spec") from error
    if actual != SPEC_SHA256:
        raise Problem("native_spec_mismatch", "native_spec")
    consumer = request["consumer"]
    fields(consumer, ("profile", "profile_spec_sha256", "operations"), path="consumer")
    if consumer["profile"] != REFINEMENT_PROFILE:
        _unsupported("unsupported_profile", "consumer.profile")
    pin = consumer["profile_spec_sha256"]
    _digest_field(pin, "consumer.profile_spec_sha256")
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
        _unsupported("unsupported_refinement_package", "source.package")
    contexts = _contexts(source["contexts"])
    if len(contexts) != 1:
        _unsupported("unsupported_refinement_contexts", "source.contexts")
    context_ref, context = next(iter(contexts.items()))
    predicate = package["predicates"][0]
    predicates = {predicate["ref"]: predicate}
    expected_atom = {"predicate": predicate["ref"], "args": [context["subject_ref"]]}

    ledger = source["ledger"]
    fields(ledger, ("schema_version", "ref", "assertions", "reviews", "refinements", "refinement_reviews"), path="source.ledger")
    if ledger["schema_version"] != LEDGER_SCHEMA:
        _unsupported("unsupported_refinement_ledger", "source.ledger.schema_version")
    string(ledger["ref"], "ledger.ref")
    assertions = indexed(ledger["assertions"], "id", 1000, "assertions")
    for item in assertions.values():
        fields(item, ("id", "context_ref", "atom", "polarity", "certainty", "recorded_at", "origin",
                      "required_capabilities", "validity", "revises"), ("change_reason",), "assertion")
        if item["context_ref"] != context_ref:
            raise Problem("unresolved_context", "assertion.context_ref")
        _atom(item["atom"], predicates)
        if item["atom"] != expected_atom:
            raise Problem("refinement_atom_mismatch", "assertion.atom")
        if item["polarity"] not in ("positive", "negative"):
            raise Problem("invalid_polarity", "assertion.polarity")
        if item["certainty"] not in ("confirmed", "suspected"):
            raise Problem("invalid_certainty", "assertion.certainty")
        timestamp(item["recorded_at"], "assertion.recorded_at")
        _origin(item, "assertion.origin")
        strings(item["required_capabilities"], 64, "assertion.required_capabilities")
        if REFINEMENT_PROFILE not in item["required_capabilities"]:
            raise Problem("missing_refinement_capability", "assertion.required_capabilities")
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
            if current["kind"] != "bounded":
                _unsupported("unsupported_revision_scope", "assertion.revises")
            # 対象が bounded なら静的に包含を検査する。対象が unknown / unspecified なら、参照時点ごとに精密化された区間へ検査する
            if old["kind"] == "bounded" and not (old["start"] <= current["start"] and current["end"] <= old["end"]):
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

    refinements = indexed(ledger["refinements"], "id", 1000, "refinements")
    for item in refinements.values():
        fields(item, ("id", "assertion_ref", "target_sha256", "validity", "certainty", "recorded_at", "origin",
                      "required_capabilities", "change_reason"), path="refinement")
        _refinement_validity(item["validity"], "refinement.validity")
        if item["certainty"] not in ("confirmed", "suspected"):
            raise Problem("invalid_certainty", "refinement.certainty")
        timestamp(item["recorded_at"], "refinement.recorded_at")
        _origin(item, "refinement.origin")
        strings(item["required_capabilities"], 64, "refinement.required_capabilities")
        if REFINEMENT_PROFILE not in item["required_capabilities"]:
            raise Problem("missing_refinement_capability", "refinement.required_capabilities")
        string(item["change_reason"], "refinement.change_reason")
        _digest_field(item["target_sha256"], "refinement.target_sha256")
        ref = item["assertion_ref"]
        if type(ref) is not str or ref not in assertions:
            raise Problem("unresolved_assertion", "refinement.assertion_ref")
        target = assertions[ref]
        if target["validity"]["kind"] == "bounded":
            raise Problem("refinement_target_not_unresolved", "refinement.assertion_ref")
        if item["recorded_at"] <= target["recorded_at"]:
            raise Problem("refinement_not_after_target", "refinement.recorded_at")
        if item["target_sha256"] != digest(target):
            raise Problem("refinement_target_hash_mismatch", "refinement.target_sha256")

    refinement_reviews = indexed(ledger["refinement_reviews"], "id", 1000, "refinement_reviews")
    for item in refinement_reviews.values():
        fields(item, ("id", "refinement_ref", "refinement_sha256", "reviewer_ref", "reviewer_kind", "recorded_at", "outcome"),
               path="refinement_review")
        ref = item["refinement_ref"]
        if type(ref) is not str or ref not in refinements:
            raise Problem("unresolved_refinement", "refinement_review.refinement_ref")
        _digest_field(item["refinement_sha256"], "refinement_review.refinement_sha256")
        if item["refinement_sha256"] != digest(refinements[ref]):
            raise Problem("refinement_review_hash_mismatch", "refinement_review.refinement_sha256")
        string(item["reviewer_ref"], "refinement_review.reviewer_ref")
        if item["reviewer_kind"] != "human" or item["outcome"] != "confirmed":
            raise Problem("invalid_review", "refinement_review")
        timestamp(item["recorded_at"], "refinement_review.recorded_at")
        if item["recorded_at"] < refinements[ref]["recorded_at"]:
            raise Problem("review_precedes_refinement", "refinement_review.recorded_at")

    views = indexed(request["views"], "id", 64, "views")
    queries = indexed(request["queries"], "id", 64, "queries")
    if not views or not queries:
        raise Problem("empty_collection", "views/queries")
    for view in views.values():
        fields(view, ("id", "as_of", "policy_ref"), path="view")
        timestamp(view["as_of"], "view.as_of")
        if view["policy_ref"] != REFINEMENT_POLICY:
            _unsupported("unsupported_policy", "view.policy_ref")
    for query in queries.values():
        fields(query, ("id", "context_ref", "atom", "target_at"), path="query")
        if query["context_ref"] != context_ref:
            raise Problem("unresolved_context", "query.context_ref")
        _atom(query["atom"], predicates)
        if query["atom"] != expected_atom:
            raise Problem("refinement_atom_mismatch", "query.atom")
        timestamp(query["target_at"], "query.target_at")
    return assertions, reviews, refinements, refinement_reviews, views, queries


def _select(assertions, reviews, refinements, refinement_reviews, as_of):
    """記録・精密化と、それぞれの人の確認の可視性だけを選ぶ。"""
    visible = {key: a for key, a in assertions.items() if a["recorded_at"] <= as_of}
    confirmations = {}
    for r in reviews.values():
        if r["assertion_ref"] in visible and r["recorded_at"] <= as_of:
            confirmations.setdefault(r["assertion_ref"], []).append(r["id"])
    eligible = {key for key, a in visible.items() if a["certainty"] == "confirmed" and key in confirmations}
    seen = {key: f for key, f in refinements.items() if f["recorded_at"] <= as_of}
    refinement_confirmations = {}
    for r in refinement_reviews.values():
        if r["refinement_ref"] in seen and r["recorded_at"] <= as_of:
            refinement_confirmations.setdefault(r["refinement_ref"], []).append(r["id"])
    effective = {key for key, f in seen.items() if f["certainty"] == "confirmed" and key in refinement_confirmations}
    return (visible, {key: sorted(refs) for key, refs in confirmations.items()}, eligible,
            seen, {key: sorted(refs) for key, refs in refinement_confirmations.items()}, effective)


def _interval(validity):
    return (validity["start"], validity["end"])


def _probe(visible, confirmations, eligible, seen, refinement_confirmations, effective, target):
    unknown_assertions = {key: set(a["required_capabilities"]) - CAPABILITIES for key, a in visible.items()}
    unknown_refinements = {key: set(f["required_capabilities"]) - CAPABILITIES for key, f in seen.items()}
    blocking_assertions = sorted(key for key, caps in unknown_assertions.items() if caps)
    blocking_refinements = sorted(key for key, caps in unknown_refinements.items() if caps)
    if blocking_assertions or blocking_refinements:
        missing = set().union(*unknown_assertions.values(), *unknown_refinements.values())
        return {"reason_codes": ["unknown_capability"], "missing_capabilities": sorted(missing),
                "blocking_assertion_refs": blocking_assertions, "blocking_refinement_refs": blocking_refinements}
    pending = sorted(set(seen) - effective)
    groups = {}
    for key in effective:
        f = seen[key]
        groups.setdefault(f["assertion_ref"], {}).setdefault(_interval(f["validity"]), []).append(key)

    def unresolved(key):
        return visible[key]["validity"]["kind"] != "bounded"

    blockers = {}
    for key in sorted(eligible):
        if unresolved(key) and len(groups.get(key, {})) != 1:
            blockers[key] = "validity_refinement_conflict" if groups.get(key) else "validity_" + visible[key]["validity"]["kind"]
    if blockers:
        requests = []
        for key in sorted(blockers):
            if blockers[key] == "validity_refinement_conflict":
                requests.append({"kind": blockers[key], "assertion_ref": key,
                                 "refinement_refs": sorted(ref for refs in groups[key].values() for ref in refs),
                                 "resolution_supported": False})
            else:
                requests.append({"kind": blockers[key], "assertion_ref": key,
                                 "requires": ["bounded_validity", "evidence", "human_confirmation"], "resolution_supported": True,
                                 "pending_refinement_refs": [ref for ref in pending if seen[ref]["assertion_ref"] == key]})
        return {"reason_codes": sorted(set(blockers.values())), "blocking_assertion_refs": sorted(blockers),
                "information_requests": requests, "pending_refinement_refs": pending}
    outside = []
    for key, a in sorted(visible.items()):
        for other in sorted(a["revises"]):
            if unresolved(other) and len(groups.get(other, {})) == 1:
                (start, end), = groups[other]
                if not (start <= a["validity"]["start"] and a["validity"]["end"] <= end):
                    outside.append({"reviser_ref": key, "target_ref": other,
                                    "refinement_refs": sorted(next(iter(groups[other].values())))})
    if outside:
        return {"reason_codes": ["revision_outside_refined_validity"], "revision_conflicts": outside, "pending_refinement_refs": pending}

    def effective_validity(key):
        a = visible[key]
        if not unresolved(key):
            return a["validity"]
        (start, end), = groups[key]
        return {"kind": "bounded", "start": start, "end": end}

    applicable = {key for key in eligible
                  if effective_validity(key)["start"] <= target < effective_validity(key)["end"]}
    edges = [(key, other) for key in sorted(applicable) for other in sorted(visible[key]["revises"])]
    masked = {other for _, other in edges}
    adopted = applicable - masked
    positive = sorted(key for key in adopted if visible[key]["polarity"] == "positive")
    negative = sorted(adopted - set(positive))
    state = ("both" if negative else "positive_only") if positive else ("negative_only" if negative else "neither")
    refined = [key for key in sorted(eligible) if unresolved(key)]
    return {"status": "ok", "literal_state": state, "reason_codes": [],
            "positive_assertion_refs": positive, "negative_assertion_refs": negative,
            "masked_assertion_refs": sorted(masked), "assumptions": list(ASSUMPTIONS),
            "assertion_evidence": [{"assertion_ref": key, "polarity": visible[key]["polarity"],
                                    "validity": deepcopy(effective_validity(key)), "declared_validity": deepcopy(visible[key]["validity"]),
                                    "review_refs": confirmations[key]} for key in sorted(adopted)],
            "revision_evidence": [{"assertion_ref": key, "target_ref": other, "review_refs": confirmations[key]} for key, other in edges],
            "refinement_evidence": [{"assertion_ref": key, "validity": deepcopy(effective_validity(key)),
                                     "refinements": [{"refinement_ref": ref, "review_refs": refinement_confirmations[ref]}
                                                     for ref in sorted(next(iter(groups[key].values())))]} for key in refined],
            "pending_refinement_refs": pending}


def run_refinement(request):
    assertions, reviews, refinements, refinement_reviews, views, queries = _validate(request)
    budget = Budget(request["budget"]["max_steps"])
    rows = [{"view": v, "query": q, "as_of": views[v]["as_of"], "target_at": queries[q]["target_at"],
             "context_ref": queries[q]["context_ref"], "policy_ref": REFINEMENT_POLICY,
             "status": "unassessed", "literal_state": None, "positive_assertion_refs": None,
             "negative_assertion_refs": None, "masked_assertion_refs": None, "assertion_evidence": None,
             "revision_evidence": None, "refinement_evidence": None, "pending_refinement_refs": None, "assumptions": [],
             "information_requests": [], "reason_codes": ["step_limit"]} for v in sorted(views) for q in sorted(queries)]
    result = {"status": "ok", "meaning_mode": ANSWER_KIND, "converted_to_base": False, "clinical_assertions_added": [],
              "certificate": {"status": "not_certified", "evidence_level": "known_policy_change",
                              "reason_codes": ["validity_refinement_policy"], "scope": None},
              "retained_assertions": sorted(assertions), "retained_reviews": sorted(reviews),
              "retained_refinements": sorted(refinements), "retained_refinement_reviews": sorted(refinement_reviews),
              "views": [], "results": rows, "reason_codes": []}
    row_index = 0
    try:
        budget.tick()
        for view in sorted(views):
            for _ in range(len(assertions) + len(reviews) + len(refinements) + len(refinement_reviews)):
                budget.tick()
            visible, confirmations, eligible, seen, refinement_confirmations, effective = _select(
                assertions, reviews, refinements, refinement_reviews, views[view]["as_of"])
            result["views"].append({"id": view, "as_of": views[view]["as_of"], "visible_assertions": sorted(visible),
                                    "eligible_assertions": sorted(eligible), "pending_assertions": sorted(set(visible) - eligible),
                                    "visible_refinements": sorted(seen), "eligible_refinements": sorted(effective),
                                    "pending_refinements": sorted(set(seen) - effective)})
            for query in sorted(queries):
                budget.tick()
                for _ in visible:
                    budget.tick()
                for _ in seen:
                    budget.tick()
                for key in eligible:
                    for _ in assertions[key]["revises"]:
                        budget.tick()
                value = _probe(visible, confirmations, eligible, seen, refinement_confirmations, effective, queries[query]["target_at"])
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
