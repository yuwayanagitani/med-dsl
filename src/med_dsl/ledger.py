"""問い合わせの前提となる、確認・参照時点・明示的訂正の選択。"""

from .model import PROFILE, Proof, atom


def select_view(ledger, view):
    visible = {item["id"]: item for item in ledger["assertions"]
               if item["recorded_at"] <= view["as_of"]}
    reviews = {}
    for review in ledger["reviews"]:
        if review["assertion_ref"] in visible and review["recorded_at"] <= view["as_of"]:
            reviews.setdefault(review["assertion_ref"], set()).add(review["id"])
    eligible = {key for key, item in visible.items()
                if item["certainty"] == "confirmed" and key in reviews}
    # 置換元も後に訂正されても、古い記録を自動復活させない。
    superseded = {target for key in eligible for target in visible[key]["supersedes"]}
    adopted = eligible - superseded
    unknown = {}
    for item in visible.values():
        missing = set(item["required_capabilities"]) - {PROFILE}
        if missing:
            unknown.setdefault(item["context_ref"], set()).update(missing)
    positive, negative = {}, {}
    for key in sorted(adopted):
        item = visible[key]
        table = positive if item["polarity"] == "positive" else negative
        facts = table.setdefault(item["context_ref"], {})
        fact = atom(item["atom"])
        proof = Proof(frozenset({key}), frozenset(reviews[key]))
        facts[fact] = facts.get(fact, Proof()).merge(proof)
    metadata = {"id": view["id"], "visible_assertions": sorted(visible),
                "adopted_assertions": sorted(adopted),
                "pending_assertions": sorted(set(visible) - eligible - superseded),
                "superseded_assertions": sorted(superseded)}
    return metadata, positive, negative, unknown
