"""P2-a の拡張契約で「防護例のない義務」だった義務に、拒否・境界の例を examples/p2/ に書き出す。
期待結果は各ゲートの意味から手で指定し、処理系の出力から生成しない。例外は予算の境界の n（無制限の実行の steps_used を測る）。
使い方: python3 -B scripts/research/p2/gen_guard_fixtures.py（環境変数 P2_REPO＝作業ツリー。既定はこのリポジトリ）"""
import copy, hashlib, json, os, sys
from pathlib import Path

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "src"))
from med_dsl import evaluate
from med_dsl.chain import endpoint, scope_hashes
from med_dsl.events import EVENT_PROFILE, EVENT_SPEC_SHA256, _restore, _source
from med_dsl.handover import HANDOVER_PROFILE, HANDOVER_SPEC_SHA256
from med_dsl.validation import digest

OUT = ROOT / "examples/p2"
OUT.mkdir(exist_ok=True)
CASES, BOUNDARIES = [], []


def src(ref):
    suite, name = ref.split("/")
    return json.loads((ROOT / f"examples/{suite}/{name}.json").read_text())


def request_of(ref):
    return copy.deepcopy(src(ref)["request"])


def chk(path, equals):
    return {"path": path, "equals": equals}


def case(cid, slug, extension, obligation, kind, gate, base, request, checks):
    CASES.append(dict(cid=cid, slug=slug, extension=extension, obligation=obligation, kind=kind, gate=gate, base=base,
                      request=request, checks=checks))


def run(request, budget=100000):
    r = copy.deepcopy(request)
    r["budget"] = {"max_steps": budget}
    return evaluate(r)


def with_budget(request, budget):
    r = copy.deepcopy(request)
    r["budget"] = {"max_steps": budget}
    return r


def minimal_ok_budget(request):
    for b in range(0, 2000):
        if run(request, b)["status"] == "ok":
            return b
    raise SystemExit("no budget up to 2000 completes")


# ---- 予算の境界（K-RES）：n = 完了に要る最小の steps。n-1 は止まり、n は完了する ----
BOUNDARY = [  # (slug, 拡張, 例)
    ("definitions", "p0-definitions", "p0/definition-extension"),
    ("absence", "p1-absence", "p1-c/absence-is-negative"),
    ("event-chain", "p1-event-chain", "p1-c/event-renaming-chain"),
    ("events", "p1-events", "p1-b/native-query"),
    ("rename-events", "p1-handover-host", "p1-c/rename-events"),
    ("projection", "p1-projection", "p1-c/kept-query-scope"),
    ("reference", "p1-reference", "p1-c/identity-template"),
    ("replay", "p1-replay", "p1-c/new-guarantee-independent-of-old-binary"),
]
MEASURED = {}
for slug, extension, ref in BOUNDARY:
    base = request_of(ref)
    n = minimal_ok_budget(base)
    MEASURED[slug] = n
    stop = [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"])]
    if slug != "events":      # events は完了した行を返す設計（汚れない）ので incomplete は固定しない
        stop.append(chk(["incomplete"], ["request"]))
    done = [dict(c) for c in src(ref)["expected"]["checks"]]
    if slug != "definitions":
        done.append(chk(["steps_used"], n))
    case(None, f"budget-below-{slug}", extension, "K-RES", "boundary", f"課金の境界：steps が {n - 1}（完了に要る {n} より 1 少ない）で止まる",
         ref, with_budget(base, n - 1), stop)
    case(None, f"budget-exact-{slug}", extension, "K-RES", "boundary", f"課金の境界：steps がちょうど {n} で完了する（上限を厳しくしすぎない）",
         ref, with_budget(base, n), done)

# ---- K-STOP ----
base = request_of("p0/definition-extension")
case(None, "definitions-zero-budget", "p0-definitions", "K-STOP", "refusal", "予算 0 では認定票を出さない", "p0/definition-extension",
     with_budget(base, 0), [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["incomplete"], ["request"])])
