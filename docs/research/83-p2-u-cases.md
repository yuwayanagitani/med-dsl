# P2-u：用語の版更新の監査の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計82](82-p2-u-design.md) の予測 AP1〜AP10・RP1〜RP7 と反例 Z1〜Z12 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・識別子・名称はすべて架空です（実データの語は使いません）。

## 0. 設計82の具体化

| ID | 決定 | 理由 |
| --- | --- | --- |
| C1 | 標準の世界 W（旧版・新版で同一）を下の表に固定する。各例は「W からの差」で書く。用語の `ref`＝`fiction:terminology:drugs`、旧版の `version`＝`2026-09`、新版＝`2026-10` | 手で追える大きさ |
| C2 | 標準の方針 POL＝`[{code_list, administrative}, {strength, definitional}]`。標準の範囲 `scope.sources`＝`[S]`。標準の参照は例ごとに書く | 例の記述を短くする |
| C3 | 結果の行の `facets` の並び：`added`・`removed`・`modified`・属性の差は昇順（原子 id、名前の順）。値の集合は昇順。`requests` は `(element, name)` の昇順。`assumptions` は昇順の文字列 `attribute_class:<名前>:<class>`（差のあった属性のうち宣言されたものだけ） | 並びの規則 |
| C4 | 料金：M＝1＋n_from＋n_to＋Σ参照の料金＋1。範囲外の参照の料金は1。範囲内で旧版にある参照は 1＋A_f＋T_f＋R_f、新版にもあれば A_t＋T_t＋R_t を足す（A＝原子数、T＝属性の数〔原子ごとの `(名前, 値)` の総数〕、R＝関係の数）。n は snapshot の概念数（出典に依らない） | 設計82の UD9 |
| C5 | 集計 `summary`＝`{references, by_state{unchanged_in_scope, changed_administrative_only, changed, needs_information, not_found, not_compared}, from_concepts, to_concepts, in_scope_from, in_scope_to, continuing, from_only, to_only}`。継続＝範囲内で (出典, id) が両版にある概念の数、旧のみ＝範囲内の旧版の概念数−継続、新のみ＝範囲内の新版の概念数−継続。予算が尽きた要求では集計は null | 設計82の UD8 |

### 標準の世界 W（出典は全て `S`）

| 概念 | 原子（id・種類・名称・属性） | 関係 |
| --- | --- | --- |
| c1 | a1・full・`alpha 5 mg tablet`・属性 `code_list=N1`、`strength=5 mg`／a2・syn・`alpha tab 5`・属性なし | `has_ingredient → c9`、`has_form → c8` |
| c2 | a3・full・`beta 10 mg tablet`・属性 `strength=10 mg` | `has_ingredient → c9` |
| c8 | a8・form・`tablet`・属性なし | なし |
| c9 | a9・ingredient・`alpha`・属性なし | なし |

料金の基礎（W のまま新版も W）：n＝4／4。c1＝1＋(2+2)＋(2+2)＋(2+2)＝13、c2＝1＋(1+1)＋(1+1)＋(1+1)＝7、c8＝c9＝1＋(1+1)＝3。

## 1. 例（U 系列）

「状態」は参照の `state`。「面」は継続した参照の `facets`。特に書かない欄は、空（差なし）・`requests` 空・`assumptions` 空・`successor` null。

