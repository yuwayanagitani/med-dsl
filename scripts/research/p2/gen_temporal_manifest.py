"""P2-eのR5宣言。gen_extension_manifests.pyが他の宣言と一緒に書き出す。"""

import hashlib


def temporal_manifest(root):
    def obligation(ident, text, test, guards, evidence="checked_native_template"):
        return {"id":ident,"statement":text,"evidence":evidence,
                "checks":["tests/p2/test_temporal.py::TemporalTests."+test],
                "guards":[{"example":"examples/p2-temporal/"+name.lower()+".json","path":path,"equals":value,"kind":"boundary"}
                          for name,path,value in guards]}
    row=lambda field:["results",0,field]
    return {
        "schema_version":"p2-extension-manifest-draft-1","id":"p2-temporal-assertion","version":"draft-1",
        "title":"有効期間と参照時点を分けた部分訂正の方針診断",
        "status":{"review_state":"author_draft","independent_review":False},"class":"R5",
        "spec":{"path":"src/med_dsl/temporal_spec.json","sha256":hashlib.sha256((root/"src/med_dsl/temporal_spec.json").read_bytes()).hexdigest()},
        "contract_doc":"docs/research/31-p2-e-design.md","implementation":{"modules":["src/med_dsl/temporal.py"]},
        "pins":[{"path":"src/med_dsl/host.py","role":"dispatcher"},{"path":"docs/research/32-p2-e-cases.md","role":"hand_specified_expectations"}],
        "embedded_in":["examples/p2-temporal/*.json"],"depends_on":[{"id":"p0-positive","version":"draft-2"}],
        "owns":{"operations":["probe_temporal_literal"],"schema_versions":["p2-temporal-request-draft-1","p2-temporal-result-draft-1","p2-temporal-ledger-draft-1"],
                "profiles":["p2-temporal-assertion-draft-1"],"answer_kinds":["temporal_literal_probe"],"predicates":[],"capabilities":["p2-temporal-assertion-draft-1"]},
        "scope":{"base_requests":"新しい期間つき要求と旧要求の保存は主張しない。旧要求は専用の旧経路に保持する",
                 "fragment":"単一文脈・個体・単項原子。有限半開区間。未知期間・未指定を保留。規則・自動取込・基底への変換なし"},
        "obligations":[
            obligation("K-ID","native仕様と消費側の版・hash・操作を照合する","test_native_identity_and_spec_mismatch_fail_closed",[("N07-hash",["status"],"unsupported_profile")]),
            obligation("K-STOP","可視の未知能力、期間情報の不足、未対応、不正を区別して止める","test_hand_expectations_and_manifest_integrity",[("T18",row("reason_codes"),["unknown_capability"])]),
            obligation("K-INV","確認前の候補を採用せず、入力を変更せず、新結果を基底へ変換しない","test_input_immutability_and_permutation_including_evidence",[("T15",row("positive_assertion_refs"),["B"])]),
            obligation("K-RES","共通予算に従い、未完了の行に値を返さない","test_budget_sweep_has_no_partial_values_or_changed_finished_rows",[("B01",["steps_used"],0)]),
            obligation("R5-1","全体訂正との意味差と、区間全体の明示主張・部分訂正の前提を示す","test_hand_expectations_and_manifest_integrity",[("T07",row("assumptions"),["explicit_interval_uniformity","scoped_revision"])]),
            obligation("R5-2","保存・医学的正しさの認定を出さない","test_no_base_conversion_and_old_route_does_not_call_temporal",[("T03",["certificate","status"],"not_certified")]),
            obligation("R5-3","臨床の主張を追加しない","test_no_base_conversion_and_old_route_does_not_call_temporal",[("T03",["clinical_assertions_added"],[])]),
            obligation("TE-1","記録・確認の可視性と対象時点を分ける","test_two_record_finite_histories_agree_with_interval_subtraction",[("T02",row("literal_state"),"neither"),("T03",row("literal_state"),"positive_only")],"finite_check"),
            obligation("TE-2","半開境界・期間不明・未指定を補完しない","test_hand_expectations_and_manifest_integrity",[("T05",row("literal_state"),"neither"),("T13",row("literal_state"),None)],"finite_check"),
            obligation("TE-3","包含される区間内だけを訂正する","test_two_record_finite_histories_agree_with_interval_subtraction",[("T07",row("literal_state"),"positive_only"),("T08",row("literal_state"),"negative_only")],"finite_check"),
            obligation("TE-4","採用から除かれた訂正元の辺も効き、元記録を復活させない","test_three_record_chains_and_branches_agree_with_interval_subtraction",[("T09",row("masked_assertion_refs"),["A","B"])],"finite_check"),
            obligation("TE-5","明示否定・競合・根拠なしを区別する","test_hand_expectations_and_manifest_integrity",[("T11",row("literal_state"),"both"),("T06",row("literal_state"),"neither")],"finite_check"),
            obligation("TE-6","未知能力を落とさず、旧経路・原記録・型の境界を保つ","test_no_base_conversion_and_old_route_does_not_call_temporal",[("T20",row("literal_state"),None),("N10",["converted_to_base"],False)],"finite_check"),
            obligation("TE-7","決定性と行の原子的な確定、完成行の予算に対する不変を守る","test_budget_sweep_has_no_partial_values_or_changed_finished_rows",[("B04-6",["results",1,"literal_state"],None)],"finite_check"),
            obligation("TE-8","仕様・方針・依存・実装を識別し、変異と再検証の対象を追跡する","test_each_of_the_five_semantic_mutants_is_detected_by_its_guard",[("N07-hash",["status"],"unsupported_profile")],"finite_check")],
        "stops":{"unknown_capability":"可視の全主張を検査しunassessed。保留・訂正済み・期間外も落とさない",
                 "unsupported":"unsupported_profile。open_end・期間不明の訂正・未対応のprofile/方針/操作",
                 "resource":"resource_limit。未完了行の値・採用集合・根拠はnull。認定なし",
                 "invalid_input":"構造・参照・区間包含・確認順序は予算に依らず検査"},
        "composition":{"shares_names_with":[],"reads_extensions":[],"order_dependent":False},
        "evaluation":{"examples":["examples/p2-temporal/*.json"],"tests":["tests/p2/test_temporal.py"],"budget_sweep":True,"oracle":"tests/p2/temporal_oracle.py"}}
