# P2-o：薄い臨床ライブラリの手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計63](63-p2-o-design.md) の予測 V1〜V10 と反例 Y1〜Y8 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・単位・property・識別子はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。

## 1. 標準の入力

| 項目 | 標準 |
| --- | --- |
| library | ref `fiction:library:session@1`。slot S（主体 `u`） |
| 操作 `A` | `record`。slot S、property `fiction:measurement:property:A@1`、specimen `{known, fiction:specimen:s, 1}`、method `{known, fiction:method:m, 1}`、validity bounded [day1, day10)、value 点 2 `u_ten`（量種 `k_a`）、確度 confirmed、記録 day2、origin `{observed, fiction:library:origin:A}` |
| 操作 `RA` | `confirm`。`A` を指定、reviewer `fiction:human:reviewer`、記録 day3 |
| view | `v`（as_of day8） |
| 問い合わせ | 対象時点 day5（`trend` は from day3・to day5）。結果は問い合わせ id 順 |

標準の `A` は 2 `u_ten`＝20 `u_base`。各例の「変更」は標準からの差分。

### 1.1 要求プロファイル

| 名前 | 内容 |
| --- | --- |
| `P-A1`＝`dest:record-line`@1 | `line`。`value`：`single_point`、`u_base`、decimal_places 1 |
| `P-B1`＝`dest:numeric-exchange`@1 | `exchange`。`value`：`domain`、`u_base`。`context`：property known |
| `P-B2`＝同 @2 | P-B1 に `context`：method known を足す（K14 の版の更新） |
| `P-B3`＝同 @3 | P-B2 に `context`：specimen known を足す（要素の順は value、property、method、specimen） |
| `P-C1`＝`dest:trend-summary`@1 | `trend`。`context_match`＝[method, property, specimen] |
| `P-E1`＝`dest:registry-entry`@1 | `exchange`。`value`：`domain`、`u_ten`。`context`：specimen known、method known（新しい出力先。データだけで足す） |

## 2. 料金の設計値（手計算）

M＝1＋C＋Σfee＋1。fee は `line`・`exchange` が14、`trend` が18。C は P2-i の計画の料金（問い合わせ数は `trend` が2、他は1）。

| 入力 | 内訳 | C | fee | M |
| --- | --- | --- | --- | --- |
| 標準＋`line` 一つ（O01） | 3＋(1＋1)＋1×11 | 16 | 14 | **32** |
| 標準＋`trend` 一つ（O40） | 3＋(1＋1)＋2×11 | 27 | 18 | **47** |
| A／B（B が A を [day4, day6) で訂正）＋`trend`（O41） | 4＋(2＋2)＋2×(2＋2＋1＋8) | 34 | 18 | **54** |
| 標準＋`exchange` 三つ（O10） | 3＋(1＋1)＋3×11 | 38 | 42 | **82** |
| A／B＋`exchange` 三つ（O30） | 4＋(2＋2)＋3×13 | 47 | 42 | **91** |
| 標準＋`line`・`exchange`・`trend`（O60） | 3＋(1＋1)＋4×11 | 49 | 46 | **97** |

## 3. 出力と流れの表

`flows`（`satisfied` の行）は次の固定の表。`not_representable` の行は `retained` と `added` が空で、`lost` は理由ごと：`value_not_a_single_point`→[interval_bounds]、`unit_not_convertible`→[value]、`contexts_differ`→[relation]、`incompatible_dimension`・`incompatible_quantity_kind`→[relation]。

| 出力 | retained | lost | added |
| --- | --- | --- | --- |
| `line` | [value:rounded_text] | [value:exact, record:identity, validity, context:specimen, context:method, origin, confirmation] | [rounding_policy] |
| `exchange` | [value:exact_domain, unit, quantity_kind, context:property, context:specimen, context:method, origin_kind, human_confirmed] | [record:identity, validity, review:identity, revision_history] | [] |
| `trend` | [relation_set, direction] | [value:exact, record:identity, validity, context, origin, confirmation] | [assumption:independent_time_variables] |

## 4. 例の期待（O：選択・要素・集約・依頼）