empty = copy.deepcopy(base)
empty["extension"] = {"ref": "fiction:definitions:extension@1", "profile": "p0-positive-1", "predicates": [], "definitions": [], "inclusions": [], "dependencies": []}
case(None, "definitions-empty-extension-zero-budget", "p0-definitions", "K-STOP", "refusal", "追加が空でも、予算 0 は未評価（認定票を出さない）", "p0/definition-extension",
     with_budget(empty, 0), [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["incomplete"], ["request"])])
case(None, "definitions-empty-extension-one-step", "p0-definitions", "K-STOP", "boundary", "追加が空なら 1 step で認定する（予算 0 との境界）", "p0/definition-extension",
     with_budget(empty, 1), [chk(["status"], "ok"), chk(["certificate", "status"], "certified")])


def seal(data):
    """変更した鎖の入力の端点・範囲の宣言を、実体から作り直す（入力の構成だけ。期待結果は別に指定する）。"""
    middle, packages = _restore(data["intermediate"])
    final, last_packages = _restore(data["target"])
    ordered = _source(data["source"], data["relation_ref"])
    old_scope, new_scope = scope_hashes(data["views"], data["queries"], data["relation_ref"])
    a = endpoint(data["source"], data["source"], ordered)
    b = endpoint(data["intermediate"], middle, packages, True)
    c = endpoint(data["target"], final, last_packages, True)
    data["stages"] = [{"kind": "event_reification", "source": a, "target": b, "source_scope_sha256": old_scope, "target_scope_sha256": new_scope},
                      {"kind": "event_rename", "source": b, "target": c, "source_scope_sha256": new_scope, "target_scope_sha256": new_scope}]
    return data


def consumer(profile, spec, operation):
    return {"profile": profile, "profile_spec_sha256": spec, "operations": [operation]}


def build_chain(source, views, queries, relation_ref):
    """源の履歴から、事象化と改名の鎖の入力を作る（実装の事象化・改名を使うのは入力の構成だけ）。"""
    reified = evaluate({"schema_version": "p1-events-request-draft-1", "operation": "reify_events",
                        "consumer": consumer(EVENT_PROFILE, EVENT_SPEC_SHA256, "reify_events"), "budget": {"max_steps": 100000},
                        "source": source, "relation_ref": relation_ref, "target_ledger_ref": "fiction:L1"})
    assert reified["status"] == "ok", reified
    target = reified["target"]
    renames = [{"from_ref": h["statement"]["event_ref"], "to_ref": f"urn:fiction:renamed:{i}"}
               for i, h in enumerate(h for h in target["ledger"]["assertions"] if h["statement"]["kind"] == "event_tuple")]
    renamed = evaluate({"schema_version": "p1-handover-request-draft-1", "operation": "rename_events",
                        "consumer": consumer(HANDOVER_PROFILE, HANDOVER_SPEC_SHA256, "rename_events"), "budget": {"max_steps": 100000},
                        "target": target, "renames": renames, "target_ledger_ref": "fiction:L2"})
    assert renamed["status"] == "ok", renamed
    data = {"schema_version": "p1-handover-request-draft-1", "operation": "check_event_chain",
            "consumer": consumer(HANDOVER_PROFILE, HANDOVER_SPEC_SHA256, "check_event_chain"), "budget": {"max_steps": 100000},
            "source": source, "relation_ref": relation_ref, "intermediate": target, "target": renamed["target"],
            "renames": renames, "stages": [], "views": views, "queries": queries}
    return seal(data)


chain = request_of("p1-c/event-renaming-chain")
unknown = copy.deepcopy(chain)
unknown["source"]["ledger"]["assertions"][0]["required_capabilities"] = ["fiction:unknown@1"]
for key in ("intermediate", "target"):
    unknown[key]["ledger"]["assertions"][0]["required_capabilities"] = ["fiction:unknown@1"]
    unknown[key]["source_sha256"] = digest(unknown["source"])
case(None, "chain-unknown-capability", "p1-event-chain", "K-STOP", "refusal", "未知の能力を含む履歴の鎖は、未評価を残して認定しない", "p1-c/event-renaming-chain",
     seal(unknown), [chk(["status"], "ok"), chk(["certificate", "status"], "not_certified"), chk(["certificate", "reason_codes"], ["incomparable_execution"]),
                     chk(["incomplete", 0, "check_index"], 0)])

