"""P2-b（概念の分割）の例を examples/p2-split/ に書き出す。
期待結果は文書 23 の意味から手で指定し、処理系の出力から生成しない。例外は予算の境界の n（完了に要る最小の steps を測る）。
使い方: python3 -B scripts/research/p2/gen_split_fixtures.py（環境変数 P2_REPO＝作業ツリー。既定はこのリポジトリ）"""
import copy, hashlib, json, os, sys
from pathlib import Path

ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "src"))
from med_dsl import evaluate
from med_dsl.split import SPEC_SHA256, SPLIT_PROFILE
from med_dsl.validation import digest

OUT = ROOT / "examples/p2-split"
OUT.mkdir(exist_ok=True)

S = "fiction:person:1"
P, Q1, Q2, Q3, X = "fiction:P@1", "fiction:P1@1", "fiction:P2@1", "fiction:P3@1", "fiction:X@1"
C_OLD, C_NEW = "fiction:context:old@1", "fiction:context:new@1"
POLICY = "fiction:confirmed-explicit-revision@1"
CAP = SPLIT_PROFILE
OTHER_CAP = "fiction:other-capability@1"
T_REC, T_REV = "2020-01-02T00:00:00Z", "2020-01-03T00:00:00Z"
VIEW = {"id": "v1", "as_of": "2026-01-01T00:00:00Z", "policy_ref": POLICY}

CASES = []


def chk(path, equals):
    return {"path": path, "equals": equals}


def case(slug, extension_obligations, kind, gate, request, checks):
    CASES.append(dict(slug=slug, obligations=extension_obligations, kind=kind, gate=gate, request=request, checks=checks))


def assertion(ident, predicate, polarity="positive", context=C_OLD, certainty="confirmed", at=T_REC, origin="observed",
              supersedes=(), caps=()):
    item = {"id": ident, "context_ref": context, "atom": {"predicate": predicate, "args": [S]}, "polarity": polarity,
            "certainty": certainty, "recorded_at": at, "origin": {"kind": origin, "ref": f"fiction:source:{ident}"},
            "supersedes": list(supersedes), "required_capabilities": list(caps)}
    if supersedes:
        item["change_reason"] = "fiction:correction"
    return item


def review(ident, assertion_ref, at=T_REV):
    return {"id": ident, "assertion_ref": assertion_ref, "reviewer_ref": "fiction:reviewer:1", "reviewer_kind": "human",
            "recorded_at": at, "outcome": "confirmed"}


def context(ref, effective):
    return {"ref": ref, "subject_ref": S, "effective_at": effective, "purpose": "fiction:research"}


def source(assertions, reviews, predicates=None, contexts=None, inclusions=()):
    names = predicates if predicates is not None else [P, Q1, Q2, Q3, X]
    return {"package": {"ref": "fiction:package:split@1", "profile": "p0-positive-1",
                        "predicates": [{"ref": n, "roles": ["subject"]} for n in names],
                        "definitions": [], "inclusions": list(inclusions), "dependencies": []},
            "contexts": contexts or [context(C_OLD, "2020-01-01T00:00:00Z"), context(C_NEW, "2026-01-01T00:00:00Z")],
            "ledger": {"ref": "fiction:ledger:split@1", "assertions": assertions, "reviews": reviews}}


def split_request(assertions, reviews, parts=(Q1, Q2), queries=None, views=None, budget=1000, **kw):
    return {"schema_version": "p2-split-request-draft-1", "operation": "query_split",
            "consumer": {"profile": SPLIT_PROFILE, "profile_spec_sha256": SPEC_SHA256, "operations": ["query_split"]},
            "budget": {"max_steps": budget}, "source": source(assertions, reviews, **kw),
            "views": views or [VIEW], "split": {"parent": P, "parts": list(parts)},
            "queries": queries or [{"id": "q1", "context_ref": C_OLD, "subject": S, "required": True}]}


def base_request(src, queries, views=None, budget=1000):
    """基底（P0）の問い合わせ。同じ snapshot を、分割を知らない消費側として読む。"""
    return {"schema_version": "p0-request-draft-1", "operation": "query", **copy.deepcopy(src),
            "views": views or [VIEW], "queries": queries, "budget": {"max_steps": budget}}