### 4.1 `line`（Y3）

| ID | 変更 | 期待 |
| --- | --- | --- |
| O01 | 標準、`P-A1` | satisfied。`output`＝`{text: "20.0", coefficient: 200, unit_ref: u_base, decimal_places: 1, rounding_policy: fiction:decimal-half-even@1}`。`elements` の状態は selection・value とも met。依頼は空。M＝32 |
| O02-5-4 | A の値を 5/4 `u_base` | text `1.2`（係数12）。1.25 は最近接偶数 |
| O02-27-20 | 27/20 `u_base` | text `1.4`（係数14）。1.35 は最近接偶数 |
| O02-m5-4 | −5/4 | text `-1.2`（係数−12） |
| O02-m27-20 | −27/20 | text `-1.4`（係数−14） |
| O02-5-2 | 5/2 `u_base`、decimal_places 0 | text `2`（係数2） |
| O02-7-2 | 7/2、decimal_places 0 | text `4`（係数4） |
| O02-m5-2 | −5/2、0 | text `-2` |
| O02-m7-2 | −7/2、0 | text `-4` |
| O02-third | 1 `u_third`（2/3 `u_base`）、decimal_places 2 | text `0.67`（係数67） |
| O02-places6 | 121/100 `u_base`、decimal_places 6 | text `1.210000`（係数1210000） |
| O03 | 値を区間 [1,2]（閉）`u_ten` | **not_representable**、理由 `[value_not_a_single_point]`。value の状態は unrepresentable、換算領域は [10,20] 閉。`output` null、`flows`＝retained [] lost [interval_bounds] added []。依頼は空 |
| O04 | 値を区間 [1,1]（閉）`u_base` | satisfied。text `1.0`（係数10） |
| O05 | `line` の value の `unit_ref` を `v_base`（次元が違う） | not_representable、理由 `[unit_not_convertible]`、lost [value] |
| O06 | `unit_ref` を `fiction:future-unit` | **unassessed**、理由 `[unknown_unit]`。依頼は空 |
| O07 | `P-B1` で値を区間 [1,2)（下端閉・上端開）`u_ten` | satisfied。換算領域は下端10・上端20、下端は閉・上端は開（`exchange` は区間を保つ） |

### 4.2 要求の版の更新と不足の依頼（K14。Y1・Y2、V3・V4）

問い合わせ三つ（`P-B1`・`P-B2`・`P-B3` をそれぞれ参照）を一つの要求に並べる。問い合わせ id は `b1`・`b2`・`b3`。

| ID | 変更 | 期待（b1／b2／b3） |
| --- | --- | --- |
| O10 | 標準 | 三つとも satisfied、依頼は空。`output.context`＝記録の値。`origin`＝`{record: observed, quantity: literal}`、`human_confirmed`＝true。M＝82 |
| O11 | A の method を `{unknown}` | b1：satisfied（出力の `context.method`＝`{kind: unknown}`）。b2：**needs_information**、理由 `[required_information_missing]`、依頼は一つ：`{element: context:method, action: observe_and_record, record_ref: A, records: [], candidates: [], slot_ref: null, target_at: null, ends: null}`。`output` null。b3：同じ一つ（specimen は known） |
| O12 | A の method を `{unspecified}`、specimen を `{unknown}` | b1：satisfied。b2：依頼一つ（method）。b3：依頼二つ（`context:method`、`context:specimen` の順） |
| O13 | O11 に、AI 候補の訂正 `A2`（`correct`、corrects [A]、method known、全期間 [day1, day10)、同じ値、確度 confirmed、記録 day6、origin `{ai_candidate, fiction:ai:A2}`、**確認なし**） | b2：needs_information。依頼は一つ：`action: confirm_candidate`、`record_ref: A`、`candidates: [{record_ref: A2, origin_kind: ai_candidate, proposed: {known, fiction:method:m, 1}}]`。**満たされたことにならない**（`output` null）。`selection.record_ref`＝A |
| O14 | O13 に A2 の確認 `RA2`（記録 day7） | b2：satisfied。**選択は A2**（A2 は A を訂正）。`selection.review_refs`＝[RA2]、`selection.record_origin.kind`＝ai_candidate。`output.origin`＝`{record: ai_candidate, quantity: ai_candidate}`、`human_confirmed`＝true、`output.context.method` は known。依頼は空。O13 の台帳の `A` の記録は変わらない |
| O15 | O11 に、clinician の訂正 `A3`（`correct`、corrects [A]、method known、origin observed、記録 day6）と確認 `RA3`（day7） | b2：satisfied（選択 A3）。出力の `origin.record`＝observed |

