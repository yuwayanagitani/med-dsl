"""P2-fのR2宣言。単位・量の種類は仕様hashの内部名で、述語として所有しない。"""
import hashlib


def quantity_manifest(root):
    def obligation(ident,text,test,guards,evidence='checked_native_template'):
        return {'id':ident,'statement':text,'evidence':evidence,
                'checks':['tests/p2/test_quantity.py::QuantityTests.'+test],
                'guards':[{'example':'examples/p2-quantity/'+name.lower()+'.json','path':path,'equals':value,'kind':'boundary'}
                          for name,path,value in guards]}
    row=lambda field:['results',0,field]
    return {
        'schema_version':'p2-extension-manifest-draft-1','id':'p2-quantity-literal','version':'draft-1',
        'title':'量リテラルの厳密換算と有限区間比較','status':{'review_state':'author_draft','independent_review':False},'class':'R2',
        'spec':{'path':'src/med_dsl/quantity_spec.json','sha256':hashlib.sha256((root/'src/med_dsl/quantity_spec.json').read_bytes()).hexdigest()},
        'contract_doc':'docs/research/34-p2-f-design.md','implementation':{'modules':['src/med_dsl/quantity.py']},
        'pins':[{'path':'src/med_dsl/host.py','role':'dispatcher'},{'path':'docs/research/35-p2-f-cases.md','role':'hand_specified_expectations'}],
        'embedded_in':['examples/p2-quantity/*.json'],'depends_on':[{'id':'p0-positive','version':'draft-2'}],
        'owns':{'operations':['evaluate_quantities'],'schema_versions':['p2-quantity-request-draft-1','p2-quantity-result-draft-1'],
                'profiles':['p2-quantity-literal-draft-1'],'answer_kinds':['quantity_literal_result'],'predicates':[],'capabilities':['p2-quantity-literal-draft-1']},
        'scope':{'base_requests':'旧要求は旧経路に保持。量の値・区間関係を基底の支持へ変換しない',
                 'fragment':'架空の固定7単位・5量種。正の倍率、有理数、有限非空区間。臨床状態の読み書きなし。R2-3は基底を読まない範囲で空虚に満たす'},
        'obligations':[
            obligation('K-ID','仕様hash、profile、操作を固定して照合する','test_native_identity_and_integer_bounds',[('N10-hash',['status'],'unsupported_profile')]),
            obligation('K-STOP','未知能力・未知単位・未知量種、不正と未対応を区別する','test_unknowns_priority_unused_literals_and_same_reference',[('Q21',row('reason_codes'),['unknown_unit']),('Q23',row('reason_codes'),['unknown_capability'])]),
            obligation('K-INV','入力・出自・未評価の不確かさを保ち、臨床情報を補わない','test_input_immutability_array_permutation_and_origin_retention',[('Q24',['clinical_confirmation'],'not_evaluated')]),
            obligation('K-RES','共有予算の途中では値と完成根拠を出さない','test_budget_sweep_atomic_rows_and_exact_costs',[('B01',['steps_used'],0),('B04-8',['results',1,'calculation_evidence'],None)]),
            obligation('R2-1','基底に書かず、原情報を変更しない','test_input_immutability_array_permutation_and_origin_retention',[('Q24',['clinical_assertions_added'],[])]),
            obligation('R2-2','計算の結論を基底の状態として返さない','test_no_clinical_or_base_promotion_and_no_base_reads',[('Q09',['converted_to_base'],False)]),
            obligation('R2-3','基底を全く読まない断片であり、採用選択を迂回した読みもない。この断片を超えた保証はしない','test_no_clinical_or_base_promotion_and_no_base_reads',[('Q24',row('status'),'computed')]),
            obligation('R2-4','回答型を分離し、数値の一致を医学的同一性にしない','test_no_clinical_or_base_promotion_and_no_base_reads',[('Q09',['meaning_mode'],'quantity_literal_result')]),
            obligation('R2-5','理解できる能力を固定し、自己申告と外部単位表を採用しない','test_hand_expectations_api_cli_and_manifest',[('N07-units',['status'],'invalid_input'),('Q23',row('converted_domain'),None)]),
            obligation('QT-1','局所名の範囲を仕様に固定し大小文字を補完しない','test_unknowns_priority_unused_literals_and_same_reference',[('Q21',row('certain_relation'),None)]),
            obligation('QT-2','負数・未約分の入力を保持し、浮動小数点化せず計算する','test_exact_conversion_and_roundtrip_for_each_compatible_unit',[('Q06',row('converted_domain'),{'lower':{'numerator':-3,'denominator':2},'upper':{'numerator':-3,'denominator':2},'lower_closed':True,'upper_closed':True})],'finite_check'),
            obligation('QT-3','正の倍率の換算は境界の開閉を保存し、入力範囲内の往復は厳密','test_exact_conversion_and_roundtrip_for_each_compatible_unit',[('Q07',['results',0,'converted_domain','lower_closed'],False)],'finite_check'),
            obligation('QT-4','区間は代表値へ潰さず、同一参照だけ一変数とする','test_finite_domain_relations_against_witness_points',[('Q15',row('relation_set'),['less','equal','greater']),('Q16',row('relation_set'),['equal'])],'finite_check'),
            obligation('QT-5','次元と量種の不一致を比較不能として別々に返す','test_hand_expectations_api_cli_and_manifest',[('Q18',row('reason_codes'),['incompatible_quantity_kind']),('Q19',row('reason_codes'),['incompatible_dimension'])],'finite_check'),
            obligation('QT-6','統計的不確かさ・丸め・臨床採用を未実装として区別する','test_hand_expectations_api_cli_and_manifest',[('N09-uncertainty',['status'],'unsupported_profile'),('Q24',['uncertainty_propagated'],False)],'finite_check'),
            obligation('QT-7','未知・静的上限・打切りで完成値を漏らさない','test_structural_refusals_precede_budget',[('N02-n',['reason_codes'],['rational_integer_limit']),('B02-7',row('converted_domain'),None)],'finite_check'),
            obligation('QT-8','旧経路の非干渉、決定性と意味の変異の検出を検査する','test_each_targeted_semantic_mutant_is_detected',[('Q24',['certificate','status'],'not_certified')],'finite_check')],
        'stops':{'unknown_capability':'参照する量の未知能力を最優先してunassessed',
                 'unsupported':'unsupported_profile。未知の演算種・不確かさ・量表現・消費側仕様',
                 'resource':'resource_limit。63bit入力上限・256bit中間上限・共有steps。未完了行はnull',
                 'invalid_input':'構造・参照・分母・区間・既知入力の次元矛盾を予算の前に検証'},
        'composition':{'shares_names_with':[],'reads_extensions':[],'order_dependent':False},
        'evaluation':{'examples':['examples/p2-quantity/*.json'],'tests':['tests/p2/test_quantity.py'],'budget_sweep':True,'oracle':'tests/p2/quantity_oracle.py'}}
