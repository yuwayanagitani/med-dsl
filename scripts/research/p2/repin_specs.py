#!/usr/bin/env python3
"""仕様の改訂後、依存の順に仕様の hash を再計算し、その hash を固定しているモジュールの定数と、依存先の仕様へ反映する（P2-l、設計53 の VD4）。

実行例と宣言は、この道具では再固定しない（派生した hash を含むので、生成器で再生成する）。何度実行しても同じ結果になる。
使い方: python3 -B scripts/research/p2/repin_specs.py [--check]（--check は書き換えず、再固定が要るかだけを確かめる）"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
# 依存の順（先の仕様の hash を後の仕様が含む）。(仕様、その hash を定数に持つモジュール、定数名)
CHAIN = [
    ("src/med_dsl/quantity_spec.json", "src/med_dsl/quantity.py", "SPEC_SHA256"),
    ("src/med_dsl/measurement_spec.json", "src/med_dsl/measurement.py", "SPEC_SHA256"),
    ("src/med_dsl/display_spec.json", "src/med_dsl/display.py", "SPEC_SHA256"),
    ("src/med_dsl/temporal_measurement_spec.json", "src/med_dsl/temporal_measurement.py", "SPEC_SHA256"),
    ("src/med_dsl/temporal_display_spec.json", "src/med_dsl/temporal_display.py", "SPEC_SHA256"),
    ("src/med_dsl/longitudinal_spec.json", "src/med_dsl/longitudinal.py", "SPEC_SHA256"),
    ("src/med_dsl/clinical_library_spec.json", "src/med_dsl/clinical_library.py", "SPEC_SHA256"),
]


def constant(text, name):
    found = re.search(rf"^{name} = ['\"]([0-9a-f]{{64}})['\"]", text, re.M)
    if not found:
        raise SystemExit(f"定数 {name} が見つからない")
    return found.group(1)


def main(argv=None):
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    specs = {spec: (ROOT / spec).read_text(encoding="utf-8") for spec, _, _ in CHAIN}
    modules = {module: (ROOT / module).read_text(encoding="utf-8") for _, module, _ in CHAIN}
    report = []
    for spec, module, name in CHAIN:
        old = constant(modules[module], name)
        new = hashlib.sha256(specs[spec].encode("utf-8")).hexdigest()
        if old == new:
            continue
        report.append({"spec": spec, "module": module, "old": old, "new": new})
        modules[module] = modules[module].replace(old, new)
        for other in specs:
            if other != spec:
                specs[other] = specs[other].replace(old, new)
    if check:
        print(json.dumps({"stale": report}, ensure_ascii=False))
        return 1 if report else 0
    for spec, text in specs.items():
        (ROOT / spec).write_text(text, encoding="utf-8")
    for module, text in modules.items():
        (ROOT / module).write_text(text, encoding="utf-8")
    print(json.dumps({"repinned": report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
