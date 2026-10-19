"""概念の分割の併用の独立オラクル（P2-c）。実装（splits.py）の枠による列挙・成分の分解・状態表を使わずに、
文書 25 の意味を、公理 A1〜A3 の式の直接評価と、記号のグラフによる成分から書き直したもの。
"""

import itertools

import split_oracle as base

POOL = [f"fiction:V{i}@1" for i in range(7)]
POOL10 = [f"fiction:V{i}@1" for i in range(10)]


def symbols_of(splits):
    return sorted({s for head, parts in splits for s in (head, *parts)})


def axioms_hold(v, splits):
    """A1 包含、A2 被覆、A3 排他を式として直接評価する。"""
    for head, parts in splits:
        if not all((not v[q]) or v[head] for q in parts):
            return False
        if v[head] and not any(v[q] for q in parts):
            return False
        if any(v[a] and v[b] for a, b in itertools.combinations(parts, 2)):
            return False
    return True


def components(splits):
    """分割の連結成分。記号を節点にした無向グラフの幅優先探索（実装の併合とは別の方法）。"""
    seen, groups = set(), []
    for start in range(len(splits)):
        if start in seen:
            continue
        group, frontier = {start}, [start]
        while frontier:
            current = frontier.pop()
            symbols = {splits[current][0], *splits[current][1]}
            for other in range(len(splits)):
                if other not in group and symbols & {splits[other][0], *splits[other][1]}:
                    group.add(other)
                    frontier.append(other)
        seen |= group
        groups.append(sorted(group))
    return sorted(groups)


def models_of(member_splits):
    """成分の語彙の全割り当てのうち、公理を満たすもの（辞書 symbol -> 真偽）。"""
    symbols = symbols_of(member_splits)
    found = []
    for bits in itertools.product((False, True), repeat=len(symbols)):
        v = dict(zip(symbols, bits))
        if axioms_hold(v, member_splits):
            found.append(v)
    return found


def old_symbols(splits):
    parts = {q for _, ps in splits for q in ps}
    return sorted(set(symbols_of(splits)) - parts)


def conservative(splits):
    """併用全体で、旧記号のすべての割り当てが拡張できるか。成分に分けず、全語彙の全割り当てから求める。"""
    symbols = symbols_of(splits)
    old = old_symbols(splits)
    extendable = set()
    for bits in itertools.product((False, True), repeat=len(symbols)):
        v = dict(zip(symbols, bits))
        if axioms_hold(v, splits):
            extendable.add(tuple(v[s] for s in old))
    for u in itertools.product((False, True), repeat=len(old)):
        if u not in extendable:
            return False, dict(zip(old, (int(x) for x in u)))
    return True, None


def status_of(head, parts, found, positive):
    """分割 s の枠への射影 found（None は親が偽）から状態を決める。P2-b の表。"""
    if not found:
        return "inconsistent", [], False
    if found == {None}:
        return "parent_opposed", [], False
    if None in found:
        return "no_parent", [], False
    candidates = [q for q in parts if q in found]
    if len(candidates) == 1:
        return ("asserted" if candidates[0] in positive else "single"), candidates, head not in positive
    return ("open" if len(candidates) == len(parts) else "narrowed"), candidates, False


def expected_row(source, view, splits, query):
    """行の期待。('blocked', 理由, 詳細) または ('computed', 分割ごとの (併用, 単独), 葉の候補, 相互作用, 基底の状態)。"""
    items, visible, adopted = base.adoption(source, view)
    context, subject = query["context_ref"], query["subject"]
    allowed = {base.P0_CAPABILITY, base.SPLIT_CAPABILITY, "p2-split-combination-draft-1"}
    unknown = sorted(k for k in visible if items[k]["context_ref"] == context and set(items[k]["required_capabilities"]) - allowed)
    if unknown:
        return ("blocked", "unknown_capability", unknown)
    positive = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in adopted
                if items[k]["context_ref"] == context and items[k]["polarity"] == "positive"}
    negative = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in adopted
                if items[k]["context_ref"] == context and items[k]["polarity"] == "negative"}
    if positive & negative:
        return ("blocked", "unresolved_conflict", None)
    vocabulary = symbols_of(splits)
    pos = {s for s in vocabulary if (s, (subject,)) in positive}
    neg = {s for s in vocabulary if (s, (subject,)) in negative}
    leaves = {q for _, ps in splits for q in ps} - {head for head, _ in splits}
    result = [None] * len(splits)
    possible, violated = set(), []
    for members in components(splits):
        member_splits = [splits[i] for i in members]
        mod = [v for v in models_of(member_splits) if all(v[s] for s in pos if s in v) and not any(v[s] for s in neg if s in v)]
        for i in members:
            head, parts = splits[i]
            found = {None if not v[head] else next(q for q in parts if v[q]) for v in mod}
            joint = status_of(head, parts, found, pos)
            own = [v for v in models_of([splits[i]]) if all(v[s] for s in pos if s in v) and not any(v[s] for s in neg if s in v)]
            single_found = {None if not v[head] else next(q for q in parts if v[q]) for v in own}
            result[i] = (joint, status_of(head, parts, single_found, pos))
        possible |= {s for v in mod for s in v if s in leaves and v[s]}
        if not mod:
            violated.append(members)
    interaction = any(all(result[i][1][0] != "inconsistent" for i in members) for members in violated)
    state = {s: "supported" if s in pos else "opposed" if s in neg else "undetermined" for s in vocabulary}
    return ("computed", result, sorted(possible), interaction, state)


