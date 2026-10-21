# P2-p：構造への写像の可否の診断の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計67](67-p2-p-design.md) の予測 W1〜W10 と反例 Z1〜Z9 に、具体的な入力と期待を与えます。期待は設計と、[監査66](66-p2-p-grounding-audit.md) で確認した構造の事実から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・単位・property・識別子はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。利用者の承認（2026-10-21「推奨案で進めてください」。U1〜U3 は設計67の推奨どおり）の後に作成しました。

## 0. 設計67の具体化（実装前に決めた細部）

設計67が決めていなかった細部を、ここで固定します。

| ID | 決定 | 理由 |
| --- | --- | --- |
| S1 | 表せる行の `flows` は、P2-o の `exchange` の流れに差分を足すのでなく、**射影が運ぶものから作り直す**（§1.2）。P2-o の流れは `quantity_kind` と `context:property` を「保持」とするが、この拡張の射影は運ばないため | `code` の写像は範囲外（設計67の§11）。保持と書くと射影と食い違う |
| S2 | 流れの項目名は P2-o に合わせる：`human_confirmed`・`origin_kind`（設計67の `human_confirmation` は使わない） | 同じ名前で同じものを指す |
| S3 | `library_request.budget.max_steps` は **0** でなければならない（`invalid_child_budget`）。子の予算はこの拡張が決める（P2-i を呼ぶ P2-o と同じ） | 予算が二重に指定されるのを避ける |
| S4 | 対象のない出力先の行は `not_declared`（P2-o の状態によらない）。対象があり、P2-o の行が `satisfied` でない行は `not_evaluated`。どちらも P2-o の行をそのまま通す | 設計67の GD7・GD8 の優先 |
| S5 | `quantity` の対象に区間を当てると、理由は `interval_not_representable_as_quantity` だけ（開閉の理由は足さない）。端の小数・桁の判定は、`quantity` でも `range` でも両端に行い、理由は和集合を整列して返す | 設計67の§5.1 |
| S6 | 静的な拒否の理由符号は§7の表。`library_request` の不正は P2-o の理由符号をそのまま返す | P2-o の検査を再実装しない |
| S8 | 行の `grounding` は `{structure, state, reasons, projection}`。`structure` は対象のある行で `fhir-r5-observation`、`not_declared` の行で null。`state` は `representable`／`not_representable`／`not_evaluated`／`not_declared`。`projection` は representable の行だけ（他は null）。`base_status` は P2-o の行の status（representable・not_representable の行でも `satisfied`） | 設計67の§3・§6 を型として固定 |
| S7 | 表せない行の `output` は null、`requests` は空、`selection`・`elements` は P2-o の行のまま | 表せない行は、依頼が要らない |

## 1. 標準の入力

| 項目 | 標準 |
| --- | --- |
| library_request | P2-o の標準（[64 の§1](64-p2-o-cases.md)）：slot S、記録 `A`（2 `u_ten`＝20 `u_base`、method・specimen は known、期間 [day1, day10)、確定）、確認 `RA`、view `v`（as_of day8）。出力先 `P-B1`＝`dest:numeric-exchange`@1（`exchange`：`value`〔`domain`、`u_base`〕、`context`：property known）。問い合わせ `q1`（day5） |
| target | `P-B1` を指す。構造 `fhir-r5-observation`、`value`：`quantity`、`context_fields`：[method, specimen]、`period` なし |
| 予算 | 100000。`library_request.budget.max_steps`＝0 |

標準の結果：P2-o の行は satisfied（`exchange`、領域 点 20）。この拡張の行は satisfied、`grounding.state`＝`representable`。M＝37（§2）。

### 1.1 構造の事実の表（native 仕様の期待）

仕様は次の6事実を持つ。出典の id は台帳の項目。

| 事実 | 内容 | 出典 | 目印 |
| --- | --- | --- | --- |
| F-R1 | Range の low・high は両端を含む（閉）。端に comparator は付かない | `fhir-datatypes-5.0.0` | `inclusive` |
| F-R2 | decimal は小数表現を持つ有理数。桁は18まで | 同 | `18 digits` |
| F-R3 | Period の start・end はともに含む | 同 | `inclusive boundary` |
| F-R4 | Observation の `value[x]` は 0..1、型に Quantity・Range | `fhir-observation-5.0.0` | `dataAbsentReason` |
| F-R5 | Observation の `method`・`specimen` は 0..1 | 同 | `specimen` |
| F-R6 | 追加の状態（released など）は Provenance で表す | `fhir-codesystem-observation-status-5.0.0` | `Provenance` |

