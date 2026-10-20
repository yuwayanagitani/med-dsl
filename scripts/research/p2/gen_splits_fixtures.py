"""P2-c（概念の分割の併用）の例を examples/p2-splits/ に書き出す。
期待結果は文書 25 の意味から手で導き、処理系の出力から生成しない。例外は予算の境界の n（完了に要る最小の steps を測る）。
使い方: python3 -B scripts/research/p2/gen_splits_fixtures.py（環境変数 P2_REPO＝作業ツリー。既定はこのリポジトリ）"""
import copy, hashlib, json, os, sys
from pathlib import Path

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "src"))
from med_dsl import evaluate
from med_dsl.split import SPLIT_PROFILE
from med_dsl.splits import SPEC_SHA256, SPLITS_PROFILE

OUT = ROOT / "examples/p2-splits"
OUT.mkdir(exist_ok=True)

S = "fiction:person:1"
P, R, A, B, C, D, X = (f"fiction:{n}@1" for n in ("P", "R", "A", "B", "C", "D", "X"))
C_OLD = "fiction:context:old@1"
POLICY = "fiction:confirmed-explicit-revision@1"
OTHER_CAP = "fiction:other-capability@1"
VIEW = {"id": "v1", "as_of": "2026-01-01T00:00:00Z", "policy_ref": POLICY}
CASES = []


def chk(path, equals):
    return {"path": path, "equals": equals}


def case(slug, obligations, kind, gate, request, checks):
    CASES.append(dict(slug=slug, obligations=obligations, kind=kind, gate=gate, request=request, checks=checks))


def package(names=(P, R, A, B, C, D, X)):
    return {"ref": "fiction:package:splits@1", "profile": "p0-positive-1", "predicates": [{"ref": n, "roles": ["subject"]} for n in names],
            "definitions": [], "inclusions": [], "dependencies": []}


def assertion(ident, predicate, polarity="positive", certainty="confirmed", origin="observed", caps=(), at="2020-01-02T00:00:00Z"):
    return {"id": ident, "context_ref": C_OLD, "atom": {"predicate": predicate, "args": [S]}, "polarity": polarity, "certainty": certainty,
            "recorded_at": at, "origin": {"kind": origin, "ref": f"fiction:source:{ident}"}, "supersedes": [], "required_capabilities": list(caps)}


def review(ident, ref):
    return {"id": ident, "assertion_ref": ref, "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
            "recorded_at": "2020-01-03T00:00:00Z", "outcome": "confirmed"}


def source(assertions=(), reviews=(), names=(P, R, A, B, C, D, X)):
    return {"package": package(names), "contexts": [{"ref": C_OLD, "subject_ref": S, "effective_at": "2020-01-01T00:00:00Z", "purpose": "fiction:research"}],
            "ledger": {"ref": "fiction:ledger:splits@1", "assertions": list(assertions), "reviews": list(reviews)}}


def split(head, parts):
    return {"parent": head, "parts": list(parts)}


