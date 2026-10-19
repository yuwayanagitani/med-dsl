#!/usr/bin/env python3
"""extensions/*.json の宣言を検査して登録する（P2-a）。意味の正しさは検査しない。"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl import evaluate
from med_dsl.extensions import EVIDENCE, Refused, Registry, guard_gaps, load_manifests, weakest_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--directory", default="extensions")
    parser.add_argument("--strict", action="store_true", help="防護例のない義務（guard_gap）があれば失敗にする")
    parser.add_argument("--no-guards", action="store_true", help="防護例を評価しない（構造と実体の一致だけ）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = Registry(args.root, None if args.no_guards else evaluate)
    rows, refused = [], []
    for manifest in load_manifests(args.root / args.directory):
        try:
            registry.register(manifest)
        except Refused as error:
            refused.append({"id": manifest.get("id") if isinstance(manifest, dict) else None,
                            "findings": [{"code": f.code, "path": f.path, "detail": f.detail} for f in error.findings]})
            continue
        rows.append({"id": manifest["id"], "class": manifest["class"], "obligations": len(manifest["obligations"]),
                     "weakest_evidence": weakest_evidence(manifest), "guard_gaps": guard_gaps(manifest)})
    gaps = sum(len(r["guard_gaps"]) for r in rows)
    report = {"registered": rows, "refused": refused, "guard_gaps": gaps, "evidence_order": list(EVIDENCE)}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['id']:22s} {r['class']:5s} 義務{r['obligations']:2d} 最弱の証拠={r['weakest_evidence']:22s} 防護例なし={len(r['guard_gaps'])}")
        for r in refused:
            print("拒否:", r["id"], [(f['code'], f['path'], f['detail']) for f in r["findings"]])
        print(f"登録 {len(rows)}／拒否 {len(refused)}／防護例なしの義務 {gaps}")
    return 1 if refused or (args.strict and gaps) else 0


if __name__ == "__main__":
    raise SystemExit(main())
