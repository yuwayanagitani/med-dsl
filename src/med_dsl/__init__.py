"""研究用 P0 / P1-a。実装した断片以外の意味を推測しない。"""

from .model import PROFILE, Problem
from .definitions import check_extension
from .compare import run_compare
from .query import run_query
from .validation import check_json, validate_compare, validate_extension, validate_header, validate_query
from .forecast import FORECAST_PROFILE, run_forecast

__all__ = ["evaluate"]


def evaluate(request):
    fingerprint = None
    is_forecast = type(request) is dict and request.get("schema_version") == "p1-request-draft-1"
    try:
        fingerprint = check_json(request)
        if is_forecast:
            response = run_forecast(request)
        else:
            validate_header(request)
            if request["operation"] == "check_extension":
                response = check_extension(request, *validate_extension(request))
            elif request["operation"] == "query":
                packages = validate_query(request)
                response = run_query(request, packages)
            else:
                response = run_compare(request, *validate_compare(request))
    except Problem as problem:
        response = {"status": problem.status, "reason_codes": [problem.code],
                    "error_path": problem.path, "incomplete": ["request"]}
    return {"schema_version": "p1-result-draft-1" if is_forecast else "p0-result-draft-1",
            "profile": FORECAST_PROFILE if is_forecast else PROFILE,
            "input_sha256": fingerprint, **response}
