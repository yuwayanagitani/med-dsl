# P2-q：Observation の status・code の写像と Provenance への出力の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計70](70-p2-q-design.md) の予測 X1〜X10 と反例 Z1〜Z9 に、具体的な入力と期待を与えます。期待は設計と、[監査66](66-p2-p-grounding-audit.md)・取得したページの読み取りから手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・識別子・写像の表はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。

## 0. 設計70の具体化（実装前に決めた細部）

| ID | 決定 | 理由 |
| --- | --- | --- |
| T1 | 結果の最上位に `grounding_run`＝`{input_sha256, reserved_steps, steps_used}`（P2-p の実行）を置く。P2-p の `library`・`ledger`・`temporal_measurement` はそのまま写す | P2-p が P2-o の実行を `library` に置くのと同じ形 |
| T2 | 行は P2-p の行の全欄を保ち、`observation` を足す。`needs_information` の行は、`status`＝`needs_information`、`reason_codes`＝[`required_information_missing`]、`requests`＝依頼、`output`・`flows`＝null。P2-p の `grounding` と `base_status` は変えない | 部分的な出力を渡さない（P2-o と同じ） |
| T3 | 依頼の型は `{element, action, record_ref, property_ref}`（4欄）。`code` の依頼は `property_ref` を持ち、`status` の依頼は `property_ref`＝null。宛先は出力先の宣言を作る人 | 医療者への依頼（P2-o の8欄）と別の宛先 |
| T4 | 許容外の写像の拒否の符号：`unsupported_status_mapping`、`unsupported_reviewer_type`（いずれも unsupported_profile）。`code_map` の重複は `duplicate_property_mapping`、宣言の重複は `duplicate_observation`、P2-p の対象のない出力先への宣言は `unresolved_target`（いずれも invalid_input） | 設計70の QD2・QD6・§3 |
| T5 | 子の要求の拒否は、P2-p の符号をそのまま返す（P2-p が P2-o の符号をそのまま返す） | 検査を再実装しない |
| T6 | 未完了行の値の欄は、P2-p の7欄＋`observation` の8欄 | 設計70の§7 |

## 1. 標準の入力

| 項目 | 標準 |
| --- | --- |
| grounding_request | P2-p の標準（[68 の§1](68-p2-p-cases.md)）：記録 `A`（2 `u_ten`＝20 `u_base`、期間 [day1, day10)、method・specimen は known、確定）、確認 `RA`（day3、確認者 `fiction:human:reviewer`）、出力先 `P-B1`、対象 `quantity`・[method, specimen]・期間なし、問い合わせ `q1`（day5） |
| observation | `P-B1` を指す。`status`＝`{original: final}`、`code_map`＝[{property_ref: `fiction:measurement:property:A@1`, system: `fiction:code-system:s`, code: `fiction-code-1`}]、`provenance`＝`{reviewer_type: Practitioner}` |
| 予算 | 100000。`grounding_request.budget.max_steps`＝0 |

標準の結果（Q01）：行は satisfied、`grounding.state`＝`representable`（P2-p のまま）、`observation.state`＝`projected`。M＝42（§2）。

### 1.1 構造の事実の表（native 仕様の期待）

仕様は次の9事実を持つ（設計70の§4。出典の id は台帳の項目）。F-S1〜F-S6 は `fhir-codesystem-observation-status-5.0.0`・`fhir-observation-5.0.0`・`fhir-datatypes-5.0.0`、F-P1〜F-P3 は `fhir-provenance-5.0.0`。許容集合：`original`→[final]、`correction`→[amended, corrected]、確認者の型→[Practitioner, PractitionerRole, Patient, RelatedPerson]。

### 1.2 表せる行の流れ（手導出の規則）

P2-p の `representable` の行の流れ（68 の§1.2）を (R, L, A) とする。

- 常に：R に `context:property` を足し、L から除く。A に `assumption:code_mapping_declared` と `assumption:status_mapping:<original|correction>:<値>`
- Provenance を出すとき：R に `human_confirmed`・`record:identity` を足し、L から除く。A に `assumption:reviewer_type_declared`
- 生成の Provenance を出すとき：R に `origin_kind` を足し、L から除く
- 各配列は整列する

