# P2-m：縦断比較の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計56](56-p2-m-design.md) の§8 の予測 W1〜W8 と反例 X1〜X9 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・単位・property はすべて架空です。

## 1. 標準の入力

[P2-i の標準の入力](44-p2-i-cases.md) を使います。

| 項目 | 標準 |
| --- | --- |
| slot | S（主体 u） |
| 数量 | Q＝点 2 `u_ten`（量種 k_a）。QB＝点 3、QC＝点 4（いずれも `u_ten`） |
| 記録 | A（S、期間 [10/1, 10/10)、記録 10/2、確定、method m v1、specimen s v1、property A@1、観測）。B は A を 10/4〜10/6 で部分訂正（QB、記録 10/6、確認 10/7）。C は B を 10/5〜10/6 で部分訂正（QC、記録 10/8、確認 10/9） |
| 確認 | RA（10/3）、RB（10/7）、RC（10/9）。いずれも人・内容一致 |
| view | v（参照時点 k＝10/8）。方針 `fiction:reviewed-scoped-measurement@1` |
| query | a（S、`u_base`、target_at 10/3）、b（S、`u_base`、target_at 10/5）。時点 n は 10/n |
| 比較 | c（view v、from a、to b、方針 `fiction:independent-time-variables@1`、必須能力 `[p2-longitudinal-comparison-draft-1]`） |

換算：`u_base`＝1、`u_ten`＝10、`u_half`＝1/2、`u_hundred`＝100（P2-l 後の表）、次元の違う `v_base`。標準の A は 2 `u_ten`＝20 `u_base`。

## 2. 料金の設計値（手計算）

C は P2-i の全計画の料金（[設計43の§6](43-p2-i-design.md)）、M＝1＋C＋18×比較数＋1。

| 入力 | 内訳 | C | 比較数 | M |
| --- | --- | --- | --- | --- |
| 標準（記録A一つ、query a・b） | 3＋(1＋1)＋2×(2＋1＋0＋8)＝27 | 27 | 1 | 47 |
| 同じで比較二つ | | 27 | 2 | 65 |
| A／B（B が A を部分訂正、k＝10/8）、query a・b | 4＋(2＋2)＋2×(2＋2＋1＋8)＝34 | 34 | 1 | 54 |
| A／B／C（k＝10/9）、query 4つ（3・4・5・6） | 5＋(3＋3)＋4×(2＋3＋2＋8)＝71 | 71 | 3 | 127 |
| 標準に参照時点より後の記録Fを追加（Q を共有、記録 10/12、確認 10/13） | 3＋(2＋2)＋2×(2＋1＋0＋8)＝29 | 29 | 1 | 49 |
| A／B、二view（k＝10/6、10/8）、query a・b | 4＋[(2＋2)＋2×(2＋2＋0＋8)]＋[(2＋2)＋2×(2＋2＋1＋8)]＝4＋28＋30＝62 | 62 | 2 | 100 |

k＝10/6 の view では B は見えるが確認（10/7）が見えないので適格でなく、訂正辺を数えない。

## 3. 意味の期待（L：選択・関係・文脈・停止）

行は比較 c の行。特記がなければ、root は ok、`meaning_mode＝longitudinal_measurement_comparison`、`converted_to_base＝false`、`clinical_assertions_added＝[]`、`clinical_confirmation＝not_evaluated`、`review_verification＝structural_only`、`uncertainty_propagated＝false`、`time_correlation_assumed＝false`、`clinical_significance＝not_evaluated`、`certificate.status＝not_certified`。computed の行は `context_differences＝[]`、`comparison_evidence.assumptions＝[independent_time_variables, explicit_period_quantity_domain, scoped_revision]`、`comparison_evidence.direction＝from_relative_to_to`、`quantity_compare` の予約12・実費12、`temporal_measurement` の予約＝実費＝C。

### 3.1 関係（X1・X9・W2・W7）