def consumer(operation, extra=()):
    return {"profile": SPLITS_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": [operation, *extra]}


def check_request(splits, names=(P, R, A, B, C, D, X), budget=1000):
    return {"schema_version": "p2-splits-request-draft-1", "operation": "check_split_combination", "consumer": consumer("check_split_combination"),
            "budget": {"max_steps": budget}, "source": {"package": package(names)}, "splits": splits}


def query_request(splits, assertions=(), reviews=(), budget=1000, views=None, queries=None):
    return {"schema_version": "p2-splits-request-draft-1", "operation": "query_split_combination", "consumer": consumer("query_split_combination"),
            "budget": {"max_steps": budget}, "source": source(assertions, reviews), "views": views or [VIEW], "splits": splits,
            "queries": queries or [{"id": "q1", "context_ref": C_OLD, "subject": S, "required": True}]}


def reviewed(*items):
    return list(items), [review(f"r{a['id'][1:]}", a["id"]) for a in items]


def joint(i, status, candidates, differs, individual):
    return [chk(["results", 0, "splits", i, "joint", "status"], status), chk(["results", 0, "splits", i, "joint", "candidates"], candidates),
            chk(["results", 0, "splits", i, "individual", "status"], individual), chk(["results", 0, "splits", i, "differs"], differs)]


OK = chk(["status"], "ok")
K04 = [split(P, [A, B]), split(R, [A, B])]
SHARED = [split(P, [A, B]), split(R, [A, C])]
CHAIN = [split(P, [A, B]), split(A, [C, D])]
DISJOINT = [split(P, [A, B]), split(R, [C, D])]

# ---- 判定（check_split_combination）----
case("check-k04-shared-parts", ["JOINT-3", "JOINT-1", "JOINT-6"], "refusal",
     "K04 型：部分を共有する二つの分割は、単独ではどちらも保存的だが、併用は旧語彙に P = R を強制するので不認定（反例つき）",
     check_request(K04),
     [OK, chk(["certificate", "status"], "not_certified"), chk(["certificate", "reason_codes"], ["not_conservative_over_old_symbols"]),
      chk(["certificate", "counterexample", "old_valuation"], {P: 0, R: 1}), chk(["certificate", "basis"], "recomputed_from_the_combination"),
      chk(["individual", 0, "certificate"], "certified"), chk(["individual", 1, "certificate"], "certified"),
      chk(["structure", "kind"], "shared_parts"), chk(["structure", "forest_condition"], False), chk(["structure", "components"], [[0, 1]]),
      chk(["structure", "old_symbols"], [P, R]), chk(["structure", "new_symbols"], [A, B])])
case("check-shared-one-part-conservative", ["JOINT-3"], "non_conversion",
     "部分を一つ共有しても、各親に固有の部分があれば保存的（森の十分条件の外でも、全数の判定は認定する）",
     check_request(SHARED),
     [OK, chk(["certificate", "status"], "certified"), chk(["certificate", "counterexample"], None), chk(["structure", "kind"], "shared_parts"),
      chk(["structure", "forest_condition"], False), chk(["certificate", "method"], "monadic-extension-exhaustive-1"), chk(["steps_used"], 10)])
case("check-chain", ["JOINT-4", "JOINT-1"], "non_conversion", "入れ子の鎖（親が別の分割の部分）は森で、保存的",
     check_request(CHAIN),
     [OK, chk(["certificate", "status"], "certified"), chk(["structure", "kind"], "forest"), chk(["structure", "chain"], True),
      chk(["structure", "leaves"], [B, C, D]), chk(["structure", "old_symbols"], [P])])
case("check-disjoint", ["JOINT-2", "JOINT-1"], "non_conversion", "語彙が互いに素な併用は、成分が分かれ、保存的",
     check_request(DISJOINT),
     [OK, chk(["certificate", "status"], "certified"), chk(["structure", "kind"], "disjoint"), chk(["structure", "components"], [[0], [1]]),
      chk(["structure", "chain"], False)])
case("check-same-parent-twice", ["JOINT-1", "JOINT-3"], "non_conversion", "同じ親の二つの細分は森（部分は重ならない）で、保存的",
     check_request([split(P, [A, B]), split(P, [C, D])]),
     [OK, chk(["certificate", "status"], "certified"), chk(["structure", "kind"], "forest"), chk(["structure", "components"], [[0, 1]])])
case("check-cyclic", ["JOINT-1"], "non_conversion", "「部分→親」に閉路がある併用は cyclic と分類する（旧記号がなければ保存性は自明）",
     check_request([split(P, [A, B]), split(A, [P, C])]),
     [OK, chk(["structure", "kind"], "cyclic"), chk(["structure", "old_symbols"], []), chk(["certificate", "status"], "certified")])
case("check-individual-certificates-refused", ["JOINT-1", "JOINT-3"], "refusal", "個別の認定票を併用の根拠として受け付けない（未知の項目として拒否）",
     {**check_request(K04), "individual_certificates": ["certified", "certified"]},
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])
case("check-claimed-structure-refused", ["JOINT-1"], "refusal", "要求の構造の自己申告（disjoint など）を受け付けない：構造は分割から再計算する",
     {**check_request(K04), "structure": "disjoint"},
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"])])
case("check-duplicate-split", ["JOINT-5"], "refusal", "同じ分割を二度宣言できない", check_request([split(P, [A, B]), split(P, [B, A])]),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["duplicate_split"])])
case("check-too-many-splits", ["JOINT-5"], "refusal", "分割は 4 個まで", check_request([split(P, [A, B]), split(R, [C, D]), split(A, [X, B]), split(C, [X, D]), split(B, [C, X])]),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["item_limit"])])
names16 = [f"fiction:V{i}@1" for i in range(16)]
case("check-vocabulary-limit", ["JOINT-5"], "refusal", "語彙は 10 記号まで",
     check_request([split(names16[0], names16[1:4]), split(names16[4], names16[5:8]), split(names16[8], names16[9:12]), split(names16[12], names16[13:16])], names=names16),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["vocabulary_limit"])])
