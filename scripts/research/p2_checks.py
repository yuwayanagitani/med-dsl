"""P2 の評価の共通部品：全例の読み込みと期待の照合、共通予算の不変条件（X12）、版の比較（X11）。

evaluate-p2.py（統合評価）、compare-versions.py（版の比較）、tests/p2 が、同じ実装を使う。
"""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from med_dsl.validation import canonical_bytes, decode_json

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUITES = ("p0", "p1-a", "p1-b", "p1-c", "review", "p2-split", "p2-splits", "p2-temporal", "p2-quantity", "p2-measurement", "p2-display")


# ---- 例の読み込みと期待の照合 ----
def lookup(result, path):
    for key in path:
        if type(result) is dict and type(key) is str and key in result:
            result = result[key]
        elif type(result) is list and type(key) is int and 0 <= key < len(result):
            result = result[key]
        else:
            return False, None
    return True, result


def failed_checks(result, checks):
    """期待した位置が結果にない、または値が違うもの。"""
    failed = []
    for check in checks:
        found, actual = lookup(result, check["path"])
        if not found or canonical_bytes(actual) != canonical_bytes(check["equals"]):
            failed.append(check["path"])
    return failed


def load_suite(directory):
    manifest = decode_json((ROOT / "examples" / directory / "manifest.json").read_bytes())
    entries = manifest["files"] + manifest.get("accepted_boundaries", [])
    return [(f"{directory}/{e['path']}", decode_json((ROOT / "examples" / directory / e["path"]).read_bytes())) for e in entries]


def load_requests(suites=SUITES):
    return [(name, data["request"]) for suite in suites for name, data in load_suite(suite)]


def suite_report(directory, evaluate):
    """一つの例の系列を評価し、手で指定した期待と照合する。"""
    failures = []
    items = load_suite(directory)
    for name, data in items:
        bad = failed_checks(evaluate(copy.deepcopy(data["request"])), data["expected"]["checks"])
        if bad:
            failures.append({"example": name, "paths": bad})
    return {"examples": len(items), "checks": sum(len(d["expected"]["checks"]) for _, d in items), "failures": failures}


# ---- X12：共通予算の不変条件 ----
# 入力不正が予算に依らない、という不変条件の例外。仕様が、その検査を steps に含めると明記している例だけ。
# p1-a/unnormalized：重みの総和が 1 かどうかは、重みの加算を課金しながら確かめる（forecast_spec.json の steps）ので、
# 予算が足りなければ入力不正と判定する前に打切りになる。
BUDGET_DEPENDENT_REFUSALS = {"p1-a/unnormalized.json": "forecast_spec.json: 重みの加算と正規化の比較は課金される"}
VALUE_FIELDS = ("bindings", "evidence", "answer", "split", "splits", "base", "leaf_candidates", "information_requests",
                "literal_state", "positive_assertion_refs", "negative_assertion_refs", "masked_assertion_refs", "assertion_evidence", "revision_evidence",
                "converted_domain", "relation_set", "certain_relation", "calculation_evidence", "binding_evidence", "diagnostics", "artifact", "artifact_sha256", "rounding_cell", "question_results", "projection_evidence", "source_evidence")


def display_values_on_stopped(row):
    # 表示の未完了値は空配列・空object・falseでもnullの代わりにしない。
    return any(key in row and row[key] is not None for key in
               ("artifact", "artifact_sha256", "rounding_cell", "question_results", "projection_evidence", "source_evidence"))


def without_input_hash(result):
    return {k: v for k, v in result.items() if k != "input_sha256"}


def contains_value(value, wanted):
    if isinstance(value, dict):
        return any(contains_value(v, wanted) for v in value.values())
    if isinstance(value, list):
        return any(contains_value(v, wanted) for v in value)
    return value == wanted


