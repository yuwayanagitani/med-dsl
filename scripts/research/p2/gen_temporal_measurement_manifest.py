"""P2-iのR5宣言。新しい確認対象・部分訂正・換算の19義務。"""
import hashlib


def temporal_measurement_manifest(root):
    rows=[
        ('K-ID','自己・量の固定版とnative実体を照合','test_static_limits_native_pins_and_schema_fuzz_before_budget','N09-profile_spec_sha256',['status'],'unsupported_profile',False),
        ('K-STOP','能力・期間不足・競合・不正・未対応を分離','test_unknown_period_and_capability_priority_is_not_context_inference','C15-record-outside',['results',0,'reason_codes'],['unknown_capability'],False),
        ('K-INV','原情報と両AI出自を保持し臨床認定をしない','test_old_routes_instant_display_boundary_and_ai_origin','C21-reviewed',['clinical_confirmation'],'not_evaluated',False),
        ('K-RES','行全体の先払いと子予算8','test_budget_atomic_rows_and_funded_child_once','B01-15',['results',0,'binding_evidence'],None,False),
        ('R5-1','新期間主張と内容指定確認を旧方針から分離','test_content_hashes_bind_period_context_quantity_and_dependency','C29-old-hash',['reason_codes'],['review_record_hash_mismatch'],False),
        ('R5-2','数値や期間の保存認定を返さない','test_old_routes_instant_display_boundary_and_ai_origin','C32',['certificate','status'],'not_certified',False),
        ('R5-3','新しい臨床主張へ書き戻さない','test_old_routes_instant_display_boundary_and_ai_origin','C01',['clinical_assertions_added'],[],False),
        ('TM-1','瞬間・集計を期間へ補完しない','test_old_routes_instant_display_boundary_and_ai_origin','C28-instant',['status'],'unsupported_profile',False),
        ('TM-2','両時点と確認の可視性、未来非干渉','test_all_confirmation_delays_and_suspected_states','C03-before',['results',0,'reason_codes'],['no_adopted_measurement'],True),
        ('TM-3','半開境界・包含・訂正範囲外の保持','test_finite_contained_dags_against_interval_subtraction','C06-6',['results',0,'binding_evidence','selected',0,'record_ref'],'A',True),
        ('TM-4','全適格辺を使い非復活・非推移・競合を保つ','test_revision_evidence_contains_masked_revisers_and_visible_reviews','C08-5',['results',0,'diagnostics','masked_records'],['A','B'],True),
        ('TM-5','未知期間と能力・slot範囲の停止順','test_seeded_histories_unknowns_and_slot_scope','C14-reviewed',['results',0,'reason_codes'],['validity_unknown'],True),
        ('TM-6','期間・文脈・量の内容hashを確認へ拘束','test_content_hashes_bind_period_context_quantity_and_dependency','N03-record-validity',['reason_codes'],['review_record_hash_mismatch'],False),
        ('TM-7','領域と期間を分離し正確な換算を行う','test_seeded_exact_quantities_and_interval_domains','C22-third',['results',0,'converted_domain','lower'],{'numerator':2,'denominator':3},True),
        ('TM-8','原順序・出自・両時点・訂正根拠を保持','test_permutations_raw_retention_and_snapshot_replay','C27-past',['results',0,'binding_evidence','selected',0,'record_ref'],'A',True),
        ('TM-9','子を支払済み予算で一度だけ呼ぶ','test_budget_atomic_rows_and_funded_child_once','B03-true-34',['steps_used'],34,True),
        ('TM-10','未完成の値・完成根拠・診断はnull','test_child_resource_stop_discards_partial_values_and_receipts','B02-26',['results',1,'diagnostics'],None,True),
        ('TM-11','表示の保存・時間解釈・医学的認定を分離','test_old_routes_instant_display_boundary_and_ai_origin','N08-display',['status'],'unsupported_profile',False),
        ('TM-12','全体の構造検証と旧経路の非干渉・決定性','test_selected_semantic_mutants_are_detected','N08-supersedes',['status'],'invalid_input',True)]
    obligations=[{'id':ident,'statement':text,'evidence':'finite_check' if finite else 'checked_native_template',
        'checks':['tests/p2/test_temporal_measurement.py::TemporalMeasurementTests.'+test],
        'guards':[{'example':'examples/p2-temporal-measurement/'+name.lower()+'.json','path':path,'equals':value,'kind':'boundary'}]} for ident,text,test,name,path,value,finite in rows]
    return {'schema_version':'p2-extension-manifest-draft-1','id':'p2-temporal-measurement','version':'draft-2',
        'title':'明示された期間つき数量主張の内容指定確認・部分訂正と換算','status':{'review_state':'author_draft','independent_review':False},'class':'R5',
        'spec':{'path':'src/med_dsl/temporal_measurement_spec.json','sha256':hashlib.sha256((root/'src/med_dsl/temporal_measurement_spec.json').read_bytes()).hexdigest()},
        'contract_doc':'docs/research/43-p2-i-design.md','implementation':{'modules':['src/med_dsl/temporal_measurement.py']},
        'pins':[{'path':'src/med_dsl/host.py','role':'dispatcher'},{'path':'docs/research/44-p2-i-cases.md','role':'hand_specified_expectations'},
                {'path':'src/med_dsl/quantity_spec.json','role':'quantity_native_spec'}],
        'embedded_in':['src/med_dsl/temporal_measurement_spec.json','src/med_dsl/quantity.py','examples/p2-temporal-measurement/*.json','examples/p2-quantity/*.json'],
        'depends_on':[{'id':'p0-positive','version':'draft-2'},{'id':'p2-quantity-literal','version':'draft-2'}],
        'owns':{'operations':['evaluate_temporal_measurements'],'schema_versions':['p2-temporal-measurement-request-draft-1','p2-temporal-measurement-result-draft-1','p2-temporal-measurement-ledger-draft-1'],
                'profiles':['p2-temporal-measurement-draft-1'],'answer_kinds':['temporal_measurement_projection'],'predicates':[],'capabilities':['p2-temporal-measurement-draft-1']},
        'scope':{'base_requests':'旧要求の処理と観測を保持し、新しい期間主張を旧基底へ変換しない',
                 'fragment':'明示された有限期間の数量領域、一対象時点の選択、内容一致の人の確認、包含した部分訂正、convertのみ。瞬間・集計・比較・表示の自動接続なし'},
        'obligations':obligations,
        'stops':{'unknown_capability':'可視のslot内の保留・訂正済み・期間外と参照数量も検査してunassessed',
                 'unsupported':'unsupported_profile。未知期間の訂正・瞬間/集計・旧方針・別操作を補完しない',
                 'resource':'resource_limit。未完了行の値・両完成根拠・diagnosticsをnull、子の部分結果は破棄',
                 'invalid_input':'全体の型・参照・hash・訂正包含・確認順序を予算前に検査'},
        'composition':{'shares_names_with':[],'reads_extensions':['p2-quantity-literal'],'order_dependent':False},
        'evaluation':{'examples':['examples/p2-temporal-measurement/*.json'],'tests':['tests/p2/test_temporal_measurement.py'],'budget_sweep':True,'oracle':'tests/p2/temporal_measurement_oracle.py'}}
