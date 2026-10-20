"""extensions/*.json の宣言を書き出す作者用の補助（宣言そのものが正本。検査は extensions.py と tests/p2）。
使い方: python3 -B scripts/research/p2/gen_extension_manifests.py（環境変数 P2_REPO＝作業ツリー。既定はこのリポジトリ）"""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
OUT = ROOT / "extensions"
SCHEMA = "p2-extension-manifest-draft-1"
VERSION = "draft-2"
sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
S = lambda p: "src/med_dsl/" + p

def g(example, path, equals, kind="refusal"):
    return {"example": example, "path": path, "equals": equals, "kind": kind}

def ob(ident, statement, evidence, checks, guards=(), gap=None, derivation=None):
    item = {"id": ident, "statement": statement, "evidence": evidence, "checks": list(checks), "guards": list(guards)}
    if gap:
        item["guard_gap"] = gap
    if derivation:
        item["derivation"] = derivation
    return item

def manifest(ident, title, cls, spec, doc, modules, pins, embedded, deps, owns, scope, obligations, stops, composition, evaluation):
    kinds = ("operations", "schema_versions", "profiles", "answer_kinds", "predicates", "capabilities")
    return {"schema_version": SCHEMA, "id": ident, "version": VERSION, "title": title,
            "status": {"review_state": "author_draft", "independent_review": False},
            "class": cls, "spec": {"path": spec, "sha256": sha(spec)} if spec else None, "contract_doc": doc,
            "implementation": {"modules": modules}, "pins": [{"path": p, "role": r} for p, r in pins], "embedded_in": embedded,
            "depends_on": [{"id": d, "version": VERSION} for d in deps], "owns": {k: owns.get(k, []) for k in kinds},
            "scope": scope, "obligations": obligations, "stops": stops, "composition": composition, "evaluation": evaluation}

def comp(reads=()):
    return {"shares_names_with": [], "reads_extensions": list(reads), "order_dependent": False}

def ev(examples, tests, sweep=True, oracle="tests/review/reference_oracle.py"):
    return {"examples": examples, "tests": tests, "budget_sweep": sweep, "oracle": oracle}

P0 = "docs/research/06-p0-contract.md"
P0_FILES = ["model.py", "validation.py", "definitions.py", "ledger.py", "query.py"]
manifests = []

# ---------------- BASE ----------------
manifests.append(manifest(
    "p0-positive", "P0 の基底（採用・問い合わせ・比較）と核の不変条件", "BASE", P0, P0,
    [S(m) for m in ("model.py", "validation.py", "ledger.py", "query.py", "compare.py", "definitions.py", "identity.py")],
    [(S("host.py"), "dispatcher"), (S("__init__.py"), "dispatcher")], [], [],
    {"operations": ["query", "compare"], "schema_versions": ["p0-request-draft-1", "p0-result-draft-1"], "profiles": ["p0-positive-1"],
     "answer_kinds": ["supported", "opposed", "undetermined", "conflict", "unassessed"], "capabilities": ["p0-positive-1"]},
    {"description": "基底そのもの。保存の主張は持たず、核の不変条件 I1〜I7（19-p2-design §2）を実現する", "data": "架空データのみ"},
    [ob("K-ID", "版・契約・依存の hash を実体から再計算して照合し、再定義を拒否する", "checked_native_template",
        ["tests/test_p0_query.py::test_dependency_hash_and_ownership", "tests/test_p0_compare.py::test_shared_package_registry_checks_hashes_across_snapshots"],
        [g("examples/p0/dependency-hash-mismatch.json", ["reason_codes"], ["dependency_hash_mismatch"]),
         g("examples/p0/redefined-package.json", ["reason_codes"], ["reference_redefined"])]),
     ob("K-STOP", "未対応の profile・未知の能力・資源上限・入力不正で、偽・空・部分回答を返さず止まる", "checked_native_template",
        ["tests/test_p0_ledger.py::test_unknown_blockers_include_every_visible_source_in_sorted_order", "tests/test_p0_query.py::test_zero_and_exhausted_budget_return_no_incomplete_bindings"],
        [g("examples/p0/unsupported-existence-profile.json", ["status"], "unsupported_profile"),
         g("examples/p0/unknown-capability.json", ["results", 0, "status"], "unassessed"),
         g("examples/p0/zero-step-budget.json", ["status"], "resource_limit"),
         g("examples/p0/duplicate-assertion.json", ["reason_codes"], ["duplicate_identifier"])]),
     ob("K-INV", "I1 支持は採用された主張からの導出だけ／I2 未決を偽にしない／I3 AI 候補を採用しない／I4 未知の能力を解釈しない／I5 打切りで部分回答を出さない／I6 入力を変更しない／I7 決定的", "checked_native_template",
        ["tests/test_p0_query.py::test_unreviewed_ai_candidate_is_retained_but_not_supported", "tests/test_p0_query.py::test_denial_is_not_derived_from_missing_binding",
         "tests/test_p0_query.py::test_serialization_and_input_are_preserved", "tests/test_p0_ledger.py::test_p22_replay_and_permutation_preserve_results_and_inputs"],
        [g("examples/p0/ai-unreviewed.json", ["results", 0, "status"], "undetermined", "non_conversion"),
         g("examples/p0/negative-defined-symbol.json", ["results", 1, "status"], "undetermined", "non_conversion"),
         g("examples/p0/unknown-capability.json", ["results", 0, "reason_codes"], ["unknown_capability"]),
         g("examples/p0/zero-step-budget.json", ["results", 0, "status"], "unassessed"),
         g("examples/review/review-precedes-assertion.json", ["reason_codes"], ["review_precedes_assertion"])]),
     ob("K-RES", "steps を課金点で数え、上限・結合数・深さを超えたら resource_limit。入力不正を予算不足にしない", "checked_native_template",
        ["tests/test_p0_query.py::test_binding_overflow_is_not_truncated_success", "tests/review/test_budget_sweep.py::BudgetSweepTests.test_every_budget_gives_the_full_answer_or_an_honest_stop"],
        [g("examples/p0/binding-limit.json", ["reason_codes"], ["binding_limit"]),
         g("examples/p0/zero-step-budget.json", ["reason_codes"], ["step_limit"])])],
    {"unknown_capability": "文脈を解釈せず unassessed。保留・訂正済みの主張の修飾も落とさない", "unsupported": "unsupported_profile",
     "resource": "resource_limit。未完了の問いは値を持たない", "invalid_input": "構造・参照・hash の不正は予算に依らず invalid_input"},
    comp(), ev(["examples/p0/*.json"], ["tests/test_p0_query.py", "tests/test_p0_ledger.py", "tests/test_p0_compare.py", "tests/test_p0_definitions.py"], True)))

# ---------------- R1 ----------------
manifests.append(manifest(
    "p0-definitions", "定義の追加（S1/S2）の保存的拡張の認定", "R1", None, P0, [S("definitions.py"), S("validation.py")], [], [], ["p0-positive"],
    {"operations": ["check_extension"], "answer_kinds": ["p0-s1-s2-dag-1"]},
    {"base_requests": "旧語彙の問い・旧データ", "data": "旧データのみ。新所属データ・方針変更・対応の変更は範囲外", "guarantee": "model_conservative_extension_over_old_signature"},
    [ob("R1-1", "新記号は追加するパッケージが所有し、基底・依存の記号を再宣言しない", "checked_native_template",
        ["tests/test_p0_definitions.py::test_individual_shared_symbol_certificates_cannot_be_composed", "tests/test_p0_definitions.py::test_old_dependency_symbols_cannot_be_reintroduced"],
        [g("examples/p0/shared-symbol-extensions.json", ["reason_codes"], ["predicate_owner_conflict"])]),
     ob("R1-2", "右辺は旧語彙と前の新記号だけで、定義の依存は非循環。役割の型が一致する", "checked_native_template",
        ["tests/test_p0_definitions.py::test_roles_and_unresolved_definition_are_invalid", "tests/test_p0_definitions.py::test_mixed_s1_s2_chain_can_be_declared_out_of_order"],
        [g("examples/p0/cyclic-definitions.json", ["certificate", "reason_codes"], ["cyclic_definitions"]),
         g("examples/p0/duplicate-definition.json", ["reason_codes"], ["duplicate_definition"])]),
     ob("R1-3", "旧モデルは新記号の解釈（N:=ψ か N:=∅）で必ず拡張できる", "checked_native_template",
        ["tests/test_p0_definitions.py::test_certified_extensions_preserve_all_old_models_on_two_individuals", "tests/audits/test_preservation_audit.py::PreservationAuditTests.test_generated_definitions_are_200_distinct_programs"],
        [], gap="モデル拡張は構文の十分条件（R1-1・R1-2・R1-4）で保証され、認定を拒否する例は R1-2・R1-4 が担う。この義務独自の拒否例はない",
        derivation="docs/research/05-principles.md"),
     ob("R1-4", "旧記号への追加の包含・新所属データ・存在の制約を持たない（隠れた依存の包含も検査する）", "checked_native_template",
        ["tests/test_p0_definitions.py::test_hidden_dependency_inclusion_is_checked", "tests/test_p0_definitions.py::test_dependency_new_symbols_are_not_skipped"],
        [g("examples/p0/unsafe-inclusions.json", ["certificate", "reason_codes"], ["additional_inclusions", "missing_definition"])]),
     ob("R1-5", "認定は十分条件で、不認定は非保存の断定ではない（保証の欄を空にする）", "checked_native_template",
        ["tests/test_p0_definitions.py::test_hidden_dependency_inclusion_is_checked"],
        [g("examples/p0/unsafe-inclusions.json", ["certificate", "scope", "guarantee"], None, "non_conversion")]),
     ob("K-ID", "認定票に base／extension／依存の hash を固定し、依存の hash の変更を拒否する", "checked_native_template",
        ["tests/test_p0_definitions.py::test_dependency_hash_cannot_be_changed", "tests/test_p0_definitions.py::test_scope_pins_theories_and_excludes_new_memberships"],
        [g("examples/p0/dependency-hash-mismatch.json", ["reason_codes"], ["dependency_hash_mismatch"])]),
     ob("K-STOP", "予算0・途中の打切りで認定票を出さない", "checked_native_template",
        ["tests/test_p0_definitions.py::test_certification_budget_zero_and_mid_graph_never_issue_certificate", "tests/review/test_boundaries.py::P0LimitTests.test_extension_certification_costs_one_step_even_when_nothing_is_added"],
        [], gap="拡張認定の予算0は例ではなくテストで検査している"),
     ob("K-INV", "I6 入力を変更しない、I7 決定的。AI 候補・確認の方針に触れない", "checked_native_template",
        ["tests/test_p0_query.py::test_serialization_and_input_are_preserved"], [], gap="認定は定義パッケージだけを読み、台帳・採用に触れないため、不変条件 I1〜I5 の新しい出力はない。拒否例はなし"),
     ob("K-RES", "認定の各検査を step に課金する", "checked_native_template",
        ["tests/test_p0_definitions.py::test_certification_budget_zero_and_mid_graph_never_issue_certificate"], [], gap="認定の課金は P0 契約 §6 に定め、テストで境界を検査している（例なし）")],
    {"unknown_capability": "認定は台帳を読まないため該当しない", "unsupported": "profile が p0-positive-1 でなければ unsupported_profile",
     "resource": "resource_limit。認定票を出さない", "invalid_input": "重複・未宣言・役割の不一致・依存の不整合は invalid_input"},
    comp(), ev(["examples/p0/*.json"], ["tests/test_p0_definitions.py", "tests/audits/test_preservation_audit.py"], True, "scripts/research/audit-preservation.py")))