### 4.3 選択の段階の依頼（Y8）

`P-B1` の一つの問い合わせ。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O20 | 対象時点を day11（期間の外） | needs_information、理由 `[no_adopted_measurement]`、`elements`＝[selection：unmet]、依頼：`{element: selection, action: record_and_confirm, record_ref: null, records: [], candidates: [], slot_ref: S, target_at: day11, ends: null}`。`selection`・`output`・`flows` は null |
| O21 | 確認 `RA` を除く | needs_information、`[no_adopted_measurement]`、依頼：`action: confirm_pending`、`records: [A]` |
| O22 | A の確度を `suspected`（`RA` あり） | needs_information、`[no_adopted_measurement]`、依頼：`record_and_confirm`（slot S、day5、records []）。suspected は確認しても適格にならない |
| O23 | 別の記録 `D`（slot S、validity [day1, day4)、値 5 `u_ten`、確定、記録 day2）と確認 `RD`（day3）を足し、対象時点を day3 | needs_information、`[unresolved_measurement_conflict]`、依頼：`resolve_conflict`、`records: [A, D]`。後勝ちで解決しない |
| O24 | 期間が `{unknown}` の確定の記録 `U`（記録 day4）と確認 `RU`（day5）を足す | needs_information、`[validity_unknown]`、依頼：`refine_validity`、`records: [U]` |
| O25 | A の `capabilities` に `future:capability` | **unassessed**、`[unknown_capability]`。`elements`＝[selection：unassessed]。依頼は空 |
| O26 | AI 由来の A（origin `{ai_candidate, fiction:ai:A}`、`RA` あり） | satisfied。`output.origin.record`＝ai_candidate（人の確認があれば適格） |
| O27 | AI 由来の A で `RA` なし | needs_information、`[no_adopted_measurement]`、依頼：`confirm_pending`、`records: [A]` |

### 4.4 部分訂正で選択が変わる（CL-4）

A に、B（`correct`、corrects [A]、validity [day4, day6)、値 3 `u_ten`、method `{known, fiction:method:m, 2}`、他は A と同じ、記録 day6、origin observed）と確認 `RB`（day7）を足す。`P-B2` の問い合わせ三つ：`q3`（day3）、`q5`（day5）、`q6`（day6）。

| ID | 期待 |
| --- | --- |
| O30 | `q3`：選択 A、`output.context.method.version`＝1、領域 20。`q5`：選択 B、version 2、領域 30。`q6`：選択 A（B の期間は day6 を含まない）、領域 20。いずれも satisfied。M＝91 |

### 4.5 `trend`（Y4）

`P-C1`、from day3・to day5。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O40 | 標準 | satisfied。`output`＝`{relation_set: [equal], certain_relation: equal, direction: from_relative_to_to, from_at: day3, to_at: day5, assumptions: [independent_time_variables]}`。`selection.from.record_ref`・`selection.to.record_ref` はともに A。M＝47 |
| O41 | A／B（B の値 3、文脈は A と同じ）を足す | satisfied、`[less]`、certain less。選択は from が A、to が B。M＝54 |
| O42 | O41 で B の method の version を 2 | **not_representable**、`[contexts_differ]`、trend の要素に `differences: [{field: method, from: {known, m, 1}, to: {known, m, 2}}]`。`output` null、lost [relation] |
| O43 | A の method を `{unknown}` | needs_information、`[required_information_missing]`、依頼は一つ：`context:method`、`observe_and_record`、`record_ref: A`、`ends: [from, to]`（同じ記録は一つにまとめる） |
| O44 | A の値を区間 [1,2] `u_ten` | satisfied、`[less, equal, greater]`、certain null（同じ記録でも独立な変数） |
| O45 | to を day11 | needs_information、`[no_adopted_measurement]`、依頼一つ：`selection`・`record_and_confirm`・`slot_ref: S`・`target_at: day11`・`ends: [to]` |
| O46 | O23 の台帳で from を day3、to を day11 | needs_information、理由 `[no_adopted_measurement, unresolved_measurement_conflict]`（整列した和集合）、依頼二つ（`record_and_confirm` が `ends: [to]`、`resolve_conflict` が `records: [A, D]`・`ends: [from]` の順） |
| O47 | A の `capabilities` に未知の能力 | unassessed、`[unknown_capability]` |
| O48 | A の単位を `fiction:future-unit`（語彙にない） | unassessed、`[unknown_unit]` |
| O49 | specimen のみ differ（B の specimen の version を 2） | not_representable、`[contexts_differ]`、differences の field は specimen |

