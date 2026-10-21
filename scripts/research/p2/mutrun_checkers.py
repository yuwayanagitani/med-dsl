"""P2-d の検査器（共通部品 p2_checks.py、統合評価 evaluate-p2.py、版の比較）自体の変異検査。
各変異で、検査器の判定を一つ壊し、対応するテストモジュールが失敗するか（検出）を記録する。変異後の木では固定対象の台帳を
作り直す（検査器のファイルは固定対象なので、作り直さないと台帳の不一致だけで失敗し、検出の判定にならない）。
最初の行 Z0 は変異のない対照で、実行器の環境が正しいこと（失敗 0）を確かめる。
使い方: python3 -B scripts/research/p2/mutrun_checkers.py [ID ...]（環境変数 P2_REPO＝作業ツリー、P2_SCRATCH＝作業場所）"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
S = Path(os.environ.get("P2_SCRATCH") or tempfile.mkdtemp(prefix="p2-mutation-"))
(S / "logs").mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]

BUDGET, VERSIONS, EVALUATE = "tests.p2.test_budget_contract", "tests.p2.test_versions", "tests.p2.test_evaluate_p2"
REGENERATED = "tests.p2.test_quantity_version"
CHECKS, EVAL = "scripts/research/p2_checks.py", "scripts/research/evaluate-p2.py"

# (id, ファイル（リポジトリ相対）, 旧, 新, 実行するテストモジュール, 備考)
M = [
    ("Z0", CHECKS, "BUDGET_DEPENDENT_REFUSALS", "BUDGET_DEPENDENT_REFUSALS", [BUDGET], "対照：変異なし"),
    # ---- 予算の不変条件 ----
    ("B01", CHECKS, '    if full["status"] == "resource_limit":', '    if False:', [BUDGET], ""),
    ("B02", CHECKS, 'if result["status"] != "resource_limit" or contains_value(result, "certified"):', 'if result["status"] != "resource_limit":', [BUDGET], ""),
    ("B03", CHECKS, '            if name in BUDGET_DEPENDENT_REFUSALS:', '            if True:', [BUDGET], ""),
    ("B04", CHECKS, 'same = same or (result["status"] == "resource_limit" and result.get("reason_codes") == ["step_limit"])', 'same = True', [BUDGET], ""),
    ("B05", CHECKS, '            if without_input_hash(result) != without_input_hash(full):', '            if False:', [BUDGET], ""),
    ("B06", CHECKS, '        if done_at is not None:', '        if False:', [BUDGET], ""),
    ("B07", CHECKS, '        if result["status"] != "resource_limit":', '        if False:', [BUDGET], ""),
    ("B08", CHECKS, '        if contains_value(result, "certified"):', '        if False:', [BUDGET], ""),
    ("B09", CHECKS, '                    if any(row.get(field) for field in VALUE_FIELDS):', '                    if False:', [BUDGET], ""),
    ("B10", CHECKS, '                elif row != full_row:', '                elif False:', [BUDGET], ""),
    ("B11", CHECKS, 'any("step_limit" in code for code in (row.get("reason_codes") or []))', 'any(code == "step_limit" for code in (row.get("reason_codes") or []))', [BUDGET], ""),
    ("B12", CHECKS, '    for budget in range(0, min(used + 3, limit)):', '    for budget in range(0, min(used, limit)):', [BUDGET], ""),
    ("B13", CHECKS, '            if run(used)["status"] == "ok":', '            if False:', [BUDGET], ""),
    ("B14", CHECKS, '    if full["status"] != "ok":', '    if False:', [BUDGET], ""),
    ("B15", CHECKS, ', "leaf_candidates", "information_requests",\n', ', "leaf_candidates",\n', [BUDGET], ""),
    ("B16", CHECKS, 'BUDGET_DEPENDENT_REFUSALS = {"p1-a/unnormalized.json": "forecast_spec.json: 重みの加算と正規化の比較は課金される"}', 'BUDGET_DEPENDENT_REFUSALS = {}', [BUDGET], ""),
    ("B17", CHECKS, '"projection_evidence", "source_evidence",\n                "relation_set", "certain_relation", "context_differences", "endpoints", "comparison_evidence",\n                "selection", "elements", "requests", "output", "flows"))', '"projection_evidence", "source_evidence",\n                "selection", "elements", "requests", "output", "flows"))', ["tests.p2.test_longitudinal"], "縦断比較（P2-m）の未完了行の値の検査（空配列・falseも漏れとして扱う）"),
    ("B18", CHECKS, '"comparison_evidence",\n                "selection", "elements", "requests", "output", "flows"))', '"comparison_evidence"))', ["tests.p2.test_library"], "薄い臨床ライブラリ（P2-o）の未完了行の値の検査（空配列・空のobject・falseも漏れとして扱う）"),
    # ---- 版の比較：分類と正規化 ----
    ("C01", CHECKS, '    if a == b:\n        return "identical"', '    if True:\n        return "identical"', [VERSIONS], ""),
    ("C02", CHECKS, '[0] in refusal_codes and embeds_pin(request, mapping):', '[0] in refusal_codes:', [VERSIONS], ""),
    ("C03", CHECKS, '(b.get("reason_codes") or [None])[0] in refusal_codes and', 'True and', [VERSIONS], ""),
    ("C04", CHECKS, '    if b.get("status") in refusal_statuses and', '    if True and', [VERSIONS], ""),
    ("C05", CHECKS, 'for k, v in value.items() if k not in dropped}', 'for k, v in value.items() if True}', [VERSIONS], ""),
    ("C06", CHECKS, '    if isinstance(value, str) and HEX64.match(value):', '    if False:', [VERSIONS], ""),
    ("C07", CHECKS, 'return mapping.get(value, value) if isinstance(value, str) else value', 'return value', [VERSIONS], ""),
    ("C08", CHECKS, '            if key not in a or key not in b:', '            if key not in a:', [VERSIONS], ""),
    ("C09", CHECKS, 'found += diff_paths(x, y, f"{path}[]")', 'found += diff_paths(x, y, path)', [VERSIONS], ""),
    ("C11", CHECKS, '    if parsed is not None:', '    if False:', [VERSIONS], ""),
    ("C10", CHECKS, '    return any(value in text for value in pins)', '    return True', [VERSIONS], ""),
    # ---- 版の比較：記録との照合 ----
    ("R01", CHECKS, '        if got != want:\n            problems.append(f"reproduction_{side}")', '        if False:\n            problems.append(f"reproduction_{side}")', [VERSIONS], ""),
    ("R02", CHECKS, '    if report["pins_changed"] != sorted(record["pins_changed"]):', '    if False:', [VERSIONS], ""),
    ("R03", CHECKS, '        if {k: len(v) for k, v in before.items()} != measured["old_inputs_without_repin"]:', '        if False:', [VERSIONS], ""),
    ("R04", CHECKS, '        if len(after["identical"]) != measured["repinned"]["identical"] or len(after["failing_old_expectations"]) != measured["repinned"]["failing_old_expectations"]:', '        if False:', [VERSIONS], ""),
    ("R05", CHECKS, '        if observed != declared_paths:', '        if False:', [VERSIONS], ""),
    ("R06", CHECKS, '        if set(before["changed"]) - declared_inputs:', '        if False:', [VERSIONS], ""),
    ("R07", CHECKS, '        if len(part["carry_added_field"]) != measured["carry_added_field"]:', '        if False:', [VERSIONS], ""),
    ("R08", CHECKS, '    for side in [s for s in ("to", "current") if s in report]:', '    for side in [s for s in ("to",) if s in report]:', [VERSIONS], ""),
    ("V01", CHECKS, 'sorted(n for n in requests if failed_checks(again[n], fixtures[n]["expected"]["checks"]))', '[]', [VERSIONS], ""),
    ("V02", CHECKS, '            again = evaluate_tree(tree, repinned)', '            again = evaluate_tree(tree, requests)', [VERSIONS], ""),
    ("V03", CHECKS, '        mapping = {old_pins[n]: new_pins[n] for n in PIN_NAMES if old_pins[n] != new_pins[n]}', '        mapping = {}', [VERSIONS], ""),
    ("V04", CHECKS, 'dropped = {c["path"] for c in record["declared_changes"] if c["kind"] == "added_field"}', 'dropped = set()', [VERSIONS], ""),
    ("V05", CHECKS, 'any(contains_key(again[n], key) for key in dropped)', 'any(contains_key(new[n], key) for key in dropped)', [VERSIONS], ""),
    ("V06", "scripts/research/compare-versions.py", '    return 0 if not problems else 1\n\n\nif __name__', '    return 0\n\n\nif __name__', [VERSIONS], ""),
    ("V07", "scripts/research/compare-versions.py", '            return 2', '            return 0', [VERSIONS], ""),
    # ---- P2 の拡張の版の更新：再生成した入力の比較の判定（P2-l） ----
    ("G01", CHECKS, '    if report["old_inputs_without_regeneration"]["changed"]:', '    if False:', [REGENERATED], ""),
    ("G02", CHECKS, '    if report["request_changed"]:', '    if False:', [REGENERATED], ""),
    ("G03", CHECKS, '    if set(report["expectation_changed"]) != declared:', '    if False:', [REGENERATED], ""),
    ("G04", CHECKS, '    if set(report["result_differences"]) != declared:', '    if False:', [REGENERATED], ""),
    ("G05", CHECKS, '        if name in prefixes and any(not allowed_difference(path, prefixes[name]) for path in paths):', '        if False:', [REGENERATED], ""),
    ("G06", CHECKS, '    if report["steps_changed"]:', '    if False:', [REGENERATED], ""),
    ("G07", CHECKS, '    if set(report["inputs"]["added"]) != added or report["inputs"]["removed"]:', '    if False:', [REGENERATED], ""),
    ("G08", CHECKS, '    if report["pins_changed"] != sorted(p["file"] for p in record["pins"]):', '    if False:', [REGENERATED], ""),
    ("G09", CHECKS, '        if report["reproduction"] and report["reproduction"][side] != record[side]["evaluation"]:', '        if False:', [REGENERATED], ""),
    ("G10", CHECKS, '    if any(report["substituted"].get(n) == "ok" for n in report["substituted"] if not n.startswith(tuple(record["pure_pin_suites"]))):', '    if False:', [REGENERATED], ""),
    ("G11", CHECKS, '    if report["affected"]["extensions"] != sorted(predicted["extensions"]) or report["affected"]["regenerate"] != report["affected"]["predicted_regenerate"]:', '    if False:', [REGENERATED], ""),
    ("G12", CHECKS, '    if sorted(set(report["necessary_repin"]) - listed) != sorted(measured["unpredicted_repin"]):', '    if False:', [REGENERATED], ""),
    ("G13", CHECKS, '    if (report["inputs"]["old"], report["inputs"]["new"]) != (measured["inputs"]["old"], measured["inputs"]["new"]):', '    if False:', [REGENERATED], ""),
    ("G14", CHECKS, '    if {k: len(v) for k, v in report["old_inputs_without_regeneration"].items()} != measured["old_inputs_without_regeneration"]:', '    if False:', [REGENERATED], ""),
    # ---- 統合評価 ----
    ("E01", EVAL, '        if got != want:\n            found.append(f"extensions.{key}")', '        if False:\n            found.append(f"extensions.{key}")', [EVALUATE], ""),
    ("E02", EVAL, '    if budget["violations"]:', '    if False:', [EVALUATE], ""),
    ("E03", EVAL, '        if report["base"][key] != want:', '        if False:', [EVALUATE], ""),
    ("E04", EVAL, '    if not report["base"]["passed"]:', '    if False:', [EVALUATE], ""),
    ("E05", EVAL, '        if got["examples"] != want["examples"] or got["checks"] != want["checks"] or got["failures"]:', '        if got["failures"]:', [EVALUATE], ""),
    ("E06", EVAL, '    if base_report()["manifest_sha256"] != report["base"]["manifest_sha256"]:', '    if False:', [EVALUATE], ""),
    ("E07", EVAL, '        if entry["status"] == "failed":', '        if False:', [EVALUATE], ""),
    ("E08", EVAL, '    if not output.is_relative_to((ROOT / "data/research/p2-d").resolve()):', '    if False:', [EVALUATE], ""),
    ("E09", EVAL, 'if budget["requests"] != EXPECTED["budget"]["requests"] or budget["evaluations"] != EXPECTED["budget"]["budget_evaluations"]:', 'if False:', [EVALUATE], ""),
    ("E10", EVAL, '    if budget["allowed_budget_dependent_refusals"] != EXPECTED["budget"]["allowed_budget_dependent_refusals"]:', '    if False:', [EVALUATE], ""),
    ("E11", EVAL, '    report["passed"] = not report["mismatches"]', '    report["passed"] = True', [EVALUATE], ""),
    ("E12", EVAL, '"independent_review": False, "evaluation_frozen": False}', '"independent_review": False, "evaluation_frozen": True}', [EVALUATE], ""),
    ("E13", EVAL, '    return 0 if report["passed"] else 1', '    return 0', [EVALUATE], ""),
    ("E14", EVAL, '        reports.append({"record": relative, "status": "not_run"', '        reports.append({"record": relative, "status": "passed"', [EVALUATE], ""),
]

if __name__ == "__main__":
    results = []
    for (ident, rel, old, new, modules, note) in M:
        if args and ident not in args:
            continue
        d = S / "mutchecker" / ident
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for sub in ("src", "tests", "examples", "scripts", "extensions"):
            shutil.copytree(REPO / sub, d / sub, ignore=shutil.ignore_patterns("__pycache__"))
        (d / "docs").mkdir()
        shutil.copytree(REPO / "docs/research", d / "docs/research")
        os.symlink(REPO / ".git", d / ".git")                     # 版の比較が git の履歴を読む
        path = d / rel
        text = path.read_text(encoding="utf-8")
        if old != new and text.count(old) != 1:
            results.append({"id": ident, "error": f"置換元が {text.count(old)} 件"})
            print(ident, "★置換元が %d 件" % text.count(old), flush=True)
            shutil.rmtree(d)
            continue
        path.write_text(text.replace(old, new), encoding="utf-8")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        snap = subprocess.run([sys.executable, "-B", "scripts/research/evaluate-p1-d.py", "--create-snapshot"], cwd=d, capture_output=True, text=True, env=env)
        row = {"id": ident, "file": rel, "note": note, "snapshot_ok": snap.returncode == 0}
        failures = {}
        for module in modules:
            t = subprocess.run([sys.executable, "-B", "-m", "unittest", module], cwd=d, capture_output=True, text=True, env=env, timeout=1800)
            failures[module] = sum(1 for line in t.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:")))
        row["failures"] = failures
        row["detected"] = any(failures.values())
        results.append(row)
        print(ident, rel.split("/")[-1], "再固定", "OK" if row["snapshot_ok"] else "★失敗", "| 失敗", sum(failures.values()), "|", "検出" if row["detected"] else "未検出", "|", note, flush=True)
        shutil.rmtree(d)
    name = "mutation-checkers-" + "-".join(args) + ".json" if args else "mutation-checkers.json"
    (S / "logs" / name).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