# ---------------- R2 ----------------
FSPEC = S("forecast_spec.json")
manifests.append(manifest(
    "p1-finite-forecast", "有限予測（読み取り専用の意味モジュール）", "R2", FSPEC, "docs/research/12-p1-a-contract.md", [S("forecast.py")],
    [(FSPEC, "native_spec")], [S("forecast.py"), "examples/p1-a/*.json"], ["p0-positive"],
    {"operations": ["query_forecast"], "schema_versions": ["p1-request-draft-1", "p1-result-draft-1"], "profiles": ["p1-finite-forecast-draft-1"],
     "answer_kinds": ["forecast_probability"], "predicates": ["fiction:forecast_reported@1"], "capabilities": ["p1-finite-forecast-draft-1"]},
    {"base_requests": "基底の全要求（非干渉）", "data": "任意。臨床の snapshot を入力に取らない", "note": "確率を臨床の肯定に変換する規則を持たない"},
    [ob("R2-1", "基底の状態への書き込み操作を持たない。許す操作は query_forecast だけ", "checked_native_template",
        ["tests/test_p1_forecast.py::test_forecast_one_does_not_change_clinical_input_or_answer"],
        [g("examples/p1-a/extra-operation.json", ["reason_codes"], ["unsupported_operation"]),
         g("examples/p1-a/unsupported-operation.json", ["reason_codes"], ["unsupported_operation"])]),
     ob("R2-2", "基底の語彙の述語へ導出せず、任意の package・規則を受け付けない", "checked_native_template",
        ["tests/test_p1_forecast.py::test_no_clinical_predicate_or_arbitrary_package_is_accepted"], [],
        gap="報告専用の固定 package しか検証に渡さない構造で、任意 package を拒否する例ファイルはなくテストで検査している"),
     ob("R2-3", "基底の状態は、核の採用選択（人の確認・訂正・時点）を通してだけ読む", "checked_native_template",
        ["tests/test_p1_forecast.py::test_confirmation_time_certainty_and_polarity_table", "tests/test_p1_forecast.py::test_revision_views_preserve_sources_and_confirmation_evidence"],
        [g("examples/p1-a/ai-unreviewed.json", ["results", 0, "status"], "undetermined", "non_conversion"),
         g("examples/p1-a/ai-suspected.json", ["results", 0, "status"], "undetermined", "non_conversion")]),
     ob("R2-4", "回答型は基底の状態と別で、確率1でも supported に変換しない", "checked_native_template",
        ["tests/test_p1_forecast.py::test_forecast_one_does_not_change_clinical_input_or_answer", "tests/test_p1_forecast.py::test_empty_and_complete_events_return_canonical_zero_and_one"],
        [g("examples/p1-a/probability-one.json", ["results", 0, "answer", "kind"], "forecast_probability", "non_conversion"),
         g("examples/p1-a/probability-one.json", ["results", 0, "status"], "computed", "non_conversion")]),
     ob("R2-5", "自己申告の read_only や未知の能力名を根拠に、未知の意味修飾を無視しない", "checked_native_template",
        ["tests/test_p1_forecast.py::test_client_cannot_whitelist_unknown_capability", "tests/test_p1_forecast.py::test_legacy_p0_still_stops_on_forecast_capability"],
        [g("examples/p1-a/read-only-self-claim.json", ["reason_codes"], ["unknown_field"]),
         g("examples/p1-a/unknown-capability.json", ["results", 0, "reason_codes"], ["unknown_capability"]),
         g("examples/p1-a/unknown-capability-pending.json", ["results", 0, "status"], "unassessed")]),
     ob("K-ID", "consumer と artifact の profile・仕様 hash・artifact の内容 hash を実体と照合する", "checked_native_template",
        ["tests/test_p1_forecast.py::test_native_spec_actual_file_is_checked_not_only_client_claim"],
        [g("examples/p1-a/artifact-hash.json", ["reason_codes"], ["artifact_hash_mismatch"]),
         g("examples/p1-a/consumer-spec.json", ["reason_codes"], ["profile_spec_mismatch"]),
         g("examples/p1-a/artifact-profile.json", ["status"], "unsupported_profile")]),
     ob("K-STOP", "未対応の操作・profile は unsupported_profile、未知の能力は unassessed、資源は resource_limit", "checked_native_template",
        ["tests/test_p1_forecast.py::test_unknown_capability_on_superseded_report_still_blocks"],
        [g("examples/p1-a/missing-operation.json", ["reason_codes"], ["unsupported_operation"]),
         g("examples/p1-a/zero-budget.json", ["status"], "resource_limit")]),
     ob("K-INV", "I3 AI 候補の報告を人の確認なしに採用しない／I4 未知の能力は保留・訂正済みも含めて停止／I5 打切りで部分の確率を出さない", "checked_native_template",
        ["tests/test_p1_forecast.py::test_every_budget_cut_before_completion_returns_no_partial_number"],
        [g("examples/p1-a/partial-probability.json", ["results", 0, "status"], "unassessed"),
         g("examples/p1-a/unknown-capability-pending.json", ["results", 0, "reason_codes"], ["unknown_capability"])]),
     ob("K-RES", "世界×事象の所属検査・有理数の加算を共通予算に課金し、整数・中間値の上限で止まる", "checked_native_template",
        ["tests/test_p1_forecast.py::test_count_and_integer_limits_stop_without_rounding", "tests/test_p1_forecast.py::test_completed_query_survives_shared_budget_exhaustion"],
        [g("examples/p1-a/integer-limit.json", ["reason_codes"], ["rational_integer_limit"]),
         g("examples/p1-a/shared-budget.json", ["results", 1, "status"], "unassessed")])],
    {"unknown_capability": "可視の主張の要求する能力が未知なら、その文脈の問いは unassessed（incomplete に列挙）", "unsupported": "unsupported_profile／unsupported_operation",
     "resource": "resource_limit。完了済みの回答は保持し、未完了は値を持たない", "invalid_input": "参照・hash・有理数の形の不正は予算に依らず invalid_input。重みの総和が 1 でないことは、重みの加算を課金しながら確かめるので、予算が足りなければ判定の前に resource_limit（補完しない）"},
    comp(), ev(["examples/p1-a/*.json"], ["tests/test_p1_forecast.py"], True)))