標準の流れ（Q01）：retained `[context:method, context:property, context:specimen, human_confirmed, record:identity, unit, value:exact_domain]`、lost `[origin_kind, quantity_kind, review:identity, revision_history, validity]`、added `[assumption:code_mapping_declared, assumption:reviewer_type_declared, assumption:status_mapping:original:final]`。

## 2. 料金の設計値（手計算）

M＝2＋M_g＋3N、M_g＝2＋M_lib＋3N、M_lib＝1＋C＋Σfee＋1（fee は `exchange` が14）。

| 構成 | M_lib | M_g | M（N問い合わせ） |
| --- | --- | --- | --- |
| 標準（記録1・確認1・問い合わせ1） | 32 | 37 | 2＋37＋3＝**42** |
| 確認が2件（C＝3＋3＋11＝17） | 1＋17＋14＋1＝33 | 38 | 2＋38＋3＝**43** |
| 訂正あり（記録2・確認2・辺1。C＝21） | 37 | 42 | 2＋42＋3＝**47** |
| 標準の問い合わせ2（C＝27） | 57 | 65 | 2＋65＋6＝**73** |

## 3. 判定の例（Q）

標準の入力から変える。特記しない限り M＝42、`observation.state`＝`projected`、`status`＝`{state: original, code: final}`、`code`＝`{system: fiction:code-system:s, code: fiction-code-1}`。

### 3.1 宣言が足りて出せる行

| ID | 変更 | 期待 |
| --- | --- | --- |
| Q01 | 標準 | 流れは§1.2のとおり。`provenance`＝1件：`{activity: confirmation, target: {type: Observation, record_ref: A}, recorded: day3, agents: [{who: {type: Practitioner, identifier: fiction:human:reviewer}}]}`。`target.record_sha256` は選択の `record_sha256` と同じ（テストで照合） |
| Q02 | `provenance` を宣言しない | `provenance`＝[]。流れ：R に `context:property`、L から除く。A は `[assumption:code_mapping_declared, assumption:status_mapping:original:final]`。`human_confirmed`・`origin_kind`・`record:identity` は lost のまま |
| Q03-role／Q03-patient／Q03-related | `reviewer_type` が PractitionerRole／Patient／RelatedPerson | Q01 と同じで、agent の `who.type` がそれぞれの型（Z4 の許容側） |
| Q04 | 確認を2件（`RA` day3、`RA2` day4）。M＝43 | `provenance`＝2件の confirmation、`recorded` は day3、day4 の順。`selection.review_refs`＝[RA, RA2] |
| Q05 | 記録 `A` の出自を `{ai_candidate, fiction:ai:A}`（Z6） | `provenance`＝2件：先頭 `{activity: creation, target: {type: Observation, record_ref: A}, recorded: day2, agents: [{who: {type: Device, identifier: fiction:ai:A}}]}`、次に confirmation（Q01 と同じ）。流れ：R に `origin_kind` も、L から除く |
| Q06 | 訂正 `B`（`correct`、corrects [A]、期間 [day4, day6)、値 3 `u_ten`、記録 day6）と確認 `RB`（day7）、問い合わせ day5。`status.correction`＝`amended`。M＝47 | 選択は B。`status`＝`{state: correction, code: amended}`、`code` は同じ。`provenance`＝1件の confirmation：target の record_ref が `B`、`recorded` は day7、確認者は同じ。A に `assumption:status_mapping:correction:amended`（`original` のものは出さない） |
| Q07 | Q06 で `correction`＝`corrected` | `status.code`＝`corrected`。A に `assumption:status_mapping:correction:corrected` |
| Q11 | 標準（訂正なし）で `status.correction`＝`corrected` も宣言 | Q01 と同じ（使わない宣言は影響しない） |
| Q15 | P2-p の対象に `period`＝`exclusive_end_as_last_second` を足す | Q01 に加え、P2-p の仮定。流れ：R に `validity`、L から `validity` を除き、A は `[assumption:code_mapping_declared, assumption:end_convention:last_second, assumption:reviewer_type_declared, assumption:second_granularity, assumption:status_mapping:original:final]` |
| Q16 | 記録の method を `{unknown}` | Q01 と同じ。P2-p の `absent`＝[method]。流れ：R から `context:method` が外れ、L に `context_state_distinction:method`（P2-p のとおり）。他は§1.2 |
| Q17 | P2-p の対象を `range` | `grounding.projection.value`＝`{low: "20", high: "20"}`。他は Q01 と同じ |
| Q19 | 確認を2件。2件目 `RA9` は day9（参照時点 day8 より後）。M＝43 | `selection.review_refs`＝[RA]、`provenance`＝1件（RA の confirmation）。見えない確認は出さない |

