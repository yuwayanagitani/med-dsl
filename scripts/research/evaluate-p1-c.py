#!/usr/bin/env python3
"""固定した P1-c 草案の必須パス・API/CLI 再実行・入力保持を照合する。"""

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
from med_dsl.handover import HANDOVER_PROFILE, HANDOVER_SPEC_SHA256
from med_dsl.validation import check_json, decode_json, digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fixtures(manifest_path):
    manifest = decode_json(manifest_path.read_bytes())
    check_json(manifest)
    ids = ["H13", "H14", "H15", "H16", "H17", "H18", "H19"]
    if (manifest.get("schema_version") != "p1-c-manifest-draft-1"
            or manifest.get("status") != "author_draft_snapshot"
            or manifest.get("independent_review") is not False
            or manifest.get("evaluation_frozen") is not False
            or manifest.get("fixture_ids") != ids
            or manifest.get("profile") != HANDOVER_PROFILE
            or manifest.get("profile_spec_sha256") != HANDOVER_SPEC_SHA256):
        raise ValueError("p1_c_author_draft_manifest_required")
    loaded, seen, cases = [], set(), set()
    for entry in manifest["files"]:
        path = (manifest_path.parent / entry["path"]).resolve()
        if path.parent != manifest_path.parent.resolve() or path.suffix != ".json" or path in seen:
            raise ValueError("invalid_or_duplicate_fixture_path")
        seen.add(path)
        if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise ValueError("fixture_hash_or_size_mismatch: " + entry["path"])
        data = decode_json(path.read_bytes())
        check_json(data)
        if (data.get("schema_version") != "p1-fixture-draft-1" or data.get("fictional") is not True
                or data.get("review_state") != "author_draft"
                or data.get("fixture_id") != entry["fixture_id"]
                or data["expected"]["comparison"] != "required_paths" or not data["expected"]["checks"]):
            raise ValueError("invalid_fixture: " + entry["path"])
        cases.add(data["fixture_id"])
        loaded.append((entry, data, path))
    if cases != set(ids) or seen != set(manifest_path.parent.glob("*.json")) - {manifest_path}:
        raise ValueError("case_or_file_inventory_mismatch")
    return loaded


def run(manifest_path, output, include_cli=False):
    fixtures = load_fixtures(manifest_path.resolve())
    records = []
    for entry, data, path in fixtures:
        original = deepcopy(data["request"])
        request = deepcopy(original)
        result = evaluate(request)
        replay = evaluate(deepcopy(original))
        checks = []
        for check in data["expected"]["checks"]:
            actual, exists = result, True
            try:
                for key in check["path"]:
                    actual = actual[key]
            except (KeyError, IndexError, TypeError):
                actual, exists = None, False
            checks.append({**check, "actual": actual, "exists": exists,
                           "passed": exists and digest(actual) == digest(check["equals"])})
        record = {"fixture_id": data["fixture_id"], "path": entry["path"], "raw_sha256": entry["sha256"],
                  "request_sha256": digest(original), "result": result, "checks": checks,
                  "input_preserved": digest(request) == digest(original), "replay_identical": result == replay}
        record["passed"] = all(c["passed"] for c in checks) and record["input_preserved"] and record["replay_identical"]
        if include_cli:
            runs = [subprocess.run([sys.executable, "-m", "med_dsl", "--fixture", str(path)],
                                   capture_output=True, cwd=ROOT,
                                   env=dict(os.environ, PYTHONPATH=str(ROOT / "src"))) for _ in range(2)]
            expected_code = {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}[result["status"]]
            record["cli_matches_api"] = all(p.returncode == expected_code and decode_json(p.stdout) == result for p in runs)
            record["passed"] &= record["cli_matches_api"]
        records.append(record)
    files = sorted([*ROOT.glob("src/med_dsl/*.py"), *ROOT.glob("src/med_dsl/*.json"),
                    *ROOT.glob("tests/*.py"), *ROOT.glob("scripts/research/evaluate-*.py"),
                    ROOT / "docs/research/14-p1-c-contract.md"])
    source_hashes = {str(path.relative_to(ROOT)): sha(path) for path in files}
    cases = {case: all(r["passed"] for r in records if r["fixture_id"] == case)
             for case in sorted({r["fixture_id"] for r in records})}
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
               "manifest_sha256": sha(manifest_path), "native_spec_sha256": HANDOVER_SPEC_SHA256,
               "source_bundle_sha256": digest(source_hashes), "source_hashes": source_hashes,
               "independent_review": False, "evaluation_frozen": False, "cli": include_cli,
               "cases": cases, "files": len(records), "passed_files": sum(r["passed"] for r in records),
               "checks": sum(len(r["checks"]) for r in records),
               "passed_checks": sum(c["passed"] for r in records for c in r["checks"])}
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "source_hashes"}, ensure_ascii=False, sort_keys=True))
    return all(cases.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/p1-c/latest")
    args = parser.parse_args()
    raise SystemExit(0 if run(ROOT / "examples/p1-c/manifest.json", args.output, args.cli) else 1)