（設計67の F-R6〔`effective[x]` の型〕は判定に使わないので仕様の表に入れず、設計67の F-R7 を本表の F-R6 とした。）

### 1.2 表せる行の流れ（手導出の規則）

射影が運ぶものから作る。lost・retained・added は整列した配列。

- **retained**：`value:exact_domain`、`unit`、運んだ（`context_fields` にあり known の）欄ごとに `context:<欄>`、期間を運ぶとき `validity`
- **lost**：`record:identity`、`review:identity`、`revision_history`、`quantity_kind`、`context:property`、`origin_kind`、`human_confirmed`；期間を運ばないとき `validity`；`context_fields` にない欄（method・specimen）ごとに `context:<欄>`；`context_fields` にあるが known でない欄ごとに `context_state_distinction:<欄>`
- **added**：期間の規約を宣言して使ったとき `assumption:end_convention:last_second`、`assumption:second_granularity`

表せない行は retained 空・added 空、lost は理由ごとの表：`interval_not_representable_as_quantity`→`interval_width`、`open_boundary_not_representable`→`interval_bounds`、`not_decimal_representable`・`digits_exceed_limit`→`exact_value`、`period_end_convention_undeclared`→`validity_end` の和集合。

標準の表せる行（G01）の流れ：retained `[context:method, context:specimen, unit, value:exact_domain]`、lost `[context:property, human_confirmed, origin_kind, quantity_kind, record:identity, review:identity, revision_history, validity]`、added `[]`。

## 2. 料金の設計値（手計算）

M＝2＋M_lib＋3N。M_lib は P2-o の料金（1＋C＋Σfee＋1、fee は `exchange` が14）。C＝1＋slot数＋量数＋Σ view〔記録数＋確認数＋Σ 問い合わせ〔10＋範囲内の記録数＋適格な訂正辺の数〕〕。

| 構成 | C | M_lib | M（N問い合わせ） |
| --- | --- | --- | --- |
| 標準（記録1・確認1・問い合わせ1） | 3＋2＋11＝16 | 1＋16＋14＋1＝32 | 2＋32＋3＝**37** |
| 標準の問い合わせ2（`exchange` 2） | 3＋2＋22＝27 | 1＋27＋28＋1＝57 | 2＋57＋6＝**65** |
| 標準の問い合わせ3（`exchange` 3。K14の三つ組） | 3＋2＋33＝38 | 1＋38＋42＋1＝82 | 2＋82＋9＝**93** |
| 訂正あり（記録2・確認2・辺1・問い合わせ1） | 4＋4＋13＝21 | 1＋21＋14＋1＝37 | 2＋37＋3＝**42** |
| `line`・`exchange`・`trend` 各1（64 の O60） | 49 | 97 | 2＋97＋9＝**108** |

## 3. 値の例（G）

標準の入力に対し、記録の値と対象の `value` を変える（出力先は `P-B1`、単位 `u_base`。換算は 1 `u_ten`＝10、1 `u_half`＝1/2、1 `u_third`＝2/3）。期間の規約と`context_fields`は標準。M＝37。

### 3.1 `quantity`

| ID | 記録の値 | 期待 |
| --- | --- | --- |
| G01 | 点 2 `u_ten`（＝20） | representable。`value`＝`{decimal: "20"}` |
| G02 | 点 1 `u_half`（＝1/2） | representable、`"0.5"` |
| G03 | 点 1 `u_third`（＝2/3） | **not_representable**、`[not_decimal_representable]`、lost `[exact_value]`（Z1。丸めない） |
| G04 | 点 1/8 `u_base` | representable、`"0.125"` |
| G05 | 点 −1/2 `u_base` | representable、`"-0.5"` |
| G06 | 点 0 `u_base` | representable、`"0"` |
| G07 | 点 7/4 `u_ten`（＝35/2） | representable、`"17.5"` |
| G08 | 点 1/3 `u_base` | not_representable、`[not_decimal_representable]` |
| G09 | 点 1/50 `u_base` | representable、`"0.02"` |
| G10 | 区間 [1,2] 閉 `u_base` | not_representable、`[interval_not_representable_as_quantity]`、lost `[interval_width]`（Z3） |
| G11 | 区間 [1,1] 閉 | representable、`"1"` |
| G12 | 区間 [1,2) | not_representable、`[interval_not_representable_as_quantity]`（S5） |
| G13 | 区間 [1,4/3] 閉 | not_representable、`[interval_not_representable_as_quantity, not_decimal_representable]`、lost `[exact_value, interval_width]` |