def atom_query(ident, predicate, context=C_OLD):
    return {"id": ident, "context_ref": context, "atoms": [{"predicate": predicate, "args": [S]}], "required": False}


def row(i=0, *tail):
    return ["results", i, *tail]


def split_checks(i, status, candidates, base_parent, base_parts, derivation, excluded=None, parent_derived=False, kind=None):
    checks = [chk(row(i, "status"), "computed"), chk(row(i, "split", "status"), status), chk(row(i, "split", "candidates"), candidates),
              chk(row(i, "base", "parent"), base_parent), chk(row(i, "split", "derivation"), derivation),
              chk(row(i, "split", "parent_derived"), parent_derived), chk(row(i, "converted_to_base"), False)]
    checks += [chk(row(i, "base", "parts", q), s) for q, s in base_parts.items()]
    if excluded is not None:
        checks.append(chk(row(i, "split", "excluded"), excluded))
    if kind is not None:
        checks.append(chk(row(i, "information_requests", 0, "kind"), kind))
    return checks


OK = chk(["status"], "ok")

# ---- 基本の状態（K06 とその周辺）----
a1 = [assertion("h1", P)]
r1 = [review("r1", "h1")]
sp01 = split_request(a1, r1)
case("old-record-only", ["R6-2", "R6-6", "R2-1", "K-INV"], "non_conversion", "K06：旧い記録だけでは、どの部分かを確定しない（候補集合と情報要求）", sp01,
     [OK] + split_checks(0, "open", [Q1, Q2], "supported", {Q1: "undetermined", Q2: "undetermined"}, ["A2_coverage"], [], False, "confirm_part")
     + [chk(row(0, "evidence", "adopted", 0, "assertion_refs"), ["h1"]), chk(["snapshot_sha256"], digest(sp01["source"])),
        chk(row(0, "information_requests", 0, "candidate_parts"), [Q1, Q2])])
case("part-asserted", ["R6-3", "R2-3", "K-INV"], "non_conversion", "部分が直接採用されていれば、他の部分は排他で除かれる（基底では他の部分は未決のまま）",
     split_request([assertion("h1", P), assertion("h2", Q1, caps=[CAP])], [review("r1", "h1"), review("r2", "h2")]),
     [OK] + split_checks(0, "asserted", [Q1], "supported", {Q1: "supported", Q2: "undetermined"}, ["A3_exclusivity"],
                         [{"part": Q2, "reasons": ["other_part_asserted"]}]))
case("part-only-parent-derived", ["R6-4", "R6-3"], "non_conversion", "部分だけが採用されたとき、親は包含から導かれる（基底の親は未決のまま。基底へ変換しない）",
     split_request([assertion("h2", Q1, caps=[CAP])], [review("r2", "h2")]),
     [OK] + split_checks(0, "asserted", [Q1], "undetermined", {Q1: "supported", Q2: "undetermined"}, ["A1_subsumption", "A3_exclusivity"],
                         [{"part": Q2, "reasons": ["other_part_asserted"]}], True))
case("single-by-exclusion", ["K-INV", "R2-2", "R2-4", "R6-4"], "non_conversion", "他の候補がすべて除かれて一つに定まっても、採用された主張にはならず、基底の状態へ変換しない",
     split_request([assertion("h1", P), assertion("h2", Q1, "negative", caps=[CAP])], [review("r1", "h1"), review("r2", "h2")]),
     [OK] + split_checks(0, "single", [Q2], "supported", {Q1: "opposed", Q2: "undetermined"}, ["A2_coverage"],
                         [{"part": Q1, "reasons": ["adopted_negative"]}], False, "confirm_part")
     + [chk(row(0, "information_requests", 0, "candidate_parts"), [Q2])])
