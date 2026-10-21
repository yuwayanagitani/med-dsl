#!/usr/bin/env python3
"""P2 の統合評価：拡張の登録、P2 の例、共通予算の不変条件（X12）、版の比較（X11）を、固定した分母と照合する。

P0・P1 の固定対象（evaluate-p1-d.py の lock）の整合を先に確認し、その上で P2 の分母を数える。
期待結果の自動更新はしない。分母（EXPECTED）は、宣言と例の台帳から数えた値を、この版で手で固定したもの。
結果は data/research/p2-d/ 以下にだけ書く（Git 管理外）。
"""

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import p2_checks
from med_dsl import evaluate
from med_dsl.extensions import EVIDENCE, Refused, Registry, guard_gaps, independent_pairs, load_manifests, weakest_evidence
from med_dsl.model import Problem

VERSION_RECORDS = ("examples/p2-versions/p0-draft-1-to-draft-2.json", "examples/p2-versions/p2-quantity-draft-1-to-draft-2.json")

# 固定した分母。実装の出力から生成した値ではなく、宣言（extensions/*.json）と例の台帳を数えて固定した値。
# budget_evaluations だけは、掃引の評価回数（要求ごとの steps_used に依る）を測って固定したもの。
EXPECTED = {
    "base": {"p1_cases": 20, "p1_files": 80, "p1_checks": 417, "p0_files": 37, "p0_checks": 221},
    "extensions": {"registered": 12, "refused": 0, "obligations": 112, "guards": 238, "guard_gaps": 3,
                   "evidence": {"checked_native_template": 95, "finite_check": 9, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
                   "independent_pairs": 42, "pairs": 55},
    "suites": {"p2": {"examples": 35, "checks": 128}, "p2-split": {"examples": 34, "checks": 224}, "p2-splits": {"examples": 38, "checks": 221}},
    "budget": {"requests": 203, "budget_evaluations": 2936, "violations": 0, "allowed_budget_dependent_refusals": 1},
}

# P2-d時点の分母を履歴資料との照合用に保持する。P2-e追加後の現在値とは区別する。
P2_D_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 13, "refused": 0, "obligations": 127, "guards": 258, "guard_gaps": 3,
    "evidence": {"checked_native_template": 102, "finite_check": 17, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 53, "pairs": 66,
}
EXPECTED["suites"]["p2-temporal"] = {"examples": 61, "checks": 462}
EXPECTED["budget"] = {"requests": 264, "budget_evaluations": 3425, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-e時点の分母を残し、数量追加後の現在値を別に固定する。
P2_E_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 14, "refused": 0, "obligations": 144, "guards": 282, "guard_gaps": 3,
    "evidence": {"checked_native_template": 112, "finite_check": 24, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 65, "pairs": 78,
}
EXPECTED["suites"]["p2-quantity"] = {"examples": 79, "checks": 609}
EXPECTED["budget"] = {"requests": 343, "budget_evaluations": 4077, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-f時点の分母を残し、測定の接続を加えた現在値を固定する。
P2_F_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 15, "refused": 0, "obligations": 163, "guards": 313, "guard_gaps": 3,
    "evidence": {"checked_native_template": 122, "finite_check": 33, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 77, "pairs": 91,
}
EXPECTED["suites"]["p2-measurement"] = {"examples": 137, "checks": 1425}
# budget欄欠落の負例1件は要求全体の拒否で照合し、予算の置換掃引へ加算しない。
EXPECTED["budget"] = {"requests": 479, "budget_evaluations": 6070, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-g時点を残し、表示射影の追加後を固定する。予算欄欠落の負例2件は掃引へ含めない。
P2_G_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 16, "refused": 0, "obligations": 182, "guards": 348, "guard_gaps": 3,
    "evidence": {"checked_native_template": 132, "finite_check": 42, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 89, "pairs": 105,
}
EXPECTED["suites"]["p2-display"] = {"examples": 145, "checks": 2128}
EXPECTED["budget"] = {"requests": 623, "budget_evaluations": 9544, "violations": 0, "allowed_budget_dependent_refusals": 1}



# P2-hの分母を保持し、期間つき数量主張の併用後を明示的に固定する。
P2_H_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 17, "refused": 0, "obligations": 201, "guards": 367, "guard_gaps": 3,
    "evidence": {"checked_native_template": 142, "finite_check": 51, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 103, "pairs": 120,
}
EXPECTED["suites"]["p2-temporal-measurement"] = {"examples": 151, "checks": 1676}
EXPECTED["budget"] = {"requests": 773, "budget_evaluations": 11895, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-iの分母を履歴として保持し、期間量の表示接続後を固定する。
P2_I_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 18, "refused": 0, "obligations": 220, "guards": 386, "guard_gaps": 3,
    "evidence": {"checked_native_template": 151, "finite_check": 61, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 117, "pairs": 136,
}
EXPECTED["suites"]["p2-temporal-display"] = {"examples": 170, "checks": 2670}
# 全946要求のうちbudget欠落4負例は元fixtureで拒否を照合し、置換掃引へ含めない。
EXPECTED["budget"] = {"requests": 942, "budget_evaluations": 16502, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-jの分母を保持し、確認済みの期間不明記録の精密化（P2-k）を加えた現在値を固定する。
P2_J_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 19, "refused": 0, "obligations": 239, "guards": 420, "guard_gaps": 3,
    "evidence": {"checked_native_template": 163, "finite_check": 68, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 134, "pairs": 153,
}
EXPECTED["suites"]["p2-refinement"] = {"examples": 66, "checks": 721}
EXPECTED["budget"] = {"requests": 1008, "budget_evaluations": 17166, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-kの分母を保持し、数量の単位表の改訂（P2-l、版draft-2）後の現在値を固定する。
# 数量の宣言に継承の差分の義務VR-1（有限確認、防護例2件）を足し、数量系列にQ25を加えた。
P2_K_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 19, "refused": 0, "obligations": 240, "guards": 422, "guard_gaps": 3,
    "evidence": {"checked_native_template": 163, "finite_check": 69, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 134, "pairs": 153,
}
EXPECTED["suites"]["p2-quantity"] = {"examples": 80, "checks": 622}
EXPECTED["budget"] = {"requests": 1009, "budget_evaluations": 17177, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-lの分母を保持し、縦断比較（P2-m）を加えた現在値を固定する。19義務と103例を足す。既存の系列と宣言は変更しない。
P2_L_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 20, "refused": 0, "obligations": 259, "guards": 441, "guard_gaps": 3,
    "evidence": {"checked_native_template": 172, "finite_check": 79, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 150, "pairs": 171,
}
EXPECTED["suites"]["p2-longitudinal"] = {"examples": 103, "checks": 2020}
EXPECTED["budget"] = {"requests": 1111, "budget_evaluations": 20909, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-mの分母を保持し、継承の欄（P2-n、宣言の書式 draft-2）を加えた現在値を固定する。宣言・例・実装の数は変わらない。
# 継承の項目は9（予測8＋予測外1）、証人は30、理由つきの欠落は2。継承で結ばれた組は独立としないので、独立な組は150から143になる。
P2_M_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"]["independent_pairs"] = 143
EXPECTED["extensions"]["inherits"] = {"entries": 9, "witnesses": 30, "gaps": 2}


# P2-nの分母を保持し、薄い臨床ライブラリ（P2-o）を加えた現在値を固定する。宣言1件（義務19、各1件の防護例、検査の水準は有限の検査10・検査済みの型9）、
# 例141、継承3項目（証人16）を足す。基底を除く他の19件との組19のうち、依存か継承で結ばれる4件を除く15組が独立。
P2_N_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 21, "refused": 0, "obligations": 278, "guards": 460, "guard_gaps": 3,
    "evidence": {"checked_native_template": 181, "finite_check": 89, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 158, "pairs": 190,
    "inherits": {"entries": 12, "witnesses": 46, "gaps": 2},
}
EXPECTED["suites"]["p2-library"] = {"examples": 141, "checks": 2417}
# 要求は1111＋140（予算欄欠落の負例1件は掃引へ含めない）。掃引の回数24,895は実測の値（予測ではない）。
EXPECTED["budget"] = {"requests": 1251, "budget_evaluations": 24895, "violations": 0, "allowed_budget_dependent_refusals": 1}


# P2-oの分母を保持し、構造への写像の可否の診断（P2-p）を加えた現在値を固定する。宣言1件（義務17、各1件の防護例、検査の水準は有限の検査8・検査済みの型9）、
# 例97。継承は宣言しない。基底を除く他の20件との組20のうち、依存（推移）で結ばれる3件を除く17組が独立。
P2_O_EXPECTED = copy.deepcopy(EXPECTED)
EXPECTED["extensions"] = {
    "registered": 22, "refused": 0, "obligations": 295, "guards": 477, "guard_gaps": 3,
    "evidence": {"checked_native_template": 190, "finite_check": 97, "hand_derivation": 8, "self_declared": 0, "individual_io": 0},
    "independent_pairs": 175, "pairs": 210,
    "inherits": {"entries": 12, "witnesses": 46, "gaps": 2},
}
EXPECTED["suites"]["p2-grounding"] = {"examples": 97, "checks": 1998}
# 要求は1251＋96（予算欄欠落の負例1件は掃引へ含めない）。掃引の回数28,345は実測の値（予測ではない）。
EXPECTED["budget"] = {"requests": 1347, "budget_evaluations": 28345, "violations": 0, "allowed_budget_dependent_refusals": 1}


def _p1d():
    spec = importlib.util.spec_from_file_location("evaluate_p1_d", ROOT / "scripts/research/evaluate-p1-d.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_report():
    """P0・P1 の固定対象の照合（lock の整合と全例の期待）。CLI の起動は省く（evaluate-p1-d --cli が行う）。"""
    p1d = _p1d()
    lock, lock_sha, fixtures = p1d.preflight()
    records = [p1d.evaluate_fixture(name, entry, data, path, False) for name, rows in fixtures.items() for entry, data, path in rows]
    summary = p1d.summarize(records, lock)
    p0 = summary["suites"]["p0"]
    return {"manifest_sha256": lock_sha, "bundle_sha256": lock["bundle_sha256"], "passed": summary["passed"],
            "p1_cases": summary["p1_cases_passed"], "p1_files": summary["p1_files"], "p1_checks": summary["p1_checks"],
            "p0_files": p0["passed_files"], "p0_checks": p0["passed_checks"]}


def extension_report():
    registry = Registry(ROOT, evaluate)
    rows, refused = [], []
    for manifest in load_manifests(ROOT / "extensions"):
        try:
            registry.register(manifest)
        except Refused as error:
            refused.append({"id": manifest.get("id") if isinstance(manifest, dict) else None, "codes": sorted(error.codes)})
            continue
        rows.append({"id": manifest["id"], "class": manifest["class"], "obligations": len(manifest["obligations"]),
                     "guards": sum(len(o.get("guards", [])) for o in manifest["obligations"]),
                     "weakest_evidence": weakest_evidence(manifest), "guard_gaps": guard_gaps(manifest),
                     "budget_sweep": manifest["evaluation"]["budget_sweep"]})
    evidence = {name: 0 for name in EVIDENCE}
    for manifest in registry:
        for obligation in manifest["obligations"]:
            evidence[obligation["evidence"]] += 1
    pairs = independent_pairs(registry)
    count = len([m for m in registry if m["class"] != "BASE"])
    inherited = [item for manifest in registry for item in manifest["inherits"]]
    return {"registered": len(rows), "refused": refused, "obligations": sum(r["obligations"] for r in rows),
            "guards": sum(r["guards"] for r in rows), "guard_gaps": sum(len(r["guard_gaps"]) for r in rows),
            "evidence": evidence, "independent_pairs": len(pairs), "pairs": count * (count - 1) // 2,
            "inherits": {"entries": len(inherited), "witnesses": sum(len(i["witnesses"]) for i in inherited), "gaps": sum(1 for i in inherited if not i["witnesses"])},
            "rows": rows}


def suites_report():
    return {name: p2_checks.suite_report(name, evaluate) for name in EXPECTED["suites"]}


def budget_report(limit):
    report = p2_checks.budget_report(p2_checks.load_requests(), evaluate, limit)
    report["allowed_budget_dependent_refusals"] = len(p2_checks.BUDGET_DEPENDENT_REFUSALS)
    return report


def versions_report():
    """版の記録ごとに比較を行う。git の履歴に旧版のコミットがなければ、行わなかったことを明示する（合格にも不合格にもしない）。"""
    reports = []
    for relative in VERSION_RECORDS:
        record = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        missing = [side for side in ("from", "to") if not p2_checks.has_commit(record[side]["commit"])]
        if missing:
            reports.append({"record": relative, "status": "not_run", "reason": "missing_commits:" + ",".join(missing)})
            continue
        if record["schema_version"] == "p2-version-record-draft-2":
            # P2 の拡張の版の更新：再生成した入力の比較（旧版・新版の統合評価の再現は、記録の測定値との照合に含める）
            report = p2_checks.regenerated_report(record)
            problems = p2_checks.regenerated_mismatches(record, report)
            reports.append({"record": relative, "status": "passed" if not problems else "failed", "problems": problems,
                            "inputs": report["inputs"], "classification": {k: len(v) for k, v in report["old_inputs_without_regeneration"].items()},
                            "expectation_changed": len(report["expectation_changed"]), "changed_files": len(report["changed_files"])})
            continue
        report = p2_checks.version_report(record)
        problems = p2_checks.record_mismatches(record, report)
        reports.append({"record": relative, "status": "passed" if not problems else "failed", "problems": problems,
                        "inputs": report["inputs"], "reproduction": report["reproduction"], "pins_changed": report["pins_changed"],
                        **{side: {"old_inputs_without_repin": {k: len(v) for k, v in report[side]["old_inputs_without_repin"].items()},
                                  "repinned_identical": len(report[side]["repinned"]["identical"]),
                                  "failing_old_expectations": len(report[side]["repinned"]["failing_old_expectations"]),
                                  "carry_added_field": len(report[side]["carry_added_field"])} for side in ("to", "current")}})
    return reports


def mismatches(report):
    """固定した分母との食い違いを、位置つきで返す。"""
    found = []
    for key, want in EXPECTED["base"].items():
        if report["base"][key] != want:
            found.append(f"base.{key}")
    if not report["base"]["passed"]:
        found.append("base.passed")
    for key, want in EXPECTED["extensions"].items():
        got = len(report["extensions"][key]) if key == "refused" else report["extensions"][key]       # 拒否は件数で照合する
        if got != want:
            found.append(f"extensions.{key}")
    for name, want in EXPECTED["suites"].items():
        got = report["suites"][name]
        if got["examples"] != want["examples"] or got["checks"] != want["checks"] or got["failures"]:
            found.append(f"suites.{name}")
    budget = report["budget"]
    if budget["requests"] != EXPECTED["budget"]["requests"] or budget["evaluations"] != EXPECTED["budget"]["budget_evaluations"]:
        found.append("budget.denominator")
    if budget["violations"]:
        found.append("budget.violations")
    if budget["allowed_budget_dependent_refusals"] != EXPECTED["budget"]["allowed_budget_dependent_refusals"]:
        found.append("budget.allowlist")
    for entry in report["versions"]:
        if entry["status"] == "failed":
            found.append("versions." + entry["record"])
    return found


def run(output, versions=True, limit=300):
    output = output.resolve()
    if not output.is_relative_to((ROOT / "data/research/p2-d").resolve()):
        raise ValueError("output_must_be_under_data_research_p2_d")
    report = {"schema_version": "p2-integrated-evaluation-draft-1", "evaluation_kind": "author_draft_engineering",
              "recorded_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "independent_review": False, "evaluation_frozen": False}
    report["base"] = base_report()
    report["extensions"] = extension_report()
    report["suites"] = suites_report()
    report["budget"] = budget_report(limit)
    report["versions"] = versions_report() if versions else []
    report["expected"] = copy.deepcopy(EXPECTED)
    report["mismatches"] = mismatches(report)
    # 評価の間にディスクの固定対象が変わっていないこと
    if base_report()["manifest_sha256"] != report["base"]["manifest_sha256"]:
        raise ValueError("snapshot_changed_during_evaluation")
    report["passed"] = not report["mismatches"]
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "results.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "results.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/p2-d/latest")
    parser.add_argument("--no-versions", action="store_true", help="版の比較（git の履歴が要る）を省く")
    parser.add_argument("--budget-limit", type=int, default=300, help="一つの要求の予算の掃引の上限")
    args = parser.parse_args()
    try:
        report = run(args.output, versions=not args.no_versions, limit=args.budget_limit)
    except (Problem, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({"passed": report["passed"], "mismatches": report["mismatches"],
                      "base": {k: report["base"][k] for k in ("p1_cases", "p1_files", "p1_checks", "p0_files", "p0_checks")},
                      "extensions": {k: report["extensions"][k] for k in ("registered", "obligations", "guards", "guard_gaps", "independent_pairs", "pairs", "inherits")},
                      "suites": {k: [v["examples"], v["checks"], len(v["failures"])] for k, v in report["suites"].items()},
                      "budget": {k: (v if k != "violations" else len(v)) for k, v in report["budget"].items()},
                      "versions": [{k: v for k, v in e.items() if k in ("record", "status", "reason")} for e in report["versions"]],
                      "manifest_sha256": report["base"]["manifest_sha256"], "bundle_sha256": report["base"]["bundle_sha256"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