| ID | 入力 | 期待 |
| --- | --- | --- |
| L01 | 標準。A を t＝3 と 5 で比べる | computed。`relation_set＝[equal]`、certain `equal`。端点は両方 A。M＝47 |
| L02 | Q を幅 [1,2] `u_ten`（閉）にする | 両端点 [10,20]。`relation_set＝[less, equal, greater]`、certain null（同じ記録でも alias にしない） |
| L03 | Q を [1,2)（上端開）にする | 両端点 [10,20)。`[less, equal, greater]`、certain null |
| L04 | A／B。B は QB＝点 3、文脈は A と同じ。t＝3 と 5 | 端点 A（20）と B（30）。`[less]`、certain `less`。M＝54 |
| L05 | L04 で QB＝点 1 | 端点 A（20）、B（10）。`[greater]`、certain `greater` |
| L06 | L04 で QB＝点 2 | A（20）と B（20）。`[equal]`、certain `equal`（別の記録でも点どうしは定まる） |
| L07 | A／B。QA＝[1,2]、QB＝[2,3]（いずれも閉）。t＝3 と 5 | [10,20] と [20,30]。`[less, equal]`、certain null |
| L08 | QA＝[1,2)（下端閉・上端開）、QB＝(2,3]（下端開・上端閉） | [10,20) と (20,30]。接する点 20 はどちらも含まない。`[less]`、certain `less` |
| L09 | QA＝点 3/2、QB＝[1,2] | 15 と [10,20]。`[less, equal, greater]` |
| L10 | QA＝点 1/2、QB＝[1,2] | 5 と [10,20]。`[less]`、certain `less` |
| L11 | QA＝点 −3/2、QB＝点 −2 | −15 と −20。`[greater]`、certain `greater` |
| L12 | L01 で端点の目標単位を変える：a→`u_base`、b→`u_ten`（同じ記録 A） | 端点 from は 20 `u_base`、to は 2 `u_ten`。`[equal]`、certain `equal` |
| L13 | L01 で b→`u_half` | 端点 from は 20 `u_base`、to は 40 `u_half`（`u_half` の倍率は 1/2）。同じ量なので `[equal]`、certain `equal` |

L12・L13 は、表す数が違っても同じ量なので関係は `equal` です。数だけを比べると `less` や `greater` に誤るため、導出リテラルが目標単位を保つことの検出に使います（W7）。

### 3.2 比較可能性（X2・W4）

A／B。B は A を部分訂正し、特記の欄だけ A と違う。t＝3（A）と t＝5（B）。

| ID | B の違い | 期待 |
| --- | --- | --- |
| L20 | method の version だけ（2） | not_comparable、`[different_method]`、`context_differences＝[{field: method, from: A の method, to: B の method}]`。relation_set／certain null、`comparison_evidence` null。端点の行は保持。M＝54 |
| L21 | method の ref だけ | `[different_method]` |
| L22 | specimen の ref だけ | `[different_specimen]` |
| L23 | specimen の version だけ | `[different_specimen]` |
| L24 | property を A-other@1 にする（量種は同じ k_a） | `[different_property]` |
| L25 | 上の三つ全部 | `[different_method, different_property, different_specimen]`。`context_differences` は同じ順 |
| L26 | 値・origin（観測→判断）だけ違う | computed（文脈の一致は値・出自に依らない）。値は L04 に従う |
| L27 | L20 の B で、t＝3 と **t＝7**（B の期間外）を比べる | 両端点が A。文脈は一致。computed、`[equal]`（B の文脈の違いは、選ばれなかった記録なので影響しない） |
| L28 | L20 の B で、t＝5 と t＝6 を比べる（t＝6 では A） | 端点 B と A。`[different_method]` で not_comparable（比べる順に依らず不一致） |

### 3.3 端点が止まる場合（X3・W5）

| ID | 入力 | 期待 |
| --- | --- | --- |
| L30 | 標準で b の target_at を 10/11（A の期間外） | 端点 to が unassessed／`no_adopted_measurement`。比較は unassessed、理由 `[no_adopted_measurement]`、`context_differences` null、`endpoints.from.status＝computed`、`endpoints.to.status＝unassessed`、`comparison_evidence` null。M＝47 |
| L31 | a を 10/11、b を 10/12 | 両端点が `no_adopted_measurement`。理由は重複なしで `[no_adopted_measurement]` |
| L32 | A（期間 [1,10)）と D（別数量 QD、期間 [1,4)、確認あり）に、訂正の関係がない。a＝10/3、b＝10/11 | a は競合 `unresolved_measurement_conflict`、b は `no_adopted_measurement`。比較は unassessed、理由 `[no_adopted_measurement, unresolved_measurement_conflict]` |
| L33 | A と、期間が unknown の確認済み記録 U（記録 10/4、確認 10/5） | 両端点が `validity_unknown`。理由 `[validity_unknown]` |
| L34 | 可視の記録に未知の能力 | 両端点が `unknown_capability`。比較は unassessed、理由 `[unknown_capability]`、**endpoints は保持**（診断あり） |
| L35 | 比較自身の必須能力に未知のもの | unassessed／`[unknown_capability]`。**endpoints・evidence・context_differences は null**。M＝47 |
| L36 | 比較が二つ（c1：未知能力、c2：標準）。同じ計画 | c2 は computed `[equal]`。c1 の停止が c2 に影響しない。M＝65 |
| L37 | b の目標単位を次元の違う `v_base` にする | 端点 to は not_comparable／`incompatible_dimension`。比較は **unassessed**、理由 `[incompatible_dimension]`、`endpoints.to.status＝not_comparable` |
| L38 | B が suspected（確認あり）で、t＝3 と 5 | B は適格でない。t＝5 は A。computed `[equal]`、端点は両方 A。`endpoints.to.diagnostics.pending_records` に B |