### 3.2 宣言が足りない行（依頼。Z1・Z2）

| ID | 変更 | 期待 |
| --- | --- | --- |
| Q08 | Q06 の台帳で `status.correction` を宣言しない。M＝47 | 行は **needs_information**、`[required_information_missing]`、依頼 `[{element: status, action: declare_correction_status, record_ref: B, property_ref: null}]`、`output`・`flows`＝null、`observation.state`＝`needs_information`、`observation.status`・`code`・`provenance`＝null。`grounding.state` は `representable` のまま（Z1。`amended` を推測で入れない） |
| Q09 | `code_map` を空にする | needs_information、依頼 `[{element: code, action: declare_code_mapping, record_ref: A, property_ref: fiction:measurement:property:A@1}]`（Z2） |
| Q10 | Q06 の台帳で `code_map` を空、`status.correction` なし。M＝47 | 依頼は2件、`code` が先：`[{code, declare_code_mapping, B, property}, {status, declare_correction_status, B, null}]` |

### 3.3 判定しない行

| ID | 変更 | 期待 |
| --- | --- | --- |
| Q12 | 記録の値を 1 `u_third`（2/3）、`code_map` を空にする | P2-p の行が `not_representable`（`[not_decimal_representable]`、68 の G03）。`observation.state`＝`not_evaluated`、行は P2-p の行のまま、`requests`＝[]（宣言が足りなくても依頼は出ない。Z7） |
| Q13 | 出力先 `P-B1`・`P-B2` を持ち、P2-p の対象は両方、`observations` は `P-B2` だけ。問い合わせは両方（標準の記録）。M＝73 | `P-B1` の行：`observation.state`＝`not_declared`、`grounding.state`＝`representable`、流れは P2-p のまま（68 の G01 の流れ。Z8）。`P-B2` の行：`projected` |
| Q14 | 出力先 `P-B2`（method known）で、記録の method を `{unknown}` | P2-o の行が `needs_information`（68 の R01 の b2 と同じ依頼）。`grounding.state`＝`not_evaluated`、`observation.state`＝`not_evaluated`。依頼は P2-o のまま |
| Q18 | 2つの出力先 `P-B1`（`quantity`）・`P-B2`（`range`）、`observations` は両方。M＝73 | b1：`{decimal: "20"}`、b2：`{low: "20", high: "20"}`。どちらも `projected` |

### 3.4 観察者が不明な記録の出自（Z9）

Q01 の記録は出自 `observed`。生成の Provenance は**出さない**（agent が分からず、出せない）。`origin_kind` は lost のまま。Q01 で確認する。

## 4. 静的検査の期待（N）

入力の不正は予算に依らず同じ結果（予算 0・1・7 でも）。

| ID | 入力 | 期待（status、reason_codes） |
| --- | --- | --- |
| N01 | 要求の必須欄の欠落・余分な欄（`operation`、`consumer`、`grounding_request`、`observations`、`budget`）、`grounding_request` が object でない | invalid_input（`missing_field`、`unknown_field`、`expected_object`） |
| N02 | `consumer` の `profile`／`profile_spec_sha256`／`grounding_profile`／`grounding_profile_spec_sha256` が別 | unsupported_profile（`unsupported_profile`、`profile_spec_mismatch`、`grounding_profile_mismatch`、`grounding_profile_mismatch`） |
| N03 | `operation` が別／`consumer.operations` が別 | unsupported_profile（`unsupported_operation`） |
| N04 | `grounding_request.schema_version` が別 | unsupported_profile（`grounding_schema_mismatch`） |
| N05 | `grounding_request.budget.max_steps` が 0 でない | invalid_input（`invalid_child_budget`） |
| N06 | 子の要求が P2-p で不正（同じ出力先に対象2件）／P2-o で不正（確認の内容 hash を持つ操作） | P2-p・P2-o の符号のまま（`duplicate_target`、`unknown_field`） |
| N07 | `observations` が空／17件 | invalid_input（`empty_collection`）／resource_limit（`item_limit`） |
| N08 | `status.original` が `amended`（Z3）／`preliminary`、`status.correction` が `final`／`registered` | unsupported_profile（`unsupported_status_mapping`） |
| N09 | `status` に `original` がない／余分な欄 | invalid_input（`missing_field`／`unknown_field`） |
| N10 | `code_map` の項目の欠落／余分／空文字／`property_ref` の重複 | invalid_input（`missing_field`／`unknown_field`／`expected_nonempty_string`／`duplicate_property_mapping`） |
| N11 | `reviewer_type` が `Device`（Z4）／`Organization`／`Nurse` | unsupported_profile（`unsupported_reviewer_type`） |
| N12 | 同じ出力先への宣言が2件／P2-p の対象のない出力先への宣言 | invalid_input（`duplicate_observation`／`unresolved_target`） |
| N13 | 予算が bool／負／100001 | invalid_input（`invalid_step_budget`）／resource_limit（`step_budget_limit`） |

