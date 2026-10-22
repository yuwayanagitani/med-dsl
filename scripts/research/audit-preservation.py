#!/usr/bin/env python3
"""固定済み P0/P1 の認定・参考含意を、有限解釈の全列挙で事前監査する。"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
# p0-draft-1 の基準は 1f01ed65…（e73d4ba）、p0-draft-2 の固定は de307919…（2b501c1）。P2-a で extensions.py を加えた固定に合わせて更新
BASELINE_MANIFEST_SHA256 = "1eea02fdba34a978de131ec240f0b23872df1217976c84e4aaf521de5a8390b3"
sys.path.insert(0, str(ROOT / "src"))
from med_dsl import evaluate
from med_dsl.validation import canonical_bytes, digest


def baseline():
    spec = importlib.util.spec_from_file_location("fixed_p1", ROOT / "scripts/research/evaluate-p1-d.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fingerprint = module.preflight()[1]
    if fingerprint != BASELINE_MANIFEST_SHA256:
        raise ValueError("review_baseline_mismatch")
    return fingerprint


def fixture(folder, name):
    return json.loads((ROOT / f"examples/{folder}/{name}.json").read_text())["request"]


def subsets(names):
    return [list(c) for n in range(1, len(names) + 1) for c in itertools.combinations(names, n)]


def definition_options(symbol, previous):
    return ([{"kind": "defined", "symbol": symbol, "all_of": refs} for refs in subsets(previous)]
            + [{"kind": "subtype", "symbol": symbol, "parent": ref} for ref in previous])


def extension_requests():
    template = fixture("p0", "definition-extension")
    refs = [f"fiction:{n}@1" for n in ("A", "B", "N", "M")]
    for old_bits in range(4):
        for first, second in itertools.product(definition_options(refs[2], refs[:2]),
                                                definition_options(refs[3], refs[:3])):
            request = deepcopy(template)
            request["base_package"]["inclusions"] = [{"sub": a, "super": b} for i, (a, b) in
                enumerate(((refs[0], refs[1]), (refs[1], refs[0]))) if old_bits & (1 << i)]
            request["extension"]["predicates"].append({"ref": refs[3], "roles": ["subject"]})
            request["extension"]["definitions"] = [first, second]
            yield request


def satisfies(model, package):
    """述語を有限集合のbit maskとして解釈する。nativeの規則/閉包は使わない。"""
    if any(model[i["sub"]] & ~model[i["super"]] for i in package["inclusions"]):
        return False
    for d in package["definitions"]:
        lhs = model[d["symbol"]]
        if d["kind"] == "subtype":
            if lhs & ~model[d["parent"]]:
                return False
        else:
            rhs = model[d["all_of"][0]]
            for ref in d["all_of"][1:]:
                rhs &= model[ref]
            if lhs != rhs:
                return False
    return True


def extension_image(request, size):
    base, extension = request["base_package"], request["extension"]
    old = [p["ref"] for p in base["predicates"]]
    names = old + [p["ref"] for p in extension["predicates"]]
    old_models = {bits for bits in itertools.product(range(1 << size), repeat=len(old))
                  if satisfies(dict(zip(old, bits)), base)}
    image, scans = set(), 0
    for bits in itertools.product(range(1 << size), repeat=len(names)):
        scans += 1
        model = dict(zip(names, bits))
        if satisfies(model, base) and satisfies(model, extension):
            image.add(bits[:len(old)])
    return old_models, image, scans


def audit_extensions():
    rows = []
    for i, request in enumerate(extension_requests()):
        native = evaluate(deepcopy(request))
        for size in (1, 2, 3):
            old, image, scans = extension_image(request, size)
            passed = native.get("certificate", {}).get("status") == "certified" and old == image
            rows.append({"id": f"extension-{i:03}-domain-{size}", "request_sha256": digest(request),
                         "native_result_sha256": digest(native), "domain_size": size, "models_scanned": scans,
                         "old_models": len(old), "reduct_image": len(image), "passed": passed,
                         "missing_old_models": sorted(old - image), "invalid_reducts": sorted(image - old)})
    return rows


def unary_theory(bits):
    atom = lambda ref, term: {"kind": "atom", "predicate": ref, "args": [term]}
    theory = [{"kind": "forall", "var": "x", "body": {"kind": "implies",
              "left": atom(a, {"var": "x"}), "right": atom(b, {"var": "x"})}}
              for i, (a, b) in enumerate((("A", "B"), ("B", "A"))) if bits & (1 << i)]
    data = [atom(p, {"const": "a"}) for i, p in enumerate(("A", "B")) if bits & (1 << (i + 2))]
    return {"theory": theory, "data": data}


def query_formulas():
    out = []
    for ref in ("A", "B"):
        out.append({"id": ref + "_a", "formula": {"kind": "atom", "predicate": ref, "args": [{"const": "a"}]}})
        for kind in ("exists", "forall"):
            out.append({"id": kind + "_" + ref, "formula": {"kind": kind, "var": "x", "body":
                       {"kind": "atom", "predicate": ref, "args": [{"var": "x"}]}}})
    return out


def query_truth(a, b):
    # 領域 {u,v}、a=u。一般AST評価器を再実装せず、この生成族を直接計算する。
    return {"A_a": bool(a & 1), "B_a": bool(b & 1), "exists_A": bool(a),
            "exists_B": bool(b), "forall_A": a == 3, "forall_B": b == 3}


def model_entry(a, b, relation=None):
    predicates = {p: [[v] for i, v in enumerate(("u", "v")) if mask & (1 << i)]
                  for p, mask in (("A", a), ("B", b))}
    if relation is not None:
        predicates["r"] = [list(pair) for i, pair in enumerate(itertools.product(("u", "v"), repeat=2))
                           if relation & (1 << i)]
    return {"id": f"m-{a}-{b}-{relation}", "model": {"domain": ["u", "v"],
            "constants": {"a": "u"}, "predicates": predicates}}


def unary_valid(bits, a, b):
    return (not bits & 1 or not a & ~b) and (not bits & 2 or not b & ~a) and (
            not bits & 4 or bool(a & 1)) and (not bits & 8 or bool(b & 1))


def reference_errors(request, result, oracle):
    """oracle は全列挙したモデルの {valid:側別, truth:問別}。native truth を使わない。"""
    errors = []
    if result.get("status") != "ok":
        return ["native_not_ok"]
    supplied = {m["id"] for m in request["models"]}
    if (len(result.get("results", [])) != len(request["queries"])
            or {r["query_id"] for r in result["results"]} != {q["id"] for q in request["queries"]}
            or len(result.get("models", [])) != len(supplied)
            or {m["model_id"] for m in result["models"]} != supplied):
        return ["missing_or_duplicate_native_rows"]
    identity = {canonical_bytes(f) for f in request["source"]["theory"] + request["source"]["data"]} == {
        canonical_bytes(f) for f in request["target"]["theory"] + request["target"]["data"]}
    if result["certificate"]["status"] == "certified" and not identity:
        errors.append("unsupported_identity_certificate")
    for row in result["models"]:
        expected = oracle[row["model_id"]]
        if any(row[s + "_model"] != expected["valid"][s] for s in ("source", "target")) or row["query_truth"] != expected["truth"]:
            errors.append("finite_model_truth_mismatch")
    for row in result["results"]:
        for side in ("source", "target"):
            answer, qid = row[side], row["query_id"]
            counter = answer["countermodel_id"]
            all_true = all(m["truth"][qid] for m in oracle.values() if m["valid"][side])
            query = next(q["formula"] for q in request["queries"] if q["id"] == qid)
            if query in request[side]["theory"] + request[side]["data"] and answer["status"] != "entailed":
                errors.append("asserted_positive_control_failed")
            if answer["status"] == "entailed":
                if answer["entails"] is not True or not answer["proof"] or counter is not None or not all_true:
                    errors.append("unsound_or_malformed_entailment")
            elif answer["status"] == "not_entailed":
                if (answer["entails"] is not False or answer["proof"] is not None or counter not in supplied
                        or not oracle[counter]["valid"][side] or oracle[counter]["truth"][qid]):
                    errors.append("invalid_countermodel")
            elif answer["status"] != "unassessed" or answer["entails"] is not None or answer["proof"] is not None or counter is not None:
                errors.append("unknown_is_not_false")
    for field, left, right in (("model_coverage", "source", "target"), ("model_reduct", "target", "source")):
        valid = all(not m["valid"][left] or m["valid"][right] for m in oracle.values())
        if result[field] is True and not valid:
            errors.append("unsound_" + field)
        if result[field] is False:
            key = result["coverage_countermodel_id" if field == "model_coverage" else "reduct_countermodel_id"]
            if valid or key not in supplied or not oracle[key]["valid"][left] or oracle[key]["valid"][right]:
                errors.append("missing_" + field + "_countermodel")
    return errors


def reference_row(label, request, oracle):
    result = evaluate(deepcopy(request))
    errors = reference_errors(request, result, oracle)
    return {"id": label, "request_sha256": digest(request), "native_result_sha256": digest(result),
            "models_enumerated": len(oracle), "models_supplied": len(request["models"]),
            "answer_checks": 2 * len(request["queries"]), "passed": not errors, "errors": errors,
            "status_counts": {state: sum(r[s]["status"] == state for r in result.get("results", [])
                              for s in ("source", "target")) for state in ("entailed", "not_entailed", "unassessed")}}


def audit_unary_reference():
    template = fixture("p1-c", "coverage-countermodel")
    template["queries"] = query_formulas()
    models = [model_entry(a, b) for a, b in itertools.product(range(4), repeat=2)]
    rows = []
    for source, target in itertools.product(range(16), repeat=2):
        request = {**template, "source": unary_theory(source), "target": unary_theory(target), "models": models}
        oracle = {entry["id"]: {"valid": {"source": unary_valid(source, a, b), "target": unary_valid(target, a, b)},
                  "truth": query_truth(a, b)} for entry, (a, b) in zip(models, itertools.product(range(4), repeat=2))}
        rows.append(reference_row(f"unary-{source:02}-{target:02}", request, oracle))
    return rows


def existential_valid(premise, consequent, reverse, fact_bits, a, b, relation):
    masks = {"A": a, "B": b}
    if fact_bits & 1 and not a & 1 or fact_bits & 2 and not b & 1:
        return False
    return all(not masks[premise] & (1 << x) or any(
        masks[consequent] & (1 << y) and relation & (1 << (2 * y + x if reverse else 2 * x + y))
        for y in (0, 1)) for x in (0, 1))


def audit_existential_reference():
    template = fixture("p1-c", "existential-without-named-witness")
    rows = []
    for premise, consequent, reverse, facts in itertools.product(("A", "B"), ("A", "B"), (False, True), range(4)):
        request = deepcopy(template)
        rule = request["source"]["theory"][0]
        rule["body"]["left"]["predicate"] = premise
        items = rule["body"]["right"]["body"]["items"]
        items[1]["predicate"] = consequent
        if reverse:
            items[0]["args"].reverse()
        request["source"]["data"] = unary_theory(facts << 2)["data"]
        request["target"]["data"] = deepcopy(request["source"]["data"])
        request["queries"] = query_formulas()
        oracle, models = {}, {}
        for a, b, r in itertools.product(range(4), range(4), range(16)):
            entry = model_entry(a, b, r)
            models[entry["id"]] = entry
            oracle[entry["id"]] = {"valid": {"source": existential_valid(premise, consequent, reverse, facts, a, b, r),
                  "target": unary_valid(facts << 2, a, b)}, "truth": query_truth(a, b)}
        # native は最大16候補。全256解釈の評価はoracle側で行い、候補は証人だけを渡す。
        selected = set()
        for side in ("source", "target"):
            valid = [key for key, m in oracle.items() if m["valid"][side]]
            selected.add(valid[0])
            for q in request["queries"]:
                witness = next((key for key in valid if not oracle[key]["truth"][q["id"]]), None)
                if witness is not None:
                    selected.add(witness)
        for left, right in (("source", "target"), ("target", "source")):
            witness = next((key for key, m in oracle.items() if m["valid"][left] and not m["valid"][right]), None)
            if witness is not None:
                selected.add(witness)
        request["models"] = [models[key] for key in sorted(selected)]
        rows.append(reference_row(f"existential-{premise}-{consequent}-{int(reverse)}-{facts}", request, oracle))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/preservation-audit/latest")
    args = parser.parse_args()
    initial = baseline()
    sources = ["scripts/research/audit-preservation.py", "tests/audits/test_preservation_audit.py",
               "docs/research/16-proof-obligations.md", "docs/research/16-review-plan.md",
               "docs/research/16-review-record-template.md", "examples/audits/existential-reversed.json"]
    import hashlib
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    records = {"extensions": audit_extensions(), "unary_reference": audit_unary_reference(),
               "existential_reference": audit_existential_reference()}
    example = json.loads((ROOT / sources[-1]).read_text())
    actual = evaluate(deepcopy(example["request"]))
    checks = []
    for expected in example["expected"]["checks"]:
        value = actual
        for key in expected["path"]:
            value = value[key]
        checks.append(canonical_bytes(value) == canonical_bytes(expected["equals"]))
    records["scope_boundary"] = [{"id": "PR01", "passed": all(checks), "checks": checks, "result": actual}]
    if baseline() != initial or any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value for name, value in hashes.items()):
        raise ValueError("audit_inputs_changed")
    report = {"schema_version": "preservation-pre-review-draft-1", "recorded_at": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "baseline_manifest_sha256": initial, "audit_sources": hashes, "audit_bundle_sha256": digest(hashes),
              "independent_review": False, "formal_proof_checked": False, "evaluation_frozen": False,
              "summary": {name: {"checks": len(rows), "passed": sum(r["passed"] for r in rows)} for name, rows in records.items()},
              "passed": all(r["passed"] for rows in records.values() for r in rows), "records": records}
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "data/research/preservation-audit").resolve()):
        raise ValueError("output_must_be_under_preservation_audit")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"], "passed": report["passed"], "audit_bundle_sha256": report["audit_bundle_sha256"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