### 3.4 参照時点・再現（C・G）

| ID | 入力 | 期待 |
| --- | --- | --- |
| L40 | 標準に、参照時点より後の記録 F（10/12）と確認（10/13）を追加 | 関係・端点の選択は L01 と同じ。source hash・料金だけが変わる（M＝49） |
| L41 | A／B、二view（k＝10/6 と 10/8）。比較 c6（view＝6）と c8（view＝8）、query a・b | c6：B の確認が見えないので両端点が A、`[equal]`。c8：A と B、`[less]`。M＝100 |
| L42 | 標準の四表・views・queries・comparisons を逆順にする | 結果は ID 順で L01 と同じ関係・端点。入力 hash は変わり得る |
| L43 | 同じ組を二つの ID（c1、c2）で比べる | 二行は ID 以外同一 |
| L44 | A／B／C（k＝10/9）、query t＝3・4・5・6（ID a・b・c・d）、比較 ab・bc・cd | 値は A＝20（t＝3、6）、B＝30（t＝4）、C＝40（t＝5）。ab `[less]`、bc `[less]`、cd `[greater]`。M＝127。ac のような比較を **推移から導くことはしない** |
| L45 | A と Q を ai_candidate にし、内容一致の確認を付ける | computed `[equal]`。端点の `record_origin.kind`／`quantity_origin.kind` が `ai_candidate`。`clinical_assertions_added＝[]` |

### 3.5 接続面の閉包（X6・W6）

| ID | 入力 | 期待 |
| --- | --- | --- |
| L50 | Q＝点 2^62（63bit）`u_ten`。a・b とも目標 `u_base` | P2-i は 10×2^62（66bit）を計算する。P2-f の入力は63bitまで。root は **resource_limit**、`reason_codes＝[rational_integer_limit]`、steps_used＝1＋27＋18＝46、行は unassessed／未完了で五欄 null、`incomplete＝[{comparison: c, reason_codes: [rational_integer_limit]}]`、認定なし |
| L51 | L50 で目標を `u_ten`（元の単位） | 値は 2^62 のまま（63bit）。computed `[equal]` |
| L52 | Q＝点 2^62 `u_base`、目標 `u_base` | computed `[equal]`（境界：63bit は通る） |
| L53 | L50 で a だけ `u_ten`、b を `u_base` | 端点 from の導出リテラルは63bit、to は66bit。**どちらか一方の超過でも止まる**。L50 と同じ resource_limit |

## 4. 静的検査の期待（N）

状態と理由コード（予算に依らず同じ）。

| ID | 入力 | 状態 | reason_codes |
| --- | --- | --- | --- |
| N01-missing | `comparisons`／`temporal_measurement_plan`／`consumer`／`budget` のいずれかを欠く | invalid_input | `missing_field` |
| N01-null | 計画が null | invalid_input | `expected_object` |
| N01-extra | 要求・比較に未知の欄（例：`artifact`、`child_result`、`certificate`） | invalid_input | `unknown_field` |
| N01-duplicate | 比較 ID の重複 | invalid_input | `duplicate_identifier` |
| N01-empty | 比較が空 | invalid_input | `empty_collection` |
| N01-count | 比較が65件 | resource_limit | `item_limit` |
| N02-view／from／to | 参照が計画にない | invalid_input | `unresolved_view_ref`／`unresolved_from_query_ref`／`unresolved_to_query_ref` |
| N03-same／equal-time／reversed | from＝to の query、異なる query で target_at が同じ、from が後 | invalid_input | `invalid_comparison_order` |
| N04 | 二つの query の slot が異なる | unsupported_profile | `unsupported_cross_slot_comparison` |
| N05-policy | 方針が `fiction:same-variable-within-record@1` | unsupported_profile | `unsupported_comparison_policy` |
| N05-type | 方針が文字列でない | invalid_input | `expected_nonempty_string` |
| N06-missing | 必須能力に自己の profile がない | invalid_input | `missing_comparison_capability` |
| N06-type | 必須能力が配列でない | invalid_input | `expected_array` |
| N07 | consumer の profile・仕様 hash・P2-i の profile・仕様 hash・量の profile・仕様 hash の誤り | unsupported_profile | `unsupported_profile`／`profile_spec_mismatch`／`temporal_measurement_profile_mismatch`（二つ）／`quantity_profile_mismatch`（二つ） |
| N07-format | 仕様 hash が64桁の16進でない | invalid_input | `invalid_sha256` |
| N08-schema／policy／compare | 計画の schema の誤り、P2-i の view の方針の誤り、query が compare | unsupported_profile | `unsupported_temporal_measurement_schema`／`unsupported_policy`／`unsupported_query_kind` |
| N09-budget | 計画に予算の欄がある | invalid_input | `unknown_field` |
| N10-quantity／validity／review | 数量・期間を変えたのに確認の hash が旧い、確認が記録より前 | invalid_input | `quantity_reference_hash_mismatch`／`review_record_hash_mismatch`／`review_precedes_record` |
| N11-budget | 予算が負・bool・100001 | invalid_input／resource_limit | `invalid_step_budget`／`step_budget_limit` |

