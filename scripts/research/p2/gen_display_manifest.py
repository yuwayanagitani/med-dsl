"""P2-hのR4宣言：表示への因子化と別添えを分ける19義務。"""
import hashlib


def display_manifest(root):
    def obligation(ident,text,test,guards,finite=False):
        return {'id':ident,'statement':text,'evidence':'finite_check' if finite else 'checked_native_template',
                'checks':['tests/p2/test_display.py::DisplayTests.'+test],
                'guards':[{'example':'examples/p2-display/'+name.lower()+'.json','path':path,'equals':value,'kind':'boundary'} for name,path,value in guards]}
    r=lambda key:['results',0,key]
    return {'schema_version':'p2-extension-manifest-draft-2','id':'p2-quantity-display','version':'draft-2',
        'title':'厳密な測定値と型付き表示の射影、問いの因子化と別添えの分離',
        'status':{'review_state':'author_draft','independent_review':False},'class':'R4',
        'spec':{'path':'src/med_dsl/display_spec.json','sha256':hashlib.sha256((root/'src/med_dsl/display_spec.json').read_bytes()).hexdigest()},
        'contract_doc':'docs/research/40-p2-h-design.md','implementation':{'modules':['src/med_dsl/display.py']},
        'pins':[{'path':'src/med_dsl/host.py','role':'dispatcher'},{'path':'docs/research/41-p2-h-cases.md','role':'hand_specified_expectations'},
                {'path':'src/med_dsl/measurement_spec.json','role':'measurement_native_spec'},{'path':'src/med_dsl/quantity_spec.json','role':'quantity_native_spec'}],
        'embedded_in':['src/med_dsl/display_spec.json','src/med_dsl/measurement_spec.json','src/med_dsl/measurement.py','src/med_dsl/quantity.py',
                       'examples/p2-display/*.json','examples/p2-measurement/*.json','examples/p2-quantity/*.json'],
        'depends_on':[{'id':'p0-positive','version':'draft-2'},{'id':'p2-quantity-literal','version':'draft-2'},{'id':'p2-measurement-binding','version':'draft-2'}],
        'owns':{'operations':['project_measurement_displays'],'schema_versions':['p2-display-request-draft-1','p2-display-result-draft-1','p2-display-artifact-draft-1'],
                'profiles':['p2-quantity-display-draft-1'],'answer_kinds':['measurement_display_projection'],'predicates':[],'capabilities':['p2-quantity-display-draft-1']},
        'scope':{'base_requests':'旧経路を変更せず、P2-gの一点convert結果を読む',
                 'fragment':'型付きartifactだけに因子化するdisplay_textとセル上で一定のthreshold。exact_valueは初回テンプレート外。出所・原値・別添えをartifactの保証へ含めない'},
        'obligations':[
            obligation('K-ID','自己・測定・量の仕様とpolicyを照合','test_native_pins_static_limits_and_refusals_precede_budget',[('N07-measurement_profile_spec_sha256',['reason_codes'],['measurement_profile_mismatch'])]),
            obligation('K-STOP','不正・未対応・未知・非単一点と予算を分離','test_hand_expectations_api_cli_manifest_and_obligations',[('P15',r('reason_codes'),['unsupported_display_domain']),('N08-compare',['status'],'unsupported_profile')]),
            obligation('K-INV','AI出自・臨床未評価と原情報の境界を保持','test_ai_origin_confirmation_and_no_clinical_writes',[('P19-reviewed',['clinical_assertions_added'],[]),('P36',['uncertainty_propagated'],False)]),
            obligation('K-RES','子と表示と最終確定を共通予算から先払い','test_budget_prepaid_child_rows_completion_and_exact_values',[('B01-16',r('artifact'),None),('B02-27',['certificate','status'],'not_certified')]),
            obligation('R4-1','セルで一定の問いだけを表示の保存範囲へ入れる','test_finite_threshold_questions_against_cell_witnesses',[('P26-none',r('question_results')+[0,'status'],'out_of_scope')],True),
            obligation('R4-2','同一artifactでも原回答が異なる受理可能な反例を保持','test_collision_encoding_typed_artifacts_and_scope',[('P28',r('question_results')+[0,'source_answer','answer'],False),('P28',['results',1,'question_results',0,'source_answer','answer'],True)],True),
            obligation('R4-3','符号化・別添えで射影の全体保存を認定しない','test_collision_encoding_typed_artifacts_and_scope',[('P29',['certificate','status'],'not_certified'),('P30',r('projection_evidence')+['artifact_encoding','roundtrip_matches'],True)]),
            obligation('DP-1','表示と双方の依存仕様・量の型・局所単位を固定','test_hand_expectations_api_cli_manifest_and_obligations',[('P33-unit',['results',1,'artifact','unit_ref'],'u_ten')]),
            obligation('DP-2','正確な直接丸め、負数、半整数、大数','test_finite_rounding_and_formatting_against_nearest_distance',[('P03',r('artifact')+['text'],'1.2'),('P11',r('artifact')+['text'],'9007199254740993')],True),
            obligation('DP-3','末尾零・負の零・表示の変更を原値と分離','test_seeded_fractions_and_units_keep_source_answers_separate',[('P07-negative',r('artifact')+['text'],'0.0'),('P09',r('artifact')+['text'],'0.50')],True),
            obligation('DP-4','セルの端点と開閉を厳密に扱う','test_finite_threshold_questions_against_cell_witnesses',[('P23-lt-1',r('question_results')+[0,'projection_answer'],None),('P24-lt-1',r('question_results')+[0,'projection_answer'],True)],True),
            obligation('DP-5','原値での偶然の正答と因子化を分ける','test_collision_encoding_typed_artifacts_and_scope',[('P26-none',['certificate','status'],'not_certified'),('P22',r('question_results')+[2,'projection_answer'],False)],True),
            obligation('DP-6','同じ表示・原回答相違・符号化・追加情報を分離','test_collision_encoding_typed_artifacts_and_scope',[('P25-source_bundle',r('question_results')+[0,'status'],'out_of_scope'),('P27',['additional_source_used'],False)],True),
            obligation('DP-7','全計画料金と子の実費を照合し一度だけ予約する','test_cost_planning_with_histories_matches_paid_child_execution',[('B03-none-38',['steps_used'],38),('N11-large-plan',['status'],'resource_limit')],True),
            obligation('DP-8','未完了の値・根拠を返さず、最終料金まで認定しない','test_child_and_row_resource_stops_do_not_salvage_partial_values',[('B02-26',r('question_results'),None),('B02-27',['incomplete'],[{'stage':'completion','reason_codes':['step_limit']}])]),
            obligation('DP-9','全計画の参照とP2-gの確認・未知・競合を尊重','test_native_pins_static_limits_and_refusals_precede_budget',[('N03-future-quantity',['reason_codes'],['quantity_reference_hash_mismatch']),('P20',r('reason_codes'),['unresolved_measurement_conflict'])]),
            obligation('DP-10','AI出自を消さず臨床主張へ書き戻さない','test_ai_origin_confirmation_and_no_clinical_writes',[('P19-pending',r('artifact'),None),('P19-reviewed',['clinical_confirmation'],'not_evaluated')]),
            obligation('DP-11','順序・snapshot・精度の変更を原情報と分け再現','test_retention_hashes_order_snapshot_and_precision_are_separate',[('P34-now',r('projection_evidence')+['selected',0,'record_ref'],'B'),('P32',['results',1,'artifact','text'],'1.3')],True),
            obligation('DP-12','非単一点・未知・静的上限・資源を誠実に停止','test_checker_detects_early_values_empty_containers_and_certificate',[('P21-display',r('reason_codes'),['unknown_capability']),('N10-questions',['status'],'resource_limit')])],
        'stops':{'unknown_capability':'表示自身の未知能力を先に検査し、P2-gの未知・競合も停止として保持',
                 'unsupported':'unsupported_profile。別policy/依存/schema/質問・compare。非単一点は行のunassessed',
                 'resource':'resource_limit。子の部分結果を拾わず、未完了行は空配列を含め全値null。最終料金不足でも認定なし',
                 'invalid_input':'全計画の型・参照・hash・確認・訂正・表示指定を予算前に検証'},
        'composition':{'shares_names_with':[],'reads_extensions':['p2-measurement-binding','p2-quantity-literal'],'order_dependent':False},
        'evaluation':{'examples':['examples/p2-display/*.json'],'tests':['tests/p2/test_display.py'],'budget_sweep':True,'oracle':'tests/p2/display_oracle.py'}}
