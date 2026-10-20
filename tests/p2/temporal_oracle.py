"""時間意味の参照計算。日時を数値へ変換し、各主張の区間から全適格訂正区間を差し引く。

runtimeの点選択・validator・定数・関数を呼ばない。妥当な初回断片に対する意味計算だけを扱う。
"""

from datetime import datetime

CAPABILITIES = {"p0-positive-1", "p2-temporal-assertion-draft-1"}


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


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
    unknown = [a["id"] for a in visible if any(cap not in CAPABILITIES for cap in a["required_capabilities"])]
    if unknown:
        return {"literal_state": None, "positive_assertion_refs": None, "negative_assertion_refs": None,
                "masked_assertion_refs": None, "reason_codes": ["unknown_capability"]}
    missing = {"validity_" + a["validity"]["kind"] for a in eligible if a["validity"]["kind"] != "bounded"}
    if missing:
        return {"literal_state": None, "positive_assertion_refs": None, "negative_assertion_refs": None,
                "masked_assertion_refs": None, "reason_codes": sorted(missing)}
    intervals = {a["id"]: (instant(a["validity"]["start"]), instant(a["validity"]["end"])) for a in eligible}
    positive, negative, masked = [], [], set()
    for correction in eligible:
        lo, hi = intervals[correction["id"]]
        if lo <= t < hi:
            masked.update(correction["revises"])
    for a in eligible:
        pieces = [intervals[a["id"]]]
        for correction in eligible:
            if a["id"] in correction["revises"]:
                pieces = subtract(pieces, intervals[correction["id"]])
        if any(lo <= t < hi for lo, hi in pieces):
            (positive if a["polarity"] == "positive" else negative).append(a["id"])
    state = {(False, False): "neither", (True, False): "positive_only", (False, True): "negative_only", (True, True): "both"}
    return {"literal_state": state[bool(positive), bool(negative)], "positive_assertion_refs": sorted(positive),
            "negative_assertion_refs": sorted(negative), "masked_assertion_refs": sorted(masked), "reason_codes": []}