def budget_violations(name, request, evaluate, limit=300):
    """一つの要求を、予算 0 から完了に要る steps+2 まで掃引し、型によらない不変条件の違反を返す。

    (1) 完了した結果は、予算を増やしても同じ（単調）。(2) 止まった結果は認定票を持たない。
    (3) 止まった結果の完了した行は、無制限の結果と同じ。(4) 打切りの行は値を持たない。
    (5) 入力不正・未対応は、予算に依らず同じ結果。

    掃引は予算欄を有効な値へ置換する。不正な予算欄そのものの拒否は元fixtureの照合で検査し、
    その拒否を修復後の要求へ引き継ぐことは要求しない。"""
    def run(budget):
        copied = copy.deepcopy(request)
        copied["budget"] = {"max_steps": budget}
        return evaluate(copied)

    problems, full = [], run(100000)
    if full["status"] == "resource_limit":
        # 無制限でも止まる（資源の上限）。予算が小さければ別の上限（steps）で止まってよいが、認定票は出さない
        # 明示した完了flagを持つ行は、下位計算のサイズ上限で止まった場合も検査する。
        for result, maximum in [(full, 100000), *((run(b), b) for b in (0, 1, 7))]:
            if result["status"] != "resource_limit" or contains_value(result, "certified"):
                problems.append((name, maximum, "resource_stop_not_honest"))
            for row in result.get("results", []):
                if row.get("assessment_complete") is False and (any(bool(row.get(key)) for key in VALUE_FIELDS) or display_values_on_stopped(row)):
                    problems.append((name, maximum, "value_on_stopped_row"))
        return problems, 3
    if full["status"] != "ok":
        for budget in (0, 1, 7):
            result = run(budget)
            same = without_input_hash(result) == without_input_hash(full)
            if name in BUDGET_DEPENDENT_REFUSALS:
                same = same or (result["status"] == "resource_limit" and result.get("reason_codes") == ["step_limit"])
            if not same:
                problems.append((name, budget, "refusal_depends_on_budget"))
        return problems, 3
    count = 0
    used = full.get("steps_used")
    if used is None:
        # P0 の結果は steps_used を持たない。予算を倍々に増やして、完了する予算の上限を求める（掃引の範囲を決めるためだけに使う）
        used = 1
        while used < limit:
            count += 1
            if run(used)["status"] == "ok":
                break
            used *= 2
    done_at = None
    for budget in range(0, min(used + 3, limit)):
        result = run(budget)
        count += 1
        if result["status"] == "ok":
            done_at = budget if done_at is None else done_at
            if without_input_hash(result) != without_input_hash(full):
                problems.append((name, budget, "completed_result_changed"))
            continue
        if done_at is not None:
            problems.append((name, budget, "completed_then_stopped"))
        if result["status"] != "resource_limit":
            problems.append((name, budget, "unexpected_status:" + result["status"]))
        if contains_value(result, "certified"):
            problems.append((name, budget, "certificate_on_stop"))
        rows, full_rows = result.get("results"), full.get("results")
        if isinstance(rows, list) and isinstance(full_rows, list) and len(rows) == len(full_rows):
            for row, full_row in zip(rows, full_rows):
                limited = row.get("status") != "ok" and any("step_limit" in code for code in (row.get("reason_codes") or []))
                limited = limited or row.get("assessment_complete") is False
                if limited:
                    if row.get("assessment_complete") is True:
                        problems.append((name, budget, "completion_on_stopped_row"))
                    if any(row.get(field) for field in VALUE_FIELDS):
                        problems.append((name, budget, "value_on_stopped_row"))
                    elif display_values_on_stopped(row):
                        problems.append((name, budget, "value_on_stopped_row"))
                elif row != full_row:
                    problems.append((name, budget, "completed_row_changed"))
    return problems, count


def budget_report(requests, evaluate, limit=300):
    problems, evaluations = [], 0
    for name, request in requests:
        if isinstance(request, dict) and isinstance(request.get("budget"), dict):
            found, count = budget_violations(name, request, evaluate, limit)
            problems += found
            evaluations += count
    return {"requests": sum(1 for _, r in requests if isinstance(r, dict) and isinstance(r.get("budget"), dict)),
            "evaluations": evaluations, "violations": [list(p) for p in problems]}


# ---- X11：版の比較 ----
PIN_NAMES = ("HANDOVER_SPEC_SHA256", "P0_SPEC_SHA256", "P0_RUNTIME_SHA256")
RUNNER = (
    "import copy, json, sys\n"
    "tree, source, target = sys.argv[1:4]\n"
    "sys.path.insert(0, tree + '/src')\n"
    "from med_dsl import evaluate\n"
    "requests = json.load(open(source))\n"
    "json.dump({name: evaluate(copy.deepcopy(request)) for name, request in requests.items()}, open(target, 'w'))\n"
)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True)