def generate_splits(rng, pool=POOL, max_splits=3, sizes=(2, 3, 4)):
    splits, seen = [], set()
    for _ in range(rng.randint(1, max_splits)):
        head = rng.choice(pool)
        parts = sorted(rng.sample([s for s in pool if s != head], rng.choice(sizes)))
        if (head, tuple(parts)) in seen:
            continue
        seen.add((head, tuple(parts)))
        splits.append((head, parts))
    return splits


def generate_state(rng, splits, pool=POOL, dense=True):
    """一つの個体・一つの文脈の台帳。語彙の記号ごとに（なし／肯定／否定）を選ぶ。まれに衝突・未知の能力・AI 候補を混ぜる。"""
    context = base.CONTEXTS[0]
    assertions = []
    for i, symbol in enumerate(pool):
        if rng.random() < (0.55 if dense else 0.3):
            draw = rng.random()
            caps = [base.SPLIT_CAPABILITY] if draw < 0.1 else ["p2-split-combination-draft-1"] if draw < 0.2 else [base.OTHER_CAPABILITY] if draw < 0.23 else []
            assertions.append({"id": f"h{i}", "context_ref": context, "atom": {"predicate": symbol, "args": [base.SUBJECTS[0]]},
                               "polarity": "positive" if rng.random() < 0.55 else "negative",
                               "certainty": "confirmed" if rng.random() < 0.95 else "suspected", "recorded_at": base.TIMES[0],
                               "origin": {"kind": rng.choice(["observed", "judgment", "imported", "ai_candidate"]), "ref": f"fiction:source:{i}"},
                               "supersedes": [], "required_capabilities": caps})
    if assertions and rng.random() < 0.05:
        twin = dict(assertions[0])
        twin.update(id="hx", polarity="negative" if assertions[0]["polarity"] == "positive" else "positive")
        assertions.append(twin)
    reviews = [{"id": f"r{a['id']}", "assertion_ref": a["id"], "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
                "recorded_at": base.TIMES[1], "outcome": "confirmed"} for a in assertions if rng.random() < 0.95]
    source = {"package": {"ref": "fiction:package:splits@1", "profile": base.P0_CAPABILITY,
                          "predicates": [{"ref": n, "roles": ["subject"]} for n in pool], "definitions": [], "inclusions": [], "dependencies": []},
              "contexts": [{"ref": c, "subject_ref": base.SUBJECTS[0], "effective_at": "2019-12-01T00:00:00Z", "purpose": "fiction:research"} for c in base.CONTEXTS],
              "ledger": {"ref": "fiction:ledger:combo@1", "assertions": assertions, "reviews": reviews}}
    views = [{"id": "v0", "as_of": base.TIMES[5], "policy_ref": base.POLICY}]
    queries = [{"id": "q0", "context_ref": context, "subject": base.SUBJECTS[0], "required": True}]
    return source, views, queries


def generate_disjoint(rng, pool=POOL10):
    """語彙が互いに素な 2〜3 個の分割を作る。"""
    symbols = list(pool)
    rng.shuffle(symbols)
    splits = []
    for _ in range(rng.randint(2, 3)):
        size = rng.choice((2, 3))
        if len(symbols) < 1 + size:
            break
        head = symbols.pop()
        splits.append((head, sorted(symbols.pop() for _ in range(size))))
    return splits


def generate_nested(rng, pool=POOL10):
    """部分の一つを次の分割の親にして、入れ子の鎖（木）を作る。どの記号も高々一つの分割の部分で、閉路はない。"""
    symbols = list(pool)
    rng.shuffle(symbols)
    splits, frontier = [], [symbols.pop()]
    while frontier and len(splits) < 3:
        head = frontier.pop(0)
        size = rng.choice((2, 3))
        if len(symbols) < size:
            break
        parts = sorted(symbols.pop() for _ in range(size))
        splits.append((head, parts))
        frontier.append(rng.choice(parts))
    return splits