### 4.6 データだけで足す出力先・複数の出力先（V2・Y5・Y6・Y7）

| ID | 入力 | 期待 |
| --- | --- | --- |
| O50 | `P-E1` を参照する問い合わせ（標準） | satisfied。`output.unit_ref`＝u_ten、換算領域は点 2。ライブラリと仕様の変更はない |
| O51 | 要素 `laterality`（未知の要素の種類） | `unsupported_profile`、`unsupported_requirement_element` |
| O52 | 出力の種類 `form_letter` | `unsupported_profile`、`unsupported_output_kind` |
| O53 | `context` の field が `laterality`／requires が `equal_to_previous`／`value` の form が `range` | `unsupported_profile`、順に `unsupported_context_field`／`unsupported_context_requirement`／`unsupported_value_form` |
| O60 | `line`（`q1`）、`exchange` @2（`q2`）、`trend`（`q3`）を一つの要求に | 三つとも satisfied、同じ記録 A を選択。M＝97。`q1`＝text `20.0`、`q2`＝領域 20、`q3`＝`[equal]` |
| O61 | O60 の操作・出力先・view・問い合わせの配列を逆順に | 結果の意味（状態・出力・依頼・選択）は O60 と同じ。`ledger` の順は操作の順 |
| O62 | O60 に、参照時点（day8）より後の操作（記録 `F`〔day12〕と確認〔day13〕）を足す | 結果の意味は O60 と同じ。`ledger` と料金だけが変わる（C は大きくなる） |

### 4.7 実装中に足した例（事前に固定した表の外）

実装のテストで、集約の優先（LD6）の変異（`not_representable` と `needs_information` の入れ替え）を、上の表のどの例も検出しないことが分かりました。表せない要素と足りない要素を一行に並べる例が表になかったためです。次の2例を、設計63の LD6（unassessed > not_representable > needs_information > satisfied）から手で導いて足しました。事前の固定ではなく、**検出の欠落を見つけた後の追加**です。期待は変異を見てから作らず、LD6 の優先だけから導いています。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O08 | A の method を `unknown`。出力先は `exchange`、要素：value（`domain`、単位 `v_base`〔次元が違う〕）、context：method known | **not_representable**、理由 `[unit_not_convertible]`。要素の状態：selection met、value unrepresentable、context:method unmet。**依頼は空**（足りない要素の依頼は、行が `needs_information` のときだけ出す）。`flows`＝retained [] lost [value] added []。M＝32 |
| O09 | 同じ記録。value の単位を `fiction:future-unit` | **unassessed**、理由 `[unknown_unit]`。要素の状態：selection met、value unassessed、context:method unmet。依頼は空。M＝32 |

## 5. 静的検査の期待（N）

入力の不正は予算に依らず同じ結果（予算 0・1・7でも）。