def has_commit(commit):
    return subprocess.run(["git", "cat-file", "-e", commit], cwd=ROOT, capture_output=True).returncode == 0


def extract(commit, destination):
    """コミットの木を作業場所へ取り出す（git archive。パスの検査つき）。"""
    data = git("archive", "--format=tar", commit).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = [m for m in tar.getmembers() if not Path(m.name).is_absolute() and ".." not in Path(m.name).parts and (m.isfile() or m.isdir())]
        try:
            tar.extractall(destination, members=members, filter="data")
        except TypeError:
            tar.extractall(destination, members=members)
    return Path(destination)


def evaluate_tree(tree, requests):
    """木の実装で要求を評価する（別のプロセス。旧版と新版の med_dsl を同じプロセスに混ぜない）。"""
    with tempfile.TemporaryDirectory() as folder:
        source, target = Path(folder) / "requests.json", Path(folder) / "results.json"
        source.write_text(json.dumps(requests), encoding="utf-8")
        subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER, str(tree), str(source), str(target)], check=True, capture_output=True)
        return json.loads(target.read_text(encoding="utf-8"))


def tree_evaluation(tree):
    """木に固定された統合評価（evaluate-p1-d）を、その木で実行する。"""
    # 取り出した木は git のリポジトリでない。評価器は実行記録のために git を呼ぶので、元のリポジトリを指す（記録の項目だけに使われる）
    env = dict(os.environ, GIT_DIR=str(ROOT / ".git"), PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-I", "-B", "scripts/research/evaluate-p1-d.py", "--cli", "--output", "data/research/p1-d/versions"],
                         cwd=tree, capture_output=True, text=True, env=env)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "{}"
    data = json.loads(last)
    manifest = Path(tree) / "examples/p1-evaluation/manifest.json"
    return {"passed": data.get("passed") is True, "p1": [data.get("p1_cases_passed"), data.get("p1_files"), data.get("p1_checks")],
            "p0": [data.get("p0", {}).get("passed_files"), data.get("p0", {}).get("passed_checks")], "bundle_sha256": data.get("bundle_sha256"),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None}


def pin_values(tree):
    text = "".join((Path(tree) / "src/med_dsl" / name).read_text(encoding="utf-8") for name in ("handover.py", "handover_common.py")
                   if (Path(tree) / "src/med_dsl" / name).is_file())
    return {n: re.search(rf'^{n} = "([0-9a-f]{{64}})"', text, re.M).group(1) for n in PIN_NAMES}