case("narrowed-three-parts", ["R6-3"], "non_conversion", "三つの部分で一つが否定されたら、残り二つを候補にする",
     split_request([assertion("h1", P), assertion("h2", Q3, "negative", caps=[CAP])], [review("r1", "h1"), review("r2", "h2")], parts=(Q1, Q2, Q3)),
     [OK] + split_checks(0, "narrowed", [Q1, Q2], "supported", {Q1: "undetermined", Q2: "undetermined", Q3: "opposed"}, ["A2_coverage"],
                         [{"part": Q3, "reasons": ["adopted_negative"]}], False, "confirm_part"))
case("parent-opposed", ["R6-2", "R6-3"], "non_conversion", "親が否定されたら、どの部分も成り立たない（候補なし。基底の部分は未決のまま）",
     split_request([assertion("h1", P, "negative")], [review("r1", "h1")]),
     [OK] + split_checks(0, "parent_opposed", [], "opposed", {Q1: "undetermined", Q2: "undetermined"}, ["A1_subsumption"],
                         [{"part": Q1, "reasons": ["parent_opposed"]}, {"part": Q2, "reasons": ["parent_opposed"]}])
     + [chk(row(0, "information_requests"), [])])
case("all-parts-opposed", ["R6-3"], "non_conversion", "すべての部分が否定されたら、被覆から親は成り立たない（基底の親は未決のまま）",
     split_request([assertion("h1", Q1, "negative", caps=[CAP]), assertion("h2", Q2, "negative", caps=[CAP])], [review("r1", "h1"), review("r2", "h2")]),
     [OK] + split_checks(0, "parent_opposed", [], "undetermined", {Q1: "opposed", Q2: "opposed"}, ["A2_coverage"],
                         [{"part": Q1, "reasons": ["adopted_negative"]}, {"part": Q2, "reasons": ["adopted_negative"]}]))
case("inconsistent-all-parts-opposed", ["R6-3", "R6-6"], "refusal", "親が採用され、すべての部分が否定されたら、公理に反する（解消を求める）",
     split_request([assertion("h1", P), assertion("h2", Q1, "negative", caps=[CAP]), assertion("h3", Q2, "negative", caps=[CAP])],
                   [review("r1", "h1"), review("r2", "h2"), review("r3", "h3")]),
     [OK, chk(row(0, "status"), "computed"), chk(row(0, "split", "status"), "inconsistent"), chk(row(0, "split", "candidates"), []),
      chk(row(0, "split", "derivation"), ["A1_subsumption", "A2_coverage", "A3_exclusivity"]),
      chk(row(0, "information_requests", 0, "kind"), "resolve_split_violation"),
      chk(row(0, "information_requests", 0, "assertion_refs"), ["h1", "h2", "h3"])])
case("inconsistent-two-parts-asserted", ["R6-3"], "refusal", "二つの部分がともに採用されたら、排他に反する",
     split_request([assertion("h1", Q1, caps=[CAP]), assertion("h2", Q2, caps=[CAP])], [review("r1", "h1"), review("r2", "h2")]),
     [OK, chk(row(0, "split", "status"), "inconsistent"), chk(row(0, "information_requests", 0, "kind"), "resolve_split_violation")])
case("no-parent", ["K-INV", "R6-2"], "non_conversion", "親も部分も採用されていなければ、候補を作らず、未決を偽にしない",
     split_request([assertion("h1", X)], [review("r1", "h1")]),
     [OK] + split_checks(0, "no_parent", [], "undetermined", {Q1: "undetermined", Q2: "undetermined"}, [], [], False)
     + [chk(row(0, "information_requests"), [])])

# ---- 採用・訂正・参照時点・文脈 ----
case("ai-candidate-pending", ["K-INV", "R2-3", "R6-6"], "non_conversion", "確認のない AI 候補は、候補集合を狭めず、保留として残す",
     split_request([assertion("h1", P), assertion("h2", Q1, origin="ai_candidate", caps=[CAP])], [review("r1", "h1")]),
     [OK] + split_checks(0, "open", [Q1, Q2], "supported", {Q1: "undetermined", Q2: "undetermined"}, ["A2_coverage"], [], False, "confirm_part")
     + [chk(row(0, "evidence", "pending"), [{"assertion_ref": "h2", "predicate": Q1, "polarity": "positive", "origin_kind": "ai_candidate"}]),
        chk(row(0, "information_requests", 0, "pending_assertion_refs"), ["h2"])])