| ID | 入力（W からの差） | 期待 |
| --- | --- | --- |
| U01 | 参照 [c1, c2]、新版＝W | c1・c2 とも `unchanged_in_scope`（三つの面とも差なし）。集計：旧4・新4・範囲内 4/4・継続4・旧のみ0・新のみ0、`by_state` は `unchanged_in_scope`＝2。M＝1＋8＋13＋7＋1＝30 |
| U02 | 参照 [c1]。新版で a1 の `code_list` が `N1`→`N2`（**Z2**） | `changed_administrative_only`。`attributes.administrative`＝`[{atom a1, name code_list, from [N1], to [N2]}]`、`attributes.state`＝changed、`assumptions`＝`[attribute_class:code_list:administrative]`。M＝1＋8＋13＋1＝23 |
| U03 | 参照 [c2]。新版で a3 の `strength` が `10 mg`→`20 mg`（**Z1**） | 継続（`presence: continues`）だが `changed`。`attributes.definitional`＝`[{a3, strength, [10 mg], [20 mg]}]`、`assumptions`＝`[attribute_class:strength:definitional]`。M＝1＋8＋7＋1＝17 |
| U04 | 参照 [c1]。新版で a2 に属性 `flag=x` が加わる（`flag` は未宣言）（**Z3**） | `needs_information`。`attributes.undeclared`＝`[{a2, flag, [], [x]}]`、`requests`＝`[{element: attribute, action: declare_attribute_class, reference: c1, name: flag}]`、`assumptions` 空。M＝1＋8＋14＋1＝24（c1 の料金は 1＋4＋(2+3)＋4＝14） |
| U05 | 参照 [c1]。新版で c1 に原子 a5（syn・`alpha tab`・属性なし）が加わる（**Z5**） | `changed`。`names.added`＝`[{a5, syn, alpha tab}]`、`names.state`＝changed。M＝24（c1 の料金 14） |
| U06 | 参照 [c1]。新版で a2 の名称が `alpha tab 5`→`alpha tablet 5` | `changed`。`names.modified`＝`[{a2, from {syn, alpha tab 5}, to {syn, alpha tablet 5}}]`。M＝23 |
| U07 | 参照 [c1, c2, c9]。新版で c9 を除き、c1・c2 の `has_ingredient → c9` も除く（**Z6**） | c9：`not_found`、`presence: not_found`、`facets` null、`successor: not_determined`、`requests`＝`[{element: history, action: provide_official_history, reference: c9, name: null}]`。c1・c2：`changed`、`relations.removed`＝`[{has_ingredient, c9, target_in_from true, target_in_to false}]`。集計：旧4・新3・範囲内 4/3・継続3・旧のみ1・新のみ0、`by_state`＝changed 2、not_found 1。M＝1＋7＋12＋6＋2＋1＝29 |
| U08 | 参照 [c2]。新版で c2 の `has_ingredient → c9` だけを除く（c9 は残る） | `changed`、`relations.removed`＝`[{has_ingredient, c9, true, true}]`（対象は残っている）。M＝1＋8＋6＋1＝16 |
| U09 | 参照 [c1]。新版に概念 c10（S、原子 a10・full・`delta`）が加わり、c1 に `has_ingredient → c10` が加わる | `changed`、`relations.added`＝`[{has_ingredient, c10, target_in_from false, target_in_to true}]`。集計：旧4・新5・継続4・旧のみ0・新のみ1。M＝1＋9＋14＋1＝25 |
| U10 | 参照 [c2]。新版で c2 を除き、概念 c11（S）を加える。c11 は c2 と同じ原子（id は a11、種類 full・名称 `beta 10 mg tablet`・属性 `strength=10 mg`）と同じ関係を持つ（**Z4**） | c2：`not_found`、`successor: not_determined`、候補なし、依頼 `provide_official_history`。集計：継続3・旧のみ1・新のみ1。M＝1＋8＋4＋1＝14 |
| U11 | 参照 [c7]。W に概念 c7（出典 `X`、原子 a7・full・`omega`）を加えた旧版と、a7 の名称を `omega2` にした新版（範囲は `[S]`）（**Z7**） | `not_compared`、`presence: not_compared`、`facets` null、依頼なし。集計：旧5・新5・範囲内 4/4・継続4、`by_state`＝not_compared 1。M＝1＋10＋1＋1＝13 |
| U12 | 参照 [c1]。旧版・新版ともに c1 に `has_part → c99`（c99 はどちらの版にもない）を加える | `unchanged_in_scope`。`relations.unresolved_in_to`＝`[{c99, in_from false}]`（旧版でも未解決の既存の状態。差でない）。M＝1＋8＋15＋1＝25 |
| U13 | 参照 [c2]。新版で c9 を除くが、c2 の `has_ingredient → c9` は残す | `changed`。`relations.added`・`removed` は空だが、`unresolved_in_to`＝`[{c9, in_from true}]` なので `relations.state`＝changed。M＝1＋7＋7＋1＝16 |
| U14 | U03 の旧版と新版を入れ替える（旧版の a3 が `20 mg`、新版が `10 mg`）（**Z8**） | `changed`、`definitional`＝`[{a3, strength, [20 mg], [10 mg]}]`。M＝17 |
| U15 | 参照 [c1]。旧版の a1 の `code_list` が `{N1, N2}`、新版が `{N1, N3}` | `changed_administrative_only`、`administrative`＝`[{a1, code_list, [N1, N2], [N1, N3]}]`。M＝1＋8＋15＋1＝25（c1 の料金 1＋4＋(3+3)＋4） |
| U16 | 参照 [c1]。旧版の a2 に属性 `flag=x` があり、新版で a2 が除かれる（**Z9**） | `changed`。`names.removed`＝`[{a2, syn, alpha tab 5}]`、`attributes.state`＝unchanged、`attributes.with_atom_change`＝`{added 0, removed 1}`（属性の差には数えない）。M＝1＋8＋13＋1＝23（c1 の料金 1＋(2+1)＋(3+2)＋4） |
| U17 | 参照 [c1]。新版で `code_list` が `N1`→`N2` に変わり、原子 a5 が加わる | `changed`（名称の差が管理上の属性の差に優先）。`names.added` と `administrative` の両方。`assumptions`＝`[attribute_class:code_list:administrative]`。M＝24 |
| U18 | 参照 [c1]。新版で `code_list` が `N1`→`N2` に変わり、a2 に `flag=x` が加わる | `needs_information`（未宣言の属性の差が管理上の差に優先）。`administrative` 1件・`undeclared` 1件、依頼 `flag`。M＝24 |
| U19 | 参照 [c1, c2]、新版＝W。方針に使われない宣言 `{extra, definitional}` を加える | U01 と同じ状態。`assumptions` 空（使われない宣言は痕跡を残さない）。結果の `policy.attributes` には3件が名前順に並ぶ。M＝30 |
| U20 | 参照 [c2]。方針 `[]`。新版で a3 の `strength` が `10 mg`→`20 mg` | `needs_information`、`undeclared`＝`[{a3, strength, [10 mg], [20 mg]}]`、依頼 `strength`。M＝17 |
| U21 | 参照 [c1]。新版で concepts の並び、c1 の原子・関係・属性の並びを逆順にする（内容は W と同じ）（**Z11**） | `unchanged_in_scope`。M＝23 |
| U22 | 範囲 `[S, X]`、参照 [c7]。U11 の入力 | `changed`、`names.modified`＝`[{a7, from {full, omega}, to {full, omega2}}]`。集計：範囲内 5/5・継続5。M＝1＋10＋3＋1＝15 |
| U23 | 参照 [c2]。新版で c2 の出典が `X`（範囲は `[S]`）（**Z10**） | `not_found`（(出典, id) が違う）。集計：範囲内 4/3・継続3・旧のみ1・新のみ0。M＝1＋8＋4＋1＝14 |
| U24 | 参照 [c1, c2]。旧版＝W から c9 と両方の `has_ingredient → c9` を除いたもの、新版＝W（U07 の入れ替え）（**Z8**） | c1・c2：`changed`、`relations.added`＝`[{has_ingredient, c9, target_in_from false, target_in_to true}]`。集計：旧3・新4・継続3・旧のみ0・新のみ1。M＝1＋7＋12＋6＋1＝27 |
| U25 | 旧版＝W に c3（S、原子 a4・full・`gamma 1 mg`・属性 `strength=1 mg`）と c7（出典 X）を加えたもの。新版＝c3 を除き、a2 に `flag=x` を加え、a3 の `strength` を `20 mg` にし、a9 に `code_list=N9` を加えたもの。参照 [c1, c2, c3, c7, c8, c9] | c1：`needs_information`。c2：`changed`。c3：`not_found`。c7：`not_compared`。c8：`unchanged_in_scope`。c9：`changed_administrative_only`（`administrative`＝`[{a9, code_list, [], [N9]}]`）。集計：旧6・新5・範囲内 5/4・継続4・旧のみ1・新のみ0、`by_state` は六つの状態が各1。M＝1＋11＋(14+7+3+1+3+4)＋1＝45 |
| U26 | U01 に、旧版・新版の `source_sha256`（架空の64桁の16進）を足す | 結果の `versions.from.source_sha256`・`versions.to.source_sha256` に同じ値がそのまま出る。他は U01 と同じ。M＝30 |
| U27 | 範囲 `[S, X]`、参照 [c2]。新版で c2 の出典が `X`。**実装中に足した例**（変異「集計の継続が出典を見ない」が U23 では見逃されたため。U23 は範囲が `[S]` で、新版の c2 が範囲の外になり、継続の集計の出典の検査に届かない）（**Z10**） | `not_found`（(出典, id) が違う）。集計：旧4・新4・範囲内 4/4・継続3・旧のみ1・新のみ1（新版の c2 は出典 X の別の概念）。M＝1＋8＋4＋1＝14 |