# ---------------- R3: events ----------------
ESPEC = S("events_spec.json")
manifests.append(manifest(
    "p1-events", "四項関係の事象化（役割付き事象への表現の改訂）", "R3", ESPEC, "docs/research/13-p1-b-contract.md", [S("events.py")],
    [(ESPEC, "native_spec")], [S("events.py"), S("handover_spec.json"), "examples/p1-b/*.json", "examples/p1-c/*.json", "examples/review/*.json"], ["p0-positive"],
    {"operations": ["reify_events", "restore_events", "query_events", "compare_event_handover"],
     "schema_versions": ["p1-events-request-draft-1", "p1-events-result-draft-1"], "profiles": ["p1-events-draft-1"],
     "answer_kinds": ["native_event_roles"], "predicates": ["urn:med-dsl:events:active", "urn:med-dsl:events:role:"]},
    {"base_requests": "有限の四項肯定事実と正の結合 Q（宣言した部分）", "data": "選んだ一つの四項関係。新しい事象の件数・同一性を問う Q は範囲外", "guarantee": "native 経路は有限照合のみ。全モデルの認定は p1-event-chain"},
    [ob("R3-1", "式の移し方 E（四役割を同じ事象に結ぶ）と回答の対応 ρ（旧変数への射影）を仕様に明示する", "checked_native_template",
        ["tests/test_p1_events.py::test_projection_deduplicates_without_losing_duplicate_support", "tests/test_p1_events.py::test_all_subsets_of_eight_tuples_against_direct_relation_membership"],
        [g("examples/p1-b/split-witness.json", ["comparison", "status"], "mismatch")]),
     ob("R3-2", "充足の対応：別の事象から役割を取る誤訳は、有限の反例として検出する", "finite_check",
        ["tests/test_p1_events.py::test_split_witness_is_an_explicit_finite_countermodel", "tests/review/test_event_paths.py::SplitRolesTests.test_wrong_role_joins_are_found_and_the_result_is_never_certified"],
        [g("examples/p1-b/split-witness.json", ["certificate", "reason_codes"], ["satisfaction_condition_failed"])]),
     ob("R3-3", "旧モデルの被覆：旧モデルの四つ組を事象の集合＋予備要素へ持ち上げられる", "hand_derivation",
        ["tests/test_p1_events.py::test_empty_relation_roundtrips_without_fabricated_spare_observation"], [],
        gap="被覆は手作業の導出（R5 C1-a）。反例の検査は参考意味（p1-reference）が担い、events 自身は有限照合だけ",
        derivation="docs/research/05-principles.md"),
     ob("R3-4", "新理論は翻訳した旧理論と型構造だけ。key の一意性・事象の一意名仮定を加えない", "hand_derivation",
        ["tests/test_p1_events.py::test_same_key_and_same_tuple_have_distinct_internal_ids"], [],
        gap="構造の性質で、拒否する入力の例はない（件数・同一性の Q を範囲外にして検査している）", derivation="docs/research/16-proof-obligations.md"),
     ob("R3-5", "原履歴の完全な読み戻しと、採用・保留・訂正の可換", "checked_native_template",
        ["tests/test_p1_events.py::test_reify_and_public_restore_preserve_complete_history", "tests/test_p1_events.py::test_history_change_is_not_hidden_by_equal_bindings"],
        [g("examples/p1-b/wrong-source-hash.json", ["reason_codes"], ["source_hash_mismatch"]),
         g("examples/p1-b/wrong-source-assertion.json", ["reason_codes"], ["source_assertion_mismatch"])]),
     ob("R3-6", "事象 ID は原台帳・主張に対して新鮮で、既存の名前・互いと衝突しない", "checked_native_template",
        ["tests/test_p1_events.py::test_generated_reference_collision_is_detected", "tests/test_p1_events.py::test_selected_relation_cannot_remain_as_old_atom_or_collide_with_native_predicate"],
        [g("examples/p1-b/existing-name-collision.json", ["reason_codes"], ["event_reference_collision"]),
         g("examples/p1-b/duplicate-event-id.json", ["reason_codes"], ["event_reference_collision"])]),
     ob("R3-7", "事象の件数・同一性・未知の式は範囲外と明示し、保証に含めない", "checked_native_template",
        ["tests/test_p1_events.py::test_event_count_identity_and_unknown_expressions_are_out_of_scope"],
        [g("examples/p1-b/out-of-scope.json", ["comparison", "status"], "partial")]),
     ob("K-ID", "仕様・consumer・snapshot の hash を実体と照合し、原 snapshot の hash を固定する", "checked_native_template",
        ["tests/test_p1_events.py::test_native_spec_and_consumer_cannot_be_spoofed"],
        [g("examples/p1-b/wrong-source-hash.json", ["status"], "invalid_input")]),
     ob("K-STOP", "未知の能力・衝突は比較不能（unassessed）。部分の結果を完全にしない", "checked_native_template",
        ["tests/test_p1_events.py::test_pending_revision_conflict_contexts_and_unknown_caps_keep_p0_selection"],
        [g("examples/p1-b/unknown-capability.json", ["comparison", "status"], "unassessed"),
         g("examples/p1-b/conflict.json", ["comparison", "status"], "unassessed")]),
     ob("K-INV", "I1 支持は採用された主張から／I3 AI 候補を採用しない／I4 未知の能力で停止／I6 原履歴を保持", "checked_native_template",
        ["tests/test_p1_events.py::test_returned_artifact_and_restored_source_do_not_alias_inputs"],
        [g("examples/p1-b/ai-unreviewed.json", ["certificate", "status"], "not_certified", "non_conversion"),
         g("examples/p1-b/unknown-capability.json", ["target_result", "results", 0, "status"], "unassessed")]),
     ob("K-RES", "生成・復元・問い合わせ・比較を共通予算に課金し、中間・返却 binding の上限で止まる", "checked_native_template",
        ["tests/test_p1_events.py::test_reify_restore_never_publish_partial_history", "tests/review/test_boundaries.py::EventLimitTests.test_intermediate_binding_limit_is_exactly_4096"], [],
        gap="上限の境界は例ではなくテスト（境界値の構成が大きいため）で検査している")],
    {"unknown_capability": "基底の方針に従い、可視の主張の未知の能力は文脈を unassessed", "unsupported": "未対応の操作・consumer は unsupported_profile",
     "resource": "resource_limit。部分の履歴・binding・差分・認定票を出さない", "invalid_input": "役割の欠落・複数・ID 衝突・由来・hash の不正は invalid_input"},
    comp(), ev(["examples/p1-b/*.json"], ["tests/test_p1_events.py", "tests/review/test_event_paths.py"], True)))

# ---------------- HOST: handover ----------------
HSPEC = S("handover_spec.json")
HPINS = [(HSPEC, "native_spec"), (P0, "p0_contract"), (ESPEC, "events_spec")] + [(S(m), "p0_runtime") for m in P0_FILES]
HEMB = [S("handover.py"), S("handover_common.py"), S("handover_spec.json"), "examples/p1-c/*.json", "examples/audits/*.json", "examples/review/*.json"]
manifests.append(manifest(
    "p1-handover-host", "引き継ぎ操作の共有の前段（識別・仕様と P0 実体の固定）", "HOST", HSPEC, "docs/research/14-p1-c-contract.md",
    [S("handover.py"), S("handover_common.py")], HPINS, HEMB, ["p0-positive", "p1-events"],
    {"schema_versions": ["p1-handover-request-draft-1", "p1-handover-result-draft-1"], "profiles": ["p1-handover-draft-1"]},
    {"description": "引き継ぎの各操作（p1-event-chain／projection／reference／absence／replay）が共有する前段。操作は持たない"},
    [ob("K-ID", "native 仕様・events 仕様・P0 契約・P0 の5ファイルを実行時に実体と照合し、consumer の profile・仕様 hash・操作を照合する", "checked_native_template",
        ["tests/test_p1_handover.py::test_native_spec_and_runtime_pins_are_checked"],
        [g("examples/p1-c/corrupt-archive.json", ["reason_codes"], ["archive_hash_mismatch"])]),
     ob("K-STOP", "未対応の操作は unsupported_profile。部分の報告・認定票を出さない", "checked_native_template",
        ["tests/test_p1_handover.py::test_each_operation_zero_budget_has_no_partial_report_or_certificate"], [],
        gap="host 独自の拒否例ファイルはなく、各操作の拒否例とテストが担う"),
     ob("K-INV", "I5 打切りで認定票を出さない／I6 入力を変更しない", "checked_native_template",
        ["tests/test_p1_handover.py::test_author_draft_all_paths_replay_and_input_preservation"], [],
        gap="host 独自の拒否例はなく、全例の入力保持をテストで検査している"),
     ob("K-RES", "全操作が共通予算を使い、合成・archive は予算を共有する", "checked_native_template",
        ["tests/test_p1_handover.py::test_replay_and_independent_chain_share_one_budget", "tests/test_p1_handover.py::test_shared_chain_budget_includes_final_certificate_commit"], [],
        gap="共有予算は例ではなくテストで検査している")],
    {"unknown_capability": "host は能力を解釈しない（操作ごとに宣言）", "unsupported": "unsupported_operation／unsupported_profile",
     "resource": "resource_limit", "invalid_input": "consumer・予算・仕様 hash の不整合は invalid_input"},
    comp(), ev(["examples/p1-c/*.json"], ["tests/test_p1_handover.py"], True)))

HDEPS = ["p1-handover-host"]
def hev(extra=()):
    return ev(["examples/p1-c/*.json", "examples/review/*.json"], ["tests/test_p1_handover.py", "tests/review/test_review_negatives.py", *extra], True)

# ---------------- COMP: event chain ----------------
manifests.append(manifest(
    "p1-event-chain", "事象化＋改名の鎖の認定（既知テンプレート）", "COMP", None, "docs/research/14-p1-c-contract.md", [S("chain.py")], [], [],
    HDEPS + ["p1-events"],
    {"operations": ["check_event_chain", "rename_events"], "answer_kinds": ["four-role-history-and-bijective-renaming-1"]},
    {"base_requests": "原履歴と、両計算が完了した旧支持断片", "guarantee": "source_history_and_completed_p0_positive_support", "excludes": "事象の件数・同一性、一般の一階推論、方針変更、新所属データ、実行完了"},
    [ob("COMP-1", "各段の端点・依存・方針・翻訳後Q・履歴を、票の値ではなく実体から再計算して照合する", "checked_native_template",
        ["tests/test_p1_handover.py::test_endpoint_scope_policy_dependencies_are_checked_against_actuals", "tests/test_p1_handover.py::test_honestly_rehashed_changed_history_is_not_a_renaming",
         "tests/review/test_event_paths.py::ChainCertificationTests.test_a_voucher_that_claims_the_split_translation_is_refused_even_when_consistent"],
        [g("examples/p1-c/wrong-intermediate.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/p1-c/wrong-policy.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/p1-c/wrong-dependencies.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/p1-c/wrong-translated-scope.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/review/chain-forged-start-endpoint.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/review/chain-forged-end-endpoint.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/review/chain-consistently-forged-policy.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/review/chain-consistently-forged-dependencies.json", ["certificate", "reason_codes"], ["chain_obligation_failed"]),
         g("examples/review/chain-consistently-forged-scope.json", ["certificate", "reason_codes"], ["chain_obligation_failed"])]),
     ob("COMP-2", "保証の範囲は各段の交差。範囲外の問い・未知・衝突を認定に含めない", "checked_native_template",
        ["tests/test_p1_handover.py::test_unknown_capability_and_outside_query_do_not_disappear", "tests/test_p1_handover.py::test_new_event_queries_are_not_included_in_the_old_query_certificate"],
        [], gap="範囲外の問いで認定が出ないことはテストで検査している（例なし）"),
     ob("COMP-3", "途中の損失は後段で回復できない", "hand_derivation", ["tests/test_p1_handover.py::test_lossless_second_step_does_not_repair_a_lossy_first_step"], [],
        gap="この鎖（事象化と改名）に損失のある段はない。損失のある鎖は p1-projection が扱う", derivation="docs/research/11-p1-contract.md"),
     ob("K-ID", "改名は全域・単射・非捕獲で、新しい台帳参照を使う", "checked_native_template",
        ["tests/test_p1_handover.py::test_rename_is_total_injective_fresh_and_uses_new_ledger_reference"],
        [g("examples/p1-c/noninjective-renaming.json", ["reason_codes"], ["renaming_not_total_injective"])]),
     ob("K-STOP", "未評価・比較不能の問いがあれば認定しない。打切りで認定票を出さない", "checked_native_template",
        ["tests/test_p1_handover.py::test_unknown_capability_and_outside_query_do_not_disappear"], [], gap="例ではなく、乱数照合（tests/review/test_event_paths.py）が衝突・未知を含む鎖の認定可否を検査している"),
     ob("K-INV", "I1〜I6：認定は旧の支持と履歴が両計算で完了し一致する場合に限る", "checked_native_template",
        ["tests/review/test_event_paths.py::ChainCertificationTests.test_certified_exactly_when_every_answer_is_complete"], [],
        gap="認定を拒否する例は COMP-1 の防護例が担う"),
     ob("K-RES", "鎖の検査と実行照合は一つの予算を共有し、最後の認定票の確定も課金する", "checked_native_template",
        ["tests/test_p1_handover.py::test_shared_chain_budget_includes_final_certificate_commit"], [], gap="共有予算はテストで検査している")],
    {"unknown_capability": "未評価の問いは認定を妨げる（not_certified、incomparable_execution）", "unsupported": "host に従う",
     "resource": "resource_limit。認定票を出さない", "invalid_input": "改名の非単射・捕獲・衝突は invalid_input"},
    comp(["p1-events"]), hev(["tests/review/test_event_paths.py"])))

