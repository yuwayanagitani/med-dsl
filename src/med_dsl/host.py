"""最上位のホスト：schema_version から処理を一つ選び、結果の包み（schema・profile・入力の hash・certifier）を付ける。
どれにも当たらない要求は P0（既定）として扱う。ここに登録のない処理を追加しない。"""

from typing import Callable, NamedTuple

from .compare import run_compare
from .definitions import check_extension
from .display import DISPLAY_PROFILE, run_displays
from .events import EVENT_PROFILE, run_events
from .forecast import FORECAST_PROFILE, run_forecast
from .handover import HANDOVER_PROFILE, run_handover
from .identity import attach_certifier
from .measurement import MEASUREMENT_PROFILE, run_measurements
from .model import PROFILE, Problem
from .quantity import QUANTITY_PROFILE, run_quantities
from .query import run_query
from .split import SPLIT_PROFILE, run_split
from .splits import SPLITS_PROFILE, run_splits
from .temporal import TEMPORAL_PROFILE, run_temporal
from .validation import check_json, validate_compare, validate_extension, validate_header, validate_query


class Surface(NamedTuple):
    request_schema: str
    result_schema: str
    profile: str
    run: Callable


def run_p0(request):
    validate_header(request)
    if request["operation"] == "check_extension":
        return check_extension(request, *validate_extension(request))
    if request["operation"] == "query":
        packages = validate_query(request)
        return run_query(request, packages)
    return run_compare(request, *validate_compare(request))


P0 = Surface("p0-request-draft-1", "p0-result-draft-1", PROFILE, run_p0)
SURFACES = {s.request_schema: s for s in (
    Surface("p1-handover-request-draft-1", "p1-handover-result-draft-1", HANDOVER_PROFILE, run_handover),
    Surface("p1-events-request-draft-1", "p1-events-result-draft-1", EVENT_PROFILE, run_events),
    Surface("p1-request-draft-1", "p1-result-draft-1", FORECAST_PROFILE, run_forecast),
    Surface("p2-split-request-draft-1", "p2-split-result-draft-1", SPLIT_PROFILE, run_split),
    Surface("p2-splits-request-draft-1", "p2-splits-result-draft-1", SPLITS_PROFILE, run_splits),
    Surface("p2-display-request-draft-1", "p2-display-result-draft-1", DISPLAY_PROFILE, run_displays),
    Surface("p2-measurement-request-draft-1", "p2-measurement-result-draft-1", MEASUREMENT_PROFILE, run_measurements),
    Surface("p2-quantity-request-draft-1", "p2-quantity-result-draft-1", QUANTITY_PROFILE, run_quantities),
    Surface("p2-temporal-request-draft-1", "p2-temporal-result-draft-1", TEMPORAL_PROFILE, run_temporal),
)}


def surface_of(request):
    if type(request) is dict:
        for surface in SURFACES.values():
            if request.get("schema_version") == surface.request_schema:
                return surface
    return P0


def evaluate(request):
    fingerprint = None
    surface = surface_of(request)
    try:
        fingerprint = check_json(request)
        response = surface.run(request)
        attach_certifier(response)
    except Problem as problem:
        response = {"status": problem.status, "reason_codes": [problem.code],
                    "error_path": problem.path, "incomplete": ["request"]}
    return {"schema_version": surface.result_schema, "profile": surface.profile,
            "input_sha256": fingerprint, **response}
