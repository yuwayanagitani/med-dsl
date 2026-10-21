#!/usr/bin/env python3
"""観察者を必須にする版の更新（P2-i：draft-3 → draft-4、依存する5拡張の再固定。旧入力を拒否する）の版の記録を作る（P2-s、設計76）。

宣言（declared_changes）と予測（predicted）は、文書76・77から手で書いた値で、旧版・新版の木の比較で求めた値（measured と
from／to の評価）とは別に持つ。新版のコミットを指すので、新版の実装を含むコミットの後で実行する。
使い方: python3 -B scripts/research/p2/make_required_observer_version_record.py <新版のコミット> [--from <旧版のコミット>] [--output <記録のパス>]"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/research"))
sys.path.insert(0, str(ROOT / "scripts/research/p2"))
sys.path.insert(0, str(ROOT / "src"))

import make_observer_version_record as earlier
import p2_checks

ADDED = {
    "D-1": ["p2-temporal-measurement/" + n + ".json" for n in ("o20", "o21", "o22", "o23")],
    "D-2": ["p2-library/" + n + ".json" for n in ("o73", "n03-observer-missing", "n03-observer-unknown-ref")],
}
EXPLICIT = ["p2-temporal-measurement/o04.json"]          # 期待を個別に変えた例（訂正は元の観察者を継がない：B は明示の unknown）


def skeleton(old, new):
    return {
        "schema_version": "p2-version-record-draft-2", "id": "p2-temporal-measurement-draft-3-to-draft-4", "status": "author_draft", "independent_review": False,
        "note": "期間つき数量（P2-i）の記録の観察者を必須にし、不明は明示の unknown で書かせる版の更新（旧入力を拒否する）と、依存する5拡張の再固定・採用の記録。"
                "旧版は消さず、旧入力は新版で受理されず、移行（旧入力に明示の unknown を足す）した入力は宣言した追加だけが違う。"
                "declared_changes と predicted は文書76・77から手で書いた値、measured と from／to の評価は比較器の測定値を固定したもの。",
        "from": {"version": "draft-3", "commit": old, "evaluation": None},
        "to": {"version": "draft-4", "commit": new, "evaluation": None},
        "extensions": earlier.EXTENSIONS, "suites": earlier.SUITES,
        "pins": [{"file": f"src/med_dsl/{m}.py", "name": "SPEC_SHA256"} for m in earlier.MODULES],
        "pin_refusals": [{"status": "unsupported_profile", "code": "profile_spec_mismatch"}],
        "pure_pin_suites": [],
        "intended_changes": ["src/med_dsl/temporal_measurement_spec.json"],
        "predicted": {"extensions": earlier.EXTENSIONS, "regenerate": earlier.REGENERATE, "undercount": earlier.UNDERCOUNT},
        "declared_changes": [
            {"id": "D-1", "kind": "required_field", "extension": "p2-temporal-measurement", "field": "record.observer", "inputs": EXPLICIT, "added_inputs": ADDED["D-1"],
             "request_leaf": "observer", "result_leaf": "record_observer", "substitution_refusal": {"status": "invalid_input", "code": "missing_field"},
             "description": "記録の観察者を必須にする（P2-r の任意の項目から）。{kind: human|device, ref} か {kind: unknown}（ref なし）。根拠に record_observer を常に出す。"
                            "旧入力は新版の入力の形でなく、移行（全ての記録に明示の unknown を足す）が要る"},
            {"id": "D-2", "kind": "added_field", "extension": "p2-clinical-library", "field": "operation.observer", "inputs": [], "added_inputs": ADDED["D-2"],
             "description": "操作 record・correct の観察者を必須にする。ライブラリは欠落を補わない。選択の根拠に record_observer を常に出す"},
            {"id": "D-3", "kind": "repinned", "inputs": [], "description": "意味の変更のない再固定：P2-j・P2-m・P2-p・P2-q（P2-q は unknown の観察者を、観察者がないことと同じに扱う）。"
                                                                          "6つの仕様の hash、それを固定するモジュールの定数、依存先の仕様・宣言・実行例"},
        ],
        "measured": None,
    }


def states_unknown(value):
    if isinstance(value, dict):
        observer = value.get("observer")
        return (isinstance(observer, dict) and observer.get("kind") == "unknown") or any(states_unknown(item) for item in value.values())
    return isinstance(value, list) and any(states_unknown(item) for item in value)


def unknown_observer_inputs(commit, names):
    """新版のコミットの入力のうち、観察者に明示の unknown を含むものの名前。"""
    found = []
    for name in sorted(names):
        document = json.loads(p2_checks.git("show", commit + ":examples/" + name).stdout)
        if states_unknown(document.get("request", document)):
            found.append(name)
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("to", help="新版の実装を含むコミット")
    parser.add_argument("--from", dest="old", default="ab4c358")
    parser.add_argument("--output", type=Path, default=ROOT / "examples/p2-versions/p2-temporal-measurement-draft-3-to-draft-4.json")
    args = parser.parse_args(argv)
    old = p2_checks.git("rev-parse", args.old).stdout.decode().strip()
    new = p2_checks.git("rev-parse", args.to).stdout.decode().strip()
    record = skeleton(old, new)
    report = p2_checks.regenerated_report(record)
    listed = set(report["affected"]["regenerate"]) | set(record["intended_changes"]) | ({report["affected"]["lock"]} if report["affected"]["lock"] else set())
    unpredicted = sorted(set(report["necessary_repin"]) - listed)
    forward = report["forward_old_pin"]
    unknown = unknown_observer_inputs(new, forward)
    first = lambda result: (result["reason_codes"] or [None])[0] if result["status"] != "ok" else None
    record["from"]["evaluation"], record["to"]["evaluation"] = report["reproduction"]["from"], report["reproduction"]["to"]
    record["measured"] = {
        "old_inputs_without_regeneration": {k: len(v) for k, v in report["old_inputs_without_regeneration"].items()},
        "inputs": {"old": report["inputs"]["old"], "new": report["inputs"]["new"]},
        "unpredicted_repin": unpredicted,
        "prediction_deviation": {"missed": sorted(set(unpredicted) - set(earlier.UNDERCOUNT)), "wrong": sorted(set(earlier.UNDERCOUNT) - set(unpredicted))},
        "changed_files": len(report["changed_files"]),
        "listed_but_unnecessary": len(set(report["affected"]["regenerate"]) - set(report["necessary_repin"])),
        "migrated": {"requests_changed": len(report["request_changed"]), "expectations_changed": len(report["expectation_changed"]),
                     "results_changed": len(report["result_differences"])},
        "forward_to_old_version": {"inputs": len(forward), "accepted": sum(1 for r in forward.values() if r["status"] == "ok"),
                                   "unknown_observer_inputs": len(unknown), "unknown_observer_accepted": sum(1 for n in unknown if forward[n]["status"] == "ok"),
                                   "unknown_observer_first_reason": {key: sum(1 for n in unknown if first(forward[n]) == key) for key in ("missing_field", "invalid_observer")}
                                   | {"other": sum(1 for n in unknown if first(forward[n]) not in ("missing_field", "invalid_observer"))}},
    }
    problems = p2_checks.regenerated_mismatches(record, report)
    if problems:
        print(json.dumps({"written": False, "problems": problems, "measured": record["measured"]}, ensure_ascii=False))
        return 1
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(args.output), "measured": record["measured"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