rename = request_of("p1-c/rename-events")
bad = copy.deepcopy(rename)
bad["operation"] = "audit_everything"
bad["consumer"]["operations"] = ["audit_everything"]
case(None, "host-unsupported-operation", "p1-handover-host", "K-STOP", "refusal", "未登録の操作は、別の操作で代用せず unsupported_profile", "p1-c/rename-events", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_operation"]), chk(["error_path"], "operation")])
bad = copy.deepcopy(rename)
bad["consumer"]["operations"] = ["rename_events", "fake_op"]
case(None, "host-consumer-operation-unsupported", "p1-handover-host", "K-STOP", "refusal", "consumer が未登録の操作を宣言していれば止まる", "p1-c/rename-events", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_operation"]), chk(["error_path"], "consumer.operations")])
bad = copy.deepcopy(rename)
bad["consumer"]["profile"] = "p1-handover-draft-9"
case(None, "host-consumer-profile", "p1-handover-host", "K-STOP", "refusal", "consumer の profile が違えば unsupported_profile", "p1-c/rename-events", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_profile"]), chk(["error_path"], "consumer.profile")])

reference = request_of("p1-c/identity-template")
bad = copy.deepcopy(reference)
bad["finite_domain_sizes"] = [2]
case(None, "reference-finite-probe-unsupported", "p1-reference", "K-STOP", "refusal", "語彙を持つ入力への有限領域の探査は未対応として止まる（非含意にしない）", "p1-c/identity-template", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_finite_probe"])])


def nested_query(request, depth):
    r = copy.deepcopy(request)
    formula = {"kind": "atom", "predicate": "B", "args": [{"const": "a"}]}
    for _ in range(depth):
        formula = {"kind": "not", "body": formula}
    r["queries"][0]["formula"] = formula
    return r


case(None, "reference-formula-depth-limit", "p1-reference", "K-STOP", "boundary", "式の深さが上限（16）を超えれば resource_limit（非含意に見せない）", "p1-c/identity-template",
     nested_query(reference, 17), [chk(["status"], "resource_limit"), chk(["reason_codes"], ["formula_limit"])])
case(None, "reference-formula-depth-exact", "p1-reference", "K-RES", "boundary", "式の深さがちょうど上限（16）なら評価する（上限を厳しくしすぎない）", "p1-c/identity-template",
     nested_query(reference, 16), [chk(["status"], "ok"), chk(["certificate", "status"], "certified")])

# ---- K-INV ----
bad = request_of("p0/definition-extension")
bad["ledger"] = {"ref": "fiction:ledger:none@1", "assertions": [], "reviews": []}
case(None, "definitions-ledger-field-refused", "p0-definitions", "K-INV", "refusal", "認定は定義パッケージだけを読む：台帳（採用・確認）を受け付けない", "p0/definition-extension", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])

ai = src("p1-b/ai-unreviewed")["request"]
case(None, "chain-ai-candidate-not-adopted", "p1-event-chain", "K-INV", "non_conversion", "確認のない AI 候補は、鎖を通っても支持にならない（未決のまま両計算が一致）", "p1-b/ai-unreviewed",
     build_chain(copy.deepcopy(ai["source"]), copy.deepcopy(ai["views"]), copy.deepcopy(ai["queries"]), ai["relation_ref"]),
     [chk(["status"], "ok"), chk(["finite_checks", 0, "comparison", "status"], "matched"), chk(["finite_checks", 1, "comparison", "status"], "matched"),
      chk(["finite_checks", 0, "target_result", "results", 0, "status"], "undetermined"),
      chk(["finite_checks", 1, "target_result", "results", 0, "status"], "undetermined")])
case(None, "chain-zero-budget", "p1-handover-host", "K-INV", "non_conversion", "打切り（予算 0）で認定票・部分の報告を出さない", "p1-c/event-renaming-chain",
     with_budget(chain, 0), [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["incomplete"], ["request"])])

# ---- COMP-2 ----
outside = copy.deepcopy(chain)
outside["queries"].append({"id": "q3", "context_ref": outside["queries"][0]["context_ref"], "kind": "event_identity", "required": False})
case(None, "chain-out-of-scope-query", "p1-event-chain", "COMP-2", "non_conversion", "鎖の範囲外の問い（事象の同一性）を、旧の問いの認定に含めない", "p1-c/event-renaming-chain",
     seal(outside), [chk(["status"], "ok"), chk(["certificate", "status"], "not_certified"), chk(["certificate", "reason_codes"], ["query_out_of_scope"]),
                     chk(["certificate", "scope", "query_ids"], ["q1", "q2"]), chk(["out_of_scope_query_ids"], ["q3"])])

# ---- 予測 R2-2 ----
forecast = request_of("p1-a/finite-forecast")
bad = copy.deepcopy(forecast)
bad["package"] = {"profile": "p1-finite-forecast-draft-1"}
case(None, "forecast-arbitrary-package-refused", "p1-finite-forecast", "R2-2", "refusal", "任意の package を受け付けない（報告専用の固定 package だけ）", "p1-a/finite-forecast", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])
bad = copy.deepcopy(forecast)
bad["report_snapshot"]["ledger"]["assertions"][0]["atom"]["predicate"] = "fiction:clinical-X@1"
case(None, "forecast-nonreport-predicate-refused", "p1-finite-forecast", "R2-2", "refusal", "報告専用の述語以外（基底の語彙の述語）を台帳に持ち込めない", "p1-a/finite-forecast", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["undeclared_predicate"]), chk(["error_path"], "atom.predicate")])

