#!/usr/bin/env python3
"""文書50/51の手指定期待を実行例へ展開する。runtimeを呼ばず、出力から期待を生成しない。
hash（target_sha256・refinement_sha256）だけは、台帳の内容から計算する標準の正規化 SHA-256 を使う。"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "src"))
from med_dsl.validation import digest  # noqa: E402

DIRECTORY = ROOT / "examples/p2-refinement"
PROFILE = "p2-validity-refinement-draft-1"
POLICY = "fiction:confirmed-validity-refinement@1"
SPEC = hashlib.sha256((ROOT / "src/med_dsl/refinement_spec.json").read_bytes()).hexdigest()
ATOM = {"predicate": "fiction:refinement:P@1", "args": ["fiction:refinement:u"]}
CONTEXT = "fiction:refinement:context@1"
UNKNOWN = "fiction:unknown-capability"
STEPS = ["bounded_validity", "evidence", "human_confirmation"]


def day(n):
    return f"2026-10-{n:02}T00:00:00Z"


def interval(start, end):
    return {"kind": "bounded", "start": day(start), "end": day(end)}


def assertion(name, polarity="positive", validity="unknown", rec=2, review=2, revises=(), certainty="confirmed", origin="observed"):
    if isinstance(validity, tuple):
        validity = interval(*validity)
    elif isinstance(validity, str):
        validity = {"kind": validity}
    a = {"id": name, "context_ref": CONTEXT, "atom": deepcopy(ATOM), "polarity": polarity, "certainty": certainty,
         "recorded_at": day(rec), "origin": {"kind": origin, "ref": f"fiction:refinement:source:{name}"},
         "required_capabilities": ["p0-positive-1", PROFILE], "validity": validity, "revises": list(revises)}
    if revises:
        a["change_reason"] = "架空の期間限定の訂正"
    r = [] if review is None else [{"id": "review-" + name, "assertion_ref": name, "reviewer_ref": "fiction:refinement:human",
                                    "reviewer_kind": "human", "recorded_at": day(review), "outcome": "confirmed"}]
    return a, r


def refinement(name, target, window=(10, 20), rec=5, review=6, certainty="confirmed", origin="observed", target_object=None):
    """精密化とその確認。target は assertion() の対（または対象の JSON）。"""
    object_ = target_object if target_object is not None else target[0]
    f = {"id": name, "assertion_ref": object_["id"], "target_sha256": digest(object_), "validity": interval(*window),
         "certainty": certainty, "recorded_at": day(rec), "origin": {"kind": origin, "ref": f"fiction:refinement:source:{name}"},
         "required_capabilities": ["p0-positive-1", PROFILE], "change_reason": "架空の期間の追加"}
    r = [] if review is None else [seal(f, "FR" + name[1:], review)]
    return f, r


def seal(f, name, rec):
    return {"id": name, "refinement_ref": f["id"], "refinement_sha256": digest(f), "reviewer_ref": "fiction:refinement:human",
            "reviewer_kind": "human", "recorded_at": day(rec), "outcome": "confirmed"}


def request(records=(), refinements=(), views=((9, "v"),), queries=((15, "q"),), budget=100000):
    return {"schema_version": "p2-refinement-request-draft-1", "operation": "probe_refined_temporal_literal",
            "consumer": {"profile": PROFILE, "profile_spec_sha256": SPEC, "operations": ["probe_refined_temporal_literal"]},
            "source": {"package": {"ref": "fiction:refinement:package@1", "profile": "p0-positive-1",
                                   "predicates": [{"ref": ATOM["predicate"], "roles": ["subject"]}],
                                   "definitions": [], "inclusions": [], "dependencies": []},
                       "contexts": [{"ref": CONTEXT, "subject_ref": ATOM["args"][0], "effective_at": day(1), "purpose": "fiction:research"}],
                       "ledger": {"schema_version": "p2-refinement-ledger-draft-1", "ref": "fiction:refinement:ledger@1",
                                  "assertions": [deepcopy(a) for a, _ in records],
                                  "reviews": [deepcopy(r) for _, rs in records for r in rs],
                                  "refinements": [deepcopy(f) for f, _ in refinements],
                                  "refinement_reviews": [deepcopy(r) for _, rs in refinements for r in rs]}},
            "views": [{"id": name, "as_of": day(k), "policy_ref": POLICY} for k, name in views],
            "queries": [{"id": name, "context_ref": CONTEXT, "atom": deepcopy(ATOM), "target_at": day(t)} for t, name in queries],
            "budget": {"max_steps": budget}}


def check(path, value):
    return {"path": path, "equals": value}


def row(index, state, pos=(), neg=(), masked=(), reasons=(), **extra):
    """1行の期待。state が None なら阻害または停止（値なし）。extra は追加の欄（pending など）。"""
    prefix = ["results", index]
    stopped = state is None
    checks = [check(prefix + ["status"], "unassessed" if stopped else "ok"), check(prefix + ["literal_state"], state),
              check(prefix + ["reason_codes"], list(reasons)),
              check(prefix + ["positive_assertion_refs"], None if stopped else list(pos)),
              check(prefix + ["negative_assertion_refs"], None if stopped else list(neg)),
              check(prefix + ["masked_assertion_refs"], None if stopped else list(masked))]
    for key, value in extra.items():
        checks.append(check(prefix + [key], value))
    return checks


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = []

    def emit(name, condition, req, checks, base=True):
        if base:
            checks = checks + [check(["meaning_mode"], "refined_temporal_literal_probe"), check(["converted_to_base"], False),
                               check(["clinical_assertions_added"], []), check(["certificate", "status"], "not_certified"),
                               check(["retained_assertions"], sorted(a["id"] for a in req["source"]["ledger"]["assertions"])),
                               check(["retained_refinements"], sorted(f["id"] for f in req["source"]["ledger"]["refinements"])),
                               check(["retained_refinement_reviews"], sorted(r["id"] for r in req["source"]["ledger"]["refinement_reviews"]))]
        value = {"schema_version": "p1-fixture-draft-1", "fixture_version": 1, "fixture_id": name, "condition": condition,
                 "fictional": True, "review_state": "author_draft", "request": req,
                 "expected": {"comparison": "required_paths", "checks": checks}}
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
        filename = name.lower() + ".json"
        (DIRECTORY / filename).write_bytes(raw)
        entries.append({"fixture_id": name, "condition": condition, "path": filename, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest()})

    def ok(name, req, *rows, **top):
        emit(name, name[:3], req, [check(["status"], "ok"), *[c for r in rows for c in r]])

    def refinement_evidence(window, *pairs, assertion_ref="A"):
        return {"assertion_ref": assertion_ref, "validity": interval(*window),
                "refinements": [{"refinement_ref": f, "review_refs": list(rs)} for f, rs in pairs]}

    A = assertion("A")
    F1 = refinement("F1", A)
    U02 = request([A], [F1])

    # U01 〜 U04
    ok("U01", request([A]), row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=[]),
       [check(["results", 0, "information_requests"], [{"kind": "validity_unknown", "assertion_ref": "A", "requires": STEPS,
                                                         "resolution_supported": True, "pending_refinement_refs": []}])])
    ok("U02", U02, row(0, "positive_only", ("A",), refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]))],
                       pending_refinement_refs=[]),
       [check(["results", 0, "assertion_evidence"], [{"assertion_ref": "A", "polarity": "positive", "validity": interval(10, 20),
                                                       "declared_validity": {"kind": "unknown"}, "review_refs": ["review-A"]}])])
    ok("U03", request([A], [F1], queries=((20, "q20"), (25, "q25"))), row(0, "neither"), row(1, "neither"))
    ok("U04", request([A], [F1], queries=((9, "q09"), (10, "q10"))), row(0, "neither"), row(1, "positive_only", ("A",)))
    # U05 〜 U07：可視性
    f_late = refinement("F1", A)
    ok("U05", request([A], [f_late], views=((5, "v"),)),
       row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=["F1"]),
       [check(["results", 0, "information_requests", 0, "pending_refinement_refs"], ["F1"])])
    ok("U06", request([A], [f_late], views=((4, "v04"), (5, "v05"), (6, "v06"))),
       row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=[]),
       row(1, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=["F1"]),
       row(2, "positive_only", ("A",), pending_refinement_refs=[]))
    same = refinement("F1", A, rec=5, review=5)
    ok("U07", request([A], [same], views=((5, "v"),)), row(0, "positive_only", ("A",), pending_refinement_refs=[]))
    # U08 〜 U13：競合・同一・効かない精密化
    F2 = refinement("F2", A, (12, 22), 7, 8)
    conflict = [{"kind": "validity_refinement_conflict", "assertion_ref": "A", "refinement_refs": ["F1", "F2"], "resolution_supported": False}]
    ok("U08", request([A], [F1, F2], queries=((15, "q15"), (21, "q21"))),
       *[row(i, None, reasons=("validity_refinement_conflict",), blocking_assertion_refs=["A"], information_requests=conflict) for i in (0, 1)])
    G2 = refinement("F2", A, (12, 22), 5, 6)
    G1 = refinement("F1", A, (10, 20), 7, 8)
    ok("U09", request([A], [G2, G1], queries=((15, "q15"), (21, "q21"))),
       *[row(i, None, reasons=("validity_refinement_conflict",), blocking_assertion_refs=["A"]) for i in (0, 1)],
       [check(["results", 0, "information_requests", 0, "refinement_refs"], ["F1", "F2"]),
        check(["results", 0, "information_requests", 0, "resolution_supported"], False)])
    ok("U10", request([A], [refinement("F1", A, certainty="suspected")]),
       row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=["F1"]))
    ok("U11", request([A], [refinement("F1", A, review=None, origin="ai_candidate")]),
       row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A"], pending_refinement_refs=["F1"]))
    ok("U12", request([A], [F1, refinement("F2", A, (10, 20), 7, 8)]),
       row(0, "positive_only", ("A",), refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]), ("F2", ["FR2"]))],
           pending_refinement_refs=[]))
    ok("U13", request([A], [F1, refinement("F2", A, (12, 22), 7, None)], queries=((15, "q15"), (21, "q21"))),
       row(0, "positive_only", ("A",), refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]))], pending_refinement_refs=["F2"]),
       row(1, "neither", refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]))], pending_refinement_refs=["F2"]))
    # U14 〜 U16：精密化と部分訂正
    B = assertion("B", "negative", (14, 16), 7, 7, ("A",))
    queries3 = ((12, "q12"), (15, "q15"), (18, "q18"))
    edge = [{"assertion_ref": "B", "target_ref": "A", "review_refs": ["review-B"]}]
    ok("U14", request([A, B], [F1], queries=queries3),
       row(0, "positive_only", ("A",), revision_evidence=[]),
       row(1, "negative_only", neg=("B",), masked=("A",), revision_evidence=edge,
           refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]))]),
       row(2, "positive_only", ("A",), revision_evidence=[]))
    late = refinement("F1", A, rec=9, review=9)
    blocked = dict(reasons=("validity_unknown",), blocking_assertion_refs=["A"])
    ok("U15", request([A, B], [late], views=((8, "v08"), (10, "v10")), queries=queries3),
       *[row(i, None, **blocked) for i in (0, 1, 2)],
       row(3, "positive_only", ("A",)), row(4, "negative_only", neg=("B",), masked=("A",), revision_evidence=edge),
       row(5, "positive_only", ("A",)))
    narrow = refinement("F1", A, (10, 12), 8, 8)
    ok("U16", request([A, B], [narrow], views=((7, "v07"), (9, "v09"))),
       row(0, None, **blocked),
       row(1, None, reasons=("revision_outside_refined_validity",),
           revision_conflicts=[{"reviser_ref": "B", "target_ref": "A", "refinement_refs": ["F1"]}]))
    # U17 〜 U19：未知の能力
    capped = refinement("F1", A, review=None)
    capped[0]["required_capabilities"].append(UNKNOWN)
    ok("U17", request([A], [capped]),
       row(0, None, reasons=("unknown_capability",), missing_capabilities=[UNKNOWN], blocking_assertion_refs=[], blocking_refinement_refs=["F1"]))
    X = assertion("X", "negative", (7, 8), 3, None)
    X[0]["required_capabilities"].append(UNKNOWN)
    ok("U18", request([A, X]), row(0, None, reasons=("unknown_capability",), blocking_assertion_refs=["X"], blocking_refinement_refs=[]))
    future = refinement("F3", A, (12, 22), 12, 13)
    future[0]["required_capabilities"].append(UNKNOWN)
    future = (future[0], [seal(future[0], "FR3", 13)])
    ok("U19", request([A], [F1, future]), row(0, "positive_only", ("A",), pending_refinement_refs=[]))
    # U20 〜 U25
    N = assertion("A", "negative")
    ok("U20", request([N], [refinement("F1", N)], queries=((15, "q15"), (25, "q25"))), row(0, "negative_only", neg=("A",)), row(1, "neither"))
    S = assertion("A", validity="unspecified")
    ok("U21A", request([S]), row(0, None, reasons=("validity_unspecified",), blocking_assertion_refs=["A"]),
       [check(["results", 0, "information_requests", 0, "kind"], "validity_unspecified")])
    ok("U21B", request([S], [refinement("F1", S)]), row(0, "positive_only", ("A",)))
    A1, A2 = assertion("A1"), assertion("A2", rec=3, review=3)
    ok("U22", request([A1, A2], [refinement("F1", A1)]), row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A2"],
                                                           refinement_evidence=None, pending_refinement_refs=[]))
    unreviewed = assertion("A", review=None)
    ok("U23", request([unreviewed, assertion("B", validity=(5, 25), rec=3, review=3)], [refinement("F1", unreviewed)]),
       row(0, "positive_only", ("B",), refinement_evidence=[], pending_refinement_refs=[]))
    other = assertion("A2", rec=3, review=3)
    f_other = refinement("F2", other, (10, 12), 5, 6)
    revising = assertion("B", "negative", (14, 16), 7, 7, ("A2",))
    ok("U24", request([A1, other, revising], [f_other]), row(0, None, reasons=("validity_unknown",), blocking_assertion_refs=["A1"]))
    future2 = refinement("F2", A, (12, 22), 12, 13)
    ok("U25", request([A], [F1, future2]), row(0, "positive_only", ("A",),
                                               refinement_evidence=[refinement_evidence((10, 20), ("F1", ["FR1"]))], pending_refinement_refs=[]))

    # N：構造・不正・境界
    def refusal(name, req, status="invalid_input", reason=None):
        checks = [check(["status"], status)]
        if reason:
            checks.append(check(["reason_codes"], [reason]))
        emit(name, name[:3], req, checks, False)

    old = json.loads((ROOT / "examples/p2-temporal/t13.json").read_text(encoding="utf-8"))["request"]
    emit("N01", "N01", old, [check(["status"], "ok"), check(["results", 0, "reason_codes"], ["validity_unknown"]),
                              check(["results", 0, "information_requests", 0, "resolution_supported"], False)], False)

    def modified(change, records=None):
        req = deepcopy(U02)
        change(req["source"]["ledger"])
        return req

    def rebuild(ledger, **changes):
        """精密化を変更した後で、確認の hash を再計算する（誤りを一つに限る）。"""
        f = ledger["refinements"][0]
        ledger["refinement_reviews"][0] = seal(f, "FR1", 6)

    bounded = deepcopy(A)
    bounded[0]["validity"] = interval(1, 30)
    f_bounded = refinement("F1", bounded)
    refusal("N02", request([bounded], [f_bounded]), reason="refinement_target_not_unresolved")
    def absent(ledger):
        ledger["refinements"][0]["assertion_ref"] = "absent"; rebuild(ledger)
    refusal("N03", modified(absent), reason="unresolved_assertion")
    def zero_target(ledger):
        ledger["refinements"][0]["target_sha256"] = "0" * 64; rebuild(ledger)
    refusal("N04", modified(zero_target), reason="refinement_target_hash_mismatch")
    for suffix, rec in (("A", 2), ("B", 1)):
        def at(ledger, rec=rec):
            ledger["refinements"][0]["recorded_at"] = day(rec); rebuild(ledger)
        refusal("N05" + suffix, modified(at), reason="refinement_not_after_target")
    for suffix, kind in (("A", "unknown"), ("B", "unspecified")):
        def unresolved_validity(ledger, kind=kind):
            ledger["refinements"][0]["validity"] = {"kind": kind}; rebuild(ledger)
        refusal("N06" + suffix, modified(unresolved_validity), reason="invalid_refinement_validity")
    for suffix, validity, status, reason in (
            ("A", {"kind": "open_end", "start": day(10)}, "unsupported_profile", "unsupported_validity"),
            ("B", {"kind": "bounded", "start": day(10), "end": day(10)}, "invalid_input", "invalid_validity_interval"),
            ("C", {"kind": "bounded", "start": day(11), "end": day(10)}, "invalid_input", "invalid_validity_interval"),
            ("D", {"kind": "bounded", "start": day(10)}, "invalid_input", None),
            ("E", {"kind": "bounded", "start": "2026-02-30T00:00:00Z", "end": day(20)}, "invalid_input", None)):
        def odd(ledger, validity=validity):
            ledger["refinements"][0]["validity"] = validity; rebuild(ledger)
        refusal("N07" + suffix, modified(odd), status, reason)
    def wrong_review_hash(ledger):
        ledger["refinement_reviews"][0]["refinement_sha256"] = "0" * 64
    refusal("N08", modified(wrong_review_hash), reason="refinement_review_hash_mismatch")
    def refine_the_refinement(ledger):
        second = refinement("F2", A, rec=7, review=None)[0]
        second["assertion_ref"] = "F1"
        ledger["refinements"].append(second)
    refusal("N09", modified(refine_the_refinement), reason="unresolved_assertion")
    for suffix, change in (("A", ("views", "policy_ref")), ("B", ("consumer", "profile")), ("C", ("top", "operation")), ("D", ("consumer", "operations"))):
        req = deepcopy(U02)
        if change[0] == "views":
            req["views"][0]["policy_ref"] = "fiction:confirmed-scoped-revision@1"
        elif change[0] == "consumer" and change[1] == "profile":
            req["consumer"]["profile"] = "unknown"
        elif change[0] == "top":
            req["operation"] = "unknown"
        else:
            req["consumer"]["operations"] = ["unknown"]
        refusal("N10" + suffix, req, "unsupported_profile")
    zero_consumer = deepcopy(U02)
    zero_consumer["consumer"]["profile_spec_sha256"] = "0" * 64
    refusal("N11", zero_consumer, "unsupported_profile", "profile_spec_mismatch")
    schema = deepcopy(U02)
    schema["source"]["ledger"]["schema_version"] = "p2-temporal-ledger-draft-1"
    refusal("N12", schema, "unsupported_profile", "unsupported_refinement_ledger")
    def early_review(ledger):
        ledger["refinement_reviews"][0]["recorded_at"] = day(4)
    refusal("N13", modified(early_review), reason="review_precedes_refinement")
    def stray_review(ledger):
        ledger["refinement_reviews"][0]["refinement_ref"] = "absent"
    refusal("N14", modified(stray_review), reason="unresolved_refinement")
    def no_capability(ledger):
        ledger["refinements"][0]["required_capabilities"] = ["p0-positive-1"]; rebuild(ledger)
    refusal("N15", modified(no_capability), reason="missing_refinement_capability")
    def duplicate(ledger):
        ledger["refinements"].append(deepcopy(ledger["refinements"][0]))
    refusal("N16", modified(duplicate), reason="duplicate_identifier")
    for suffix, key, value in (("A", "reviewer_kind", "ai"), ("B", "outcome", "rejected")):
        def not_human(ledger, key=key, value=value):
            ledger["refinement_reviews"][0][key] = value
        refusal("N17" + suffix, modified(not_human), reason="invalid_review")
    both_unknown = [A, assertion("B", validity="unknown", rec=3, review=3, revises=("A",))]
    refusal("N18", request(both_unknown), "unsupported_profile", "unsupported_revision_scope")
    ok("N19", request([A, B]), row(0, None, **blocked))
    def without_reason(ledger):
        del ledger["refinements"][0]["change_reason"]
    refusal("N20A", modified(without_reason))
    def extra_field(ledger):
        ledger["refinements"][0]["note"] = "余分な項目"
    refusal("N20B", modified(extra_field))

    # B：予算（設計50の§8の式から手で導出）
    u02 = deepcopy(U02)
    for name, maximum, used, complete in (("B01", 0, 0, False), ("B02-below", 8, 8, False), ("B02-exact", 9, 9, True), ("B02-above", 10, 9, True)):
        req = deepcopy(u02); req["budget"]["max_steps"] = maximum
        checks = [check(["status"], "ok" if complete else "resource_limit"), check(["steps_used"], used),
                  *(row(0, "positive_only", ("A",)) if complete else row(0, None, reasons=("step_limit",)))]
        emit(name, name[:3], req, checks)
    revision = request([A, B], [F1], queries=((15, "q15"),))
    for name, maximum, complete in (("B03-below", 12, False), ("B03-exact", 13, True)):
        req = deepcopy(revision); req["budget"]["max_steps"] = maximum
        checks = [check(["status"], "ok" if complete else "resource_limit"), check(["steps_used"], maximum),
                  *(row(0, "negative_only", neg=("B",), masked=("A",)) if complete else row(0, None, reasons=("step_limit",)))]
        emit(name, name[:3], req, checks)
    two = request([A], [F1], queries=((15, "q"), (15, "q2")))
    for maximum in (9, 13):
        req = deepcopy(two); req["budget"]["max_steps"] = maximum
        checks = [check(["status"], "ok" if maximum == 13 else "resource_limit"), check(["steps_used"], maximum),
                  *row(0, "positive_only", ("A",)),
                  *(row(1, "positive_only", ("A",)) if maximum == 13 else row(1, None, reasons=("step_limit",)))]
        emit(f"B04-{maximum}", "B04", req, checks)
    zero_budget = modified(zero_target)
    zero_budget["budget"]["max_steps"] = 0
    refusal("B05", zero_budget, reason="refinement_target_hash_mismatch")

    manifest = {"schema_version": "p2-refinement-manifest-draft-1", "status": "author_draft", "independent_review": False,
                "evaluation_frozen": False, "expectations_source": "docs/research/51-p2-k-cases.md", "profile_spec_sha256": SPEC,
                "conditions": {"U": 25, "N": 20, "B": 5}, "files": entries}
    (DIRECTORY / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(entries), "checks": sum(len(json.loads((DIRECTORY / e["path"]).read_text(encoding="utf-8"))["expected"]["checks"]) for e in entries),
                      "spec_sha256": SPEC}))


if __name__ == "__main__":
    main()