case("corrected-assertion", ["R2-3"], "non_conversion", "訂正された部分の主張は採用に残らず、訂正後の主張だけが候補を決める",
     split_request([assertion("h1", P), assertion("h2", Q1, caps=[CAP]), assertion("h3", Q1, "negative", at="2020-01-04T00:00:00Z", supersedes=["h2"], caps=[CAP])],
                   [review("r1", "h1"), review("r2", "h2"), review("r3", "h3", "2020-01-05T00:00:00Z")]),
     [OK] + split_checks(0, "single", [Q2], "supported", {Q1: "opposed", Q2: "undetermined"}, ["A2_coverage"], [{"part": Q1, "reasons": ["adopted_negative"]}], False, "confirm_part")
     + [chk(row(0, "evidence", "pending"), [])])
case("views-over-time", ["R2-3", "R6-5"], "non_conversion", "参照時点ごとに別の結果を返す（時点の履歴を消さない）",
     split_request([assertion("h1", P), assertion("h2", Q1, at="2021-06-01T00:00:00Z", caps=[CAP])],
                   [review("r1", "h1"), review("r2", "h2", "2021-06-02T00:00:00Z")],
                   views=[{"id": "v0", "as_of": "2020-06-01T00:00:00Z", "policy_ref": POLICY}, VIEW]),
     [OK, chk(row(0, "view"), "v0"), chk(row(0, "split", "status"), "open"), chk(row(1, "view"), "v1"), chk(row(1, "split", "status"), "asserted")])
case("contexts-do-not-leak", ["R6-5"], "non_conversion", "別の文脈の部分の主張は、旧い文脈の候補集合に入らない（文脈をまたぐ推論をしない）",
     split_request([assertion("h1", P), assertion("h2", Q1, context=C_NEW, at="2026-01-02T00:00:00Z", caps=[CAP])], [review("r1", "h1"), review("r2", "h2", "2026-01-03T00:00:00Z")],
                   queries=[{"id": "q_new", "context_ref": C_NEW, "subject": S, "required": False},
                            {"id": "q_old", "context_ref": C_OLD, "subject": S, "required": False}],
                   views=[{"id": "v1", "as_of": "2026-06-01T00:00:00Z", "policy_ref": POLICY}]),
     [OK, chk(row(0, "query"), "q_new"), chk(row(0, "split", "status"), "asserted"), chk(row(0, "split", "parent_derived"), True),
      chk(row(1, "query"), "q_old"), chk(row(1, "split", "status"), "open")])

# ---- 停止 ----
case("unknown-capability-blocks", ["K-STOP", "K-INV"], "refusal", "未知の能力を要求する保留中の主張があれば、その文脈の行を解釈しない",
     split_request([assertion("h1", P), assertion("h2", Q1, certainty="suspected", caps=[OTHER_CAP])], [review("r1", "h1")]),
     [OK, chk(row(0, "status"), "blocked"), chk(row(0, "reason_codes"), ["unknown_capability"]), chk(row(0, "missing_capabilities"), [OTHER_CAP]),
      chk(row(0, "blocking_assertion_refs"), ["h2"]), chk(row(0, "split"), None), chk(["incomplete"], [{"view": "v1", "query": "q1"}])])
case("conflict-blocks", ["K-STOP"], "refusal", "同じ原子の肯定と否定がともに採用されていれば、解決せずに止める",
     split_request([assertion("h1", P), assertion("h2", P, "negative")], [review("r1", "h1"), review("r2", "h2")]),
     [OK, chk(row(0, "status"), "blocked"), chk(row(0, "reason_codes"), ["unresolved_conflict"]), chk(row(0, "split"), None)])

# ---- 基底の消費側（X04, X05, X14 の旧い問い）----
unaware_src = source([assertion("h1", P), assertion("h2", Q1, caps=[CAP]), assertion("h3", Q1, "negative", at="2020-01-04T00:00:00Z", supersedes=["h2"], caps=[CAP]),
                      assertion("h4", Q2, certainty="suspected", caps=[CAP])],
                     [review("r1", "h1"), review("r2", "h2"), review("r3", "h3", "2020-01-05T00:00:00Z")])
