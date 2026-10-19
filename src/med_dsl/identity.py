"""認定票に付ける、認定器の実装の同一性。"""

import hashlib
from pathlib import Path

from .model import Problem
from .validation import digest

_CACHE = {}


def implementation_identity():
    """`src/med_dsl/` の *.py と *.json の生バイトの束。共通 manifest の該当行から再計算できる。"""
    directory = Path(__file__).parent
    if "value" not in _CACHE:
        try:
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted([*directory.glob("*.py"), *directory.glob("*.json")])}
        except OSError as error:
            raise Problem("native_spec_unavailable", "implementation") from error
        _CACHE["value"] = {"kind": "native_python_modules", "files": len(files), "bundle_sha256": digest(files)}
    return dict(_CACHE["value"])


def attach_certifier(value):
    """結果に含まれる全ての certificate に certifier を付ける（既にあれば変更しない）。"""
    if type(value) is dict:
        for key, item in value.items():
            if key in ("certificate", "second_step_certificate") and type(item) is dict and "status" in item:
                item.setdefault("certifier", implementation_identity())
            attach_certifier(item)
    elif type(value) is list:
        for item in value:
            attach_certifier(item)
    return value
