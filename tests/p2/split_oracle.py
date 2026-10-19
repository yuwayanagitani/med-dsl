"""概念の分割の独立オラクル（P2-b）。実装（split.py）の規則・基底の採用選択（ledger.py）を使わずに、
文書 23 の意味を、個体ごとの k+1 個のモデルの全数列挙と、PO04 の採用の定義から書き直したもの。
"""

import random

POLICY = "fiction:confirmed-explicit-revision@1"
P0_CAPABILITY = "p0-positive-1"
SPLIT_CAPABILITY = "p2-concept-split-draft-1"
OTHER_CAPABILITY = "fiction:other-capability@1"
PARENT = "fiction:P@1"
OTHER = "fiction:X@1"
SUBJECTS = ["fiction:person:1", "fiction:person:2"]
CONTEXTS = ["fiction:c1", "fiction:c2"]
TIMES = ["2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z", "2020-01-03T00:00:00Z", "2020-01-04T00:00:00Z",
         "2020-01-05T00:00:00Z", "2020-01-06T00:00:00Z"]
BASE_STATUSES = {"supported", "opposed", "undetermined", "conflict", "unassessed"}


def parts_of(k):
    return [f"fiction:Q{i}@1" for i in range(1, k + 1)]


def adoption(source, view):
    """PO04：可視 V、確認済み C、訂正された S、採用 A = C − S。"""
    items = {h["id"]: h for h in source["ledger"]["assertions"]}
    visible = {k for k, h in items.items() if h["recorded_at"] <= view["as_of"]}
    reviewed = {r["assertion_ref"] for r in source["ledger"]["reviews"] if r["recorded_at"] <= view["as_of"]}
    confirmed = {k for k in visible if items[k]["certainty"] == "confirmed" and k in reviewed}
    superseded = {t for k in confirmed for t in items[k]["supersedes"]}
    return items, visible, confirmed - superseded


def models(parent, parts, positive, negative):
    """個体一つの、公理を満たす割り当て（すべて偽 None、または親と一つの部分だけ真）のうち、採用された肯定・否定に合うもの。"""
    found = []
    for w in [None, *parts]:
        true = set() if w is None else {parent, w}
        if positive <= true and not (negative & true):
            found.append(w)
    return found


def expected_row(source, view, split, query):
    """行の期待。('blocked', 理由, 詳細) または ('computed', 状態, 候補, 親の導出, 基底の状態)。"""
    parent, parts = split["parent"], sorted(split["parts"])
    vocabulary = [parent, *parts]
    items, visible, adopted = adoption(source, view)
    context, subject = query["context_ref"], query["subject"]
    unknown = sorted(k for k in visible if items[k]["context_ref"] == context
                     and set(items[k]["required_capabilities"]) - {P0_CAPABILITY, SPLIT_CAPABILITY})
    if unknown:
        return ("blocked", "unknown_capability", unknown)
    positive = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in adopted
                if items[k]["context_ref"] == context and items[k]["polarity"] == "positive"}
    negative = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in adopted
                if items[k]["context_ref"] == context and items[k]["polarity"] == "negative"}
    if positive & negative:
        return ("blocked", "unresolved_conflict", None)
    pos = {name for name in vocabulary if (name, (subject,)) in positive}
    neg = {name for name in vocabulary if (name, (subject,)) in negative}
    found = models(parent, parts, pos, neg)
    base = {name: "supported" if name in pos else "opposed" if name in neg else "undetermined" for name in vocabulary}
    if not found:
        return ("computed", "inconsistent", [], False, base)
    if found == [None]:
        return ("computed", "parent_opposed", [], False, base)
    if None in found:
        return ("computed", "no_parent", [], False, base)
    if len(found) == 1:
        status = "asserted" if found[0] in pos else "single"
        return ("computed", status, list(found), parent not in pos, base)
    return ("computed", "open" if len(found) == len(parts) else "narrowed", list(found), False, base)