## 5. 資源の期待（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | 標準（M＝42、prepay の後ろは1＋M_g＝38、行ごとに3：41）。予算 0・1・37・38・39・40・41・42 | 41 までは `resource_limit`、`steps_used`＝予算。38〜40 は行が未完了（8欄が null、理由 `step_limit`）。41 は行が完成し、`incomplete` に完成の段。42 で ok |
| B02 | 標準の問い合わせ2（M＝73、1＋65＝66、行：69・72）。予算 0・65・66・68・69・71・72・73 | 予算ごとに、完成した行は保持し、未完了の行は null。72 は二行とも完成し完成の段だけ未完了 |
| B03 | 68 の B03 の大きな計画に標準の宣言を足す。予算 100000 | resource_limit、`steps_used`＝100000、行は未完了、認定票は `not_certified` |

## 6. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1（X2） | 宣言の全数：`status.correction` の有無×`code_map`（空／該当／別の性質）×選ばれる記録（原本／訂正）×`provenance`（なし／4種の型） | 依頼の有無と内容が規則どおり（足りないものは全て依頼、足りれば projected）。推測で補った `status`・`code` は決して出ない |
| D2（X3） | 使った写像の仮定が `added` に出る。Provenance なしでは `human_confirmed`・`origin_kind` が lost | 規則どおり |
| D3（X4） | 過去の対象時点（訂正の前）の行は原本の `status` | 選ばれた記録で決まる |
| D4（X5） | 確認の数×出自（observed／ai_candidate） | 確認の数と同数の confirmation、AI 由来のときだけ先頭に creation |
| D5 | P2-p 単独の実行との差分（乱数）：行の P2-p の欄が同じ。`projected` 以外の行は、P2-p の行と同じ | 同じ |
| D6（X6） | 乱数の要求 | M＝2＋M_g＋3N。子の実費は M_g |
| D7 | 入力の不変性、問い合わせ・宣言・出力先の順序を替える | 結果の意味は同じ |
| D8（X10） | `system`・`code` の文字列を変える | 判定は同じで、出力にそのまま載る |

## 7. 検出すべき変異（実装時に選ぶ候補）

宣言のない `status`・`code` の補完（`final` を黙って入れる）、仮定の欠落、依頼の欠落・重複・順序の誤り、訂正と原本の取り違え、確認の欠落・重複・順序の誤り、見えない確認の出力、生成の Provenance の誤出力（observed に出す、ai_candidate に出さない）、確認者の型の取り違え、許容外の写像の受理、`not_evaluated` の行で依頼を出す、`not_declared` を `projected` と言う、流れの項目の取りこぼし、先払いの省略、子の予約の誤り、認定の誤り。

## 8. 前提と限界

- 期待は設計70・取得したページの読み取りから手で導いた値です。P2-p・P2-o の行の内容は、[68](68-p2-p-cases.md)・[64](64-p2-o-cases.md) に従います。
- `status` の許容集合は、ページの定義の保守的な読みで、作成者のものです。人の確認を `final` とする判断は、宣言の判断であり、このライブラリの主張ではありません。
- `code` の符号の系・符号の内容は検査しません。Provenance の entity・activity・role・署名は範囲外です。FHIR の資源としての生成と適合は評価しません。