## 2. 静的検査（N）。いずれも U01 の入力を壊す

| ID | 壊し方 | 期待 |
| --- | --- | --- |
| N01 | トップレベルの `operation`・`consumer`・`from`・`to`・`scope`・`policy`・`references`・`budget` の欠落（8）／余分な欄／`from` が object でない | `missing_field`／`unknown_field`／`expected_object` |
| N02 | `consumer` の `profile`・`profile_spec_sha256` が別の値 | `unsupported_profile`／`profile_spec_mismatch`（状態は unsupported_profile） |
| N03 | `operation`／`consumer.operations` が別 | `unsupported_operation` |
| N04 | `from.concepts` の欠落／`from.concepts` が配列でない | `missing_field`／`expected_array` |
| N05 | `to.ref` が `from.ref` と違う（**Z12**） | `system_mismatch`（unsupported_profile） |
| N06 | `to.version` が `from.version` と同じ（**Z12**） | `same_version` |
| N07 | 重複：旧版の概念 id／原子 id（別の概念にまたがる）／同じ概念の同じ `(種類, 対象)` の関係／同じ原子の同じ `(名前, 値)` の属性／方針の同じ名前／参照 | `duplicate_identifier`／`duplicate_identifier`／`duplicate_relation`／`duplicate_attribute`／`duplicate_policy`／`duplicate_reference` |
| N08 | 方針の `class` が `clinical` | `unsupported_attribute_class`（unsupported_profile） |
| N09 | 参照が旧版にない id | `unresolved_reference` |
| N10 | `references` が空／`scope.sources` が空／参照257件／概念513件／一つの概念に原子33件／方針65件 | `empty_collection`／`empty_collection`／`item_limit`（resource_limit）×4 |
| N11 | 原子の `kind` が空文字／概念の `source` が数／関係に `target` がない／属性に余分な欄／`source_sha256` が64桁の16進でない | `expected_nonempty_string`／`expected_nonempty_string`／`missing_field`／`unknown_field`／`invalid_sha256` |
| N12 | `budget.max_steps` が bool／負／上限超過 | `invalid_step_budget`／`invalid_step_budget`／`step_budget_limit`（resource_limit） |

