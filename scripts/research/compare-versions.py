#!/usr/bin/env python3
"""版の記録（examples/p2-versions/*.json）に沿って、旧版と新版を git の履歴から取り出して比べる。

(1) 旧版は旧版の契約で再現できるか（旧版の評価が通り、束の hash が記録と一致）。
(2) 旧入力は新版で黙って再解釈されないか（同じ／宣言した付加／固定した hash の不一致による拒否のどれか）。
(3) hash を再固定しただけの旧入力は、旧版の期待を満たすか。満たさない差は宣言した変更に属するか。
宣言にない差があれば失敗する。期待結果の自動更新はしない。
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import p2_checks

ROOT = p2_checks.ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", default="examples/p2-versions/p0-draft-1-to-draft-2.json")
    parser.add_argument("--no-current", action="store_true", help="作業ツリーの実装との照合を省く")
    args = parser.parse_args(argv)
    record = json.loads((ROOT / args.record).read_text(encoding="utf-8"))
    for side in ("from", "to"):
        if not p2_checks.has_commit(record[side]["commit"]):
            print(json.dumps({"passed": False, "reason": f"git の履歴に {side} のコミットがない"}, ensure_ascii=False))
            return 2
    report = p2_checks.version_report(record, current=not args.no_current)
    problems = p2_checks.record_mismatches(record, report)
    summary = {"id": record["id"], "passed": not problems, "problems": problems, "inputs": report["inputs"],
               "reproduction": report["reproduction"], "pins_changed": report["pins_changed"]}
    for side in ("to", "current"):
        if side in report:
            part = report[side]
            summary[side] = {"old_inputs_without_repin": {k: len(v) for k, v in part["old_inputs_without_repin"].items()},
                             "repinned": {"identical": len(part["repinned"]["identical"]), "changed": part["repinned"]["changed"],
                                          "failing_old_expectations": len(part["repinned"]["failing_old_expectations"])},
                             "carry_added_field": len(part["carry_added_field"])}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
