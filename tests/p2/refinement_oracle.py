"""期間不明記録の精密化の参照計算。日時を数値へ変換し、精密化から各記録の有効な期間を数え、区間の差引きで除去を求める。

runtimeの選択・validator・定数・関数を呼ばない。妥当な初回断片に対する意味計算だけを扱う。
"""

from datetime import datetime

CAPABILITIES = {"p0-positive-1", "p2-validity-refinement-draft-1"}
STOPPED = {"literal_state": None, "positive_assertion_refs": None, "negative_assertion_refs": None, "masked_assertion_refs": None}


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def span(validity):
    return (instant(validity["start"]), instant(validity["end"]))


def subtract(pieces, cut):
    result = []
    lo, hi = cut
    for start, end in pieces:
        if end <= lo or hi <= start:
            result.append((start, end))
        else:
            if start < lo:
                result.append((start, lo))
            if hi < end:
                result.append((hi, end))
    return result


def answer(request, view, query):
    ledger = request["source"]["ledger"]
    k, t = instant(view["as_of"]), instant(query["target_at"])
    visible = [a for a in ledger["assertions"] if instant(a["recorded_at"]) <= k]
    reviewed = {r["assertion_ref"] for r in ledger["reviews"] if instant(r["recorded_at"]) <= k}
    eligible = [a for a in visible if a["certainty"] == "confirmed" and a["id"] in reviewed]
    seen = [f for f in ledger["refinements"] if instant(f["recorded_at"]) <= k]
    confirmed = {r["refinement_ref"] for r in ledger["refinement_reviews"] if instant(r["recorded_at"]) <= k}
    live = [f for f in seen if f["certainty"] == "confirmed" and f["id"] in confirmed]

    if any(cap not in CAPABILITIES for item in visible + seen for cap in item["required_capabilities"]):
        return {**STOPPED, "reason_codes": ["unknown_capability"]}

    def windows(a):
        return {span(f["validity"]) for f in live if f["assertion_ref"] == a["id"]}

    reasons = set()
    for a in eligible:
        if a["validity"]["kind"] == "bounded":
            continue
        found = windows(a)
        if len(found) > 1:
            reasons.add("validity_refinement_conflict")
        elif not found:
            reasons.add("validity_" + a["validity"]["kind"])
    if reasons:
        return {**STOPPED, "reason_codes": sorted(reasons)}

    by_id = {a["id"]: a for a in visible}
    for b in visible:
        for name in b["revises"]:
            target = by_id[name]
            found = windows(target)
            if target["validity"]["kind"] != "bounded" and len(found) == 1:
                (lo, hi), = found
                start, end = span(b["validity"])
                if not (lo <= start and end <= hi):
                    return {**STOPPED, "reason_codes": ["revision_outside_refined_validity"]}

    def own(a):
        return span(a["validity"]) if a["validity"]["kind"] == "bounded" else next(iter(windows(a)))

    masked = set()
    for correction in eligible:
        lo, hi = own(correction)
        if lo <= t < hi:
            masked.update(correction["revises"])
    positive, negative = [], []
    for a in eligible:
        pieces = [own(a)]
        for correction in eligible:
            if a["id"] in correction["revises"]:
                pieces = subtract(pieces, own(correction))
        if any(lo <= t < hi for lo, hi in pieces):
            (positive if a["polarity"] == "positive" else negative).append(a["id"])
    state = {(False, False): "neither", (True, False): "positive_only", (False, True): "negative_only", (True, True): "both"}
    return {"literal_state": state[bool(positive), bool(negative)], "positive_assertion_refs": sorted(positive),
            "negative_assertion_refs": sorted(negative), "masked_assertion_refs": sorted(masked), "reason_codes": []}