# ---------------- R4: projection ----------------
manifests.append(manifest(
    "p1-projection", "既知の射影と、その実際の出力だけを保存する符号化", "R4", None, "docs/research/14-p1-c-contract.md", [S("projection.py")], [], [],
    HDEPS, {"operations": ["check_projection_chain"], "answer_kinds": ["finite_relation_projection"]},
    {"base_requests": "保持した列だけに依る問い（因子化できる Q）", "excludes": "捨てた列に依る問い、原記録の履歴。別添えは追加入力"},
    [ob("R4-1", "保持列に収まる問いだけを範囲にし、全ての問いが収まるときだけ認定する", "checked_native_template",
        ["tests/test_p1_handover.py::test_all_eight_tuple_subsets_preserve_queries_using_only_kept_columns", "tests/test_p1_handover.py::test_discarded_fields_stay_out_of_scope"],
        [g("examples/p1-c/discarded-query-scope.json", ["results", 0, "status"], "out_of_scope"),
         g("examples/review/projection-mixed-scope.json", ["certificate", "reason_codes"], ["query_out_of_scope"])]),
     ob("R4-2", "同じ射影値で旧回答が異なる二記録を、反例として記録する", "checked_native_template",
        ["tests/test_p1_handover.py::test_lossless_second_step_does_not_repair_a_lossy_first_step"],
        [g("examples/p1-c/lossy-composition.json", ["certificate", "status"], "not_certified"),
         g("examples/review/projection-collision-evidence.json", ["certificate", "evidence_level"], "verified_collision")]),
     ob("R4-3", "後段の無損失符号化・別添えで全体の復元を主張しない。別添えは追加入力として分ける", "checked_native_template",
        ["tests/test_p1_handover.py::test_sidecar_is_explicit_extra_information_not_projection_recovery", "tests/test_p1_handover.py::test_available_sidecar_is_not_reported_as_used_for_a_kept_query"],
        [g("examples/p1-c/sidecar-is-additional-input.json", ["certificate", "status"], "not_certified"),
         g("examples/review/projection-sidecar-mismatch.json", ["reason_codes"], ["sidecar_mismatch"])]),
     ob("K-ID", "射影後の符号化は実際の出力の hash を保つ（二段目の認定は範囲を限る）", "checked_native_template",
        ["tests/test_p1_handover.py::test_lossless_second_step_does_not_repair_a_lossy_first_step"],
        [g("examples/p1-c/lossy-composition.json", ["second_step_certificate", "scope"], "canonical_json_value_identity", "boundary")]),
     ob("K-STOP", "入力不正（重複・型・別添えの不一致）は invalid_input", "checked_native_template",
        ["tests/test_p1_handover.py::test_bool_positions_domain_sizes_and_budgets_are_not_integers"],
        [g("examples/review/projection-sidecar-mismatch.json", ["status"], "invalid_input")]),
     ob("K-INV", "I2 捨てた区別を偽・空の差分にしない／I6 入力を変更しない", "checked_native_template",
        ["tests/test_p1_handover.py::test_discarded_fields_stay_out_of_scope"],
        [g("examples/p1-c/discarded-query-scope.json", ["full_difference_status"], "incomparable", "non_conversion")]),
     ob("K-RES", "各行の射影・照合・符号化の検証を共通予算に課金する", "checked_native_template",
        ["tests/test_p1_handover.py::test_each_operation_zero_budget_has_no_partial_report_or_certificate"], [], gap="予算の境界はテストで検査している")],
    {"unknown_capability": "射影は台帳を読まないため該当しない", "unsupported": "未対応の射影は unsupported_profile", "resource": "resource_limit。認定票を出さない",
     "invalid_input": "arity・重複・位置・別添えの不一致は invalid_input"},
    comp(), hev()))

# ---------------- R3: reference (identity translation) ----------------
manifests.append(manifest(
    "p1-reference", "参考意味：同じ語彙での文集合の恒等テンプレートと有限モデルの反例", "R3", None, "docs/research/14-p1-c-contract.md",
    [S("reference.py")], [], [], HDEPS,
    {"operations": ["check_reference_change"], "answer_kinds": ["first_order_reference"]},
    {"base_requests": "同じ語彙・同じ文集合の恒等（E=恒等、ρ=恒等）", "excludes": "一般の一階理論の保存判定。有限モデルは証人であって網羅ではない"},
    [ob("R3-1", "E と ρ は恒等。認定は文集合の一致（同じ語彙）に限る", "checked_native_template",
        ["tests/test_p1_handover.py::test_same_sentence_sets_have_an_identity_template_proof", "tests/test_p1_handover.py::test_equal_report_hashes_do_not_prove_sentence_identity"],
        [g("examples/p1-c/coverage-countermodel.json", ["certificate", "status"], "not_certified")]),
     ob("R3-2", "充足の対応：恒等では自明。ただし、これだけでは保存と認定しない", "checked_native_template",
        ["tests/test_p1_handover.py::test_identity_satisfaction_does_not_imply_model_coverage"],
        [g("examples/p1-c/finite-check-is-not-coverage.json", ["certificate", "status"], "not_certified")]),
     ob("R3-3", "旧モデルの被覆と新モデルの還元：反例モデルがあれば偽、文集合の包含があれば真、それ以外は未決", "finite_check",
        ["tests/test_p1_handover.py::test_one_and_two_element_agreement_is_not_all_model_coverage", "tests/audits/test_preservation_audit.py::PreservationAuditTests.test_false_entailment_and_invalid_countermodel_are_detected"],
        [g("examples/p1-c/finite-check-is-not-coverage.json", ["model_coverage"], False, "boundary"),
         g("examples/p1-c/existential-without-named-witness.json", ["model_reduct"], False, "boundary")]),
     ob("R3-4", "新理論と旧理論の差を、追加される文として検査する（文集合の比較）", "checked_native_template",
        ["tests/test_p1_handover.py::test_reference_rules_are_not_hardcoded_to_example_symbols"], [], gap="文集合の比較は R3-1 の防護例が担う"),
     ob("R3-5", "履歴・採用は持たない（参考意味は台帳を読まない）", "hand_derivation", ["tests/test_p1_handover.py::test_invalid_models_and_open_or_shadowed_formulas_are_rejected"], [],
        gap="該当なし：参考意味は履歴を持たない", derivation="docs/research/14-p1-c-contract.md"),
     ob("R3-6", "新しい名前を導入しない（同じ語彙）", "hand_derivation", ["tests/test_p1_handover.py::test_invalid_models_and_open_or_shadowed_formulas_are_rejected"], [],
        gap="該当なし：恒等の翻訳で新しい名前を導入しない", derivation="docs/research/14-p1-c-contract.md"),
     ob("R3-7", "存在の含意と名前付きの事実を分け、証明も反例もない問いは未評価にする", "checked_native_template",
        ["tests/test_p1_handover.py::test_existential_consequence_does_not_create_named_fact", "tests/test_p1_handover.py::test_missing_countermodel_is_unassessed_not_nonentailment",
         "tests/review/test_boundaries.py::HandoverBoundaryTests.test_reference_scope_is_the_narrow_two_conjunct_existential_rule_only"],
        [g("examples/p1-c/no-countermodel-no-proof.json", ["results", 0, "source", "status"], "unassessed", "non_conversion"),
         g("examples/p1-c/existential-without-named-witness.json", ["named_witness_assertions_added"], [], "non_conversion")]),
     ob("K-ID", "認定票に方法・範囲を持ち、文集合は正規化 JSON で比較する", "checked_native_template",
        ["tests/test_p1_handover.py::test_same_sentence_sets_have_an_identity_template_proof"], [g("examples/p1-c/identity-template.json", ["certificate", "evidence_level"], "checked_identity_template", "boundary")]),
     ob("K-STOP", "形式の不正は invalid_input、上限は resource_limit。量化・式の上限を非含意に見せない", "checked_native_template",
        ["tests/test_p1_handover.py::test_quantifier_and_formula_limits_never_look_like_nonentailment"], [], gap="上限の挙動はテストで検査している"),
     ob("K-INV", "I2 証明も反例もない問いを偽（非含意）にしない", "checked_native_template",
        ["tests/test_p1_handover.py::test_missing_countermodel_is_unassessed_not_nonentailment"],
        [g("examples/p1-c/finite-check-without-countermodel.json", ["results", 0, "source", "status"], "unassessed", "non_conversion")]),
     ob("K-RES", "式の各節点・量化の各割り当て・証明の各候補を課金する", "checked_native_template",
        ["tests/test_p1_handover.py::test_quantifier_and_formula_limits_never_look_like_nonentailment"], [], gap="上限の境界はテストで検査している")],
    {"unknown_capability": "参考意味は台帳を読まないため該当しない", "unsupported": "未対応の式は unsupported_profile", "resource": "resource_limit。非含意に見せない",
     "invalid_input": "未束縛の変数・未宣言の述語・arity の不一致は invalid_input"},
    comp(), hev(["tests/audits/test_preservation_audit.py"])))

