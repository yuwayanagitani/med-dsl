#!/usr/bin/env python3
"""固定した全 P1 条件と P0 回帰を照合する。期待結果の自動更新はしない。"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.model import Problem
from med_dsl.validation import canonical_bytes, check_json, decode_json, digest

LOCK = "examples/p1-evaluation/manifest.json"
SUITES = {
    "p0": ([f"P{i:02}" for i in range(1, 23)], 37, 221),
    "p1-a": ([f"H{i:02}" for i in [1, 2, 3, 4, 5, 6, 20]], 31, 141),
    "p1-b": ([f"H{i:02}" for i in range(7, 13)], 22, 150),
    "p1-c": ([f"H{i:02}" for i in range(13, 20)], 27, 126),
}
CONTRACTS = ["06-p0-contract", "11-p1-contract", "11-p1-cases", "12-p1-a-contract",
             "13-p1-b-contract", "14-p1-c-contract", "15-p1-d-contract", "23-p2-b-design", "25-p2-c-design",
             "31-p2-e-design", "32-p2-e-cases", "34-p2-f-design", "35-p2-f-cases", "37-p2-g-design", "38-p2-g-cases", "40-p2-h-design", "41-p2-h-cases", "43-p2-i-design", "44-p2-i-cases", "46-p2-j-design", "47-p2-j-cases", "50-p2-k-design", "51-p2-k-cases", "53-p2-l-design", "54-p2-l-cases", "56-p2-m-design", "57-p2-m-cases", "59-p2-n-design", "60-p2-n-cases", "63-p2-o-design", "64-p2-o-cases", "67-p2-p-design", "68-p2-p-cases", "70-p2-q-design", "71-p2-q-cases", "73-p2-r-design", "74-p2-r-cases"]
MODES = {**{f"H{i:02}": "typed_forecast" for i in range(1, 7)},
         **{f"H{i:02}": "finite_event_support" for i in range(7, 13)},
         "H13": "first_order_reference", "H14": "first_order_reference",
         "H15": "absence_policy_change", "H16": "checked_event_template",
         "H17": "projection_scope", "H18": "first_order_reference",
         "H19": "replay_inventory_and_separate_handover", "H20": "resource_boundary"}


# P2-a：拡張の宣言と、宣言が根拠として引く実体（防護例・検査・オラクル・登録の入口）。
# scripts/research/audit-preservation.py は lock の hash を定数に持つので、載せると循環する（載せない）。
EXTENSION_PATTERNS = ("extensions/*.json", "examples/p2/*.json", "examples/p2-split/*.json", "examples/p2-splits/*.json", "examples/p2-temporal/*.json", "examples/p2-quantity/*.json", "examples/p2-measurement/*.json", "examples/p2-display/*.json", "examples/p2-temporal-measurement/*.json", "examples/p2-temporal-display/*.json", "examples/p2-refinement/*.json", "examples/p2-longitudinal/*.json", "examples/p2-library/*.json", "examples/p2-grounding/*.json", "examples/p2-observation/*.json", "examples/review/*.json", "tests/review/*.py",
                      "tests/p2/*.py", "tests/audits/*.py", "scripts/research/check-extensions.py",
                      # P2-d：統合評価が使う共通部品、版の比較、版の記録、独立確認の資料（変異表・生成器・前後比較）
                      "scripts/research/p2_checks.py", "scripts/research/compare-versions.py", "scripts/research/p2/*.py",
                      "examples/p2-versions/*.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    """閉じた対象一覧。lock 自体と結果文書を除き、自己ハッシュの循環を避ける。"""
    paths = {root / f"docs/research/{name}.md" for name in CONTRACTS}
    for pattern in ("src/med_dsl/*.py", "src/med_dsl/*.json", "tests/*.py",
                    "scripts/research/evaluate-*.py", "examples/p1/*.json",
                    *(f"examples/{name}/*.json" for name in SUITES), *EXTENSION_PATTERNS):
        paths.update(root.glob(pattern))
    return sorted(str(path.relative_to(root)) for path in paths)


def build_manifest(root=ROOT):
    """明示的な固定操作専用。run は呼ばない。既存の期待結果は変更しない。"""
    paths = inventory(root)
    hashes = {name: {"sha256": sha(root / name), "bytes": (root / name).stat().st_size} for name in paths}
    suites = {name: {"manifest": f"examples/{name}/manifest.json", "case_ids": ids,
                     "files": count, "checks": checks} for name, (ids, count, checks) in SUITES.items()}
    cases = [{"id": case, "suite": next(name for name, (ids, _, _) in SUITES.items() if case in ids),
              "meaning_mode": MODES[case]} for case in sorted(MODES)]
    return {"schema_version": "p1-integrated-snapshot-draft-1", "status": "author_draft_snapshot",
            "independent_review": False, "evaluation_frozen": False,
            "suites": suites, "cases": cases, "files": hashes, "bundle_sha256": digest(hashes)}


def _module(name, root):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), root / f"scripts/research/evaluate-{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_checks(data):
    checks = data["expected"]["checks"]
    seen = set()
    for item in checks:
        path = item["path"]
        if (set(item) != {"path", "equals"} or type(path) is not list or not path
                or any(type(key) not in (str, int) or (type(key) is int and key < 0) for key in path)):
            raise ValueError("invalid_required_path")
        key = canonical_bytes(path)
        if key in seen:
            raise ValueError("duplicate_required_path")
        seen.add(key)


def preflight(root=ROOT, snapshot=None):
    """全実体を確認してから既存 loader を使う。計算・結果出力はまだ行わない。"""
    lock_path = root / LOCK
    raw = lock_path.read_bytes() if snapshot is None else (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode()
    lock = decode_json(raw)
    check_json(lock)
    expected = build_manifest(root)
    # 実体から再構成した台帳と完全一致。欠落・追加・意味層の混同も拒否する。
    if canonical_bytes(lock) != canonical_bytes(expected):
        raise ValueError("snapshot_mismatch: review changes and explicitly create a new snapshot")
    for name in lock["files"]:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("snapshot_path_outside_root")
    loaded = {}
    for name, (ids, count, checks) in SUITES.items():
        manifest = root / f"examples/{name}/manifest.json"
        fixtures = _module(name, root).load_fixtures(manifest)
        if ({path.resolve() for _, _, path in fixtures}
                != set(manifest.parent.glob("*.json")) - {manifest}):
            raise ValueError("fixture_inventory_mismatch: " + name)
        if (len(fixtures) != count or sum(len(data["expected"]["checks"]) for _, data, _ in fixtures) != checks
                or {data["fixture_id"] for _, data, _ in fixtures} != set(ids)):
            raise ValueError("suite_denominator_mismatch: " + name)
        for _, data, _ in fixtures:
            _validate_checks(data)
        loaded[name] = fixtures
    design = root / "examples/p1/manifest.json"
    design_manifest = decode_json(design.read_bytes())
    for entry in design_manifest["files"] + design_manifest["dependencies"]:
        path = (design.parent / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != entry["sha256"]:
            raise ValueError("design_dependency_mismatch")
        if "bytes" in entry and path.stat().st_size != entry["bytes"]:
            raise ValueError("design_size_mismatch")
    return lock, hashlib.sha256(raw).hexdigest(), loaded


def check_paths(result, expected):
    checks = []
    for item in expected:
        actual, exists = result, True
        for key in item["path"]:
            if ((type(actual) is dict and type(key) is str and key in actual)
                    or (type(actual) is list and type(key) is int and 0 <= key < len(actual))):
                actual = actual[key]
            else:
                actual, exists = None, False
                break
        checks.append({"path": item["path"], "expected": item["equals"], "actual": actual,
                       "exists": exists, "passed": exists and canonical_bytes(actual) == canonical_bytes(item["equals"])})
    return checks


def evaluate_fixture(name, entry, data, path, include_cli):
    original = deepcopy(data["request"])
    request = deepcopy(original)
    result = evaluate(request)
    replay = evaluate(deepcopy(original))
    checks = check_paths(result, data["expected"]["checks"])
    record = {"suite": name, "fixture_id": data["fixture_id"], "path": str(path.relative_to(ROOT)),
              "raw_sha256": entry["sha256"], "request_sha256": digest(original), "result": result,
              "checks": checks, "input_preserved": canonical_bytes(request) == canonical_bytes(original),
              "replay_identical": canonical_bytes(result) == canonical_bytes(replay)}
    record["passed"] = all(c["passed"] for c in checks) and record["input_preserved"] and record["replay_identical"]
    if include_cli:
        runs = [subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)],
                              capture_output=True, cwd=ROOT,
                              env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), timeout=30) for _ in range(2)]
        expected_code = {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}[result["status"]]
        record["cli_matches_api"] = all(p.returncode == expected_code and canonical_bytes(decode_json(p.stdout))
                                        == canonical_bytes(result) for p in runs)
        record["passed"] &= record["cli_matches_api"]
    return record


def summarize(records, lock):
    grouped = {name: [r for r in records if r["suite"] == name] for name in SUITES}
    suites = {}
    for name, (ids, count, checks) in SUITES.items():
        rows = grouped[name]
        cases = {case: bool(members := [r for r in rows if r["fixture_id"] == case])
                 and all(r["passed"] for r in members) for case in ids}
        suites[name] = {"cases": cases, "files": len(rows), "passed_files": sum(r["passed"] for r in rows),
                        "checks": sum(len(r["checks"]) for r in rows),
                        "passed_checks": sum(c["passed"] for r in rows for c in r["checks"])}
        if len(rows) != count or suites[name]["checks"] != checks:
            raise ValueError("incomplete_suite_results: " + name)
    p22 = {Path(r["path"]).name: deepcopy(r["result"]) for r in grouped["p0"] if r["fixture_id"] == "P22"}
    left, right = p22["reproducibility-original.json"], p22["reproducibility-reordered.json"]
    relations = {"P22_different_input_hashes": left.pop("input_sha256") != right.pop("input_sha256"),
                 "P22_equal_results_except_input_hash": canonical_bytes(left) == canonical_bytes(right)}
    suites["p0"]["cases"]["P22"] &= all(relations.values())
    cases = [{**case, "passed": suites[case["suite"]]["cases"][case["id"]]} for case in lock["cases"]]
    return {"p1_cases": cases, "p1_cases_passed": sum(c["passed"] for c in cases), "p1_case_count": 20,
            "p1_files": sum(suites[n]["files"] for n in SUITES if n != "p0"),
            "p1_checks": sum(suites[n]["checks"] for n in SUITES if n != "p0"),
            "suites": suites, "p0_relations": relations,
            "passed": all(all(s["cases"].values()) for s in suites.values())}


def run(output, include_cli=False):
    # 固定対象への上書きを防ぎ、全件照合後に一つの記録だけを発行する。
    output = output.resolve()
    if not output.is_relative_to((ROOT / "data/research/p1-d").resolve()):
        raise ValueError("output_must_be_under_data_research_p1_d")
    lock, lock_sha, fixtures = preflight()
    records = [evaluate_fixture(name, entry, data, path, include_cli)
               for name, rows in fixtures.items() for entry, data, path in rows]
    summary = summarize(records, lock)
    # CLI 実行中を含むディスクの変更を成功記録として残さない。
    _, final_sha, _ = preflight()
    if final_sha != lock_sha:
        raise ValueError("snapshot_changed_during_evaluation")
    report = {"schema_version": "p1-integrated-evaluation-draft-1", "evaluation_kind": "author_draft_engineering",
              "recorded_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "manifest_sha256": lock_sha, "bundle_sha256": lock["bundle_sha256"],
              "independent_review": False, "evaluation_frozen": False, "cli": include_cli,
              "summary": summary, "records": records}
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "results.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output / "results.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/p1-d/latest")
    parser.add_argument("--create-snapshot", action="store_true", help="変更確認後に作成者草案の実体を明示的に固定する（評価しない）")
    args = parser.parse_args()
    try:
        if args.create_snapshot:
            lock = build_manifest()
            preflight(snapshot=lock)
            path = ROOT / LOCK
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({"manifest_sha256": sha(path), "bundle_sha256": lock["bundle_sha256"]}))
            return 0
        report = run(args.output, args.cli)
        print(json.dumps({"p1_cases_passed": report["summary"]["p1_cases_passed"],
                          "p1_files": report["summary"]["p1_files"], "p1_checks": report["summary"]["p1_checks"],
                          "p0": report["summary"]["suites"]["p0"], "bundle_sha256": report["bundle_sha256"],
                          "passed": report["summary"]["passed"]}, ensure_ascii=False))
        return 0 if report["summary"]["passed"] else 1
    except (Problem, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