## 3. 資源（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | U01、M＝30（開始 1、索引 8 で 9、c1 の後 22、c2 の後 29、最後の確定 30）。予算は 0・1・8・9・21・22・28・29・30 | 予算が足りる行は U01 の期待、足りない行は全欄 null で `step_limit`。集計は予算30のときだけ値あり。`incomplete` は未完了の参照と（29のとき）最後の確定 |
| B02 | U07、M＝29（開始 1、索引 7 で 8、c1 の後 20、c2 の後 26、c9 の後 28、最後の確定 29）。予算は 0・1・7・8・19・20・25・26・27・28・29 | 同様 |

## 4. 差分・不変性の検査（有限・乱数）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1 | 全数：差の種類（なし・名称・関係・定義の属性・管理上の属性・未宣言の属性）の部分集合 × 継続／不在 × 方針の宣言（あり／なし） | 別計算と一致。各参照がちょうど一つの状態 |
| D2 | 乱数：概念20〜40、原子・関係・属性の乱数の変更（追加・削除・値の変更・出典の変更・概念の除去と追加）、方針の乱数 | 別計算と一致。集計の和＝参照の数 |
| D3 | 入れ替え：任意の要求の旧版と新版を入れ替える | 継続した参照の各面で追加と削除、値の from と to が入れ替わる。`not_found` と新のみの数が入れ替わる（範囲が両版で同じ場合） |
| D4 | 並びの入れ替え（概念・原子・関係・属性・参照・方針） | 結果は同じ |
| D5 | 継続の独立：名称・属性・関係をそのまま別の ID に移した概念を加える | 旧版の概念の状態は変わらない（`not_found`）。候補は出ない |
| D6 | 料金 | M の式が全要求で成り立つ |
| D7 | 属性値の文字列を替えても判定は不透明のまま同じ | 文字列以外は不変 |