# ---------------- R5: absence / replay ----------------
manifests.append(manifest(
    "p1-absence", "欠落を否定に変える方針変更の診断（閉世界の仮定）", "R5", None, "docs/research/14-p1-c-contract.md",
    [S("absence.py")], [], [], HDEPS, {"operations": ["check_absence_policy"], "answer_kinds": ["support_policy_probe"]},
    {"base_requests": "保存を主張しない。変わる点と追加される仮定を記録する診断"},
    [ob("R5-1", "変わる点（未決→否定）と追加される仮定（closed_world_assumption）を記録する", "checked_native_template",
        ["tests/test_p1_handover.py::test_absence_probe_reports_semantic_change_without_clinical_assertions"],
        [g("examples/p1-c/absence-is-negative.json", ["results", 0, "assumptions"], ["closed_world_assumption"], "non_conversion")]),
     ob("R5-2", "認定を出さない", "checked_native_template",
        ["tests/test_p1_handover.py::test_absence_probe_reports_semantic_change_without_clinical_assertions"],
        [g("examples/p1-c/absence-is-negative.json", ["certificate", "status"], "not_certified"),
         g("examples/p1-c/same-current-answer.json", ["certificate", "status"], "not_certified")]),
     ob("R5-3", "臨床の主張を追加しない", "checked_native_template",
        ["tests/test_p1_handover.py::test_absence_probe_reports_semantic_change_without_clinical_assertions"],
        [g("examples/p1-c/absence-is-negative.json", ["clinical_assertions_added"], [], "non_conversion")]),
     ob("K-ID", "診断の結果は meaning_mode と証拠の強さ（known_policy_change）を持つ", "checked_native_template",
        ["tests/test_p1_handover.py::test_absence_probe_reports_semantic_change_without_clinical_assertions"],
        [g("examples/p1-c/absence-is-negative.json", ["certificate", "evidence_level"], "known_policy_change", "boundary")]),
     ob("K-STOP", "未知・衝突の元は閉世界の否定にしない", "checked_native_template",
        ["tests/test_p1_handover.py::test_unknown_or_conflicting_source_is_not_closed_world_negative"],
        [g("examples/p1-c/unknown-does-not-become-negative.json", ["results", 0, "after_status"], "unassessed", "non_conversion")]),
     ob("K-INV", "I2 未知を否定にしない／I4 未知の能力を解釈しない", "checked_native_template",
        ["tests/test_p1_handover.py::test_unknown_or_conflicting_source_is_not_closed_world_negative"],
        [g("examples/p1-c/unknown-does-not-become-negative.json", ["results", 0, "before_status"], "unassessed", "non_conversion")]),
     ob("K-RES", "既存の P0 の課金と、診断の各行を課金する", "checked_native_template",
        ["tests/test_p1_handover.py::test_each_operation_zero_budget_has_no_partial_report_or_certificate"], [], gap="予算の境界はテストで検査している")],
    {"unknown_capability": "P0 の停止に従う（unassessed のまま）", "unsupported": "複数 atom の問いは unsupported_profile", "resource": "resource_limit。診断を出さない",
     "invalid_input": "P0 の入力検査に従う"}, comp(), hev()))

manifests.append(manifest(
    "p1-replay", "原保存・旧処理系の可用性と、新側の保証の分離（点検）", "R5", None, "docs/research/14-p1-c-contract.md",
    [S("replay.py")], [], [], HDEPS + ["p1-event-chain"], {"operations": ["audit_replay"], "answer_kinds": ["verified_supplied_inventory_and_native_registry"]},
    {"base_requests": "保存を主張しない点検。保存バイト・解釈可能性・可用性・新側の保証を別々に返す", "excludes": "旧処理系の実行（executed は常に false）"},
    [ob("R5-1", "可用性の範囲（提供された inventory と native registry）と、実行していないことを明示する", "checked_native_template",
        ["tests/test_p1_handover.py::test_stored_runtime_bytes_are_not_an_interpreter"],
        [g("examples/p1-c/known-native-ready.json", ["legacy_replay", "availability_scope"], "verified_supplied_inventory_and_native_registry", "boundary"),
         g("examples/p1-c/known-native-ready.json", ["legacy_replay", "executed"], False, "non_conversion")]),
     ob("R5-2", "旧処理系の可用性と新側の意味保証を独立に返す（片方が他方を認定しない）", "checked_native_template",
        ["tests/test_p1_handover.py::test_old_runtime_availability_and_new_semantic_guarantee_are_independent"],
        [g("examples/p1-c/new-guarantee-independent-of-old-binary.json", ["legacy_replay", "status"], "unavailable", "non_conversion"),
         g("examples/p1-c/stored-runtime-is-not-handler.json", ["legacy_replay", "status"], "unavailable", "non_conversion")]),
     ob("R5-3", "runtime の hash・依存の hash・runtime 要求数を実体と照合し、保存バイトだけで実行可能にしない", "checked_native_template",
        ["tests/test_p1_handover.py::test_dependency_integrity_and_archive_to_chain_binding_are_checked", "tests/test_p1_handover.py::test_known_runtime_with_uninterpretable_archive_is_not_ready"],
        [g("examples/review/archive-runtime-wrong-hash.json", ["legacy_replay", "status"], "unavailable"),
         g("examples/review/archive-dependency-hash-mismatch.json", ["legacy_replay", "status"], "unavailable"),
         g("examples/review/archive-no-runtime-requirement.json", ["reason_codes"], ["expected_one_runtime_requirement"]),
         g("examples/review/archive-two-runtime-requirements.json", ["reason_codes"], ["expected_one_runtime_requirement"])]),
     ob("K-ID", "archive の内容 hash・仕様 hash・資源の hash を照合する", "checked_native_template",
        ["tests/test_p1_handover.py::test_dependency_integrity_and_archive_to_chain_binding_are_checked"],
        [g("examples/p1-c/corrupt-archive.json", ["reason_codes"], ["archive_hash_mismatch"])]),
     ob("K-STOP", "解釈できない保存バイトは準備完了にしない", "checked_native_template",
        ["tests/test_p1_handover.py::test_known_runtime_with_uninterpretable_archive_is_not_ready"],
        [g("examples/p1-c/missing-runtime.json", ["legacy_replay", "status"], "unavailable")]),
     ob("K-INV", "I6 原バイトを保持し解釈しない範囲を明示／I5 打切りで報告を出さない", "checked_native_template",
        ["tests/test_p1_handover.py::test_decoded_archive_unicode_is_validated_before_interpretation"],
        [g("examples/p1-c/missing-dependency.json", ["legacy_replay", "requirements", 1, "available"], False)]),
     ob("K-RES", "archive の検証・各要求・独立した鎖の検査を共通予算に課金する", "checked_native_template",
        ["tests/test_p1_handover.py::test_replay_and_independent_chain_share_one_budget"], [], gap="共有予算はテストで検査している")],
    {"unknown_capability": "未知の runtime は unknown_runtime_handler として利用不可", "unsupported": "profile が P0 でなければ unsupported_profile",
     "resource": "resource_limit。報告を出さない", "invalid_input": "base64・hash・資源の重複・runtime 要求数の不正は invalid_input"},
    comp(["p1-event-chain"]), hev()))

# ---------------- P2-a 拡張: 防護例のなかった義務への防護例（examples/p2/、gen_guard_fixtures.py が生成） ----------------
def gx(slug, path, equals, kind="refusal"):
    return g(f"examples/p2/{slug}.json", path, equals, kind)

def boundary(slug, base_n=True):
    return [gx(f"budget-below-{slug}", ["status"], "resource_limit", "boundary"),
            gx(f"budget-exact-{slug}", ["status"], "ok", "boundary")]

P2_GUARDS = {
    ("p0-definitions", "K-STOP"): [gx("definitions-zero-budget", ["status"], "resource_limit"), gx("definitions-zero-budget", ["reason_codes"], ["step_limit"]),
                                   gx("definitions-empty-extension-zero-budget", ["status"], "resource_limit"),
                                   gx("definitions-empty-extension-one-step", ["certificate", "status"], "certified", "boundary")],
    ("p0-definitions", "K-INV"): [gx("definitions-ledger-field-refused", ["reason_codes"], ["unknown_field"])],
    ("p0-definitions", "K-RES"): boundary("definitions"),
    ("p1-finite-forecast", "R2-2"): [gx("forecast-arbitrary-package-refused", ["reason_codes"], ["unknown_field"]),
                                     gx("forecast-nonreport-predicate-refused", ["reason_codes"], ["undeclared_predicate"])],
    ("p1-events", "R3-4"): [g("examples/p1-b/shared-key.json", ["target_result", "retained_assertions"], ["h1", "h2"], "non_conversion")],
    ("p1-events", "K-RES"): boundary("events"),
    ("p1-handover-host", "K-STOP"): [gx("host-unsupported-operation", ["reason_codes"], ["unsupported_operation"]),
                                     gx("host-consumer-operation-unsupported", ["reason_codes"], ["unsupported_operation"]),
                                     gx("host-consumer-profile", ["reason_codes"], ["unsupported_profile"])],
    ("p1-handover-host", "K-INV"): [gx("chain-zero-budget", ["incomplete"], ["request"], "non_conversion")],
    ("p1-handover-host", "K-RES"): boundary("rename-events"),
    ("p1-event-chain", "COMP-2"): [gx("chain-out-of-scope-query", ["certificate", "reason_codes"], ["query_out_of_scope"], "non_conversion"),
                                   gx("chain-out-of-scope-query", ["out_of_scope_query_ids"], ["q3"], "non_conversion")],
    ("p1-event-chain", "K-STOP"): [gx("chain-unknown-capability", ["certificate", "reason_codes"], ["incomparable_execution"])],
    ("p1-event-chain", "K-INV"): [gx("chain-ai-candidate-not-adopted", ["finite_checks", 1, "target_result", "results", 0, "status"], "undetermined", "non_conversion")],
    ("p1-event-chain", "K-RES"): boundary("event-chain"),
    ("p1-absence", "K-RES"): boundary("absence"),
    ("p1-projection", "K-RES"): boundary("projection"),
    ("p1-replay", "K-RES"): boundary("replay"),
    ("p1-reference", "R3-4"): [gx("reference-stronger-target", ["certificate", "reason_codes"], ["model_coverage_not_established"], "non_conversion"),
                               gx("reference-stronger-target", ["model_coverage"], None, "non_conversion")],
    ("p1-reference", "R3-5"): [gx("reference-ledger-field-refused", ["reason_codes"], ["unknown_field"])],
    ("p1-reference", "R3-6"): [gx("reference-new-name-refused", ["reason_codes"], ["undeclared_predicate"])],
    ("p1-reference", "K-STOP"): [gx("reference-finite-probe-unsupported", ["reason_codes"], ["unsupported_finite_probe"]),
                                 gx("reference-formula-depth-limit", ["reason_codes"], ["formula_limit"], "boundary")],
    ("p1-reference", "K-RES"): boundary("reference") + [gx("reference-formula-depth-exact", ["status"], "ok", "boundary")],
}
used = set()
for m in manifests:
    for item in m["obligations"]:
        key = (m["id"], item["id"])
        if key in P2_GUARDS:
            assert not item["guards"], key
            item["guards"] = P2_GUARDS[key]
            item.pop("guard_gap", None)
            used.add(key)
            for field, extra in (("examples", "examples/p2/*.json"), ("tests", "tests/p2/test_guard_examples.py")):
                if extra not in m["evaluation"][field]:
                    m["evaluation"][field].append(extra)
