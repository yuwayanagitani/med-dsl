"""P2-uのR5宣言。用語の版更新を、旧版の参照ごとに、継続の有無と、名称・関係・属性の三つの面の差で監査し、後継を決めず、未宣言の属性の差を依頼にする拡張の16義務（共通4＋R5の3＋AU-1〜9）。"""
import hashlib


def audit_manifest(root):
    tests = 'tests/p2/test_audit.py::AuditTests.'
    mutants = 'test_selected_mutants_are_detected_by_reference'
    first = lambda name: name if isinstance(name, list) else [name]
    rows = [
        ('K-ID', '自己の版と実体を固定し、旧profileや他拡張の結果を代用しない', 'test_static_validation_pins_limits_and_native_refusals',
         'N02-profile_spec_sha256', ['status'], 'unsupported_profile', False, 'refusal'),
        ('K-STOP', '比較範囲の外の参照は比較せず（not_compared）、新版にない参照は後継を決めない（not_found）', 'test_continuation_is_by_source_and_id_never_by_name',
         'U11', ['results', 0, 'audit_state'], 'not_compared', False, 'boundary'),
        ('K-INV', '推測で補った情報を作らず、入力を変更せず、臨床の主張を追加しない', 'test_attribute_policy_is_declared_never_guessed',
         'U01', ['inferred_information'], [], False, 'non_conversion'),
        ('K-RES', '共通予算に従い、未完了の行に値を返さず、資源停止で認定しない', 'test_budget_sweep_keeps_finished_rows_and_has_no_partial_values',
         'B01-22', ['certificate', 'status'], 'not_certified', False, 'boundary'),
        ('R5-1', '使った宣言（差のあった属性の分類）を仮定として示す', 'test_hand_expectations_api_cli_manifest_and_obligations',
         'U02', ['results', 0, 'policy_assumptions'], ['attribute_class:code_list:administrative'], False, 'boundary'),
        ('R5-2', '保存・医学的な意味の認定を出さない', 'test_attribute_policy_is_declared_never_guessed',
         'U01', ['certificate', 'status'], 'not_certified', False, 'non_conversion'),
        ('R5-3', '薬剤の意味の同一・置換・臨床の同等を主張しない', 'test_attribute_policy_is_declared_never_guessed',
         'U01', ['converted_to_base'], False, False, 'non_conversion'),
        ('AU-1', '自己のprofileと仕様hashを固定し、呼び出し側が実体を変えられない', 'test_static_validation_pins_limits_and_native_refusals',
         'N02-profile', ['reason_codes'], ['unsupported_profile'], False, 'refusal'),
        ('AU-2', '各参照がちょうど一つの状態に入り、状態別の数の和は参照の数に等しい', ['test_enumeration_of_differences_against_the_oracle', 'test_random_requests_against_the_oracle', mutants],
         'U25', ['summary', 'by_state'],
         {'unchanged_in_scope': 1, 'changed_administrative_only': 1, 'changed': 1, 'needs_information': 1, 'not_found': 1, 'not_compared': 1}, True, 'boundary'),
        ('AU-3', '継続は (出典, id) だけで決まり、新版にない参照の後継を決めず、候補も出さない', ['test_continuation_is_by_source_and_id_never_by_name', mutants],
         'U10', ['results', 0, 'successor'], 'not_determined', True, 'non_conversion'),
        ('AU-4', '名称・関係・属性を別の面として比べ、全ての面に差がないときだけ「比較した範囲で差なし」と言う',
         ['test_enumeration_of_differences_against_the_oracle', 'test_input_order_never_matters_and_the_input_is_not_changed', mutants],
         'U05', ['results', 0, 'facets', 'attributes', 'state'], 'unchanged', True, 'boundary'),
        ('AU-5', '属性の分類は宣言だけで決め、未宣言の差は依頼にして分類せず、使われなかった宣言は痕跡を残さない', ['test_attribute_policy_is_declared_never_guessed', mutants],
         'U04', ['results', 0, 'audit_state'], 'needs_information', True, 'non_conversion'),
        ('AU-6', '関係は与えられた向きのまま比べ、対象が各版に存在するかと、新版で未解決かを区別する', ['test_swapping_the_versions_swaps_the_differences_and_infers_nothing', mutants],
         'U07', ['results', 0, 'facets', 'relations', 'removed'], [{'kind': 'has_ingredient', 'target': 'c9', 'target_in_from': True, 'target_in_to': False}], True, 'boundary'),
        ('AU-7', '比較範囲（出典・面・比較していないもの）を明示し、集計は範囲内の継続・旧のみ・新のみを分ける', ['test_random_requests_against_the_oracle', mutants],
         'U11', ['summary', 'in_scope_from'], 4, True, 'boundary'),
        ('AU-8', '料金を参照ごとに先払いし、最後の確定1を払うまで集計を返さず、未完了の行は値を持たない',
         ['test_the_cost_formula_is_exact_and_prepaid_per_reference', 'test_budget_sweep_keeps_finished_rows_and_has_no_partial_values', mutants],
         'U25', ['steps_used'], 45, True, 'boundary'),
        ('AU-9', '逆向きの成立・後継・意味を推定しない', ['test_swapping_the_versions_swaps_the_differences_and_infers_nothing', 'test_continuation_is_by_source_and_id_never_by_name'],
         'U01', ['reverse_inferred'], False, False, 'non_conversion')]
    obligations = [{'id': ident, 'statement': text, 'evidence': 'finite_check' if finite else 'checked_native_template',
                    'checks': [tests+name for name in first(test)],
                    'guards': [{'example': 'examples/p2-audit/'+example.lower()+'.json', 'path': path, 'equals': value, 'kind': kind}]}
                   for ident, text, test, example, path, value, finite, kind in rows]
    return {'schema_version': 'p2-extension-manifest-draft-2', 'id': 'p2-terminology-audit', 'version': 'draft-1',
            'title': '用語の版更新を、旧版の参照ごとの継続と、名称・関係・属性の三つの面の差で監査し、後継を決めず、未宣言の属性の差を依頼にする',
            'status': {'review_state': 'author_draft', 'independent_review': False}, 'class': 'R5',
            'spec': {'path': 'src/med_dsl/terminology_audit_spec.json', 'sha256': hashlib.sha256((root/'src/med_dsl/terminology_audit_spec.json').read_bytes()).hexdigest()},
            'contract_doc': 'docs/research/82-p2-u-design.md', 'implementation': {'modules': ['src/med_dsl/terminology_audit.py']},
            'pins': [{'path': 'src/med_dsl/host.py', 'role': 'dispatcher'}, {'path': 'docs/research/83-p2-u-cases.md', 'role': 'hand_specified_expectations'}],
            'embedded_in': ['src/med_dsl/terminology_audit_spec.json', 'examples/p2-audit/*.json'],
            'depends_on': [{'id': 'p0-positive', 'version': 'draft-2'}],
            'owns': {'operations': ['run_terminology_audit'], 'schema_versions': ['p2-audit-request-draft-1', 'p2-audit-result-draft-1'],
                     'profiles': ['p2-terminology-audit-draft-1'], 'answer_kinds': ['terminology_version_audit'], 'predicates': [],
                     'capabilities': ['p2-terminology-audit-draft-1']},
            'scope': {'base_requests': '旧要求と他のP2拡張を変えず、旧版と新版の正規化したsnapshotだけを入力とする',
                      'fragment': '旧版の参照ごとの継続（(出典, id)）と、名称（原子）・関係・属性（原子に付く）の差。属性の分類は宣言。後継・廃止・置換・薬剤の意味・原子間の関係・抑制・履歴は範囲外。一方向（旧→新）'},
            'obligations': obligations,
            'stops': {'unknown_capability': '比較範囲の外の出典は比較せず not_compared と明示する',
                      'unsupported': 'unsupported_profile。許容外の属性の分類・別の用語の組を補完しない',
                      'resource': 'resource_limit。未完了の七欄は全てnull、集計はnull、完成料金前は認定なし',
                      'invalid_input': 'snapshot・方針・参照の形を予算前に検査'},
            'composition': {'shares_names_with': [], 'reads_extensions': [], 'order_dependent': False},
            'evaluation': {'examples': ['examples/p2-audit/*.json'], 'tests': ['tests/p2/test_audit.py'], 'budget_sweep': True, 'oracle': 'tests/p2/audit_oracle.py'}}
