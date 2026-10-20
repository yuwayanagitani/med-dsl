"""P2-a の防護例（examples/p2/）の検出力：実装のゲートを壊したとき、意図した例が失敗するか。
各変異で、(a) examples/p2/ の全例を評価して失敗した例を集め、(b) 既存の開発テスト（tests/）とレビュー系列（tests/review/）が
その変異を検出するかも記録する（防護例が既存の検査で見逃される退行を新しく検出するか）。
P0 実行体のファイルを変異させるときは、固定された hash が合わなくなって別の理由で失敗しないよう、変異後の hash で再固定する。
使い方: python3 -B scripts/research/p2/mutrun_guards.py [--no-tests] [ID ...]（環境変数 P2_REPO＝作業ツリー、P2_SCRATCH＝作業場所。既定は、このリポジトリと一時ディレクトリ）"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
S = Path(os.environ.get("P2_SCRATCH") or tempfile.mkdtemp(prefix="p2-mutation-"))
(S / "logs").mkdir(parents=True, exist_ok=True)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
RUN_TESTS = "--no-tests" not in sys.argv
sys.path.insert(0, str(REPO / "src"))
from med_dsl.validation import digest  # 再固定の計算は元の実装で行う
import hashlib

P0_FILES = ("model.py", "validation.py", "definitions.py", "ledger.py", "query.py")

# (id, ファイル, 旧, 新, 意図した例)
M = [
    ("C0", "chain.py", "certified = complete and not outside", "certified = complete and not outside", []),   # 対照：変異なし（実行器が失敗を出さないことの確認）
    ("K1", "absence.py", '    for r in before["results"]:\n        budget.tick()\n', '    for r in before["results"]:\n', ["budget-below-absence"]),
    ("K2", "chain.py", "    def check(name, ok):\n        budget.tick()\n", "    def check(name, ok):\n", ["budget-below-event-chain"]),
    ("K3", "events.py", '        budget.tick()\n        response = _run_target(', '        response = _run_target(', ["budget-below-events"]),
    ("K4", "chain.py", '    budget.tick()\n    return {"status": "ok", "target": renamed,', '    return {"status": "ok", "target": renamed,', ["budget-below-rename-events"]),
    ("K5", "projection.py", '    for row in rows:\n        budget.tick()\n        if all(', '    for row in rows:\n        if all(', ["budget-below-projection"]),
    ("K6", "reference.py", "def truth(formula, model, budget, env=None):\n    budget.tick()\n", "def truth(formula, model, budget, env=None):\n", ["budget-below-reference"]),
    ("K7", "replay.py", "def _run_archive(request, inventory, validated, interpretation, budget):\n    budget.tick()\n", "def _run_archive(request, inventory, validated, interpretation, budget):\n", ["budget-below-replay"]),
    ("K8", "definitions.py", "    budget.tick()  # 空の追加でも 0 は未評価。\n", "", ["budget-below-definitions", "definitions-empty-extension-zero-budget"]),
    ("K9", "handover.py", "    validated = operation.validate(request, budget)\n    budget.tick()\n", "    validated = operation.validate(request, budget)\n", ["budget-below-reference", "budget-below-projection"]),
    ("G1", "reference.py", "if count > 512 or depth > 16:", "if count > 512 or depth > 17:", ["reference-formula-depth-limit"]),
    ("G2", "reference.py", "if count > 512 or depth > 16:", "if count > 512 or depth > 15:", ["reference-formula-depth-exact"]),
    ("G3", "reference.py", 'if sizes and (predicates or signature["constants"]):', "if False:", ["reference-finite-probe-unsupported"]),
    ("G4", "handover.py", 'if op not in c["operations"] or set(c["operations"]) - set(OPERATIONS):', 'if op not in c["operations"]:', ["host-consumer-operation-unsupported"]),
    ("G5", "handover.py", 'if c["profile"] != HANDOVER_PROFILE:', "if False:", ["host-consumer-profile"]),
    ("G6", "handover.py", "if type(op) is not str or op not in OPERATIONS:", "if type(op) is not str:", ["host-unsupported-operation"]),
    ("G7", "forecast.py", '"predicates": [{"ref": REPORT_PREDICATE, "roles": ["subject", "forecast"]}],',
     '"predicates": [{"ref": REPORT_PREDICATE, "roles": ["subject", "forecast"]}, {"ref": "fiction:clinical-X@1", "roles": ["subject", "forecast"]}],', ["forecast-nonreport-predicate-refused"]),
    ("G8", "forecast.py", '"report_snapshot", "views", "queries", "budget"))', '"report_snapshot", "views", "queries", "budget"), ("package",))', ["forecast-arbitrary-package-refused"]),
    ("G9", "reference.py", '("signature", "source", "target", "queries", "models", "finite_domain_sizes"), False', '("signature", "source", "target", "queries", "models", "finite_domain_sizes", "ledger"), False', ["reference-ledger-field-refused"]),
    ("G10", "reference.py", 'if f["predicate"] not in predicates:\n                raise Problem("undeclared_predicate")', 'if False:\n                raise Problem("undeclared_predicate")', ["reference-new-name-refused"]),
    ("G11", "reference.py", 'True if sentences["target"] <= sentences["source"] else None', 'True if sentences["target"] <= sentences["source"] else True', ["reference-stronger-target"]),
    # G12 は等価変異：outside が空でなければ _compare の状態が "partial" になり complete が偽になるので、`and not outside` は冗長（多重の防御）
    ("G12", "chain.py", "certified = complete and not outside", "certified = complete", []),
    ("G12b", "chain.py", '    outside = [q["id"] for q in request["queries"] if q["kind"] != "legacy_positive"]\n', "    outside = []\n", ["chain-out-of-scope-query"]),
    ("G13", "chain.py", 'complete = all(c["comparison"]["status"] == "matched" for c in checks)', "complete = True", ["chain-unknown-capability"]),
    ("G14", "validation.py", 'else ("dependency_packages",)\n    fields(request, ("schema_version", "operation", "budget", *required), optional)',
     'else ("dependency_packages", "ledger")\n    fields(request, ("schema_version", "operation", "budget", *required), optional)', ["definitions-ledger-field-refused"]),
    ("G15", "ledger.py", 'if item["certainty"] == "confirmed" and key in reviews}', 'if item["certainty"] == "confirmed"}', ["chain-ai-candidate-not-adopted"]),
    ("G16", "model.py", "if self.used >= self.maximum:", "if self.used > self.maximum:", ["budget-below-absence", "budget-below-event-chain", "budget-below-reference"]),
    ("G17", "model.py", "if self.used >= self.maximum:", "if self.used >= self.maximum and self.maximum > 0:", ["definitions-zero-budget"]),
    # 停止時の応答の形（部分の報告・認定票を出さない）を壊す：host.evaluate の except 節
    ("G18", "host.py", '"error_path": problem.path, "incomplete": ["request"]}', '"error_path": problem.path, "incomplete": []}', ["chain-zero-budget", "definitions-zero-budget"]),
]

EVALUATOR = r'''
import copy, json, sys
sys.path.insert(0, "src")
from med_dsl import evaluate
from med_dsl.validation import canonical_bytes
manifest = json.load(open("examples/p2/manifest.json"))
failed = []
for entry in manifest["files"]:
    data = json.load(open("examples/p2/" + entry["path"]))
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
        failed.append(entry["path"][:-5])
print(json.dumps(failed))
'''

results = []
for (ident, filename, old, new, intended) in M:
    if args and ident not in args:
        continue
    d = S / "mutguard" / ident
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for sub in ("src", "tests", "examples", "scripts"):
        shutil.copytree(REPO / sub, d / sub, ignore=shutil.ignore_patterns("__pycache__"))
    (d / "docs").mkdir()
    shutil.copytree(REPO / "docs/research", d / "docs/research")
    path = d / "src/med_dsl" / filename
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (ident, filename, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")
    if filename in P0_FILES:
        hashes = {name: hashlib.sha256((d / "src/med_dsl" / name).read_bytes()).hexdigest() for name in P0_FILES}
        common = d / "src/med_dsl/handover_common.py"
        t = common.read_text(encoding="utf-8")
        import re
        t = re.sub(r'P0_RUNTIME_SHA256 = "[0-9a-f]{64}"', f'P0_RUNTIME_SHA256 = "{digest(hashes)}"', t)
        common.write_text(t, encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_DIR=str(REPO / ".git"))  # テストが git の履歴を読む（複製には .git がない）
    out = subprocess.run([sys.executable, "-B", "-c", EVALUATOR], cwd=d, capture_output=True, text=True, env=env, timeout=900)
    try:
        failed = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        failed = ["<evaluator error: %s>" % out.stderr[-200:]]
    row = {"id": ident, "file": filename, "intended": intended, "intended_hit": all(i in failed for i in intended),
           "failed_guard_examples": failed}
    if RUN_TESTS:
        # 変異した実装の束に合わせて lock を作り直す（そうしないと束の再計算の検査が全変異で失敗する）
        subprocess.run([sys.executable, "-B", "scripts/research/evaluate-p1-d.py", "--create-snapshot"], cwd=d, capture_output=True, text=True, env=env, timeout=300)
        counts = {}
        for name, folder in (("tests", "tests"), ("review", "tests/review")):
            t = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", folder], cwd=d, capture_output=True, text=True, env=env, timeout=1800)
            counts[name] = sum(1 for line in t.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")))
        row["existing_test_failures"] = counts
        row["detected_by_existing_tests"] = any(counts.values())
    results.append(row)
    print(ident, filename, "意図した例:", "失敗(検出)" if row["intended_hit"] else "★通過(見逃し)", "| 失敗した例", len(failed),
          "| 既存テスト:", ("検出" if row["detected_by_existing_tests"] else "見逃し") if RUN_TESTS else "-", flush=True)
    shutil.rmtree(d)
(S / "logs" / (("mutation-guards-" + "-".join(args) + ".json") if args else "mutation-guards.json")).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