## 5. 検出すべき変異

継続を名称の一致で決める、`not_found` に後継の候補を返す、`successor` を決める、未宣言の属性を `administrative` や `definitional` に推測する、使われない宣言を `assumptions` に載せる、優先順（`changed`／`needs_information`／`changed_administrative_only`）の取り違え、範囲外の参照を比較する、範囲外を差なしに数える、関係の対象の存在の旗を取り違える、未解決の既存の状態を差に数える、追加・削除された原子の属性を属性の差に数える、原子の並びで差を作る、(出典, id) を id だけにする、先払いの省略、最後の確定の省略、`inferred_information` に値、`certified`、方針の `class` の集合を広げる、`reverse_inferred` を真にする、集計の和の誤り。

## 6. 実データの実行（道具、予測は設計82の RP1〜RP7）

実データの結果は予測と既知の値の別に集計する。道具の正規化の写像は、架空の RRF 形式の ZIP（`RXNCONSO`・`RXNREL`・`RXNSAT` の列の位置を持つ数行）で確かめる：(a) 概念＝`SAB=RXNORM` の `RXCUI`、原子＝`RXAUI`・`TTY`・`STR`。(b) 関係の所有者＝`RXCUI2`、対象＝`RXCUI1`、種類＝`RELA`（空なら `REL`）、`STYPE1`・`STYPE2` が `CUI` の行だけ。(c) 属性＝`STYPE=AUI` の行を `RXAUI` の原子に付ける。(d) 重複する行は一つ。(e) 原子に結べない属性・原子対原子の関係・`RXNORM` 以外の行の件数を報告。

## 7. 前提と限界

- 期待は設計82から手で導いた値です。料金は、手で導いた式で求めました。実装の値と食い違ったときは、実装・式の読み・期待のどれが誤りかを調べて記録します。
- `required_paths` の fixture は配列の長さを確かめられないので、`results` の数と項目の数は、別計算の全数と乱数（D1・D2）で確かめます。
- 属性の分類は宣言で、実データの分類（P-full、P-partial）は作り手の研究上の仮定です。出典の変更は別の概念として扱い、同じ ID が別の出典に現れたことを区別して報告しません（Z10 の限界）。
- 実データの行（概念の ID・名称・属性）は文書に書きません。集計と方法だけを残します。
