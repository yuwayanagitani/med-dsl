"""P2-g：型付き測定版のR5宣言。数量への依存と19義務を明示する。"""
import hashlib


def measurement_manifest(root):
    def obligation(ident,text,test,guards,evidence='checked_native_template'):
        return {'id':ident,'statement':text,'evidence':evidence,
                'checks':['tests/p2/test_measurement.py::MeasurementTests.'+test],
                'guards':[{'example':'examples/p2-measurement/'+name.lower()+'.json','path':path,'equals':value,'kind':'boundary'} for name,path,value in guards]}
    row=lambda key:['results',0,key]
    return {'schema_version':'p2-extension-manifest-draft-2','id':'p2-measurement-binding','version':'draft-2',
        'title':'確認対象の内容を固定した測定記録の選択と数量計算への接続','status':{'review_state':'author_draft','independent_review':False},'class':'R5',
        'spec':{'path':'src/med_dsl/measurement_spec.json','sha256':hashlib.sha256((root/'src/med_dsl/measurement_spec.json').read_bytes()).hexdigest()},
        'contract_doc':'docs/research/37-p2-g-design.md','implementation':{'modules':['src/med_dsl/measurement.py']},
        'pins':[{'path':'src/med_dsl/host.py','role':'dispatcher'},{'path':'docs/research/38-p2-g-cases.md','role':'hand_specified_expectations'},
                {'path':'src/med_dsl/quantity_spec.json','role':'quantity_native_spec'}],
        'embedded_in':['src/med_dsl/measurement_spec.json','src/med_dsl/quantity.py','examples/p2-measurement/*.json','examples/p2-quantity/*.json'],
        'depends_on':[{'id':'p0-positive','version':'draft-2'},{'id':'p2-quantity-literal','version':'draft-2'}],
        'owns':{'operations':['evaluate_measurements'],'schema_versions':['p2-measurement-request-draft-1','p2-measurement-result-draft-1','p2-measurement-ledger-draft-1'],
                'profiles':['p2-measurement-binding-draft-1'],'answer_kinds':['measurement_literal_projection'],'predicates':[],'capabilities':['p2-measurement-binding-draft-1']},
        'scope':{'base_requests':'旧schemaは旧経路に保持する。型付き確認から旧基底の支持へ変換しない',
                 'fragment':'三つの架空property、瞬間・未知・未指定の文脈、slot単位の全体訂正、内容全体を指定した人の確認。文脈一致の数値点検のみ'},
        'obligations':[
            obligation('K-ID','nativeと量の依存版・hash・方針を照合','test_native_dependency_pins_and_structural_refusals_precede_budget',[('N10-hash',['status'],'unsupported_profile')]),
            obligation('K-STOP','未知能力・情報不足・競合・相違・不正を区別','test_hand_expectations_api_cli_and_manifest',[('M22-masked-record',row('reason_codes'),['unknown_capability']),('M16',row('reason_codes'),['method_unknown'])]),
            obligation('K-INV','原情報・両出自を保持し臨床主張を生成しない','test_ai_origin_and_confirmation_are_preserved_without_clinical_or_base_writes',[('M08',['clinical_confirmation'],'not_evaluated')]),
            obligation('K-RES','共有予算から予約し未完了の値・根拠を返さない','test_budget_sweep_atomic_values_receipts_and_no_child_before_reservation',[('B02-15',row('binding_evidence'),None),('B02-16',['steps_used'],16)]),
            obligation('R5-1','内容を指定した確認とslot選択を旧採用と分離','test_hash_chain_binds_all_original_content_and_cannot_reuse_confirmation',[('N04-method',['reason_codes'],['review_record_hash_mismatch'])]),
            obligation('R5-2','保存・医学的妥当性の認定を返さない','test_ai_origin_and_confirmation_are_preserved_without_clinical_or_base_writes',[('M24',['certificate','status'],'not_certified')]),
            obligation('R5-3','計算結果を新しい臨床主張へ書き戻さない','test_ai_origin_and_confirmation_are_preserved_without_clinical_or_base_writes',[('M01',['clinical_assertions_added'],[])]),
            obligation('MB-1','数量・記録・確認の内容参照を連鎖して拘束','test_hash_chain_binds_all_original_content_and_cannot_reuse_confirmation',[('N03-unit_ref',['reason_codes'],['quantity_reference_hash_mismatch']),('N04-origin',['status'],'invalid_input')]),
            obligation('MB-2','人の確認・確定性・両記録時刻の可視性','test_all_small_revision_graphs_and_confirmation_arrivals',[('M05-before',row('reason_codes'),['no_adopted_measurement']),('M05-at',row('status'),'computed')],'finite_check'),
            obligation('MB-3','適格な訂正辺を使い、復活・最新勝ち・等値の統合をしない','test_all_small_revision_graphs_and_confirmation_arrivals',[('M11',['results',0,'binding_evidence','selected',0,'record_ref'],'C'),('M12-before',row('reason_codes'),['unresolved_measurement_conflict'])],'finite_check'),
            obligation('MB-4','不明と未指定を分け、新しい版と確認でのみ精密化','test_hand_expectations_api_cli_and_manifest',[('M33-before',row('reason_codes'),['method_unknown']),('M33-after',row('status'),'computed')],'finite_check'),
            obligation('MB-5','文脈一致を限定し医学的同等性に変換しない','test_two_slot_context_variable_and_unknown_cross_product',[('M30-version',row('reason_codes'),['different_method'])],'finite_check'),
            obligation('MB-6','共有literalでも別記録は別変数、同じ版だけ自己比較','test_record_identity_preserves_shared_domains_without_aliasing_distinct_measurements',[('M25',row('relation_set'),['less','equal','greater']),('M26',row('relation_set'),['equal'])],'finite_check'),
            obligation('MB-7','保留・訂正済みの可視の未知能力も検査しslot外は分離','test_two_slot_context_variable_and_unknown_cross_product',[('M22-pending-quantity',row('reason_codes'),['unknown_capability']),('M23-other',row('status'),'computed')],'finite_check'),
            obligation('MB-8','量の固定版・厳密演算と未対応の境界','test_native_dependency_pins_and_structural_refusals_precede_budget',[('N07-dependency',['reason_codes'],['quantity_profile_mismatch']),('M35-negative',['results',0,'converted_domain','lower'],{'numerator':-3,'denominator':2})]),
            obligation('MB-9','AI由来・未評価の不確かさを保持し確認を補わない','test_ai_origin_and_confirmation_are_preserved_without_clinical_or_base_writes',[('M07',row('reason_codes'),['no_adopted_measurement']),('M08',['uncertainty_propagated'],False)]),
            obligation('MB-10','行の先払いと子予算の予約、完成値・根拠の原子性','test_child_size_and_injected_resource_stop_have_no_partial_receipts',[('B04-16',['results',1,'assessment_complete'],False),('B03-true-20',['steps_used'],20)],'finite_check'),
            obligation('MB-11','固定snapshotの再現と旧経路の非干渉','test_input_retention_permutation_snapshot_pins_and_no_hidden_latest_state',[('M36-past',['results',0,'binding_evidence','selected',0,'record_ref'],'A'),('M36-now',['results',0,'binding_evidence','selected',0,'record_ref'],'B')],'finite_check'),
            obligation('MB-12','全体の検証・決定性・依存の識別','test_targeted_semantic_mutants_are_detected_by_their_guards',[('N02-literal-id',['status'],'invalid_input')],'finite_check')],
        'stops':{'unknown_capability':'可視の全記録・数量の能力を問うslot内で検査しunassessed',
                 'unsupported':'unsupported_profile。別の方針・scope・量仕様・context/record表現',
                 'resource':'resource_limit。先払い前に子を呼ばず、未完了行の値・根拠・diagnosticsはnull',
                 'invalid_input':'全体の構造・参照・hash・型・訂正・確認順序を予算前に検査'},
        'composition':{'shares_names_with':[],'reads_extensions':['p2-quantity-literal'],'order_dependent':False},
        'evaluation':{'examples':['examples/p2-measurement/*.json'],'tests':['tests/p2/test_measurement.py'],'budget_sweep':True,'oracle':'tests/p2/measurement_oracle.py'}}
