#!/usr/bin/env python3
"""記録に観察者を足す版の更新（P2-i：draft-2 → draft-3、依存する5拡張の再固定）の版の記録を作る（P2-r、設計73）。

宣言（declared_changes）と予測（predicted）は、文書73・74から手で書いた値で、旧版・新版の木の比較で求めた値（measured と
from／to の評価）とは別に持つ。新版のコミットを指すので、新版の実装を含むコミットの後で実行する。
使い方: python3 -B scripts/research/p2/make_observer_version_record.py <新版のコミット> [--from <旧版のコミット>] [--output <記録のパス>]"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/research"))
sys.path.insert(0, str(ROOT / "src"))

import p2_checks

SUITES = ["p2-temporal-measurement", "p2-temporal-display", "p2-longitudinal", "p2-library", "p2-grounding", "p2-observation"]
MODULES = ["temporal_measurement", "temporal_display", "longitudinal", "clinical_library", "structure_grounding", "observation_projection"]
EXTENSIONS = ["p2-clinical-library", "p2-longitudinal-comparison", "p2-observation-projection", "p2-structure-grounding", "p2-temporal-display", "p2-temporal-measurement"]
ADDED = {
    "D-1": ["p2-temporal-measurement/" + n + ".json" for n in ("o01", "o02", "o03", "o04", "o05", "o10", "o11", "o12", "o13", "o14-null", "o14-string")],
    "D-2": ["p2-library/" + n + ".json" for n in ("o70", "o71", "o72", "n03-observer-kind", "n03-observer-ref", "n03-observer-confirm")],
    "D-3": ["p2-observation/" + n + ".json" for n in ("q20", "q21", "q22", "q23", "q24", "q25", "n14-observer-type-device", "n14-observer-type-organization")],
}
# 文書73の Y5：宣言の embedded_in から機械的に列挙される範囲（globで書く）と、実際の再固定の範囲のうち列挙にないと予測した実体。
# 実際に旧い hash を埋め込んでいたのは P2-i の仕様の hash を含む実行例などで、列挙は P2-f の例（p2-quantity）まで広く数える（過大）。
REGENERATE = (["src/med_dsl/clinical_library.py", "src/med_dsl/clinical_library_spec.json", "src/med_dsl/longitudinal_spec.json", "src/med_dsl/observation_projection_spec.json",
               "src/med_dsl/quantity.py", "src/med_dsl/structure_grounding.py", "src/med_dsl/structure_grounding_spec.json", "src/med_dsl/temporal_display_spec.json",
               "src/med_dsl/temporal_measurement.py", "src/med_dsl/temporal_measurement_spec.json"]
              + [f"examples/{suite}/*.json" for suite in SUITES + ["p2-quantity"]])
UNDERCOUNT = (["src/med_dsl/temporal_display.py", "src/med_dsl/longitudinal.py", "src/med_dsl/observation_projection.py"] + [f"extensions/{i}.json" for i in EXTENSIONS])


def skeleton(old, new):
    return {
        "schema_version": "p2-version-record-draft-2", "id": "p2-temporal-measurement-draft-2-to-draft-3", "status": "author_draft", "independent_review": False,
        "note": "期間つき数量（P2-i）の記録に任意の項目 observer を足す版の更新と、依存する5拡張の再固定・採用の記録。旧版は消さず、旧入力は新版で黙って再解釈されず、"
                "再生成した入力と比べて宣言した変更だけが違う。declared_changes と predicted は文書73・74から手で書いた値、measured と from／to の評価は比較器の測定値を固定したもの。",
        "from": {"version": "draft-2", "commit": old, "evaluation": None},
        "to": {"version": "draft-3", "commit": new, "evaluation": None},
        "extensions": EXTENSIONS, "suites": SUITES,
        "pins": [{"file": f"src/med_dsl/{m}.py", "name": "SPEC_SHA256"} for m in MODULES],
        "pin_refusals": [{"status": "unsupported_profile", "code": "profile_spec_mismatch"}],
        "pure_pin_suites": [],
        "intended_changes": ["src/med_dsl/temporal_measurement_spec.json"],
        "predicted": {"extensions": EXTENSIONS, "regenerate": REGENERATE, "undercount": UNDERCOUNT},
        "declared_changes": [
            {"id": "D-1", "kind": "added_field", "extension": "p2-temporal-measurement", "field": "record.observer", "inputs": [], "added_inputs": ADDED["D-1"],
             "description": "記録の任意の項目 observer {kind: human|device, ref}。省略は観察者不明。確認が拘束する内容の一部。選ばれた記録が持つときだけ根拠に record_observer を出す"},
            {"id": "D-2", "kind": "added_field", "extension": "p2-clinical-library", "field": "selection.record_observer", "inputs": [], "added_inputs": ADDED["D-2"],
             "description": "操作の任意の observer を台帳へ渡し、選択の根拠に、あるときだけ record_observer を出す"},
            {"id": "D-3", "kind": "added_field", "extension": "p2-observation-projection", "field": "provenance.observer_type", "inputs": [], "added_inputs": ADDED["D-3"],
             "description": "観察者から生成の Provenance を出し、人の観察者の型は宣言を使う（推測せず依頼 declare_observer_type）"},
            {"id": "D-4", "kind": "repinned", "inputs": [], "description": "意味の変更のない再固定：P2-j・P2-m・P2-p。6つの仕様の hash、それを固定するモジュールの定数、依存先の仕様・宣言・実行例"},
        ],
        "measured": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("to", help="新版の実装を含むコミット")
    parser.add_argument("--from", dest="old", default="dc0aabe")
    parser.add_argument("--output", type=Path, default=ROOT / "examples/p2-versions/p2-temporal-measurement-draft-2-to-draft-3.json")
    args = parser.parse_args(argv)
    old = p2_checks.git("rev-parse", args.old).stdout.decode().strip()
    new = p2_checks.git("rev-parse", args.to).stdout.decode().strip()
    record = skeleton(old, new)
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
        "listed_but_unnecessary": len(set(report["affected"]["regenerate"]) - set(report["necessary_repin"])),
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