### 3.2 `range`

| ID | 記録の値 | 期待 |
| --- | --- | --- |
| G20 | 区間 [1,2] 閉 `u_base` | representable、`{low: "1", high: "2"}` |
| G21 | 点 2 `u_ten` | representable、`{low: "20", high: "20"}` |
| G22 | 区間 [1,2) | not_representable、`[open_boundary_not_representable]`、lost `[interval_bounds]`（Z2。閉じない） |
| G23 | 区間 (1,2] | 同上 |
| G24 | 区間 (1,2) | 同上 |
| G25 | 区間 [1,4/3] 閉 | not_representable、`[not_decimal_representable]` |
| G26 | 区間 (0,1/3] | not_representable、`[not_decimal_representable, open_boundary_not_representable]`、lost `[exact_value, interval_bounds]` |
| G27 | 区間 [1/8,5/4] 閉 | representable、`{low: "0.125", high: "1.25"}` |
| G28 | 区間 [1,1] 閉 | representable、`{low: "1", high: "1"}` |

### 3.3 桁数（Z4。18桁の数え方は保守側：先頭の 0 を数え、符号と小数点を数えない）

| ID | 記録の値（`u_base`、`quantity`） | 期待 |
| --- | --- | --- |
| G30 | 点 123456789012345678（18桁） | representable、`"123456789012345678"` |
| G31 | 点 1234567890123456789（19桁） | not_representable、`[digits_exceed_limit]`、lost `[exact_value]` |
| G32 | 点 −123456789012345678 | representable、`"-123456789012345678"`（符号は数えない） |
| G33 | 点 12345678901234567/10^17 | representable、`"0.12345678901234567"`（先頭の 0 を数えて18桁。**解釈に依る**） |
| G34 | 点 123456789012345678/10^18 | not_representable、`[digits_exceed_limit]`（先頭の 0 を数えて19桁。**解釈に依る**。FHIR が許す境界とは主張しない） |

G33・G34 は、ページの記述（"18 digits and a decimal point"）の数え方を決められない点（設計67の I1）で、保守側の解釈の例です。

## 4. 期間の例（P。Z5）

標準の記録の期間は [day1, day10)。値は標準（点 20）。`period` を足す。

| ID | `period` | 期待 |
| --- | --- | --- |
| P01 | `{end_convention: undeclared}` | **not_representable**、`[period_end_convention_undeclared]`、lost `[validity_end]` |
| P02 | `{end_convention: exclusive_end_as_last_second}` | representable。`period`＝`{start: "2026-10-01T00:00:00Z", end: "2026-10-09T23:59:59Z"}`。流れ：retained に `validity`、lost に `validity` なし、added `[assumption:end_convention:last_second, assumption:second_granularity]` |
| P03 | なし（G01） | representable。`period` は null。lost に `validity` |
| P04 | G03 の値（not_decimal）＋ `undeclared` | not_representable、`[not_decimal_representable, period_end_convention_undeclared]`、lost `[exact_value, validity_end]` |
| P05 | G03 の値＋ `exclusive_end_as_last_second` | not_representable、`[not_decimal_representable]`、lost `[exact_value]`、added は空（足した仮定は出さない） |
| P06 | 訂正あり：A に B（`correct`、期間 [day4, day6)、値 3 `u_ten`、method の version 2、記録 day6）と確認 `RB`（day7）を足し、問い合わせ day5。`exclusive_end_as_last_second`。M＝42 | representable。選択は B、`value`＝`{decimal: "30"}`、`period`＝`{start: "2026-10-04T00:00:00Z", end: "2026-10-05T23:59:59Z"}` |

## 5. 文脈の例（C。Z6）

`context_fields` と、記録の method・specimen を変える。値は標準（点 20）、`period` なし。`absent` と `context` は射影の欄。M＝37。