rules = check_request(K04)
rules["source"]["package"]["inclusions"] = [{"sub": A, "super": X}]
case("check-symbol-has-rules", ["JOINT-5", "R6-1"], "refusal", "規則に現れる述語の分割は範囲外", rules,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["split_symbol_has_rules"]), chk(["error_path"], "splits[0]")])
case("check-extra-axiom-refused", ["R6-1"], "refusal", "併用でも公理を追加・変更できない", check_request([{**split(P, [A, B]), "axioms": ["fiction:extra"]}]),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "splits[0]")])
bad = check_request(K04)
bad["consumer"]["profile"] = "p2-split-combination-draft-9"
case("check-consumer-profile", ["K-ID", "K-STOP"], "refusal", "consumer の profile が違えば unsupported_profile", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_profile"]), chk(["error_path"], "consumer.profile")])
bad = check_request(K04)
bad["consumer"]["profile_spec_sha256"] = "0" * 64
case("check-consumer-spec-hash", ["K-ID"], "refusal", "consumer が違う仕様の hash を持てば拒否", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["profile_spec_mismatch"])])
bad = check_request(K04)
bad["consumer"]["operations"] = ["check_split_combination", "other_operation"]
case("check-consumer-operations", ["K-STOP"], "refusal", "consumer が未登録の操作を宣言していれば止まる", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_operation"])])
bad = check_request(K04)
bad["operation"] = "audit_combination"
bad["consumer"]["operations"] = ["audit_combination"]
case("check-unsupported-operation", ["K-STOP"], "refusal", "未登録の操作は unsupported_profile", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_operation"]), chk(["error_path"], "operation")])
n_check = next(b for b in range(0, 200) if evaluate(check_request(K04, budget=b))["status"] == "ok")
case("check-budget-zero", ["K-STOP", "K-INV", "K-RES"], "refusal", "予算 0 では認定票を出さない", check_request(K04, budget=0),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["incomplete"], ["request"])])
case("check-budget-below", ["K-RES"], "boundary", f"課金の境界：steps が {n_check - 1}（完了に要る {n_check} より 1 少ない）で止まる", check_request(K04, budget=n_check - 1),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["incomplete"], ["request"])])
case("check-budget-exact", ["K-RES"], "boundary", f"課金の境界：steps がちょうど {n_check} で完了する", check_request(K04, budget=n_check),
     [OK, chk(["steps_used"], n_check), chk(["certificate", "status"], "not_certified")])

