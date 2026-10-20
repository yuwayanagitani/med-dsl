"""挙動を変えない分離（P2 の拡張ホスト）の前後比較用。全例、改変入力、予算の全値掃引の結果の digest を出す。
certifier（実装の束の hash）だけは、ファイルを足せば変わるので除いて比べる。
使い方: python3 -B scripts/research/p2/refactor_digest.py <リポジトリのルート> <出力 JSON>"""
import copy, hashlib, json, random, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "src"))
from med_dsl import evaluate
from med_dsl.validation import canonical_bytes, decode_json

SUITES = ("p0", "p1-a", "p1-b", "p1-c", "review")
MUTATIONS = 150


def strip(value):
    if isinstance(value, dict):
        return {k: (None if k == "certifier" else strip(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


KINDS = {}


def outcome(request):
    try:
        result = strip(evaluate(copy.deepcopy(request)))
        reasons = result.get("reason_codes") or []
        KINDS[(result.get("status"), reasons[0] if reasons else None)] = KINDS.get((result.get("status"), reasons[0] if reasons else None), 0) + 1
        return hashlib.sha256(canonical_bytes(result)).hexdigest()
    except Exception as error:  # 例外も結果として比べる
        return "EXC:" + type(error).__name__


def walk(x, path=()):
    yield path, x
    if isinstance(x, dict):
        for k, v in x.items():
            yield from walk(v, path + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk(v, path + (i,))


def get(x, path):
    for k in path:
        x = x[k]
    return x


def mutate(request, rng):
    r = copy.deepcopy(request)
    nodes = [p for p, _ in walk(r) if p]
    if not nodes:
        return r
    path = rng.choice(nodes)
    parent = get(r, path[:-1])
    key = path[-1]
    val = parent[key]
    op = rng.choice(["delete", "none", "str", "int", "bool", "list", "dict", "neg", "dup", "empty_str", "big", "swap"])
    if op == "delete":
        if isinstance(parent, dict):
            del parent[key]
        else:
            parent.pop(key)
    elif op == "none":
        parent[key] = None
    elif op == "str":
        parent[key] = "x"
    elif op == "empty_str":
        parent[key] = ""
    elif op == "int":
        parent[key] = 0
    elif op == "neg":
        parent[key] = -1
    elif op == "big":
        parent[key] = 10 ** 30
    elif op == "bool":
        parent[key] = True
    elif op == "list":
        parent[key] = []
    elif op == "dict":
        parent[key] = {}
    elif op == "swap" and isinstance(val, str) and len(val) > 1:
        parent[key] = val[::-1]
    elif op == "dup":
        if isinstance(parent, list):
            parent.append(copy.deepcopy(val))
        elif isinstance(val, list) and val:
            val.append(copy.deepcopy(val[0]))
    return r


rows = {}
for suite in SUITES:
    manifest = decode_json((root / f"examples/{suite}/manifest.json").read_bytes())
    for entry in manifest["files"] + manifest.get("accepted_boundaries", []):
        name = f"{suite}/{entry['path']}"
        request = decode_json((root / f"examples/{suite}" / entry["path"]).read_bytes())["request"]
        rows[name] = outcome(request)
        rng = random.Random(int(hashlib.sha256(name.encode()).hexdigest()[:12], 16))
        for i in range(MUTATIONS):
            rows[f"{name}#m{i}"] = outcome(mutate(request, rng))
        if isinstance(request, dict) and isinstance(request.get("budget"), dict):
            full = copy.deepcopy(request)
            full["budget"] = {"max_steps": 100000}
            try:
                used = evaluate(full).get("steps_used") or 0
            except Exception:
                used = 0
            top = min(used + 3, 160)
            for b in sorted(set(range(0, top + 1)) | {used + 1, used + 50}):
                r = copy.deepcopy(request)
                r["budget"] = {"max_steps": b}
                rows[f"{name}#b{b}"] = outcome(r)
Path(sys.argv[2]).write_text(json.dumps(rows, sort_keys=True, indent=0), encoding="utf-8")
print(len(KINDS), "distinct (status, first reason) pairs")
print(len(rows), "outcomes;", sum(v.startswith("EXC:") for v in rows.values()), "exceptions;",
      hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:16])
