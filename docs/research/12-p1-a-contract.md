# P1-a：有限予測の実行契約

作成日：2026-10-18。実装前に具体化した作成者草案です。[P1 の研究契約](11-p1-contract.md) を、`query_forecast` に限定して実行します。事象化・引き継ぎ認定・臨床的妥当性の検査は含みません。設計用の `examples/p1` は変更せず、実行例を `examples/p1-a` に置きます。

## 識別と入出力

native profile は `p1-finite-forecast-draft-1`、request/result は `p1-request-draft-1` / `p1-result-draft-1` です。[機械可読仕様](../../src/med_dsl/forecast_spec.json) の生バイト SHA-256 を handler に固定し、実行時の仕様実体と照合します。仕様の記述だけで正しさを認定するものではありません。改訂時は版・固定ハッシュ・実装・検証を一緒に改訂します。

request の必須フィールドは次の通りです。未知のフィールドは拒否します。

| フィールド | 内容 |
| --- | --- |
| schema_version / operation | 上記 request schema / `query_forecast` |
| consumer | `profile`, `profile_spec_sha256`, `operations`。既知の native profile と固定ハッシュを照合し、操作一覧に今回の操作が含まれることを要求 |
| artifacts | `{artifact,sha256}` の配列。artifact は P1 設計の ref/profile/profile_spec_sha256/subject_ref/context_ref/interval/model_ref/sample_space_ref/worlds/events。sha256 は既存の canonical JSON 関数による実体ハッシュ |
| report_snapshot | `kind=forecast_reports`, `contexts`, `ledger`。台帳・主張・確認は P0 と同じ形。文脈の purpose は `fiction:forecast-reporting@1` |
| views | P0 と同じ id/as_of/policy_ref。最大64 |
| queries | id/forecast_ref/all_of。一問は一 artifact 内の1〜8事象。別 artifact の事象は参照解決できず、同じ事象名があっても選んだ artifact 内だけで解釈 |
| budget | `max_steps`、厳密な整数0〜100000 |

artifacts/worlds/events/queries/views は空不可です。空の事象の world_refs は許可します。参照は各集合内で一意。report_snapshot の主張は固定の二項述語 `fiction:forecast_reported@1` だけで、args は subject/artifact。原主張・未確認主張も含め subject/context を artifact・文脈定義と一致させます。P0 の検証を再利用し、任意の定義規則や外部 package を受け付けません。臨床 snapshot を入力する欄や更新命令はありません。台帳参照は根拠のスコープであり、別リクエストとの大域的な名前の所有権までは検査しません。

P0 の採用方針を再利用します。confirmed の主張と別の human review が view の時点までに存在して初めて採用し、採用された訂正の置換元を除外します。AI 生成でも条件を緩めません。同じ文脈で可視な主張の required_capabilities を全件確認し、pending・superseded の未知修飾も無視しません。処理系が認識する能力は P0 と固定した有限予測だけです。consumer の自己申告で未知能力を許可しません。

## 状態と根拠

root の status は ok/invalid_input/unsupported_profile/resource_limit。正常処理内の各結果には view_id/query_id/status/answer/reason_codes/evidence/information_requests を持ちます。

| 結果 | 条件 |
| --- | --- |
| computed | 採用済み肯定報告があり、同じ文脈に未知能力や未解消の衝突がなく、計算が完了 |
| undetermined | 肯定・否定いずれも未採用。answer=null、報告・確認の情報要求 |
| opposed | 採用済み否定報告だけが存在。予測事象の否定や確率0へは変換しない |
| conflict | 文脈内の同じ報告 atom に採用済み肯定・否定が共存。双方の根拠を保持 |
| unassessed | 文脈内の未知能力または共通予算不足。answer=null、阻害主張・能力または打切り理由 |

computed の answer は `kind=forecast_probability`、約分した probability、subject_ref/context_ref/interval/model_ref/sample_space_ref/forecast_ref/artifact_sha256/event_refs。evidence は台帳参照・snapshot hash・assertion/review 参照を持ちます。元の artifact と全履歴は入力に保持し、出力の input_sha256 と report_snapshot_sha256 で固定します。出力に原情報の複製を作らず、原入力を併せて保存する運用です。数値1もこの型の予測です。出力は臨床 assertion や supported 回答を生成しません。

未知 profile・未対応操作は unsupported_profile。既知仕様の実体不一致、consumer/artifact のハッシュ不一致は invalid_input。自己申告の read_only フィールドは unknown_field。unknown capability は数値を返さず、既存 P0 の停止規則も維持します。

## 有理数と資源

整数の bool・浮動小数を拒否し、0≤分子≤分母・分母>0 を要求します。入力の各整数は63 bit、丸め前の積・和を含む中間整数は4096 bitまで。超過は resource_limit。全世界の和は厳密に1、違えば invalid_input。連言は集合の積から重みを加算します。独立性・平均・期間の合併は導入しません。

1 MiB・深さ64、各64 artifact/query/view/world/event、1000 context/assertion/review の上限は機械可読仕様に固定します。構造・参照・ハッシュ・整数範囲を先に全件検証し、その後の有理数の総和検査も共通 steps を消費します。従って予算0では、構造が妥当でも総和の正当性は未評価です。入力不正を予算不足で正常化しません。

課金は仕様の steps と同じで、request 開始1、artifact ごと ref 順に世界の加算各1と総和比較1、view ごと id 順に台帳の各主張・確認各1を前払い、query ごと id 順に開始1、世界×連言事象の全所属検査各1、積集合の各世界の加算1、数値回答の確定1です。世界・事象も ref 順。所属検査は短絡せず、零重みも数えます。構造・ハッシュ検査は steps 外ですが入力サイズ等で制限します。

予算が尽きた一問の部分値は返しません。完了済みの別の回答は保持し、残りは unassessed/null、root は resource_limit、steps_used と incomplete を返します。総和検査・view 選択前の打切りでも全ての未完了 query/view を明示します。実行完了の保証と意味の保存は別です。

## 検証範囲

H01〜H06・H20 の実行例・必須パスは処理系の出力から生成せず、期待する有理数・採用状態・停止理由を指定します。作成者草案との一致で、独立レビュー・全20件・臨床評価の完了とはしません。P0 の37例も別の分母で回帰照合します。実行記録は後続の結果文書に残します。

## p0-draft-2 での追補（レビュー AI-001）

- `incomplete` は、打切りで未完了になった行だけでなく、未知能力で `unassessed` になった行も列挙する（P0 の query・P1-b と同じ。形式は `{view_id, query_id}`）。conflict・undetermined・opposed の行は列挙しない。
- 「中間整数は4096 bitまで」は、入力上限（各整数63 bit、世界64）の下では約4033 bitを超えないため**到達しない防御**である。到達しないことは `tests/review/test_boundaries.py` が最大の入力で確認する（超過の負例は作れない）。