# ---- 併用の候補集合（query_split_combination）----
a, r = reviewed(assertion("h1", P), assertion("h2", R, "negative"))
q_k04 = query_request(K04, a, r)
case("query-k04-old-data", ["JOINT-3", "JOINT-6", "R6-2"], "refusal",
     "K04 型：旧記号だけの採用された状態（P 肯定・R 否定）で、併用は矛盾する（単独では open と parent_opposed）。旧データで矛盾する＝併用は保存的でない",
     q_k04,
     [OK, chk(["results", 0, "status"], "computed")] + joint(0, "inconsistent", [], True, "open") + joint(1, "inconsistent", [], True, "parent_opposed")
     + [chk(["results", 0, "interaction_violation"], True), chk(["results", 0, "leaf_candidates"], []), chk(["results", 0, "converted_to_base"], False),
        chk(["results", 0, "base", P], "supported"), chk(["results", 0, "base", R], "opposed"), chk(["results", 0, "base", A], "undetermined"),
        chk(["results", 0, "information_requests", 0, "kind"], "resolve_split_violation"), chk(["results", 0, "information_requests", 0, "splits"], [0, 1]),
        chk(["results", 0, "information_requests", 0, "assertion_refs"], ["h1", "h2"])])
case("query-base-unchanged-by-the-combination", ["R2-4", "JOINT-6"], "non_conversion",
     "併用が矛盾する状態でも、基底の問い（P の支持・R の否定）は変わらない：併用の結論は基底の状態に変換されない",
     {"schema_version": "p0-request-draft-1", "operation": "query", **copy.deepcopy(source(a, r)), "views": [VIEW], "budget": {"max_steps": 1000},
      "queries": [{"id": "q_p", "context_ref": C_OLD, "atoms": [{"predicate": P, "args": [S]}], "required": False},
                  {"id": "q_r", "context_ref": C_OLD, "atoms": [{"predicate": R, "args": [S]}], "required": False}]},
     [OK, chk(["results", 0, "status"], "supported"), chk(["results", 1, "status"], "opposed")])
a, r = reviewed(assertion("h1", P), assertion("h2", R, "negative"))
case("query-shared-part-narrows", ["JOINT-3", "JOINT-6"], "non_conversion",
     "部分を共有する併用：R の否定が共有する部分 A を除き、P の候補が単独の open から single [B] に狭まる（単独の結果では分からない）",
     query_request(SHARED, a, r),
     [OK] + joint(0, "single", [B], True, "open") + joint(1, "parent_opposed", [], False, "parent_opposed")
     + [chk(["results", 0, "interaction_violation"], False), chk(["results", 0, "leaf_candidates"], [B]),
        chk(["results", 0, "base", B], "undetermined")])
a, r = reviewed(assertion("h1", P), assertion("h2", A, "negative"), assertion("h3", R, "negative"))
case("query-shared-part-narrowed-differently", ["JOINT-6", "JOINT-3"], "non_conversion",
     "状態（narrowed）は同じでも候補が違う：R の否定が共有する部分 B を除き、P の候補が単独の [B, C, D] から [C, D] に狭まる（differs は候補の違いも見る）",
     query_request([split(P, [A, B, C, D]), split(R, [B, X])], a, r),
     [OK] + joint(0, "narrowed", [C, D], True, "narrowed") + joint(1, "parent_opposed", [], False, "parent_opposed")
     + [chk(["results", 0, "splits", 0, "individual", "candidates"], [B, C, D]), chk(["results", 0, "leaf_candidates"], [C, D])])
a, r = reviewed(assertion("h1", P), assertion("h2", B, "negative"))
case("query-chain-exclusion-flows", ["JOINT-4", "JOINT-6"], "non_conversion",
     "鎖：前段の除外（P かつ B でない → A）が後段に流れ、後段は単独では no_parent だが、併用では open [C, D]",
     query_request(CHAIN, a, r),
     [OK] + joint(0, "single", [A], False, "single") + joint(1, "open", [C, D], True, "no_parent")
     + [chk(["results", 0, "leaf_candidates"], [C, D]), chk(["results", 0, "information_requests", 0, "kind"], "confirm_part"),
        chk(["results", 0, "information_requests", 0, "split"], 0), chk(["results", 0, "information_requests", 1, "split"], 1),
        chk(["results", 0, "base", A], "undetermined")])
