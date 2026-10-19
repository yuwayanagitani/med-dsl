"""レビュー系列の独立オラクルと乱数生成器（テストではなく、テストが読み込む補助）。

実装（med_dsl）の閉包・結合・採用の関数を使わず、PO04 の集合定義と単項 Horn の不動点、
全探索の結合を書き直したもの。`split_roles=True` は、関係の四役割を別々の事象から取る
既知の誤訳（役割ごとの値の直積）を評価する。参照計算も同じ作者が書いたもので、
定義自体の誤りは検出できない。
"""

import collections
import itertools

POLICY = "fiction:confirmed-explicit-revision@1"
REL = "fiction:O@1"
UNARY = ["fiction:U1@1", "fiction:U2@1", "fiction:U3@1", "fiction:U4@1"]
CONSTS = ["a", "b", "c"]
CTX = ["fiction:c1", "fiction:c2"]
TIMES = ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z",
         "2026-01-04T00:00:00Z", "2026-01-05T00:00:00Z", "2026-01-06T00:00:00Z"]


def var(name):
    return {"var": name}


def generate(rng):
    """(source, views, queries)。確認は主張以後（p0-draft-2）。関係の値は少数にして、役割の取り違えが起きやすくする。"""
    predicates = [{"ref": REL, "roles": ["k", "s", "m", "v"]}] + [{"ref": u, "roles": ["x"]} for u in UNARY]
    inclusions, definitions = set(), []
    for _ in range(rng.randint(0, 3)):
        a, b = rng.sample(UNARY[:3], 2)
        inclusions.add((a, b))
    if rng.random() < 0.5:
        definitions.append({"kind": "defined", "symbol": UNARY[3], "all_of": rng.sample(UNARY[:3], rng.randint(1, 2))})
    package = {"ref": "fiction:pkg@1", "profile": "p0-positive-1", "predicates": predicates, "definitions": definitions,
               "inclusions": [{"sub": a, "super": b} for a, b in sorted(inclusions)], "dependencies": []}
    contexts = [{"ref": c, "subject_ref": "fiction:p1", "effective_at": TIMES[0], "purpose": "fiction:r"} for c in CTX]
    assertions = []
    for i in range(rng.randint(1, 7)):
        ctx = rng.choice(CTX)
        if rng.random() < 0.6:
            atom = {"predicate": REL, "args": [rng.choice(CONSTS[:2]), rng.choice(CONSTS), rng.choice(CONSTS[:2]), rng.choice(CONSTS)]}
        else:
            atom = {"predicate": rng.choice(UNARY), "args": [rng.choice(CONSTS)]}
        when = rng.choice(TIMES[:5])
        supersedes = []
        earlier = [x for x in assertions if x["context_ref"] == ctx and x["atom"] == atom and x["recorded_at"] < when]
        if earlier and rng.random() < 0.3:
            supersedes = [rng.choice(earlier)["id"]]
        item = {"id": f"h{i}", "context_ref": ctx, "atom": atom, "polarity": "negative" if rng.random() < 0.2 else "positive",
                "certainty": "suspected" if rng.random() < 0.2 else "confirmed", "recorded_at": when,
                "origin": {"kind": "observed", "ref": f"fiction:o{i}"}, "supersedes": supersedes,
                "required_capabilities": ["fiction:cap@1"] if rng.random() < 0.06 else []}
        if supersedes:
            item["change_reason"] = "fiction:fix"
        assertions.append(item)
    reviews = []
    for item in assertions:
        for _ in range(rng.choice([0, 1, 1, 2])):
            reviews.append({"id": f"r{len(reviews)}", "assertion_ref": item["id"], "reviewer_ref": "fiction:rev", "reviewer_kind": "human",
                            "recorded_at": rng.choice([t for t in TIMES if t >= item["recorded_at"]]), "outcome": "confirmed"})
    views = [{"id": f"v{i}", "as_of": t, "policy_ref": POLICY} for i, t in enumerate(sorted(rng.sample(TIMES, rng.randint(1, 2))))]
    queries = []
    for i in range(rng.randint(1, 4)):
        atoms = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.55:
                atoms.append({"predicate": REL, "args": [rng.choice([var("x"), var("y"), "a", "b"]), rng.choice([var("x"), var("y"), var("z"), "a", "b", "c"]),
                                                          rng.choice([var("y"), var("w"), "a", "b"]), rng.choice([var("z"), var("x"), var("w"), "a", "c"])]})
            else:
                atoms.append({"predicate": rng.choice(UNARY), "args": [rng.choice([var("x"), var("y"), var("z"), "a", "b"])]})
        queries.append({"id": f"q{i}", "context_ref": rng.choice(CTX), "atoms": atoms, "required": rng.random() < 0.5})
    source = {"package": package, "dependency_packages": [], "contexts": contexts,
              "ledger": {"ref": "fiction:L0", "assertions": assertions, "reviews": reviews}}
    return source, views, queries