case("base-unaware-consumer-stops", ["R2-5", "K-INV"], "refusal", "分割を理解しない消費側は、分割の能力を要求する文脈を解釈せず、保留・訂正済みの主張も落とさない",
     base_request(unaware_src, [atom_query("q1", P)]),
     [OK, chk(row(0, "status"), "unassessed"), chk(row(0, "reason_codes"), ["unknown_capability"]), chk(row(0, "missing_capabilities"), [CAP]),
      chk(row(0, "blocking_assertion_refs"), ["h2", "h3", "h4"])])
case("aware-consumer-reads-the-same-ledger", ["R2-5"], "non_conversion", "同じ台帳を分割を理解する消費側が読めば、保留・訂正済みを除いて解釈する",
     split_request(unaware_src["ledger"]["assertions"], unaware_src["ledger"]["reviews"]),
     [OK] + split_checks(0, "single", [Q2], "supported", {Q1: "opposed", Q2: "undetermined"}, ["A2_coverage"], [{"part": Q1, "reasons": ["adopted_negative"]}], False)
     + [chk(row(0, "evidence", "pending", 0, "assertion_ref"), "h4")])
case("old-queries-unchanged", ["R2-4", "R6-2"], "non_conversion", "K06：旧い問い（基底）は分割の有無によらず、旧回答を再現する（部分の問いは未決のまま）",
     base_request(sp01["source"], [atom_query("q_p", P), atom_query("q_p1", Q1), atom_query("q_p2", Q2)]),
     [OK, chk(row(0, "query"), "q_p"), chk(row(0, "status"), "supported"), chk(row(1, "status"), "undetermined"), chk(row(2, "status"), "undetermined")])
sp04 = split_request([assertion("h1", P), assertion("h2", Q1, "negative", caps=[CAP])], [review("r1", "h1"), review("r2", "h2")])
sp04_base = copy.deepcopy(sp04["source"])
for item in sp04_base["ledger"]["assertions"]:
    item["required_capabilities"] = []
case("single-is-not-base-support", ["R2-4", "R6-4"], "non_conversion", "分割の結論（残りの一つ）は、基底の問い合わせでは支持されない（変換の経路がない）",
     base_request(sp04_base, [atom_query("q_p1", Q1), atom_query("q_p2", Q2)]),
     [OK, chk(row(0, "status"), "opposed"), chk(row(1, "status"), "undetermined")])

# ---- 拒否（範囲・公理・宣言）----
case("symbol-has-rules", ["R6-1", "R6-5"], "refusal", "部分が包含の規則に現れる述語の分割は範囲外として拒否する",
     split_request(a1, r1, inclusions=[{"sub": Q1, "super": P}]),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["split_symbol_has_rules"]), chk(["error_path"], "split")])
case("duplicate-parts", ["R6-1"], "refusal", "同じ部分を二度宣言できない", split_request(a1, r1, parts=(Q1, Q1)),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["duplicate_reference"]), chk(["error_path"], "split.parts")])
case("parent-among-parts", ["R6-1"], "refusal", "親を部分に含められない", split_request(a1, r1, parts=(P, Q2)),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["parent_among_parts"])])
case("one-part", ["R6-1"], "refusal", "部分が一つでは分割にならない", split_request(a1, r1, parts=(Q1,)),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["too_few_parts"])])
case("undeclared-part", ["R6-1"], "refusal", "package に宣言のない述語を部分にできない", split_request(a1, r1, parts=(Q1, "fiction:P9@1")),
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["undeclared_predicate"])])
binary = split_request(a1, r1)
for pred in binary["source"]["package"]["predicates"]:
    if pred["ref"] == Q2:
        pred["roles"] = ["subject", "other"]
