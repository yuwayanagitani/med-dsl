"""P2 系列のテストが共有する補助：拡張を不活性にする、依存を数える、要求の所有者を求める、全例を読む。"""

from contextlib import ExitStack, contextmanager
import importlib
import inspect
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl.model import Problem
from med_dsl.validation import decode_json

SUITES = ("p0", "p1-a", "p1-b", "p1-c", "review", "p2-split", "p2-splits", "p2-temporal", "p2-quantity", "p2-measurement", "p2-display", "p2-temporal-measurement", "p2-temporal-display", "p2-refinement")
# 不活性にできる拡張。基底（p0-positive）と p0-definitions は、実装のモジュールが核（validation.py）を含むので対象外
DISABLABLE = ["p1-finite-forecast", "p1-events", "p1-handover-host", "p1-event-chain", "p1-projection", "p1-reference",
              "p1-absence", "p1-replay", "p2-concept-split", "p2-split-combination", "p2-temporal-assertion", "p2-quantity-literal", "p2-measurement-binding", "p2-quantity-display", "p2-temporal-measurement", "p2-temporal-display", "p2-validity-refinement"]


def load_requests(suites=SUITES):
    requests = []
    for suite in suites:
        manifest = decode_json((ROOT / "examples" / suite / "manifest.json").read_bytes())
        for entry in manifest["files"] + manifest.get("accepted_boundaries", []):
            request = decode_json((ROOT / "examples" / suite / entry["path"]).read_bytes())["request"]
            requests.append((f"{suite}/{entry['path']}", request))
    return requests


def functions_of(registry, ident):
    """宣言した実装モジュールが定義する関数（その拡張の入口と内部）。"""
    found = {}
    for path in registry.get(ident)["implementation"]["modules"]:
        module = importlib.import_module("med_dsl." + Path(path).stem)
        for obj in vars(module).values():
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                found[id(obj)] = obj
    return found


@contextmanager
def inert(registry, ident):
    """拡張を不活性にする：宣言した実装モジュールの全関数を、他のモジュールが import した束縛も含めて差し替え、
    ホストの登録表（host.SURFACES・handover.OPERATIONS）の該当の項目も差し替える。"""
    own = functions_of(registry, ident)

    def absent(*args, **kwargs):
        raise Problem("extension_absent", status="unsupported_profile")

    from med_dsl import handover, host
    with ExitStack() as stack:
        for module in [m for n, m in list(sys.modules.items()) if n.startswith("med_dsl") and m is not None]:
            for name, obj in list(vars(module).items()):
                if id(obj) in own and obj is own[id(obj)]:
                    stack.enter_context(patch.object(module, name, absent))
        stack.enter_context(patch.dict(host.SURFACES, {k: v._replace(run=absent) for k, v in host.SURFACES.items() if id(v.run) in own}))
        stack.enter_context(patch.dict(handover.OPERATIONS, {
            k: v._replace(validate=absent if id(v.validate) in own else v.validate, run=absent if id(v.run) in own else v.run)
            for k, v in handover.OPERATIONS.items() if id(v.validate) in own or id(v.run) in own}))
        yield


def dependents(registry, ident):
    found, grew = {ident}, True
    while grew:
        grew = False
        for manifest in registry:
            if manifest["id"] not in found and any(d["id"] in found for d in manifest["depends_on"]):
                found.add(manifest["id"])
                grew = True
    return found


def owner_of(registry, request):
    """要求を扱う拡張：操作の所有者、なければ schema_version の所有者。"""
    owners = registry.owners()
    operation = request.get("operation") if isinstance(request, dict) else None
    for kind, value in (("operations", operation), ("schema_versions", request.get("schema_version") if isinstance(request, dict) else None)):
        if (kind, value) in owners:
            return owners[(kind, value)]
    return None
