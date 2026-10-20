"""P2-b：split.py（と host.py の登録）の変異に対して、(a) examples/p2-split の手で指定した例、(b) オラクルのテスト
（tests/p2/test_concept_split.py）、(c) 拡張契約の検査（tests/p2/test_extension_contract.py）が、それぞれ失敗するかを記録する。
使い方: python3 -B scripts/research/p2/mutrun_split.py [ID ...]（環境変数 P2_REPO＝作業ツリー、P2_SCRATCH＝作業場所。既定は、このリポジトリと一時ディレクトリ）"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
S = Path(os.environ.get("P2_SCRATCH") or tempfile.mkdtemp(prefix="p2-mutation-"))
(S / "logs").mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]

# (id, ファイル, 旧, 新, 意図した例, 備考)
M = [
    ("S01", "split.py", 'if positive_parts - {part}:', 'if False:', ["part-asserted", "inconsistent-two-parts-asserted"], ""),
    ("S02", "split.py", 'if part in negative_parts:', 'if False:', ["single-by-exclusion", "narrowed-three-parts"], ""),
    ("S03", "split.py", 'if negative_parent:', 'if False:', ["parent-opposed"], ""),
    ("S04", "split.py", 'parent_forced = positive_parent or bool(positive_parts)', 'parent_forced = positive_parent', ["part-only-parent-derived"], ""),
    ("S05", "split.py", 'if parent_forced and not candidates:', 'if False:', ["inconsistent-all-parts-opposed"], ""),
    ("S06", "split.py", '            return "parent_opposed", [], excluded, False\n        return "no_parent"', '            return "no_parent", [], excluded, False\n        return "no_parent"', ["all-parts-opposed"], ""),
    ("S07", "split.py", '("asserted" if candidates[0] in positive_parts else "single")', '"single"', ["part-asserted"], ""),
    ("S08", "split.py", '("asserted" if candidates[0] in positive_parts else "single")', '"asserted"', ["single-by-exclusion"], ""),
    ("S09", "split.py", '("open" if len(candidates) == len(parts) else "narrowed")', '"open"', ["narrowed-three-parts"], ""),
    ("S10", "split.py", 'derived = not positive_parent', 'derived = False', ["part-only-parent-derived"], ""),
    ("S11", "split.py", 'if collisions:', 'if False:', ["conflict-blocks"], ""),
    ("S12", "split.py", 'known_capabilities={PROFILE, SPLIT_PROFILE}', 'known_capabilities={PROFILE}', ["part-asserted"], ""),
    ("S13", "split.py", 'if context in unknown:', 'if False:', ["unknown-capability-blocks"], ""),
    ("S14", "split.py", 'if a["id"] in pending_ids and a["context_ref"] == context', 'if a["context_ref"] == context', ["ai-candidate-pending"], ""),
    ("S15", "split.py", 'if status in ("open", "narrowed", "single"):\n                    requests', 'if status in ("open", "narrowed"):\n                    requests', ["single-by-exclusion"], ""),
    ("S16", "split.py", '"converted_to_base": False, "base": None', '"converted_to_base": True, "base": None', ["old-record-only"], ""),
    ("S17", "split.py", '"supported" if atoms[name] in pos else "opposed" if atoms[name] in neg else "undetermined"', '"supported" if atoms[name] in pos else "undetermined"', ["single-by-exclusion"], ""),
    ("S18", "split.py", 'if any(rule.head in mentioned or mentioned & set(rule.body) for rule in rules):', 'if False:', ["symbol-has-rules"], ""),
    ("S19", "split.py", 'if len(roles[name]) != 1:', 'if False:', ["non-unary-part"], ""),
    ("S20", "split.py", 'if len(set(parts)) != len(parts):', 'if False:', ["duplicate-parts"], ""),
    ("S21", "split.py", 'if parent in parts:', 'if False:', ["parent-among-parts"], ""),
    ("S22", "split.py", 'if len(parts) < 2:', 'if len(parts) < 1:', ["one-part"], ""),
    ("S23", "split.py", 'if consumer["operations"] != ["query_split"]:', 'if False:', ["consumer-operations"], ""),
    ("S24", "split.py", 'if value != SPEC_SHA256:', 'if False:', ["consumer-spec-hash"], ""),
    ("S25", "split.py", 'if value != SPLIT_PROFILE:', 'if False:', ["consumer-profile"], ""),
    ("S27", "split.py", '                budget.tick()\n                row.update(status="computed"', '                row.update(status="computed"', ["budget-below"], ""),
    ("S28", "split.py", '                for _ in vocabulary:\n                    budget.tick()\n', '', ["budget-below"], ""),
    ("S29", "split.py", '        budget.tick()\n        row_index = 0', '        row_index = 0', ["budget-below"], ""),
    ("S30", "split.py", '    return parent, sorted(parts)\n', '    return parent, list(parts)\n', [], "並べ替えの不変性はオラクルのテストが見る"),
    ("S31", "split.py", '    if status in ("open", "narrowed", "single"):\n        used.add("A2_coverage")', '    if status in ("narrowed", "single"):\n        used.add("A2_coverage")', ["old-record-only"], ""),
    ("S32", "split.py", 'snapshot_hash = digest(source)', 'snapshot_hash = digest(ledger)', ["old-record-only"], ""),
    ("S33", "split.py", '    ledger = source["ledger"]\n', '    ledger = source["ledger"]\n    ledger["assertions"].reverse()\n', [], "入力の変更はオラクルのテストが見る"),
    ("S34", "host.py", '    Surface("p2-split-request-draft-1", "p2-split-result-draft-1", SPLIT_PROFILE, run_split),\n', '', ["old-record-only"], "登録を外す"),
    ("S35", "split.py", 'row.update(status="blocked", reason_codes=["unknown_capability"],', 'row.update(status="blocked", reason_codes=["unknown_capability_x"],', ["unknown-capability-blocks"], ""),
    ("S36", "split.py", 'candidates = [part for part in parts if part not in excluded]', 'candidates = [part for part in parts if part not in excluded and part not in negative_parts]', [], "等価（除外に adopted_negative が含まれる）"),
]

EVALUATOR = r'''
import copy, json, sys
sys.path.insert(0, "src")
from med_dsl import evaluate
from med_dsl.validation import canonical_bytes
failed = []
for suite in ("p2-split", "p2"):
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
    d = S / "mutsplit" / ident
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
    for name, target in (("oracle_tests", "tests.p2.test_concept_split"), ("contract_tests", "tests.p2.test_extension_contract")):
        t = subprocess.run([sys.executable, "-B", "-m", "unittest", target], cwd=d, capture_output=True, text=True, env=env, timeout=1800)
        counts[name] = sum(1 for line in t.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")))
    row = {"id": ident, "file": filename, "intended": intended, "note": note,
           "intended_hit": all(f"p2-split/{i}" in failed for i in intended), "failed_examples": failed, **counts}
    row["detected"] = bool(failed) or any(counts.values())
    results.append(row)
    kind = "未検出" if not row["detected"] else "例のみ" if failed and not any(counts.values()) else "テストのみ" if not failed else "例とテスト"
    print(ident, filename, "意図した例:", "失敗" if (row["intended_hit"] and intended) else "－" if not intended else "★通過", "| 検出:", kind,
          "| 例", len(failed), "| オラクル", counts["oracle_tests"], "| 契約", counts["contract_tests"], "|", note, flush=True)
    shutil.rmtree(d)
(S / "logs" / ("mutation-split-" + "-".join(args) + ".json" if args else "mutation-split.json")).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