def repin(value, mapping):
    if isinstance(value, dict):
        return {k: repin(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [repin(v, mapping) for v in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def normalize(value, dropped):
    """宣言した付加の項目を除き、64桁の hash 値を区別しない形にする（再固定で変わる値の違いを無視する）。"""
    if isinstance(value, dict):
        return {k: normalize(v, dropped) for k, v in value.items() if k not in dropped}
    if isinstance(value, list):
        return [normalize(v, dropped) for v in value]
    if isinstance(value, str) and HEX64.match(value):
        return "<sha256>"
    return value


def diff_paths(a, b, path=""):
    found = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                found.append(f"{path}/{key}")
            else:
                found += diff_paths(a[key], b[key], f"{path}/{key}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for index, (x, y) in enumerate(zip(a, b)):
            found += diff_paths(x, y, f"{path}[]")
    elif a != b:
        found.append(path)
    return sorted(set(found))


def embeds_pin(request, pins):
    text = json.dumps(request, ensure_ascii=False)
    return any(value in text for value in pins)


def classify(old, new, request, mapping, dropped, refusal_codes):
    """旧入力を新版で実行した結果の分類：identical（宣言した付加を除き同じ）／pin_refused（固定した hash が変わったことによる
    拒否。入力が実際に旧い hash を埋め込んでいる場合だけ）／changed（それ以外。黙った再解釈の疑い）。"""
    a, b = normalize(old, dropped), normalize(new, dropped)
    if a == b:
        return "identical"
    if b.get("status") == "invalid_input" and (b.get("reason_codes") or [None])[0] in refusal_codes and embeds_pin(request, mapping):
        return "pin_refused"
    return "changed"


def version_report(record, current=True):
    """版の記録に沿って、旧版の再現・旧入力の分類・再固定した旧入力の期待を計算する（git の履歴が要る）。"""
    dropped = {c["path"] for c in record["declared_changes"] if c["kind"] == "added_field"}
    refusal_codes = set(record["pin_refusal_codes"])
    with tempfile.TemporaryDirectory() as folder:
        trees = {"from": extract(record["from"]["commit"], Path(folder) / "from"), "to": extract(record["to"]["commit"], Path(folder) / "to")}
        report = {"reproduction": {side: tree_evaluation(trees[side]) for side in trees}}
        old_pins, new_pins = pin_values(trees["from"]), pin_values(trees["to"])
        mapping = {old_pins[n]: new_pins[n] for n in PIN_NAMES if old_pins[n] != new_pins[n]}
        report["pins_changed"] = sorted(n for n in PIN_NAMES if old_pins[n] != new_pins[n])
        fixtures = {}
        for suite in record["suites"]:
            manifest = decode_json((trees["from"] / "examples" / suite / "manifest.json").read_bytes())
            for entry in manifest["files"]:
                fixtures[f"{suite}/{entry['path']}"] = decode_json((trees["from"] / "examples" / suite / entry["path"]).read_bytes())
        requests = {name: data["request"] for name, data in fixtures.items()}
        repinned = {name: repin(request, mapping) for name, request in requests.items()}
        old = evaluate_tree(trees["from"], requests)
        sides = {"to": trees["to"]}
        if current:
            sides["current"] = ROOT
        report["inputs"] = len(requests)
        for side, tree in sides.items():
            new = evaluate_tree(tree, requests)
            again = evaluate_tree(tree, repinned)
            categories = {"identical": [], "pin_refused": [], "changed": []}
            for name in requests:
                categories[classify(old[name], new[name], requests[name], mapping, dropped, refusal_codes)].append(name)
            after = {"identical": [], "changed": {}}
            for name in requests:
                a, b = normalize(old[name], dropped), normalize(again[name], dropped)
                if a == b:
                    after["identical"].append(name)
                else:
                    after["changed"][name] = diff_paths(a, b)
            report[side] = {
                "old_inputs_without_repin": {k: sorted(v) for k, v in categories.items()},
                "repinned": {"identical": sorted(after["identical"]), "changed": dict(sorted(after["changed"].items())),
                             "failing_old_expectations": sorted(n for n in requests if failed_checks(again[n], fixtures[n]["expected"]["checks"]))},
                "carry_added_field": sorted(n for n in requests if any(contains_key(again[n], key) for key in dropped)),
            }
        return report


def contains_key(value, key):
    if isinstance(value, dict):
        return key in value or any(contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(contains_key(v, key) for v in value)
    return False


def record_mismatches(record, report):
    """記録（宣言と固定した測定値）と計算した報告の食い違い。空なら一致。"""
    problems = []
    for side in ("from", "to"):
        got, want = report["reproduction"][side], record[side]["evaluation"]
        if got != want:
            problems.append(f"reproduction_{side}")
    if report["pins_changed"] != sorted(record["pins_changed"]):
        problems.append("pins_changed")
    measured = record["measured"]
    declared_inputs = {n for c in record["declared_changes"] for n in c.get("inputs", [])}
    declared_paths = {(n, c["path"]) for c in record["declared_changes"] if c["kind"] == "changed_value" for n in c.get("inputs", [])}
    for side in [s for s in ("to", "current") if s in report]:
        part = report[side]
        before, after = part["old_inputs_without_repin"], part["repinned"]
        if {k: len(v) for k, v in before.items()} != measured["old_inputs_without_repin"]:
            problems.append(f"{side}:classification_counts")
        if len(after["identical"]) != measured["repinned"]["identical"] or len(after["failing_old_expectations"]) != measured["repinned"]["failing_old_expectations"]:
            problems.append(f"{side}:repinned_counts")
        # 宣言していない差は許さない：再固定後に変わった入力と経路は、宣言した変更に属する
        observed = {(n, p) for n, paths in after["changed"].items() for p in paths}
        if observed != declared_paths:
            problems.append(f"{side}:undeclared_or_missing_change")
        if set(before["changed"]) - declared_inputs:
            problems.append(f"{side}:undeclared_change_without_repin")
        if len(part["carry_added_field"]) != measured["carry_added_field"]:
            problems.append(f"{side}:added_field_count")
    return problems