| ID | 入力 | 状態 | reason_codes |
| --- | --- | --- | --- |
| N01-missing | `library`／`destinations`／`views`／`queries`／`consumer`／`budget` を欠く | invalid_input | `missing_field` |
| N01-extra | 要求の最上位に `source`・`ledger`・`result`・`certificate` など | invalid_input | `unknown_field` |
| N01-null | `library` が null | invalid_input | `expected_object` |
| N01-empty | `destinations`／`views`／`queries`／`slots` が空 | invalid_input | `empty_collection` |
| N01-duplicate | slots／operations／views／queries の id の重複 | invalid_input | `duplicate_identifier` |
| N01-destination | 同じ（id, version）の出力先が二つ | invalid_input | `duplicate_destination` |
| N02 | 問い合わせの `view_ref`／`slot_ref`／`destination_ref` が存在しない | invalid_input | `unresolved_view_ref`／`unresolved_slot`／`unresolved_destination` |
| N02-ops | `confirm` の `record_ref`／`correct` の `corrects` が存在しない | invalid_input | `unresolved_record` |
| N03-kind | 操作の kind が未知 | unsupported_profile | `unsupported_operation_kind` |
| N03-hash | 操作が `record_sha256`・`quantity_ref` の欄を持つ | invalid_input | `unknown_field` |
| N03-missing | 操作の必須の欄を欠く | invalid_input | `missing_field` |
| N03-p2i | 期間 end≤start／確認が記録より前／訂正の期間が元に含まれない／訂正の対象が bounded でない／値の分母が0／分子が63bitを超える／量種と単位の次元の不一致／property と量種の不一致 | invalid_input（分子の上限は resource_limit、bounded でない訂正は unsupported_profile） | P2-i が検出する理由：`invalid_validity_interval`／`review_precedes_record`／`invalid_revision_interval`／`unsupported_revision_scope`／`invalid_rational`／`rational_integer_limit`／`input_dimension_mismatch`／`property_quantity_kind_mismatch` |
| N04-profile | 要素の組み合わせの矛盾（`line` に value がない、`trend` に value がある、`line` の form が domain）／構造の誤り | invalid_input | `invalid_destination_profile` |
| N04-places | decimal_places が負・bool／7 | invalid_input／unsupported_profile | `invalid_decimal_places`／`unsupported_decimal_places` |
| N05 | `trend` の from_at が to_at 以後／`line`・`exchange` に from_at／`trend` に target_at | invalid_input | `invalid_trend_order`／`unknown_field`／`missing_field` |
| N06 | consumer の profile・仕様 hash・P2-i の profile・仕様 hash・量の profile・仕様 hash の誤り | unsupported_profile | `unsupported_profile`／`profile_spec_mismatch`／`temporal_measurement_profile_mismatch`（二つ）／`quantity_profile_mismatch`（二つ） |
| N06-format | 仕様 hash が64桁の16進でない | invalid_input | `invalid_sha256` |
| N07 | 予算が負・bool・100001 | invalid_input／resource_limit | `invalid_step_budget`／`step_budget_limit` |
| N08 | 操作が257件／出力先が17件／問い合わせが33件 | resource_limit | `item_limit` |

## 6. 資源の期待（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | O01（M＝32）。予算 0・1・16・17・30・31・32・33 | 状態は予算≧32 で ok、他は resource_limit。steps_used＝min(予算, 32)。行は予算≧31 で完成、未満で未完了（五欄 null、`reason_codes＝[step_limit]`）。予算＝31 は行が完成し `incomplete＝[{stage: completion, reason_codes: [step_limit]}]` |
| B02 | O40（M＝47）。予算 27・28・45・46・47 | 行は予算≧46 で完成 |
| B03 | O60（M＝97）。予算 49・50・63・64・77・78・95・96・97 | 行 `q1` は予算≧64、`q2` は≧78、`q3` は≧96 で完成。最後の1は97 |
| B04 | 全計画の料金が上限を超える（64 view × 32 問い合わせ、可視の記録64）。予算 100000 | resource_limit、steps_used＝100000、全行未完了、P2-i は呼ばれない |