入力の不正は予算に依らず同じ結果です（予算0、1、7でも）。

## 5. 資源の期待（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | 標準（M＝47）。予算 0・1・27・28・45・46・47・48 | 状態は予算≧47 で ok、他は resource_limit。steps_used＝min(予算, 47)。行は予算≧46 で完成（関係あり）、未満で未完了（五欄 null、`reason_codes＝[step_limit]`）。予算＝46 は行が完成し `incomplete＝[{stage: completion, reason_codes: [step_limit]}]`。認定なし |
| B02 | 比較二つ（M＝65）。予算 27・28・45・46・63・64・65 | 行0 は予算≧46 で、行1 は予算≧64 で完成。他は未完了。完成した行は後の停止で変わらない |
| B03 | A／B（C＝34、M＝54）。予算 34・35・52・53・54 | 予算 34 は子の先払いの途中、35 は子を実行した後で行は未払い（steps_used＝35）、53 で行が完成、54 で ok |
| B04 | 意味上停止する標準（L30、M＝47）。予算 47 | 状態 ok、steps_used＝47（意味上止まる行でも全額を払う） |
| B05 | 全計画の料金が上限を超える（64 view × 64 query、記録20）。予算 100000 | resource_limit、steps_used＝100000、全行未完了、**子の P2-i は呼ばれない** |
| B06 | 子の P2-f が部分結果を返す／資源停止する（注入） | root は resource_limit。途中の値を拾わない。先に完成した比較は保持 |

予算の掃引では、完成した行の値が予算を増やしても変わらず、未完了の行の五欄はすべて null（空の object・配列・false にしない）、資源停止の root は認定されません。

## 6. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1 | 全ての（view、query）について、`endpoints` の行は、同じ計画を P2-i に直接渡した結果の行と完全に一致する | 継承の差分 0（W8、LC-7） |
| D2 | 文脈を property（A@1、A-other@1）× specimen（s v1、s v2、別 ref）× method（m v1、m v2、別 ref）の18通りに変えた二つの記録の全324対について、P2-m（A と、A を部分訂正する B を、t＝3 と 5 で比較）の `different_*` の理由集合は、P2-g（二つの slot に同じ主体・同じ瞬間の記録を置き、文脈だけを同じ組にして `matched_context` で比較）の `different_property`／`different_specimen`／`different_method` の部分と一致する | 一致（W4） |
| D3 | 目標単位を同じ次元の単位の全ての組（63bit に収まる範囲）で変えて、関係の集合が不変 | 不変（W7） |
| D4 | 点・幅（閉・開・半開）・符号・単位の全数（小さい列挙）で、P2-m の関係が、元のリテラルを直接 P2-f の別計算で比べた関係と一致する | 一致（第二の経路） |
| D5 | 妥当な未来の記録・確認の追加 | 完成した比較の関係・端点の選択は不変 |
| D6 | 入力の不変性（呼び出しの前後で入力が同一）、四表の並べ替えで結果の意味が不変 | 不変 |

## 7. 検出すべき変異（実装時に選ぶ候補）

alias（二端点を同じ ID にする）、文脈の判定の省略、property だけを見る、slot の最初の記録の文脈で代用、最新の記録の文脈で代用、端点の入れ替え（from／to を逆にする）、値の中点で比べる、順序の検査の省略、slot の検査の省略、理由の和集合を一方だけにする、`unassessed` の端点でも関係を作る、先払いの省略（18→6）、子の実費の未照合（P2-i の C、P2-f の 12）、導出リテラルの上限超過時に元のリテラルへ切り替える、導出リテラルで目標単位を無視して数だけ渡す、認定票を `certified` にする、臨床の語（`improved` など）を結果に加える。

## 8. 前提と限界

- 期待は設計56から手で導いた値です。標準の入力と料金は [P2-i の手指定44](44-p2-i-cases.md) の計算規則に従い、L13 の単位換算と L08 の接する開区間は、手で端点の包含を確かめた値です。
- 関係の語（less／equal／greater）は算術の関係で、増減・悪化・改善の意味を持ちません。`equal` は「同じ値でありうる」ことを含み、変化がないという臨床の判断ではありません。
- 二点の関係から三点以上の関係を導きません（L44）。
- 導出リテラルの上限（L50〜L53）は、この断片の接続面の制約の記録で、一般の数値処理の性能を主張しません。
