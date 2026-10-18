"""JSON の読み書きだけを担当する CLI。期待結果を evaluate に渡さない。"""

import argparse
import json
from pathlib import Path
import sys

from . import evaluate
from .model import MAX_BYTES, PROFILE, Problem
from .validation import decode_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="研究用 P0 / P1-a の JSON 問い合わせ")
    parser.add_argument("file", nargs="?", default="-", help="request JSON または - (標準入力)")
    parser.add_argument("--fixture", action="store_true", help="草案例から request のみを読む")
    args = parser.parse_args(argv)
    try:
        if args.file == "-":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with Path(args.file).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        request = decode_json(raw)
        if args.fixture:
            if (type(request) is not dict
                    or request.get("schema_version") not in ("p0-fixture-draft-1", "p1-fixture-draft-1")
                    or type(request.get("request")) is not dict):
                raise Problem("invalid_fixture")
            request = request["request"]
        result = evaluate(request)
    except (Problem, OSError) as problem:
        if isinstance(problem, Problem):
            status, code, path = problem.status, problem.code, problem.path
        else:
            status, code, path = "invalid_input", "input_io_error", "$"
        result = {"schema_version": "p0-result-draft-1", "profile": PROFILE,
                  "input_sha256": None, "status": status, "reason_codes": [code],
                  "error_path": path, "incomplete": ["request"]}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                indent=2, allow_nan=False) + "\n")
    return {"ok": 0, "invalid_input": 2, "unsupported_profile": 3, "resource_limit": 4}[result["status"]]