assert used == set(P2_GUARDS), set(P2_GUARDS) - used
# 防護例は固定した仕様・契約の hash を含むので、hash を埋め込む実体（再生成の対象）に加える
for m in manifests:
    if any(pattern.startswith("examples/") for pattern in m["embedded_in"]) and "examples/p2/*.json" not in m["embedded_in"]:
        m["embedded_in"].append("examples/p2/*.json")

# ---------------- P2-b：概念の分割（R6 公理つき読み取りモジュール）。防護例は最初から義務ごとに付ける ----------------
import sys
sys.path.insert(0, str(ROOT / "src"))
from med_dsl.validation import digest as _digest

def sx(slug, path, equals, kind="refusal"):
    return g(f"examples/p2-split/{slug}.json", path, equals, kind)

def split_source_digest(slug):
    return _digest(json.loads((ROOT / f"examples/p2-split/{slug}.json").read_text(encoding="utf-8"))["request"]["source"])

T = "tests/p2/test_concept_split.py::"
OP, CAND, BASE = ["results", 0, "split", "status"], ["results", 0, "split", "candidates"], ["results", 0, "base"]
SPLIT_CAP = "p2-concept-split-draft-1"
manifests.append(manifest(
    "p2-concept-split", "概念の分割：候補集合と情報要求（公理つき読み取りモジュール）", "R6", S("split_spec.json"), "docs/research/23-p2-b-design.md",
    [S("split.py")], [(S("split_spec.json"), "native_spec")], [S("split.py"), "examples/p2-split/*.json"], ["p0-positive"],
    {"operations": ["query_split"], "schema_versions": ["p2-split-request-draft-1", "p2-split-result-draft-1"], "profiles": [SPLIT_CAP],
     "answer_kinds": ["candidate_set"], "capabilities": [SPLIT_CAP]},
    {"base_requests": "基底の要求は一切変えない（読み取り専用）。新しい要求 query_split だけを所有する",
     "data": "一つの文脈・一つの個体の、採用された原子。規則のない単項述語の分割。文脈をまたぐ推論・時間の持続・定義のある述語は範囲外",
     "guarantee": "候補集合は、仕様に固定した公理（包含・被覆・排他）の下で、採用された主張に矛盾しない部分の集合"},
    [ob("K-ID", "仕様の生バイトを hash で照合し、consumer の profile・仕様 hash・操作を検査する", "checked_native_template",
        [T + "NativeSpecTests.test_the_actual_spec_file_is_checked_not_only_the_client_claim", T + "NativeSpecTests.test_the_pinned_hash_is_the_raw_hash_of_the_spec_file"],
        [sx("consumer-spec-hash", ["reason_codes"], ["profile_spec_mismatch"]), sx("consumer-profile", ["reason_codes"], ["unsupported_profile"])]),
     ob("K-STOP", "未知の能力・未解決の衝突・未登録の操作・資源上限で、候補集合を返さず止まる", "checked_native_template",
        [T + "BudgetTests.test_every_budget_gives_complete_rows_or_an_honest_stop", T + "DifferentialTests.test_every_row_equals_the_enumeration_oracle"],
        [sx("unknown-capability-blocks", ["results", 0, "reason_codes"], ["unknown_capability"]), sx("conflict-blocks", ["results", 0, "reason_codes"], ["unresolved_conflict"]),
         sx("consumer-operations", ["reason_codes"], ["unsupported_operation"]), sx("budget-zero", ["reason_codes"], ["step_limit"])]),
     ob("K-INV", "I1 結論を支持にしない／I2 候補を作れないとき偽にしない／I3 AI 候補を採用しない／I4 未知の能力を解釈しない／I5 打切りで値を出さない／I6 入力を変更しない／I7 決定的", "checked_native_template",
        [T + "DifferentialTests.test_the_input_is_preserved_and_the_result_is_deterministic", T + "DifferentialTests.test_every_row_equals_the_enumeration_oracle"],
        [sx("single-by-exclusion", ["results", 0, "base", "parts", "fiction:P2@1"], "undetermined", "non_conversion"), sx("no-parent", OP, "no_parent", "non_conversion"),
         sx("ai-candidate-pending", ["results", 0, "evidence", "pending", 0, "assertion_ref"], "h2", "non_conversion"), sx("budget-zero", ["results", 0, "split"], None, "non_conversion")]),
     ob("K-RES", "steps を課金点で数え、上限に達したら完了した行を残して未完了の行は値を持たない", "checked_native_template",
        [T + "BudgetTests.test_every_budget_gives_complete_rows_or_an_honest_stop", T + "FixtureTests.test_the_measured_budget_is_the_smallest_that_completes"],
        [sx("budget-below", ["status"], "resource_limit", "boundary"), sx("budget-exact", ["status"], "ok", "boundary")]),
     ob("R2-1", "基底の状態への書き込み操作を持たず、入力を変更しない", "checked_native_template",
        [T + "DifferentialTests.test_the_input_is_preserved_and_the_result_is_deterministic"],
        [sx("old-record-only", ["snapshot_sha256"], split_source_digest("old-record-only"), "non_conversion")]),
     ob("R2-2", "基底の語彙の述語についての結論を、基底の原子・状態として返さず、基底の閉包に入れない（読み替え：23 の §4）", "checked_native_template",
        [T + "DifferentialTests.test_base_block_equals_the_p0_query_on_a_ledger_without_the_split_capability"],
        [sx("single-by-exclusion", ["results", 0, "base", "parts", "fiction:P2@1"], "undetermined", "non_conversion"),
         sx("part-only-parent-derived", ["results", 0, "base", "parent"], "undetermined", "non_conversion")]),
     ob("R2-3", "基底の状態は核の採用選択を通してだけ読む（疑い・確認のない AI 候補・訂正済みの主張は候補を決めない）", "checked_native_template",
        [T + "DifferentialTests.test_every_row_equals_the_enumeration_oracle"],
        [sx("ai-candidate-pending", OP, "open", "non_conversion"), sx("corrected-assertion", OP, "single", "non_conversion"), sx("views-over-time", ["results", 1, "split", "status"], "asserted", "non_conversion")]),
     ob("R2-4", "回答型は基底と別で、分割の状態から基底の状態への変換規則を持たない", "checked_native_template",
        [T + "DifferentialTests.test_no_split_status_is_ever_a_base_status_and_nothing_is_converted", T + "ContractConditionTests.test_x05_the_single_candidate_is_not_a_base_support"],
        [sx("single-by-exclusion", ["results", 0, "converted_to_base"], False, "non_conversion"), sx("single-is-not-base-support", ["results", 1, "status"], "undetermined", "non_conversion"),
         sx("old-queries-unchanged", ["results", 1, "status"], "undetermined", "non_conversion")]),
     ob("R2-5", "自己申告（read_only など）を根拠にせず、理解する能力を固定した集合にする。分割を理解しない消費側は停止する", "checked_native_template",
        [T + "ContractConditionTests.test_x04_an_unaware_consumer_stops_and_an_aware_consumer_reads", T + "ContractConditionTests.test_x04_a_third_unknown_capability_still_blocks_the_aware_consumer"],
        [sx("self-claim-refused", ["reason_codes"], ["unknown_field"]), sx("base-unaware-consumer-stops", ["results", 0, "reason_codes"], ["unknown_capability"])]),
     ob("R6-1", "公理は仕様に固定され、要求は変更できない。分割できるのは、宣言された規則のない単項述語だけ", "checked_native_template",
        [T + "FixtureTests.test_every_example_returns_its_hand_specified_expectation"],
        [sx("extra-axiom-refused", ["reason_codes"], ["unknown_field"]), sx("symbol-has-rules", ["reason_codes"], ["split_symbol_has_rules"]),
         sx("duplicate-parts", ["reason_codes"], ["duplicate_reference"]), sx("parent-among-parts", ["reason_codes"], ["parent_among_parts"]),
         sx("one-part", ["reason_codes"], ["too_few_parts"]), sx("undeclared-part", ["reason_codes"], ["undeclared_predicate"])]),
     ob("R6-2", "旧データ（部分の原子を含まない状態）は、公理を加えても矛盾しない。旧い任意のモデルは公理を満たす拡張を持つ", "hand_derivation",
        [T + "ExhaustiveRuleTests.test_old_data_never_makes_the_split_inconsistent", T + "ExhaustiveRuleTests.test_every_small_old_model_expands_to_a_model_of_the_axioms",
         T + "DifferentialTests.test_old_data_only_ledgers_never_produce_a_violation"],
        [sx("old-record-only", OP, "open", "non_conversion"), sx("parent-opposed", OP, "parent_opposed", "non_conversion"), sx("no-parent", OP, "no_parent", "non_conversion")],
        derivation="docs/research/23-p2-b-design.md"),
     ob("R6-3", "候補集合は、公理を満たすモデルのうち採用された主張に合うものの部分の集合に等しい（健全かつ完全）", "finite_check",
        [T + "ExhaustiveRuleTests.test_rules_agree_with_the_enumeration_for_every_assignment", T + "DifferentialTests.test_every_row_equals_the_enumeration_oracle",
         T + "DenseDifferentialTests.test_dense_ledgers_agree_with_the_oracle_and_reach_every_status_often"],
        [sx("narrowed-three-parts", OP, "narrowed", "non_conversion"), sx("all-parts-opposed", OP, "parent_opposed", "non_conversion"), sx("part-asserted", OP, "asserted", "non_conversion"),
         sx("inconsistent-two-parts-asserted", OP, "inconsistent"), sx("inconsistent-all-parts-opposed", OP, "inconsistent")]),
     ob("R6-4", "公理から導いた結論（除外・残りの一つ・親の導出）は、頼る公理を挙げ、採用された主張として示さない", "checked_native_template",
        [T + "DifferentialTests.test_conclusions_name_the_axioms_they_rely_on"],
        [sx("single-by-exclusion", ["results", 0, "split", "derivation"], ["A2_coverage"], "non_conversion"), sx("part-only-parent-derived", ["results", 0, "split", "parent_derived"], True, "non_conversion")]),
     ob("R6-5", "範囲（一つの文脈・採用された原子・規則のない単項述語）を明示し、範囲外を黙って広げない", "checked_native_template",
        [T + "ContractConditionTests.test_x14_old_answers_are_reproduced_and_the_new_question_returns_candidates"],
        [sx("contexts-do-not-leak", ["results", 1, "split", "status"], "open", "non_conversion"), sx("symbol-has-rules", ["error_path"], "split"),
         sx("non-unary-part", ["reason_codes"], ["split_predicate_not_unary"])]),
     ob("R6-6", "情報要求は候補だけを求め、実現でき、臨床上の否定を含意しない。AI 候補・疑いは保留として残す", "finite_check",
        [T + "DifferentialTests.test_every_candidate_offered_in_a_request_can_actually_be_asserted"],
        [sx("old-record-only", ["results", 0, "information_requests", 0, "kind"], "confirm_part", "non_conversion"),
         sx("inconsistent-all-parts-opposed", ["results", 0, "information_requests", 0, "kind"], "resolve_split_violation"),
         sx("ai-candidate-pending", ["results", 0, "information_requests", 0, "pending_assertion_refs"], ["h2"], "non_conversion")])],
    {"unknown_capability": "その文脈の行を解釈せず blocked。保留・訂正済みの主張が未知の能力を要求しても落とさない",
     "unsupported": "unsupported_profile", "resource": "resource_limit。未完了の行は候補集合を持たない",
     "invalid_input": "構造・参照・hash・分割の宣言の不正は予算に依らず invalid_input"},
    comp(), ev(["examples/p2-split/*.json"], ["tests/p2/test_concept_split.py"], True, "tests/p2/split_oracle.py")))