| ID | 記録・対象 | 期待 |
| --- | --- | --- |
| C01 | method を `{unknown}`。`context_fields`＝[method, specimen] | representable。`absent`＝[method]、`context`＝{specimen: {ref: fiction:specimen:s, version: "1"}}。retained `[context:specimen, unit, value:exact_domain]`、lost に `context_state_distinction:method` を足す |
| C02 | method を `{unspecified}`、specimen を `{unknown}`。[method, specimen] | `absent`＝[method, specimen]、`context`＝{}。lost に両欄の `context_state_distinction:*`。retained `[unit, value:exact_domain]`。C01 と C02 で unknown と unspecified の区別が落ちること（どちらも不在）が分かる |
| C03 | 標準の記録。`context_fields`＝[] | `absent`＝[]、`context`＝{}。lost に `context:method`、`context:specimen` を足す（運ばない） |
| C04 | 標準。`context_fields`＝[method] | `context`＝{method}。lost に `context:specimen` |
| C05 | method の version を 2（known）。[method, specimen] | `context.method`＝{ref: fiction:method:m, version: "2"} |
| C06 | C02 と同じ記録で、`context_fields` を [specimen, method] の順に書く | C02 と同じ結果（`absent` は整列した [method, specimen]。順序によらない） |

## 6. 通す行・対象のない行（R・D。Z7・Z9）

| ID | 入力 | 期待 |
| --- | --- | --- |
| R01 | 64 の O11 の台帳（method が unknown）。出力先 `P-B1`・`P-B2`（method known）・`P-B3`（specimen も known）の問い合わせ b1・b2・b3、三つとも対象を宣言。M＝93 | b1：representable（C01 と同じ `absent`）。b2・b3：status `needs_information`、`[required_information_missing]`、`base_status` も同じ、`grounding.state`＝`not_evaluated`、依頼は P2-o と同じ（`context:method`・`observe_and_record`・`record_ref` A が一つずつ）、`flows` は null |
| R02 | 出力先の値の単位を `v_base`（次元が違う）、対象を宣言 | status `not_representable`、`[unit_not_convertible]`、`grounding.state`＝`not_evaluated`、flows は P2-o のまま（lost `[value]`） |
| R03 | A の `capabilities` に未知の能力 | status `unassessed`、`[unknown_capability]`、`not_evaluated` |
| R04 | 問い合わせを day11（期間の外） | `needs_information`、`[no_adopted_measurement]`、依頼 `record_and_confirm`、`not_evaluated` |
| D01 | 出力先 `P-B1`・`P-B2` を持ち、対象は `P-B2` だけ。問い合わせは両方（標準の記録）。M＝65 | `P-B1` の行：satisfied、`grounding.state`＝`not_declared`、P2-o の行と同じ（`flows` は P2-o の `exchange` の流れ）。`P-B2` の行：representable |
| D02 | `line`（`P-A1`）の問い合わせ、`exchange`（`P-B1`、対象あり）の問い合わせ | `line` の行：`not_declared`、output の text が `20.0`。`exchange` の行：representable |
| D03 | 64 の O60（`line`・`exchange`@2・`trend` 各1）。対象は `exchange` のみ。M＝108 | 三つの行：`line` と `trend` は `not_declared`（P2-o の行のまま）、`exchange` は representable |
| D04 | 二つの対象：`P-B1` に `quantity`、`P-B2` に `range`。標準の記録（点 20）。M＝65 | b1：`{decimal: "20"}`、b2：`{low: "20", high: "20"}` |

## 7. 静的検査の期待（N）

入力の不正は予算に依らず同じ結果（予算 0・1・7 でも）。

| ID | 入力 | 期待（status、reason_codes） |
| --- | --- | --- |
| N01 | 要求の必須欄の欠落・余分な欄（`schema_version`、`operation`、`consumer`、`library_request`、`targets`、`budget`）、null、`library_request` が object でない | invalid_input（`missing_field`、`unknown_field`、`expected_object`） |
| N02 | `consumer.profile` が別、`profile_spec_sha256` が別、`library_profile` が別、`library_profile_spec_sha256` が別 | unsupported_profile（`unsupported_profile`、`profile_spec_mismatch`、`library_profile_mismatch`、`library_profile_mismatch`） |
| N03 | `operation` が別／`consumer.operations` が別 | unsupported_profile（`unsupported_operation`） |
| N04 | `library_request.schema_version` が別 | unsupported_profile（`library_schema_mismatch`） |
| N05 | `library_request.budget.max_steps` が 0 でない | invalid_input（`invalid_child_budget`）（S3） |
| N06 | `library_request` が P2-o で不正（64 の N03 系：確認の内容 hash を持つ操作、無効な訂正 など） | P2-o の符号のまま（`unknown_field`、`unsupported_revision_scope` など） |
| N07 | `targets` が空／17件 | invalid_input（`empty_collection`）／resource_limit（`item_limit`） |
| N08 | 対象の `structure` が `fhir-r4-observation`、`value` が `ratio`、`period.end_convention` が `inclusive_end`、`context_fields` に `property` | unsupported_profile（`unsupported_structure`、`unsupported_target_value`、`unsupported_end_convention`、`unsupported_context_field`） |
| N09 | `context_fields` の重複／対象の余分な欄／欠落 | invalid_input（`duplicate_reference`、`unknown_field`、`missing_field`） |
| N10 | 同じ出力先を指す対象が2件／存在しない出力先を指す対象 | invalid_input（`duplicate_target`、`unresolved_destination`） |
| N11 | `line`・`trend` の出力先に対象を宣言（Z8） | unsupported_profile（`unsupported_grounding_output_kind`） |
| N12 | 予算が bool／負／100001 | invalid_input（`invalid_step_budget`）／resource_limit（`step_budget_limit`） |