a, r = reviewed(assertion("h1", P))
case("query-chain-loss-not-recovered", ["JOINT-4"], "non_conversion",
     "鎖：前段が A と B を区別していない個体（P だけが採用）は、後段の分割だけでは葉まで確定しない（後段は no_parent、葉の候補は B・C・D）",
     query_request(CHAIN, a, r),
     [OK] + joint(0, "open", [A, B], False, "open") + joint(1, "no_parent", [], False, "no_parent") + [chk(["results", 0, "leaf_candidates"], [B, C, D])])
a, r = reviewed(assertion("h1", C))
case("query-chain-later-info-flows-back", ["JOINT-4", "JOINT-6"], "non_conversion",
     "鎖：後段の情報（C の肯定）が前段へ流れ、A が定まる（前段を単独で見ると no_parent）",
     query_request(CHAIN, a, r),
     [OK] + joint(0, "single", [A], True, "no_parent") + joint(1, "asserted", [C], False, "asserted")
     + [chk(["results", 0, "splits", 0, "joint", "parent_derived"], True), chk(["results", 0, "leaf_candidates"], [C])])
a, r = reviewed(assertion("h1", P), assertion("h2", C, "negative"))
case("query-disjoint-factors", ["JOINT-2", "JOINT-6"], "non_conversion", "互いに素な併用：各分割の併用での結果は単独の結果と同じ（differs が偽）",
     query_request(DISJOINT, a, r),
     [OK] + joint(0, "open", [A, B], False, "open") + joint(1, "no_parent", [], False, "no_parent")
     + [chk(["structure", "components"], [[0], [1]]), chk(["results", 0, "interaction_violation"], False)])
a, r = reviewed(assertion("h1", P), assertion("h2", A, "negative"), assertion("h3", B, "negative"), assertion("h4", R))
case("query-disjoint-violation-does-not-leak", ["JOINT-2", "JOINT-6"], "non_conversion",
     "互いに素な併用：一方の分割が矛盾しても、他方の結果は矛盾の影響を受けない（成分ごとの分解）",
     query_request(DISJOINT, a, r),
     [OK] + joint(0, "inconsistent", [], False, "inconsistent") + joint(1, "open", [C, D], False, "open")
     + [chk(["results", 0, "interaction_violation"], False), chk(["results", 0, "information_requests", 0, "kind"], "confirm_part"),
        chk(["results", 0, "information_requests", 0, "split"], 1), chk(["results", 0, "information_requests", 1, "kind"], "resolve_split_violation"),
        chk(["results", 0, "information_requests", 1, "splits"], [0])])
a, r = reviewed(assertion("h1", P))
a.append(assertion("h2", A, origin="ai_candidate"))
case("query-ai-candidate-pending", ["K-INV", "R2-3"], "non_conversion", "確認のない AI 候補は併用でも候補を狭めず、保留として残す",
     query_request(SHARED, a, r),
     [OK] + joint(0, "open", [A, B], False, "open") + joint(1, "no_parent", [], False, "no_parent")
     + [chk(["results", 0, "evidence", "pending", 0, "assertion_ref"], "h2")])
a, r = reviewed(assertion("h1", P), assertion("h2", A, certainty="suspected", caps=[OTHER_CAP]))
case("query-unknown-capability-blocks", ["K-STOP", "K-INV"], "refusal", "未知の能力を要求する保留中の主張があれば、その文脈の行を解釈しない",
     query_request(SHARED, a, r),
     [OK, chk(["results", 0, "status"], "blocked"), chk(["results", 0, "reason_codes"], ["unknown_capability"]), chk(["results", 0, "blocking_assertion_refs"], ["h2"]),
      chk(["results", 0, "splits"], None)])
a, r = reviewed(assertion("h1", P), assertion("h2", P, "negative"))
case("query-conflict-blocks", ["K-STOP"], "refusal", "同じ原子の肯定と否定がともに採用されていれば、解決せずに止める", query_request(SHARED, a, r),
     [OK, chk(["results", 0, "status"], "blocked"), chk(["results", 0, "reason_codes"], ["unresolved_conflict"])])