## 7. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1（V3） | 文脈の状態（method：known／unknown／unspecified、specimen：同）× 保留中の候補の有無（なし／AI 由来の候補〔method known〕／人由来の候補）× 選択の種類（単一／部分訂正）の全数の台帳で、`P-B1`→`P-B2`→`P-B3` の依頼の数の差 | 差＝「選択された記録の method が known でない」(1) と「specimen が known でない」(1) の数。method・specimen がともに known なら0。依頼の数＝新しく要求される欄で known でないものの数 |
| D2（V4） | 保留中の AI 候補があるすべての台帳 | 候補は `candidates` にだけ現れ、要素が met になることはない。人の確認の後は met |
| D3（V5） | 全ての出力のある行 | `selection` が非 null。`exchange` の出力は `origin` と `human_confirmed` を持つ。`flows` が §3 の表と一致 |
| D4（V2） | 出力先の名前（id）を別の名前に替えた同じ要素の出力先 | 結果の意味（状態・出力・依頼）は同じ |
| D5（Y6） | 操作・出力先・view・問い合わせの順序を入れ替える | 結果の意味は同じ |
| D6（Y7） | 参照時点より後の妥当な操作を足す | 完成した行の状態・出力・依頼・選択は同じ |
| D7（V9） | 乱数の要求 | 料金 M＝2＋C＋Σfee。P2-i の実費は C、P2-f の実費は予約（換算8、比較12）と一致 |

## 8. 継承の証人（V7）

宣言する継承は3項目。証人の組は、**入力の構造が断片について等しい**既存の例どうしから選ぶ（出力を見て選ばない）。

| 継承する側の項目 | 元 | 証人（元の例 ↔ O の例、位置） |
| --- | --- | --- |
| 丸めの数式（義務 CL-7） | p2-temporal-display | j02-5 ↔ O02-5-4、j02-27 ↔ O02-27-20、j02--5 ↔ O02-m5-4、j02--27 ↔ O02-m27-20、j06-5 ↔ O02-5-2、j06-7 ↔ O02-7-2（元：`results[0].artifact.text`、こちら：`results[0].output.text`） |
| 二時点の関係と文脈の規則 | p2-longitudinal-comparison | l01 ↔ O40、l04 ↔ O41（元：`results[0].relation_set`、こちら：`results[0].output.relation_set`）、l20 ↔ O42（元：`results[0].context_differences[0].field`、こちら：`results[0].elements[1].differences[0].field`） |
| 全計画の料金 C | p2-temporal-measurement | c01 ↔ O01、c25 ↔ O40（元：`steps_used`、こちら：`temporal_measurement.reserved_steps`） |

予測：証人は計11（丸め6、関係と文脈3、料金2）。全て登録時に一致する。

**実装時の差**：宣言した証人は計16（丸め8、関係と文脈5、料金3）で、上の表より5つ多い。足したのは、丸めの `j06--5`↔O02-m5-2・`j06--7`↔O02-m7-2、関係の `l02`↔O44、文脈の `l23`↔O49、料金の `c30`↔O41 で、いずれも入力の構造が等しい例の組（出力を見て選んでいない）。表の予測を書き換えず、ここに差として残す。`affected()`：`display.py`・`temporal_display` の変更はこの拡張を含む（V10）。

## 9. 検出すべき変異（実装時に選ぶ候補）

要素の判定の省略（文脈を見ない、single_point を見ない）、推測の補完（method が未知なら既定を入れる）、AI 候補の昇格（保留中の候補で要素を met にする）、後勝ち（競合を解決する）、集約の優先の入れ替え、依頼の重複・欠落、満たされた行の依頼、`output` の漏れ（満たされない行に出力）、丸めの方向（half-up）、端点の取り違え、先払いの省略（fee）、子の予約の誤り、プロファイルの id による分岐、未知の要素の受理、`ends` の取りこぼし。

## 10. 前提と限界

- 期待は設計63から手で導いた値です。P2-i の振る舞い（保留中の記録、候補、理由）は、[43](43-p2-i-design.md)・[44](44-p2-i-cases.md) と P2-i の例の手指定の期待に従います。
- 丸め・関係の数式は P2-j・P2-m と同じ規則の再述で、継承の宣言と証人で結びます。同じ規則だから正しい、という保証ではありません。
- 依頼の内容（どの行動をとるか）は、このライブラリの作業定義です。臨床の手順や、実際の画面の質問ではありません。
- 要求の版 v1→v2→v3 は架空です。実在する出力先の要求ではありません。