## 8. 資源の期待（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | 標準（M＝37、prepay の後ろは1＋M_lib＝33）。予算 0・1・32・33・34・35・36・37 | 予算 36 までは `resource_limit`、`steps_used`＝予算。33〜35 は行が未完了（行の五つの欄＋`grounding`・`base_status` が null、理由 `step_limit`）。36 は行が完成し、`incomplete` に完成の段（`stage: completion`）。37 で ok |
| B02 | 三つ組（M＝93、33→83、行ごとに3：86・89・92）。予算 82・83・85・86・88・89・91・92・93 | 予算ごとに、完成した行は保持し、未完了の行は null。92 は三行とも完成し完成の段だけ未完了 |
| B03 | 64 の B04（計画が上限を超える大きな計画）に標準の対象を足す。予算 100000 | resource_limit、`steps_used`＝100000、行は未完了、認定票は `not_certified` |

## 9. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1（W2） | 値の判定を、分母 1〜40・分子 −60〜60（約分して重複を除く）の点と、端の開閉4通りの区間（下端〜上端の組）の格子の全数で、`quantity`／`range` の可否と理由 | 手導出の規則（§3）と一致。小数で書ける分母は素因数が 2・5 だけ |
| D2（W3） | P2-o の行との差分。乱数の要求で、基底の欄（選択・要素・出力・依頼）を比べる | 表せる行：selection・elements・output・requests が P2-o の行と同じ。通す行：全欄が同じ |
| D3（W4） | 期間の規約。標準＋すべての期間（半開区間 [day s, day e)） | `undeclared` は全て表せない。宣言すると end が1秒戻る |
| D4（W5） | `context_fields` の全部分集合×記録の method・specimen の3状態の全数 | `context_state_distinction:*` の数が、`context_fields` のうち known でない欄の数に等しい。`human_confirmed`・`origin_kind` は常に lost |
| D5（W6） | 乱数の要求 | M＝2＋M_lib＋3N。子の実費は M_lib |
| D6 | 入力の不変性、問い合わせ・対象・出力先の順序を替える | 結果の意味は同じ |
| D7（W7） | 仕様の構造の事実の目印が、手元の取得したページに存在する（ページがあるとき） | 全て存在 |

## 10. 検出すべき変異（実装時に選ぶ候補）

端を閉じる（open を受理する）、丸める、`quantity` を区間に当てて中点にする、桁数を数えない／符号を数える／先頭の 0 を数えない、有限小数の判定の誤り（素因数 3 を許す）、規約を宣言なしに使う、仮定を `added` に出さない、文脈の区別の損失を出さない、`human_confirmed`／`origin_kind` の損失を出さない、`context_fields` の順序依存、不足の行を変える（通さない）、`not_declared` を `representable` と言う、先払いの省略、子の予約の誤り、構造名で分岐、認定の誤り。

## 11. 前提と限界

- 期待は設計67・監査66から手で導いた値です。P2-o の行の内容（選択・要素・依頼・出力）は、[64](64-p2-o-cases.md) と P2-o の例の手指定の期待に従います。
- 構造の事実は取得したページの記述の読み取りで、FHIR への適合を保証しません。「18桁」の数え方（G33・G34）は保守側の解釈です。Quantity の comparator、`code` の写像、Provenance、`status` は範囲外です。
- 期間の規約は、ライブラリの時刻が秒の粒度であることに依ります。FHIR の dateTime の精度の意味づけは検証していません。
- 構造の名前・事実の表は 1 構造だけで、一般の構造の網羅ではありません。