a, r = reviewed(assertion("h1", P, caps=[SPLITS_PROFILE]), assertion("h2", A, caps=[SPLIT_PROFILE, SPLITS_PROFILE]))
sp_caps = query_request(SHARED, a, r)
case("query-combination-capability-understood", ["R2-5"], "non_conversion", "併用と分割の能力を要求する主張は、併用を理解する消費側が解釈する",
     sp_caps, [OK] + joint(0, "asserted", [A], False, "asserted"))
case("base-unaware-consumer-stops-on-combination-capability", ["R2-5", "K-INV"], "refusal", "併用の能力を要求する主張は、併用を理解しない消費側（基底）には文脈ごと解釈されない",
     {"schema_version": "p0-request-draft-1", "operation": "query", **copy.deepcopy(source(a, r)), "views": [VIEW], "budget": {"max_steps": 1000},
      "queries": [{"id": "q_p", "context_ref": C_OLD, "atoms": [{"predicate": P, "args": [S]}], "required": False}]},
     [OK, chk(["results", 0, "status"], "unassessed"), chk(["results", 0, "reason_codes"], ["unknown_capability"]),
      chk(["results", 0, "missing_capabilities"], [SPLIT_PROFILE, SPLITS_PROFILE]), chk(["results", 0, "blocking_assertion_refs"], ["h1", "h2"])])
a, r = reviewed(assertion("h1", P))
n_query = next(b for b in range(0, 500) if evaluate(query_request(SHARED, a, r, budget=b))["status"] == "ok")
case("query-budget-zero", ["K-STOP", "K-INV", "K-RES"], "refusal", "予算 0 では、候補集合も部分の値も返さない", query_request(SHARED, a, r, budget=0),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["results", 0, "status"], "blocked"), chk(["results", 0, "splits"], None),
      chk(["results", 0, "base"], None)])
case("query-budget-below", ["K-RES"], "boundary", f"課金の境界：steps が {n_query - 1}（完了に要る {n_query} より 1 少ない）で止まる", query_request(SHARED, a, r, budget=n_query - 1),
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(["results", 0, "splits"], None)])
case("query-budget-exact", ["K-RES"], "boundary", f"課金の境界：steps がちょうど {n_query} で完了する", query_request(SHARED, a, r, budget=n_query),
     [OK, chk(["steps_used"], n_query), chk(["results", 0, "status"], "computed")])
bad = query_request(SHARED, a, r)
bad["read_only"] = True
case("query-self-claim-refused", ["R2-5"], "refusal", "要求の自己申告（read_only など）を根拠にしない", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])

# ---- 書き出し ----
files = []
for i, c in enumerate(CASES, 1):
    cid = f"SC{i:02}"
    data = {"schema_version": "p1-fixture-draft-1", "fixture_id": cid, "fixture_version": 1, "fictional": True, "review_state": "author_draft",
            "extension": "p2-split-combination", "obligations": c["obligations"], "kind": c["kind"], "gate": c["gate"], "request": c["request"],
            "expected": {"comparison": "required_paths", "checks": c["checks"]}}
    path = OUT / f"{c['slug']}.json"
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    files.append({"fixture_id": cid, "path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "obligations": c["obligations"],
                  "kind": c["kind"], "gate": c["gate"]})
manifest = {"schema_version": "p2-splits-manifest-draft-1", "status": "author_draft", "independent_review": False, "evaluation_frozen": False,
            "contract_version": "p0-draft-2", "profile": SPLITS_PROFILE, "profile_spec_sha256": SPEC_SHA256,
            "note": "P2-c（概念の分割の併用）の例。P1の20条件・80 JSON・417必須パス、231開発テスト、レビュー系列、防護例（p2）、概念の分割（p2-split）とは別の分母。"
                    "期待結果は文書 25 の意味から手で導いた。予算の境界の n（完了に要る最小の steps）だけは測った。",
            "measured_budgets": {"check": n_check, "query": n_query}, "files": files}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(files), "combination examples written; n =", manifest["measured_budgets"])
