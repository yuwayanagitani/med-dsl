"""P2-c：splits.py（と host.py の登録）の変異に対して、(a) examples/p2-splits の手で導いた例、(b) オラクルのテスト
（tests/p2/test_split_combination.py）、(c) 拡張契約・独立の検査（test_extension_contract.py・test_combinations.py）が、
それぞれ失敗するかを記録する。
使い方: python3 -B scripts/research/p2/mutrun_splits.py [ID ...]（環境変数 P2_REPO＝作業ツリー、P2_SCRATCH＝作業場所。既定は、このリポジトリと一時ディレクトリ）"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
S = Path(os.environ.get("P2_SCRATCH") or tempfile.mkdtemp(prefix="p2-mutation-"))
(S / "logs").mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]

# (id, ファイル, 旧, 新, 意図した例, 備考)
M = [
    ("J01", "splits.py", "        if valuation not in extendable:", "        if False:", ["check-k04-shared-parts"], ""),
    ("J02", "splits.py", '    for valuation in itertools.product((0, 1), repeat=len(component["old"])):', '    for valuation in list(itertools.product((0, 1), repeat=len(component["old"])))[:-1]:', [], "最後の割り当ては調べない：例の反例は最後ではないので、全数のテストが見る"),
    ("J03", "splits.py", 'for bits in component["valid"]}', 'for bits in component["valid"][:1]}', ["check-k04-shared-parts"], ""),
    ("J04", "splits.py", "(bits[index[head]] == 1 and ones == 1)", "(bits[index[head]] == 1 and ones >= 1)", [], "排他を外す：K04 の判定は変わらない（P = R の強制は被覆と包含から出る）ので、別の例とテストが見る"),
    ("J05", "splits.py", "(bits[index[head]] == 0 and ones == 0)", "(bits[index[head]] == 0 and ones >= 0)", ["check-k04-shared-parts"], ""),
    ("J06", "splits.py", "            if symbol in owner:", "            if False:", ["check-k04-shared-parts"], ""),
    ("J07", "splits.py", "    return all(visit(node) for node in sorted(edges))", "    return True", ["check-cyclic"], ""),
    ("J08", "splits.py", '    elif len(set(all_parts)) != len(all_parts):\n        kind = "shared_parts"', '    elif False:\n        kind = "shared_parts"', ["check-k04-shared-parts"], ""),
    ("J09", "splits.py", '"forest_condition": kind in ("single", "disjoint", "forest")', '"forest_condition": kind in ("single", "disjoint", "forest", "shared_parts")', ["check-k04-shared-parts"], ""),
    ("J10", "splits.py", '"chain": any(head in set(all_parts) for head in heads)', '"chain": False', ["check-chain"], ""),
    ("J11", "splits.py", "    old = sorted(set(vocabulary) - set(all_parts))", "    old = sorted(set(vocabulary))", ["check-k04-shared-parts"], ""),
    ("J12", "splits.py", '"certificate": "certified" if single is None else "not_certified"}', '"certificate": "not_certified"}', ["check-k04-shared-parts"], ""),
    ("Q01", "splits.py", "    if found == {None}:", "    if False:", ["query-shared-part-narrows"], ""),
    ("Q02", "splits.py", '("asserted" if candidates[0] in positive else "single")', '"single"', ["query-chain-later-info-flows-back"], ""),
    ("Q03", "splits.py", '"differs": (status, candidates) != (single[0], single[1]),', '"differs": status != single[0],', ["query-shared-part-narrowed-differently"], ""),
    ("Q04", "splits.py", 'interaction = any(all(entries[p]["individual"]["status"] != "inconsistent" for p in c["members"]) for c in violated)', "interaction = bool(violated)", ["query-disjoint-violation-does-not-leak"], ""),
    ("Q05", "splits.py", 'for s in component["symbols"] if s in leaves and bits[index[s]] == 1}', 'for s in component["symbols"] if bits[index[s]] == 1}', ["query-chain-loss-not-recovered"], ""),
    ("Q06", "splits.py", 'if all(bits[index[s]] == 1 for s in component["symbols"] if s in positive_set) \\', 'if True \\', ["query-chain-later-info-flows-back"], ""),
    ("Q07", "splits.py", '                                and all(bits[index[s]] == 0 for s in component["symbols"] if s in negative_set):', '                                and True:', ["query-chain-exclusion-flows"], ""),
    ("Q08", "splits.py", "known_capabilities={PROFILE, SPLIT_PROFILE, SPLITS_PROFILE}", "known_capabilities={PROFILE}", ["query-combination-capability-understood"], ""),
    ("Q09", "splits.py", "                if context in unknown:", "                if False:", ["query-unknown-capability-blocks"], ""),
    ("Q10", "splits.py", "                if collisions:", "                if False:", ["query-conflict-blocks"], ""),
    ("Q11", "splits.py", '"converted_to_base": False, "base": None, "splits": None', '"converted_to_base": True, "base": None, "splits": None', ["query-k04-old-data"], ""),
    ("Q12", "splits.py", '                    for bits in component["valid"]:\n                        budget.tick()\n', '                    for bits in component["valid"]:\n', ["query-budget-below"], ""),
    ("Q13", "splits.py", '                budget.tick()\n                row.update(status="computed"', '                row.update(status="computed"', ["query-budget-below"], ""),
    ("Q14", "splits.py", "    for valuation in itertools.product((0, 1), repeat=len(component[\"old\"])):\n        budget.tick()\n", "    for valuation in itertools.product((0, 1), repeat=len(component[\"old\"])):\n", ["check-budget-below"], ""),
    ("Q15", "splits.py", "    budget.tick()\n    certified = counterexample is None", "    certified = counterexample is None", ["check-budget-below"], ""),
    ("Q16", "splits.py", "        if (head, tuple(parts)) in seen:", "        if False:", ["check-duplicate-split"], ""),
    ("Q17", "splits.py", "    if len({s for head, parts in splits for s in (head, *parts)}) > MAX_SYMBOLS:", "    if len({s for head, parts in splits for s in (head, *parts)}) > 99:", ["check-vocabulary-limit"], ""),
    ("Q18", "splits.py", "MAX_SPLITS, MAX_SYMBOLS = 4, 10", "MAX_SPLITS, MAX_SYMBOLS = 5, 10", ["check-too-many-splits"], ""),
    ("Q19", "splits.py", "    if op not in consumer[\"operations\"] or set(consumer[\"operations\"]) - set(OPERATIONS):", "    if op not in consumer[\"operations\"]:", ["check-consumer-operations"], ""),
    ("Q20", "splits.py", "    if value != SPLITS_PROFILE:", "    if False:", ["check-consumer-profile"], ""),
    ("Q21", "splits.py", "    if value != SPEC_SHA256:", "    if False:", ["check-consumer-spec-hash"], ""),
    ("Q22", "splits.py", "single = classify(head, parts, head in positive_set, head in negative_set,", "single = classify(head, parts, head in positive_set, False,", ["query-k04-old-data"], ""),
    ("Q23", "splits.py", '    ledger = source["ledger"]\n    snapshot_hash = digest(source)', '    ledger = source["ledger"]\n    ledger["assertions"].reverse()\n    snapshot_hash = digest(source)', [], "入力の変更はオラクルのテストが見る"),
    ("Q24", "splits.py", 'if a["id"] in pending_ids and a["context_ref"] == context', 'if a["context_ref"] == context', ["query-ai-candidate-pending"], ""),
    ("Q25", "splits.py", '                    if status in ("open", "narrowed", "single"):\n                        requests.append', '                    if status in ("open", "narrowed"):\n                        requests.append', ["query-chain-exclusion-flows"], ""),
    ("Q26", "host.py", '    Surface("p2-splits-request-draft-1", "p2-splits-result-draft-1", SPLITS_PROFILE, run_splits),\n', '', ["check-k04-shared-parts"], "登録を外す"),
    ("Q27", "splits.py", '    return {"status": "ok", "structure": structure,\n            "certificate": {"status": "certified" if certified else "not_certified", "method": METHOD,', '    return {"status": "ok", "structure": structure,\n            "certificate": {"status": "certified", "method": METHOD,', ["check-k04-shared-parts"], ""),
]

EVALUATOR = r'''
import copy, json, sys
sys.path.insert(0, "src")
from med_dsl import evaluate
from med_dsl.validation import canonical_bytes
failed = []
for suite in ("p2-splits", "p2-split", "p2"):
    manifest = json.load(open(f"examples/{suite}/manifest.json"))
    for entry in manifest["files"]:
        data = json.load(open(f"examples/{suite}/" + entry["path"]))
        try:
            result = evaluate(copy.deepcopy(data["request"]))
            ok = True
            for check in data["expected"]["checks"]:
                actual = result
                try:
                    for key in check["path"]:
                        actual = actual[key]
                except Exception:
                    ok = False
                    break
                if canonical_bytes(actual) != canonical_bytes(check["equals"]):
                    ok = False
                    break
        except Exception:
            ok = False
        if not ok:
            failed.append(suite + "/" + entry["path"][:-5])
print(json.dumps(failed))
'''

results = []
for (ident, filename, old, new, intended, note) in M:
    if args and ident not in args:
        continue
    d = S / "mutsplits" / ident
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for sub in ("src", "tests", "examples", "scripts", "extensions"):
        shutil.copytree(REPO / sub, d / sub, ignore=shutil.ignore_patterns("__pycache__"))
    (d / "docs").mkdir()
    shutil.copytree(REPO / "docs/research", d / "docs/research")
    path = d / "src/med_dsl" / filename
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        results.append({"id": ident, "error": f"置換元が {text.count(old)} 件"})
        print(ident, "★置換元が %d 件" % text.count(old), flush=True)
        shutil.rmtree(d)
        continue
    path.write_text(text.replace(old, new), encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_DIR=str(REPO / ".git"))
    out = subprocess.run([sys.executable, "-B", "-c", EVALUATOR], cwd=d, capture_output=True, text=True, env=env, timeout=900)
    try:
        failed = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        failed = ["<evaluator error: %s>" % out.stderr[-200:]]
    counts = {}
    for name, target in (("oracle_tests", "tests.p2.test_split_combination"), ("contract_tests", "tests.p2.test_extension_contract"), ("independence_tests", "tests.p2.test_combinations")):
        t = subprocess.run([sys.executable, "-B", "-m", "unittest", target], cwd=d, capture_output=True, text=True, env=env, timeout=1800)
        counts[name] = sum(1 for line in t.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")))
    row = {"id": ident, "file": filename, "intended": intended, "note": note,
           "intended_hit": all(f"p2-splits/{i}" in failed for i in intended), "failed_examples": failed, **counts}
    row["detected"] = bool(failed) or any(counts.values())
    results.append(row)
    kind = "未検出" if not row["detected"] else "例のみ" if failed and not any(counts.values()) else "テストのみ" if not failed else "例とテスト"
    print(ident, filename, "意図した例:", "失敗" if (row["intended_hit"] and intended) else "－" if not intended else "★通過", "| 検出:", kind,
          "| 例", len(failed), "| オラクル", counts["oracle_tests"], "| 契約", counts["contract_tests"], "| 独立", counts["independence_tests"], "|", note, flush=True)
    shutil.rmtree(d)
(S / "logs" / ("mutation-splits-" + "-".join(args) + ".json" if args else "mutation-splits.json")).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
