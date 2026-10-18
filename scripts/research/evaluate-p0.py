#!/usr/bin/env python3
"""固定した作成者草案 P01〜P22 の照合・再実行・環境を記録する。"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.model import PROFILE, Problem
from med_dsl.validation import check_json, decode_json, digest


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def load_fixtures(manifest_path):
    manifest = decode_json(manifest_path.read_bytes())
    check_json(manifest)
    if (manifest.get("schema_version") != "p0-fixture-manifest-draft-1"
            or manifest.get("status") != "author_draft_snapshot"
            or manifest.get("independent_review") is not False
            or manifest.get("evaluation_frozen") is not False):
        raise ValueError("author_draft_manifest_required")
    expected_ids = [f"P{i:02}" for i in range(1, 23)]
    if manifest["fixture_ids"] != expected_ids:
        raise ValueError("all_22_case_ids_required")
    loaded, seen, cases = [], set(), set()
    for entry in manifest["files"]:
        path = (manifest_path.parent / entry["path"]).resolve()
        if path.parent != manifest_path.parent.resolve() or path.suffix != ".json" or path in seen:
            raise ValueError("invalid_or_duplicate_fixture_path")
        seen.add(path)
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or sha256(raw) != entry["sha256"]:
            raise ValueError("fixture_hash_or_size_mismatch: " + entry["path"])
        data = decode_json(raw)
        check_json(data)
        if (data.get("schema_version") != "p0-fixture-draft-1" or data.get("fictional") is not True
                or data.get("review_state") != "author_draft" or data.get("fixture_id") != entry["fixture_id"]
                or data["expected"]["comparison"] != "required_paths" or not data["expected"]["checks"]):
            raise ValueError("invalid_fixture: " + entry["path"])
        cases.add(data["fixture_id"])
        loaded.append((entry, data, path))
    if cases != set(expected_ids):
        raise ValueError("all_22_case_files_required")
    return loaded


def _checks(result, expected):
    checks = []
    for check in expected:
        actual, exists = result, True
        try:
            for key in check["path"]:
                actual = actual[key]
        except (KeyError, IndexError, TypeError):
            actual, exists = None, False
        checks.append({"path": check["path"], "expected": check["equals"], "actual": actual,
                       "exists": exists, "passed": exists and digest(actual) == digest(check["equals"])})
    return checks


def _cli(path):
    process = subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)],
                             capture_output=True, env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), cwd=ROOT)
    return process.returncode, decode_json(process.stdout)


def run(manifest_path, output, include_cli=False):
    # 全ファイルの照合を先に完了する。変更された期待値を使って途中まで評価しない。
    fixtures = load_fixtures(manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    records, results = [], {}
    for entry, data, path in fixtures:
        original = deepcopy(data["request"])
        request = deepcopy(original)
        result = evaluate(request)
        replay = evaluate(deepcopy(original))
        checks = _checks(result, data["expected"]["checks"])
        record = {"fixture_id": data["fixture_id"], "path": entry["path"], "raw_sha256": entry["sha256"],
                  "request_sha256": digest(original), "checks": checks,
                  "input_preserved": request == original, "replay_identical": result == replay}
        record["passed"] = all(c["passed"] for c in checks) and record["input_preserved"] and record["replay_identical"]
        if include_cli:
            code, cli_result = _cli(path)
            replay_code, cli_replay = _cli(path)
            expected_code = {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}[result["status"]]
            record["cli"] = {"exit_code": code, "matches_api": cli_result == result,
                             "replay_identical": code == replay_code and cli_result == cli_replay,
                             "expected_exit_code": expected_code}
            record["passed"] &= code == expected_code and record["cli"]["matches_api"] and record["cli"]["replay_identical"]
        target = output / (path.stem + "-result.json")
        target.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        record["result_sha256"] = sha256(target.read_bytes())
        records.append(record)
        results[path.name] = result
    first = deepcopy(results["reproducibility-original.json"])
    second = deepcopy(results["reproducibility-reordered.json"])
    relations = {"P22_different_input_hashes": first.pop("input_sha256") != second.pop("input_sha256"),
                 "P22_equal_results_except_input_hash": first == second}
    cases = [{"id": f"P{i:02}", "passed": all(r["passed"] for r in records if r["fixture_id"] == f"P{i:02}")}
             for i in range(1, 23)]
    cases[-1]["passed"] &= all(relations.values())
    sources = {str(p.relative_to(ROOT)): sha256(p.read_bytes())
               for folder in ("src/med_dsl", "tests") for p in sorted((ROOT / folder).glob("*.py"))}
    sources[str(Path(__file__).relative_to(ROOT))] = sha256(Path(__file__).read_bytes())
    report = {"schema_version": "p0-evaluation-draft-1", "evaluation_kind": "author_draft_engineering",
              "recorded_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "profile": PROFILE, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "manifest_sha256": sha256(manifest_path.read_bytes()),
              "contract_sha256": sha256((ROOT / "docs/research/06-p0-contract.md").read_bytes()),
              "source_files": sources, "source_bundle_sha256": digest(sources),
              "fixtures": records, "cases": cases, "relations": relations,
              "case_count": len(cases), "cases_passed": sum(c["passed"] for c in cases),
              "fixture_count": len(records), "fixtures_passed": sum(r["passed"] for r in records),
              "checks_passed": sum(c["passed"] for r in records for c in r["checks"]),
              "checks_total": sum(len(r["checks"]) for r in records),
              "independent_review": False, "evaluation_frozen": False}
    (output / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "examples/p0/manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/p0-d")
    parser.add_argument("--cli", action="store_true", help="CLI との一致・終了コード・再実行も照合")
    args = parser.parse_args()
    try:
        report = run(args.manifest, args.output, args.cli)
    except (Problem, OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({key: report[key] for key in ("source_commit", "cases_passed", "case_count", "fixtures_passed",
                                                  "fixture_count", "checks_passed", "checks_total", "source_bundle_sha256")}, indent=2))
    return 0 if report["cases_passed"] == 22 else 1


if __name__ == "__main__":
    sys.exit(main())