case("non-unary-part", ["R6-1", "R6-5"], "refusal", "単項でない述語の分割は範囲外として拒否する", binary,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["split_predicate_not_unary"])])
extra_axiom = split_request(a1, r1)
extra_axiom["split"]["axioms"] = ["fiction:extra-axiom"]
case("extra-axiom-refused", ["R6-1"], "refusal", "要求は公理を追加・変更できない（公理は仕様に固定されている）", extra_axiom,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "split")])
claim = split_request(a1, r1)
claim["read_only"] = True
case("self-claim-refused", ["R2-5"], "refusal", "要求の自己申告（read_only など）を根拠にしない：未知の項目として拒否する", claim,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["unknown_field"]), chk(["error_path"], "$")])
bad = split_request(a1, r1)
bad["consumer"]["profile"] = "p2-concept-split-draft-9"
case("consumer-profile", ["K-ID", "K-STOP"], "refusal", "consumer の profile が違えば unsupported_profile", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_profile"]), chk(["error_path"], "consumer.profile")])
bad = split_request(a1, r1)
bad["consumer"]["profile_spec_sha256"] = "0" * 64
case("consumer-spec-hash", ["K-ID"], "refusal", "consumer が違う仕様の hash を持てば拒否する", bad,
     [chk(["status"], "invalid_input"), chk(["reason_codes"], ["profile_spec_mismatch"]), chk(["error_path"], "consumer.profile_spec_sha256")])
bad = split_request(a1, r1)
bad["consumer"]["operations"] = ["query_split", "other_operation"]
case("consumer-operations", ["K-STOP"], "refusal", "consumer が未登録の操作を宣言していれば止まる", bad,
     [chk(["status"], "unsupported_profile"), chk(["reason_codes"], ["unsupported_operation"]), chk(["error_path"], "consumer.operations")])

# ---- 予算 ----
n = next(b for b in range(0, 500) if evaluate({**copy.deepcopy(sp01), "budget": {"max_steps": b}})["status"] == "ok")
case("budget-zero", ["K-STOP", "K-INV", "K-RES"], "refusal", "予算 0 では、候補集合も部分の値も返さない", {**copy.deepcopy(sp01), "budget": {"max_steps": 0}},
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(row(0, "status"), "blocked"), chk(row(0, "split"), None),
      chk(row(0, "base"), None), chk(["steps_used"], 0)])
case("budget-below", ["K-RES"], "boundary", f"課金の境界：steps が {n - 1}（完了に要る {n} より 1 少ない）で止まる", {**copy.deepcopy(sp01), "budget": {"max_steps": n - 1}},
     [chk(["status"], "resource_limit"), chk(["reason_codes"], ["step_limit"]), chk(row(0, "status"), "blocked"), chk(row(0, "split"), None)])
case("budget-exact", ["K-RES"], "boundary", f"課金の境界：steps がちょうど {n} で完了する", {**copy.deepcopy(sp01), "budget": {"max_steps": n}},
     [OK, chk(row(0, "split", "status"), "open"), chk(["steps_used"], n)])

# ---- 書き出し ----
files = []
for i, c in enumerate(CASES, 1):
    cid = f"SP{i:02}"
    data = {"schema_version": "p1-fixture-draft-1", "fixture_id": cid, "fixture_version": 1, "fictional": True,
            "review_state": "author_draft", "extension": "p2-concept-split", "obligations": c["obligations"], "kind": c["kind"],
            "gate": c["gate"], "request": c["request"], "expected": {"comparison": "required_paths", "checks": c["checks"]}}
    path = OUT / f"{c['slug']}.json"
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    files.append({"fixture_id": cid, "path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                  "obligations": c["obligations"], "kind": c["kind"], "gate": c["gate"]})
manifest = {"schema_version": "p2-split-manifest-draft-1", "status": "author_draft", "independent_review": False, "evaluation_frozen": False,
            "contract_version": "p0-draft-2", "profile": SPLIT_PROFILE, "profile_spec_sha256": SPEC_SHA256,
            "note": "P2-b（概念の分割）の例。P1の20条件・80 JSON・417必須パス、231開発テスト、レビュー系列、防護例（p2）とは別の分母。"
                    "期待結果は文書 23 の意味から手で指定した。予算の境界の n（完了に要る最小の steps）だけは測った。",
            "measured_budget": n, "files": files}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(files), "split examples written; n =", n)