# ---------------- P2-c：概念の分割の併用（JOINT 併用）。防護例は最初から義務ごとに付ける ----------------
def cx(slug, path, equals, kind="refusal"):
    return g(f"examples/p2-splits/{slug}.json", path, equals, kind)

def combo_source_digest(slug):
    return _digest(json.loads((ROOT / f"examples/p2-splits/{slug}.json").read_text(encoding="utf-8"))["request"]["source"])

U = "tests/p2/test_split_combination.py::"
V = "tests/p2/test_combinations.py::IndependenceTests."
SPLITS_CAP = "p2-split-combination-draft-1"
CA = "fiction:A@1"
manifests.append(manifest(
    "p2-split-combination", "概念の分割の併用：保存性の判定と併用での候補集合（記号を共有し得る拡張の合成）", "JOINT", S("splits_spec.json"), "docs/research/25-p2-c-design.md",
    [S("splits.py")], [(S("splits_spec.json"), "native_spec")], [S("splits.py"), "examples/p2-splits/*.json"], ["p0-positive", "p2-concept-split"],
    {"operations": ["check_split_combination", "query_split_combination"], "schema_versions": ["p2-splits-request-draft-1", "p2-splits-result-draft-1"],
     "profiles": [SPLITS_CAP], "answer_kinds": ["split_combination_certificate", "joint_candidate_set"], "capabilities": [SPLITS_CAP]},
    {"base_requests": "基底の要求は一切変えない（読み取り専用）。新しい要求 check_split_combination・query_split_combination だけを所有する",
     "data": "分割 4 個・語彙 10 記号まで、規則のない単項述語。一つの文脈・一つの個体の、採用された原子。情報を失う段（射影）・文脈をまたぐ推論は範囲外",
     "guarantee": "併用の保存性は、併用全体の公理の下で旧記号の全割り当てを列挙して判定する。個別の認定票は根拠にしない"},
    [ob("K-ID", "仕様の生バイトを hash で照合し、consumer の profile・仕様 hash・操作を検査する", "checked_native_template",
        [U + "NativeSpecTests.test_the_actual_spec_file_is_checked_not_only_the_client_claim", U + "NativeSpecTests.test_the_pinned_hash_is_the_raw_hash_of_the_spec_file"],
        [cx("check-consumer-spec-hash", ["reason_codes"], ["profile_spec_mismatch"]), cx("check-consumer-profile", ["reason_codes"], ["unsupported_profile"])]),
     ob("K-STOP", "未知の能力・未解決の衝突・未登録の操作・資源上限で、候補集合も認定票も返さず止まる", "checked_native_template",
        [U + "BudgetTests.test_every_query_budget_gives_complete_rows_or_an_honest_stop", U + "BudgetTests.test_a_check_is_either_complete_or_has_no_certificate"],
        [cx("query-unknown-capability-blocks", ["results", 0, "reason_codes"], ["unknown_capability"]), cx("query-conflict-blocks", ["results", 0, "reason_codes"], ["unresolved_conflict"]),
         cx("check-consumer-operations", ["reason_codes"], ["unsupported_operation"]), cx("check-unsupported-operation", ["reason_codes"], ["unsupported_operation"]),
         cx("check-budget-zero", ["reason_codes"], ["step_limit"])]),
     ob("K-INV", "I1 結論を支持にしない／I3 AI 候補を採用しない／I4 未知の能力を解釈しない／I5 打切りで値を出さない／I6 入力を変更しない／I7 決定的", "checked_native_template",
        [U + "DifferentialTests.test_the_input_is_preserved_and_the_result_is_deterministic", U + "DifferentialTests.test_every_row_equals_the_oracle"],
        [cx("query-ai-candidate-pending", ["results", 0, "evidence", "pending", 0, "assertion_ref"], "h2", "non_conversion"),
         cx("query-base-unchanged-by-the-combination", ["results", 0, "status"], "supported", "non_conversion"),
         cx("query-budget-zero", ["results", 0, "splits"], None, "non_conversion"), cx("check-budget-zero", ["incomplete"], ["request"], "non_conversion")]),
     ob("K-RES", "steps を課金点で数え、上限に達したら完了した行を残して未完了の行は値を持たない。認定票は完了したときだけ出す", "checked_native_template",
        [U + "BudgetTests.test_every_query_budget_gives_complete_rows_or_an_honest_stop", U + "FixtureTests.test_the_measured_budgets_are_the_smallest_that_complete"],
        [cx("check-budget-below", ["status"], "resource_limit", "boundary"), cx("check-budget-exact", ["status"], "ok", "boundary"),
         cx("query-budget-below", ["status"], "resource_limit", "boundary"), cx("query-budget-exact", ["status"], "ok", "boundary")]),
     ob("R2-1", "基底の状態への書き込み操作を持たず、入力を変更しない", "checked_native_template",
        [U + "DifferentialTests.test_the_input_is_preserved_and_the_result_is_deterministic"],
        [cx("query-k04-old-data", ["snapshot_sha256"], combo_source_digest("query-k04-old-data"), "non_conversion")]),
     ob("R2-2", "基底の語彙の述語についての結論を、基底の原子・状態として返さず、基底の閉包に入れない", "checked_native_template",
        [U + "DifferentialTests.test_base_block_equals_the_p0_query_on_a_ledger_without_the_capabilities"],
        [cx("query-shared-part-narrows", ["results", 0, "base", "fiction:B@1"], "undetermined", "non_conversion"),
         cx("query-chain-exclusion-flows", ["results", 0, "base", CA], "undetermined", "non_conversion")]),
     ob("R2-3", "基底の状態は核の採用選択を通してだけ読む（疑い・確認のない AI 候補・訂正済みの主張は候補を決めない）", "checked_native_template",
        [U + "DifferentialTests.test_every_row_equals_the_oracle"],
        [cx("query-ai-candidate-pending", ["results", 0, "splits", 0, "joint", "status"], "open", "non_conversion")]),
     ob("R2-4", "回答型は基底と別で、併用の状態から基底の状態への変換規則を持たない", "checked_native_template",
        [U + "DifferentialTests.test_statuses_are_disjoint_from_base_statuses_and_nothing_is_converted"],
        [cx("query-k04-old-data", ["results", 0, "converted_to_base"], False, "non_conversion"),
         cx("query-base-unchanged-by-the-combination", ["results", 1, "status"], "opposed", "non_conversion")]),
     ob("R2-5", "自己申告を根拠にせず、理解する能力を固定した集合にする。併用を理解しない消費側は停止する", "checked_native_template",
        [U + "FixtureTests.test_every_example_returns_its_hand_derived_expectation"],
        [cx("query-self-claim-refused", ["reason_codes"], ["unknown_field"]), cx("base-unaware-consumer-stops-on-combination-capability", ["results", 0, "reason_codes"], ["unknown_capability"]),
         cx("query-combination-capability-understood", ["results", 0, "splits", 0, "joint", "status"], "asserted", "non_conversion")]),
     ob("R6-1", "公理は仕様に固定され、要求は変更できない。併用できるのは、宣言された規則のない単項述語の分割だけ", "checked_native_template",
        [U + "FixtureTests.test_every_example_returns_its_hand_derived_expectation"],
        [cx("check-extra-axiom-refused", ["reason_codes"], ["unknown_field"]), cx("check-symbol-has-rules", ["reason_codes"], ["split_symbol_has_rules"])]),
     ob("R6-2", "旧データでの無矛盾を、併用の保存性の判定と一致させる（単独の分割では無条件、併用では判定が保存的なときに限る）", "hand_derivation",
        [U + "JudgmentTests.test_certification_agrees_with_the_data_level_old_only_states"],
        [cx("query-k04-old-data", ["results", 0, "splits", 0, "joint", "status"], "inconsistent"), cx("check-shared-one-part-conservative", ["certificate", "status"], "certified", "non_conversion"),
         cx("check-k04-shared-parts", ["certificate", "status"], "not_certified")],
        derivation="docs/research/25-p2-c-design.md"),
     ob("R6-3", "併用での候補集合は、併用の公理を満たすモデルのうち採用された主張に合うものの射影に等しい（健全かつ完全）", "finite_check",
        [U + "DifferentialTests.test_every_row_equals_the_oracle", U + "DenseTests.test_dense_states_reach_every_status_often_and_agree_with_the_oracle"],
        [cx("query-chain-later-info-flows-back", ["results", 0, "splits", 1, "joint", "status"], "asserted", "non_conversion"),
         cx("query-shared-part-narrows", ["results", 0, "splits", 0, "joint", "status"], "single", "non_conversion"), cx("query-k04-old-data", ["results", 0, "splits", 1, "joint", "status"], "inconsistent")]),
     ob("R6-4", "結論は、頼る公理の分割（連結成分）を挙げる。他の成分の公理には頼らない", "checked_native_template",
        [U + "DifferentialTests.test_a_split_alone_in_its_component_has_the_same_joint_and_individual_result"],
        [cx("query-chain-exclusion-flows", ["results", 0, "splits", 1, "axioms_of_splits"], [0, 1], "non_conversion"),
         cx("query-disjoint-factors", ["results", 0, "splits", 1, "axioms_of_splits"], [1], "non_conversion")]),
     ob("R6-5", "範囲（4 分割・10 記号・規則のない単項述語・一つの文脈と個体）を明示し、範囲外を黙って広げない", "checked_native_template",
        [U + "FixtureTests.test_every_example_returns_its_hand_derived_expectation"],
        [cx("check-vocabulary-limit", ["reason_codes"], ["vocabulary_limit"]), cx("check-too-many-splits", ["reason_codes"], ["item_limit"]), cx("check-symbol-has-rules", ["error_path"], "splits[0]")]),
     ob("R6-6", "情報要求は候補だけを求め、実現でき、臨床上の否定を含意しない。矛盾した成分は解消を求める", "finite_check",
        [U + "DifferentialTests.test_every_offered_candidate_can_actually_be_asserted"],
        [cx("query-chain-exclusion-flows", ["results", 0, "information_requests", 0, "kind"], "confirm_part", "non_conversion"),
         cx("query-k04-old-data", ["results", 0, "information_requests", 0, "kind"], "resolve_split_violation"),
         cx("query-disjoint-violation-does-not-leak", ["results", 0, "information_requests", 0, "split"], 1, "non_conversion")]),
     ob("JOINT-1", "併用の構造・成分・旧記号と新記号を、宣言した分割から再計算する。個別の認定票・構造の自己申告を受け付けない", "checked_native_template",
        [U + "JudgmentTests.test_structure_is_recomputed_from_the_splits_and_matches_the_definitions"],
        [cx("check-individual-certificates-refused", ["reason_codes"], ["unknown_field"]), cx("check-claimed-structure-refused", ["reason_codes"], ["unknown_field"]),
         cx("check-cyclic", ["structure", "kind"], "cyclic", "non_conversion")]),
     ob("JOINT-2", "互いに素な併用は個別の結果に分解できる。拡張の独立は機械的に検査でき、独立な拡張の併用は全例の結果を変えない（X08）", "finite_check",
        [U + "DifferentialTests.test_a_split_alone_in_its_component_has_the_same_joint_and_individual_result", U + "ConstructedStructureTests.test_disjoint_combinations_are_certified_and_decompose",
         V + "test_every_independent_subset_gives_the_same_results_as_each_extension_alone",
         V + "test_registration_and_dispatch_order_do_not_change_any_result"],
        [cx("query-disjoint-factors", ["results", 0, "splits", 0, "differs"], False, "non_conversion"),
         cx("query-disjoint-violation-does-not-leak", ["results", 0, "splits", 1, "joint", "status"], "open", "non_conversion")]),
     ob("JOINT-3", "記号を共有する併用の保存性は、併用全体の公理の下で旧記号の全割り当てを列挙して判定する。個別に保存的でも不認定になり得る（K04 型）", "hand_derivation",
        [U + "JudgmentTests.test_the_judgment_agrees_with_the_oracle_for_every_one_and_two_split_combination_over_four_symbols", U + "JudgmentTests.test_random_combinations_with_more_splits_and_parts_agree_with_the_oracle",
         U + "ContractConditionTests.test_x09_individually_conservative_splits_are_not_conservative_together"],
        [cx("check-k04-shared-parts", ["individual", 0, "certificate"], "certified", "non_conversion"), cx("check-k04-shared-parts", ["certificate", "reason_codes"], ["not_conservative_over_old_symbols"]),
         cx("check-shared-one-part-conservative", ["certificate", "status"], "certified", "non_conversion"), cx("query-k04-old-data", ["results", 0, "interaction_violation"], True, "non_conversion")],
        derivation="docs/research/25-p2-c-design.md"),
     ob("JOINT-4", "鎖（入れ子）では、後段の状態は前段が定める個体に限り定まる。前段で区別されないものを、後段の分割だけで葉まで確定しない", "finite_check",
        [U + "ConstructedStructureTests.test_nested_combinations_are_forests_certified_and_agree_with_the_oracle", U + "ContractConditionTests.test_x10_the_later_stage_is_decided_only_when_the_earlier_stage_decides_the_individual",
         U + "ContractConditionTests.test_x10_the_chain_result_differs_from_composing_the_stages_one_after_the_other"],
        [cx("query-chain-loss-not-recovered", ["results", 0, "splits", 1, "joint", "status"], "no_parent", "non_conversion"),
         cx("query-chain-exclusion-flows", ["results", 0, "splits", 1, "individual", "status"], "no_parent", "non_conversion"),
         cx("query-chain-later-info-flows-back", ["results", 0, "splits", 0, "differs"], True, "non_conversion")]),
     ob("JOINT-5", "併用の範囲を明示する：分割 4 個・語彙 10 記号・重複する分割の拒否。範囲外は拒否する", "checked_native_template",
        [U + "FixtureTests.test_every_example_returns_its_hand_derived_expectation"],
        [cx("check-duplicate-split", ["reason_codes"], ["duplicate_split"]), cx("check-too-many-splits", ["reason_codes"], ["item_limit"]), cx("check-vocabulary-limit", ["reason_codes"], ["vocabulary_limit"])]),
     ob("JOINT-6", "個別の結果と併用の結果の両方と、その差（differs）を返し、差を隠さない", "finite_check",
        [U + "DifferentialTests.test_the_individual_result_equals_the_p2_b_query_split_for_the_same_split"],
        [cx("query-shared-part-narrows", ["results", 0, "splits", 0, "differs"], True, "non_conversion"), cx("query-k04-old-data", ["results", 0, "splits", 0, "individual", "status"], "open", "non_conversion"),
         cx("query-shared-part-narrowed-differently", ["results", 0, "splits", 0, "differs"], True, "non_conversion"),
         cx("query-chain-exclusion-flows", ["results", 0, "splits", 1, "differs"], True, "non_conversion")])],
    {"unknown_capability": "その文脈の行を解釈せず blocked。保留・訂正済みの主張が未知の能力を要求しても落とさない",
     "unsupported": "unsupported_profile", "resource": "resource_limit。未完了の行は候補集合を持たず、未完了の判定は認定票を出さない",
     "invalid_input": "構造・参照・hash・分割の宣言・併用の範囲の不正は予算に依らず invalid_input"},
    comp(["p2-concept-split"]), ev(["examples/p2-splits/*.json"], ["tests/p2/test_split_combination.py", "tests/p2/test_combinations.py"], True, "tests/p2/splits_oracle.py")))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_temporal_manifest import temporal_manifest