def adopted(source, as_of):
    """PO04：V（可視）、C（確認済み）、S（訂正された）、A=C−S と、文脈ごとの未知能力の可視主張。"""
    items = {h["id"]: h for h in source["ledger"]["assertions"]}
    visible = {k for k, h in items.items() if h["recorded_at"] <= as_of}
    reviewed = {r["assertion_ref"] for r in source["ledger"]["reviews"] if r["recorded_at"] <= as_of}
    confirmed = {k for k in visible if items[k]["certainty"] == "confirmed" and k in reviewed}
    superseded = {a for k in confirmed for a in items[k]["supersedes"]}
    unknown = collections.defaultdict(set)
    for k in visible:
        if set(items[k]["required_capabilities"]) - {"p0-positive-1"}:
            unknown[items[k]["context_ref"]].add(k)
    return items, confirmed - superseded, unknown


def evaluate_source(source, views, queries, split_roles=False):
    """(view, query) -> (status, binding の集合または None)。status は supported／undetermined／opposed／conflict／unassessed。"""
    package = source["package"]
    rules = [([i["sub"]], i["super"]) for i in package["inclusions"]]
    for d in package["definitions"]:
        rules.append((list(d["all_of"]), d["symbol"]))
        rules.extend(([d["symbol"]], t) for t in d["all_of"])
    out = {}
    for view in views:
        items, chosen, unknown = adopted(source, view["as_of"])
        for q in queries:
            ctx = q["context_ref"]
            key = (view["id"], q["id"])
            if ctx in unknown:
                out[key] = ("unassessed", None)
                continue
            pos = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in chosen
                   if items[k]["context_ref"] == ctx and items[k]["polarity"] == "positive"}
            neg = {(items[k]["atom"]["predicate"], tuple(items[k]["atom"]["args"])) for k in chosen
                   if items[k]["context_ref"] == ctx and items[k]["polarity"] == "negative"}
            changed = True
            while changed:
                changed = False
                for body, head in rules:
                    for c in {a for (p, a) in pos if p == body[0]}:
                        if all((b, c) in pos for b in body) and (head, c) not in pos:
                            pos.add((head, c))
                            changed = True
            if pos & neg:
                out[key] = ("conflict", None)
                continue
            facts = set(pos)
            if split_roles:
                tuples = [a for (p, a) in pos if p == REL]
                facts = {f for f in facts if f[0] != REL}
                facts |= {(REL, combo) for combo in itertools.product(*({t[i] for t in tuples} for i in range(4)))}
            names = sorted({t["var"] for a in q["atoms"] for t in a["args"] if isinstance(t, dict)})
            pool = sorted({x for (_, a) in facts for x in a})
            solutions = set()
            for combo in itertools.product(pool, repeat=len(names)):
                env = dict(zip(names, combo))
                if all((a["predicate"], tuple(env[t["var"]] if isinstance(t, dict) else t for t in a["args"])) in facts for a in q["atoms"]):
                    solutions.add(tuple(sorted(env.items())))
            single = q["atoms"][0] if len(q["atoms"]) == 1 else None
            if solutions:
                out[key] = ("supported", solutions)
            elif single and all(isinstance(x, str) for x in single["args"]) and (single["predicate"], tuple(single["args"])) in neg:
                out[key] = ("opposed", None)
            else:
                out[key] = ("undetermined", None)
    return out


def bindings_of(entry):
    status, found = entry
    return found if status == "supported" else set()
