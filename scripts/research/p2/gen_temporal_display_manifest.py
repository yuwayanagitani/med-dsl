"""P2-jのR4宣言。数値表示の保存と期間・原回答の境界の19義務。"""
import hashlib


def temporal_display_manifest(root):
    rows=[
        ('K-ID','自己・期間量・量の仕様を固定','test_static_validation_hashes_pins_limits_and_native_refusals','N07-temporal_measurement_profile_spec_sha256',['reason_codes'],['temporal_measurement_profile_mismatch'],False),
        ('K-STOP','未知・非単一点・不正・資源を区別','test_semantic_stops_do_not_answer_metadata_or_expose_values','J09',['results',0,'reason_codes'],['unsupported_display_domain'],False),
        ('K-INV','AI由来・原情報と臨床未評価を保持','test_ai_origin_and_old_profiles_are_separate','J19-reviewed',['clinical_assertions_added'],[],False),
        ('K-RES','全子計画・表示・完成を先払い','test_budget_child_rows_and_final_fee','B01-27',['certificate','status'],'not_certified',False),
        ('R4-1','全セルで一定の問いだけを認定','test_finite_thresholds_against_witnesses','J24',['results',0,'question_results',2,'projection_answer'],False,True),
        ('R4-2','同一artifactと原回答の相違を受理可能な反例にする','test_actual_artifact_collisions_do_not_restore_source','J25-source_bundle',['results',1,'question_results',0,'source_answer','answer'],True,True),
        ('R4-3','符号化と別添えで認定範囲を広げない','test_provenance_retention_encoding_and_seven_questions','J35-source_bundle',['certificate','status'],'not_certified',False),
        ('TD-1','自己/I/量の版・実体と新artifact型を固定','test_static_validation_hashes_pins_limits_and_native_refusals','N07-profile_spec_sha256',['status'],'unsupported_profile',False),
        ('TD-2','計画を再実行し確認・G/Hの偽装をしない','test_ai_origin_and_old_profiles_are_separate','N09-child-budget',['status'],'invalid_input',False),
        ('TD-3','二時点・半開境界・局所訂正・非復活を保持','test_confirmation_delays_revisions_and_context_against_subtraction','J15',['results',0,'projection_evidence','revision_evidence',0,'record_ref'],'B',True),
        ('TD-4','全可視slotの未知能力・期間・文脈を保持','test_seeded_quantities_units_unknowns_and_intervals','J21-masked',['results',0,'reason_codes'],['unknown_capability'],True),
        ('TD-5','単一点だけを厳密に丸め区間を潰さない','test_finite_rounding_against_nearest_distance','J04',['results',0,'artifact','text'],'1.3',True),
        ('TD-6','セルで一定の問いと原値での偶然の回答を分離','test_finite_thresholds_against_witnesses','J24-13-0-gt',['results',0,'question_results',0,'projection_answer'],True,True),
        ('TD-7','原値・記録・両時点・期間の問いの入力族と範囲を明示','test_actual_artifact_collisions_do_not_restore_source','J29-9-source_bundle',['results',0,'question_results',0,'status'],'out_of_scope',True),
        ('TD-8','元の確認・両origin・訂正根拠・原入力を保持','test_provenance_retention_encoding_and_seven_questions','J19-reviewed',['clinical_confirmation'],'not_evaluated',False),
        ('TD-9','別添え・符号化・artifactの区別を認定へ反映','test_provenance_retention_encoding_and_seven_questions','J32-source_bundle',['additional_source_used'],False,True),
        ('TD-10','全計画C・実費・一度の呼出・共通予算を照合','test_full_plan_cost_funded_once_without_unreferenced_row_leak','J23-method',['steps_used'],42,True),
        ('TD-11','原子性・最後の完成・子の部分結果を拾わない停止','test_child_partial_and_later_row_resource_failure_are_atomic','B02-36',['results',1,'question_results'],None,False),
        ('TD-12','旧観測・順序・snapshot・変更波及を検査','test_order_hashes_snapshot_future_and_precision','J30',['results',0,'projection_evidence','selected',0,'record_ref'],'A',True)]
    obligations=[{'id':ident,'statement':text,'evidence':'finite_check' if finite else 'checked_native_template',
        'checks':['tests/p2/test_temporal_display.py::TemporalDisplayTests.'+test],
        'guards':[{'example':'examples/p2-temporal-display/'+name.lower()+'.json','path':path,'equals':value,'kind':'boundary'}]} for ident,text,test,name,path,value,finite in rows]
    return {'schema_version':'p2-extension-manifest-draft-2','id':'p2-temporal-display','version':'draft-2',
        'title':'期間付き数量計画の丸め表示と、原値・記録・時点・期間の保存境界',
        'status':{'review_state':'author_draft','independent_review':False},'class':'R4',
        'spec':{'path':'src/med_dsl/temporal_display_spec.json','sha256':hashlib.sha256((root/'src/med_dsl/temporal_display_spec.json').read_bytes()).hexdigest()},
        'contract_doc':'docs/research/46-p2-j-design.md','implementation':{'modules':['src/med_dsl/temporal_display.py']},
        'pins':[{'path':'src/med_dsl/host.py','role':'dispatcher'},{'path':'docs/research/47-p2-j-cases.md','role':'hand_specified_expectations'},
                {'path':'src/med_dsl/temporal_measurement_spec.json','role':'temporal_measurement_native_spec'},{'path':'src/med_dsl/quantity_spec.json','role':'quantity_native_spec'}],
        'embedded_in':['src/med_dsl/temporal_display_spec.json','src/med_dsl/temporal_measurement.py','src/med_dsl/temporal_measurement_spec.json','src/med_dsl/quantity.py','examples/p2-temporal-display/*.json','examples/p2-temporal-measurement/*.json','examples/p2-quantity/*.json'],
        'depends_on':[{'id':'p0-positive','version':'draft-2'},{'id':'p2-quantity-literal','version':'draft-2'},{'id':'p2-temporal-measurement','version':'draft-2'}],
        'owns':{'operations':['project_temporal_measurement_displays'],'schema_versions':['p2-temporal-display-request-draft-1','p2-temporal-display-result-draft-1','p2-temporal-display-artifact-draft-1'],
                'profiles':['p2-temporal-display-draft-1'],'answer_kinds':['temporal_measurement_display_projection'],'predicates':[],'capabilities':['p2-temporal-display-draft-1']},
        'scope':{'base_requests':'旧要求とG/Hを変えずIの原計画を再実行',
                 'fragment':'閉じた単一点の型付き表示、全実数セルで一定の問い。原値・記録・両時点・期間は初回テンプレート外。時点固定族の普遍的喪失証明ではない'},
        'obligations':obligations,
        'stops':{'unknown_capability':'表示自身を先に検査し、Iの未知能力も停止として保持',
                 'unsupported':'unsupported_profile。別意味・旧schema・未知質問等を補完しない',
                 'resource':'resource_limit。未完了六値は全てnull、完成料金前は認定なし、子の部分結果は使わない',
                 'invalid_input':'全計画の型・参照・hash・確認と表示指定を予算前に検査'},
        'composition':{'shares_names_with':[],'reads_extensions':['p2-temporal-measurement','p2-quantity-literal'],'order_dependent':False},
        'evaluation':{'examples':['examples/p2-temporal-display/*.json'],'tests':['tests/p2/test_temporal_display.py'],'budget_sweep':True,'oracle':'tests/p2/temporal_display_oracle.py'}}