manifests.append(temporal_manifest(ROOT))
from gen_quantity_manifest import quantity_manifest
manifests.append(quantity_manifest(ROOT))
from gen_measurement_manifest import measurement_manifest
manifests.append(measurement_manifest(ROOT))
from gen_display_manifest import display_manifest
manifests.append(display_manifest(ROOT))
from gen_temporal_measurement_manifest import temporal_measurement_manifest
manifests.append(temporal_measurement_manifest(ROOT))

from gen_temporal_display_manifest import temporal_display_manifest
manifests.append(temporal_display_manifest(ROOT))

OUT.mkdir(exist_ok=True)
for m in manifests:
    (OUT / (m["id"] + ".json")).write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(manifests), "manifests written to", OUT)

index = {"schema_version": "p2-extension-index-draft-1", "status": "author_draft", "independent_review": False,
         "note": "P2-a の宣言一覧。P1の20条件・80 JSON・417必須パス、231開発テスト、レビュー系列とは別の分母。宣言は意味の正しさの証拠ではない",
         "extensions": [{"id": m["id"], "class": m["class"], "path": m["id"] + ".json",
                         "sha256": hashlib.sha256((OUT / (m["id"] + ".json")).read_bytes()).hexdigest()} for m in manifests]}
(OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("index written")
