#!/usr/bin/env python3
"""数量の単位表の版の更新（draft-1 → draft-2）の版の記録を作る（P2-l、設計53の§5）。

宣言（declared_changes）と予測（predicted）は、文書54から手で書いた値で、旧版・新版の木の比較で求めた値（measured と
from／to の評価）とは別に持つ。新版のコミットを指すので、新版の実装を含むコミットの後で実行する。
使い方: python3 -B scripts/research/p2/make_version_record.py <新版のコミット> [--from <旧版のコミット>] [--output <記録のパス>]"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/research"))
sys.path.insert(0, str(ROOT / "src"))

import p2_checks

OLD_COMMIT = "906766d2ad064746abecb46e532c48058b7f1bd2"        # 改訂前（原理の草案49・P2-kの直後）のコミット
SUITES = ["p2-quantity", "p2-measurement", "p2-display", "p2-temporal-measurement", "p2-temporal-display"]
MODULES = ["quantity", "measurement", "display", "temporal_measurement", "temporal_display"]
EXTENSIONS = ["p2-measurement-binding", "p2-quantity-display", "p2-quantity-literal", "p2-temporal-display", "p2-temporal-measurement"]
CHANGED = ["p2-quantity/q03.json", "p2-quantity/q04.json", "p2-quantity/q08.json", "p2-display/p12.json",
           "p2-temporal-measurement/c22-third.json", "p2-temporal-display/j07.json"]
# 文書54の§5：宣言から列挙される範囲（globで書く）と、実際の再固定の範囲のうち列挙にないと予測した実体
REGENERATE = (["src/med_dsl/measurement_spec.json", "src/med_dsl/display_spec.json", "src/med_dsl/temporal_measurement_spec.json",
               "src/med_dsl/temporal_display_spec.json", "src/med_dsl/quantity.py", "src/med_dsl/measurement.py", "src/med_dsl/temporal_measurement.py"]
              + [f"examples/{suite}/*.json" for suite in SUITES])
UNDERCOUNT = ["src/med_dsl/display.py", "src/med_dsl/temporal_display.py", "extensions/index.json"] + [f"extensions/{i}.json" for i in EXTENSIONS]


def skeleton(old, new):
    return {
        "schema_version": "p2-version-record-draft-2", "id": "p2-quantity-draft-1-to-draft-2", "status": "author_draft", "independent_review": False,
        "note": "数量（P2-f）の単位表の改訂と、依存する4拡張の再固定の記録。旧版は消さず、旧入力は新版で黙って再解釈されず、再生成した入力との差は宣言した変更だけ。"
                "declared_changes と predicted は文書54から手で書いた値、measured と from／to の評価は比較器の測定値を固定したもの。",
        "from": {"version": "draft-1", "commit": old, "evaluation": None},
        "to": {"version": "draft-2", "commit": new, "evaluation": None},
        "extensions": EXTENSIONS, "suites": SUITES,
        "pins": [{"file": f"src/med_dsl/{m}.py", "name": "SPEC_SHA256"} for m in MODULES],
        "pin_refusals": [{"status": "unsupported_profile", "code": "profile_spec_mismatch"}],
        "pure_pin_suites": ["p2-quantity"],
        "intended_changes": ["src/med_dsl/quantity_spec.json"],
        "predicted": {"extensions": EXTENSIONS, "regenerate": REGENERATE, "undercount": UNDERCOUNT},
        "declared_changes": [
            {"id": "D-1", "kind": "added_unit", "unit": "u_hundred", "dimension": [1, 0], "scale": [100, 1], "inputs": [],
             "added_inputs": ["p2-quantity/q25.json"], "description": "基底の100倍の単位を追加（旧版では未知の単位）"},
            {"id": "D-2", "kind": "changed_value", "unit": "u_third", "from_scale": [1, 3], "to_scale": [2, 3], "inputs": CHANGED,
             "allowed_prefixes": ["/results[]"], "description": "同じ ID の換算係数の改訂。u_third を使う旧入力6件だけが、結果の欄の内側で変わる"},
            {"id": "D-3", "kind": "repinned", "inputs": [], "description": "5つの仕様の hash と、それを固定するモジュールの定数、依存先の仕様・宣言・実行例（派生した hash を含む）の再固定。意味の変更なし"},
        ],
        "measured": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("to", help="新版の実装を含むコミット")
    parser.add_argument("--from", dest="old", default=OLD_COMMIT)
    parser.add_argument("--output", type=Path, default=ROOT / "examples/p2-versions/p2-quantity-draft-1-to-draft-2.json")
    args = parser.parse_args(argv)
    record = skeleton(args.old, args.to)
    report = p2_checks.regenerated_report(record)
    listed = set(report["affected"]["regenerate"]) | set(record["intended_changes"]) | ({report["affected"]["lock"]} if report["affected"]["lock"] else set())
    unpredicted = sorted(set(report["necessary_repin"]) - listed)
    record["from"]["evaluation"], record["to"]["evaluation"] = report["reproduction"]["from"], report["reproduction"]["to"]
    record["measured"] = {
        "old_inputs_without_regeneration": {k: len(v) for k, v in report["old_inputs_without_regeneration"].items()},
        "inputs": {"old": report["inputs"]["old"], "new": report["inputs"]["new"]},
        "unpredicted_repin": unpredicted,
        "prediction_deviation": {"missed": sorted(set(unpredicted) - set(UNDERCOUNT)), "wrong": sorted(set(UNDERCOUNT) - set(unpredicted))},
        "changed_files": len(report["changed_files"]),
    }
    problems = p2_checks.regenerated_mismatches(record, report)
    if problems:
        print(json.dumps({"written": False, "problems": problems}, ensure_ascii=False))
        return 1
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(args.output), "measured": record["measured"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
