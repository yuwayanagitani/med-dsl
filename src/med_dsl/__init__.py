"""研究用 P0 ライブラリ。実装した断片以外の意味を推測しない。"""

from .model import PROFILE, Problem
from .definitions import check_extension
from .query import run_query
from .validation import check_json, validate_extension, validate_header, validate_query

__all__ = ["evaluate"]


def evaluate(request):
    fingerprint = None
    try:
        fingerprint = check_json(request)
        validate_header(request)
        if request["operation"] == "check_extension":
            response = check_extension(request, *validate_extension(request))
        elif request["operation"] == "query":
            packages = validate_query(request)
            response = run_query(request, packages)
        else:
            raise Problem("operation_not_implemented", "operation", "unsupported_profile")
    except Problem as problem:
        response = {"status": problem.status, "reason_codes": [problem.code],
                    "error_path": problem.path, "incomplete": ["request"]}
    return {"schema_version": "p0-result-draft-1", "profile": PROFILE,
            "input_sha256": fingerprint, **response}