def generate_dense(rng):
    """一つの個体・一つの文脈に採用された記述を集中させる（稀な状態：single・narrowed・inconsistent などを十分な件数で出す）。"""
    k = rng.randint(2, 3)
    parts = parts_of(k)
    assertions = []
    for i in range(rng.randint(1, 6)):
        draw = rng.random()
        predicate = PARENT if draw < 0.3 else OTHER if draw < 0.35 else rng.choice(parts)
        assertions.append({"id": f"h{i}", "context_ref": CONTEXTS[0], "atom": {"predicate": predicate, "args": [SUBJECTS[0]]},
                           "polarity": "positive" if rng.random() < 0.55 else "negative",
                           "certainty": "confirmed" if rng.random() < 0.95 else "suspected", "recorded_at": rng.choice(TIMES[:2]),
                           "origin": {"kind": rng.choice(["observed", "judgment", "imported", "ai_candidate"]), "ref": f"fiction:source:{i}"},
                           "supersedes": [], "required_capabilities": [SPLIT_CAPABILITY] if rng.random() < 0.3 else []})
    reviews = [{"id": f"r{a['id']}", "assertion_ref": a["id"], "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
                "recorded_at": TIMES[2], "outcome": "confirmed"} for a in assertions if rng.random() < 0.95]
    source = {"package": {"ref": "fiction:package:split@1", "profile": P0_CAPABILITY,
                          "predicates": [{"ref": n, "roles": ["subject"]} for n in [PARENT, *parts_of(4), OTHER]],
                          "definitions": [], "inclusions": [], "dependencies": []},
              "contexts": [{"ref": c, "subject_ref": SUBJECTS[0], "effective_at": "2019-12-01T00:00:00Z", "purpose": "fiction:research"} for c in CONTEXTS],
              "ledger": {"ref": "fiction:ledger:dense@1", "assertions": assertions, "reviews": reviews}}
    views = [{"id": "v0", "as_of": TIMES[5], "policy_ref": POLICY}]
    queries = [{"id": "q0", "context_ref": CONTEXTS[0], "subject": SUBJECTS[0], "required": True}]
    return source, views, {"parent": PARENT, "parts": parts}, queries


def generate(rng, with_parts=True, k=None):
    """妥当な要求の部品。台帳には、肯定・否定、疑い、AI 候補、確認の有無、訂正、能力の要求を混ぜる。"""
    k = k or rng.randint(2, 4)
    parts = parts_of(k)
    names = [PARENT, *(parts if with_parts else []), OTHER]
    contexts = [{"ref": c, "subject_ref": SUBJECTS[0], "effective_at": "2019-12-01T00:00:00Z", "purpose": "fiction:research"} for c in CONTEXTS]
    assertions = []
    for i in range(rng.randint(0, 9)):
        draw = rng.random()
        caps = [] if draw < 0.85 else [SPLIT_CAPABILITY] if draw < 0.95 else [OTHER_CAPABILITY]
        assertions.append({"id": f"h{i}", "context_ref": rng.choice(CONTEXTS), "atom": {"predicate": rng.choice(names), "args": [rng.choice(SUBJECTS)]},
                           "polarity": "positive" if rng.random() < 0.6 else "negative",
                           "certainty": "confirmed" if rng.random() < 0.85 else "suspected", "recorded_at": rng.choice(TIMES[:4]),
                           "origin": {"kind": rng.choice(["observed", "judgment", "imported", "ai_candidate"]), "ref": f"fiction:source:{i}"},
                           "supersedes": [], "required_capabilities": caps})
    for j, later in enumerate(assertions):
        if rng.random() < 0.3:
            earlier = [a for a in assertions[:j] if a["context_ref"] == later["context_ref"] and a["atom"] == later["atom"]
                       and a["recorded_at"] < later["recorded_at"]]
            if earlier:
                later["supersedes"] = [rng.choice(earlier)["id"]]
                later["change_reason"] = "fiction:correction"
    reviews = []
    for a in assertions:
        if rng.random() < 0.7:
            reviews.append({"id": f"r{a['id']}", "assertion_ref": a["id"], "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
                            "recorded_at": rng.choice([t for t in TIMES if t >= a["recorded_at"]]), "outcome": "confirmed"})
    source = {"package": {"ref": "fiction:package:split@1", "profile": P0_CAPABILITY,
                          "predicates": [{"ref": n, "roles": ["subject"]} for n in [PARENT, *parts_of(4), OTHER]],
                          "definitions": [], "inclusions": [], "dependencies": []},
              "contexts": contexts, "ledger": {"ref": "fiction:ledger:random@1", "assertions": assertions, "reviews": reviews}}
    views = [{"id": f"v{i}", "as_of": rng.choice(TIMES), "policy_ref": POLICY} for i in range(rng.randint(1, 2))]
    views = list({v["id"]: v for v in views}.values())
    queries = [{"id": f"q{ci}{si}", "context_ref": c, "subject": s, "required": rng.random() < 0.5}
               for ci, c in enumerate(CONTEXTS) for si, s in enumerate(SUBJECTS)]
    return source, views, {"parent": PARENT, "parts": parts}, queries