# ---- 参考意味 R3-4, R3-5, R3-6 ----
stronger = copy.deepcopy(reference)
stronger["target"]["data"].append({"kind": "atom", "predicate": "B", "args": [{"const": "a"}]})
stronger["models"] = []
case(None, "reference-stronger-target", "p1-reference", "R3-4", "non_conversion", "新理論が文を一つ追加するとき、保存を認定せず、被覆を真にも偽にもしない", "p1-c/identity-template", stronger,
     [chk(["status"], "ok"), chk(["certificate", "status"], "not_certified"), chk(["certificate", "reason_codes"], ["model_coverage_not_established"]),
      chk(["model_coverage"], None), chk(["model_reduct"], True)])
bad = copy.deepcopy(reference)
bad["ledger"] = {"ref": "fiction:ledger:none@1", "assertions": [], "reviews": []}
case(None, "reference-ledger-field-refused", "p1-reference", "R3-5", "refusal", "参考意味は履歴・採用を持たない：台帳を受け付けない", "p1-c/identity-template", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])
bad = copy.deepcopy(reference)
bad["target"]["data"].append({"kind": "atom", "predicate": "C", "args": [{"const": "a"}]})
case(None, "reference-new-name-refused", "p1-reference", "R3-6", "refusal", "翻訳は新しい名前を導入しない：宣言した語彙にない述語を目標に持ち込めない", "p1-c/identity-template", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["undeclared_predicate"])])

# ---- 書き出し ----
files = []
for i, c in enumerate(CASES, 1):
    cid = f"GD{i:02}"
    data = {"schema_version": "p1-fixture-draft-1", "fixture_id": cid, "fixture_version": 1, "fictional": True,
            "review_state": "author_draft", "extension": c["extension"], "obligation": c["obligation"], "kind": c["kind"],
            "gate": c["gate"], "derived_from": c["base"], "request": c["request"],
            "expected": {"comparison": "required_paths", "checks": c["checks"]}}
    path = OUT / f"{c['slug']}.json"
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    files.append({"fixture_id": cid, "path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                  "extension": c["extension"], "obligation": c["obligation"], "kind": c["kind"], "gate": c["gate"]})
manifest = {"schema_version": "p2-guard-examples-manifest-draft-1", "status": "author_draft", "independent_review": False,
            "evaluation_frozen": False, "contract_version": "p0-draft-2",
            "note": "P2-a の防護例（宣言の guards が引く）。P1の20条件・80 JSON・417必須パス、231開発テスト、レビュー系列とは別の分母。"
                    "期待結果はゲートの意味から手で指定した。予算の境界の n（完了に要る最小の steps）だけは無制限の実行から測った。",
            "measured_budgets": MEASURED, "files": files}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(files), "guard examples written;", "n =", MEASURED)
