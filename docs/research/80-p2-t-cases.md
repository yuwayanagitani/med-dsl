# P2-t：Provenance の activity の符号と revision の entity の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計79](79-p2-t-design.md) の予測 T1〜T10 と反例 Z1〜Z12 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・識別子はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。P2-q の fixture 名（Q01 など）は [71](71-p2-q-cases.md) の入力の呼び名で、「Q25 の入力」は P2-q の fixture Q25 と同じ要求（P2-q の宣言と台帳）を指す。

## 0. 設計79の具体化

| ID | 決定 | 理由 |
| --- | --- | --- |
| C1 | 宣言の例：`Dt(activities, revision)`＝`{destination_ref: P-B1, activities, revision}`（`activities` が空、`revision` が偽のときは該当の欄を省く場合がある）。活動の符号の定数：`C1`＝`{system: fiction:activity-system:s, code: fiction-create}`、`C2`＝`{…s, code: fiction-correct}`、`C3`＝`{…s, code: fiction-confirm}`。`A_ALL`＝`{creation: C1, correction: C2, confirmation: C3}` | 架空の符号 |
| C2 | 項目の種類：確認の項目＝`confirmation`。生成側の項目（P2-q が `creation` と呼ぶもの）は、選ばれた記録が訂正なら `correction`、そうでなければ `creation` | 設計79の TD4 |
| C3 | `coding.entries[i]` は P2-q の `observation.provenance[i]` と同じ順序・同じ数。`index`＝i | 添字で結ぶ |
| C4 | `revision.state` の優先：`not_applicable`→`not_requested`→`no_provenance`→`no_agent`→`carried`。`predecessors`＝訂正記録の `revises` の昇順（訂正のとき）、訂正でなければ空 | TD8 |
| C5 | 流れ：P2-q の行の流れ（P2-q の fixture の流れ）に、次を足す。(a) 符号を付けた項目が1つ以上あれば A に `assumption:activity_coding_declared`。(b) 符号を付けられなかった項目の種類ごとに L に `activity:<種類>`。(c) 訂正のとき、`carried` なら R に `revision:predecessor_identity` と A に `assumption:revision_role_declared`、そうでなければ L に `revision:predecessor_identity`。以下の表では「Q01 の流れ＋…」のように差分で書く | 設計79の§5 |
| C6 | 料金：M＝2＋M_q＋2N。子の予約は M_q（P2-q の全体の料金）。計画の料金 C は P2-i の式〔1＋スロット数＋数量数＋Σ表示（記録数＋確認数＋Σ問い合わせ（10＋見える範囲内の記録数＋確認済みで見える範囲内の記録の `revises` の数の和））〕から手で導く。標準 C＝16、Q06 の入力 C＝21、記録3・確認3の入力 C＝26、過去の時点で A だけが見える入力 C＝19。1問い合わせで M_lib＝C＋16、M_g＝M_lib＋5、M_q＝M_g＋5、M＝M_q＋4 | P2-q の料金の式の延長 |
| C7 | 新しい入力は、P2-q の要求に `coding` を足し、`observation_request` の予算は0にする | 設計79の TD11 |

## 1. 出せる行（V）

標準の入力＝ops `[rec A, confirm A(day3)]`、問い合わせ q1 は P-B1 の day5、参照時点 day8。「Q06 の入力」「Q25 の入力」は P2-q の fixture と同じ ops（訂正 B、day7 に確認）。`Dq(…)` は P2-q の宣言。「結果」は P2-t の行の `coding` と、必要な欄。ハッシュは fixture では確かめず、テストで独立な計算と照合する。

| ID | 入力 | 期待 |
| --- | --- | --- |
| V01 | 標準の入力、`Dq(P-B1)`、`Dt(A_ALL, true)` | state `coded`。entries 1件＝`{0, confirmation, C3, []}`。revision＝`{not_applicable, []}`。流れ＝Q01 の流れ＋A `assumption:activity_coding_declared`。M＝46、観察の子 42、接地の子 37 |
| V02 | 標準の入力、`Dq(P-B1)`、`Dt({creation: C1}, 偽)` | entries 1件＝`{0, confirmation, null, []}`。revision＝`{not_applicable, []}`。流れ＝Q01 の流れ＋L `activity:confirmation`（宣言は使われず、仮定は足されない）。M＝46 |
| V03 | Q20 の入力（観察者が人、確認あり。`Dq` は `observer_type: PractitionerRole`）、`Dt({creation: {system: fiction:activity-system:other, code: fiction-origin}, confirmation: C3}, 偽)` | entries 2件＝`{0, creation, {other, fiction-origin}, []}`、`{1, confirmation, C3, []}`。revision＝not_applicable。流れ＝Q20 の流れ＋A `assumption:activity_coding_declared`。M＝46 |
| V04 | Q25 の入力（訂正 B、観察者が人）、`Dq(P-B1, correction: amended, observer_type: Practitioner)`、`Dt(A_ALL, true)`（**Z1**） | entries 2件＝`{0, correction, C2, [{revision, {Observation, A}}]}`、`{1, confirmation, C3, []}`。revision＝`{carried, [A]}`。流れ＝Q25 の流れ＋R `revision:predecessor_identity`＋A `assumption:activity_coding_declared`・`assumption:revision_role_declared`。M＝51、観察の子 47、接地の子 42 |
| V05 | V04 の入力で `Dt(A_ALL, 偽)`（**Z6**） | entries の0番の entities は空。revision＝`{not_requested, [A]}`。流れ＝Q25 の流れ＋A `assumption:activity_coding_declared`＋L `revision:predecessor_identity`。M＝51 |
| V06 | Q06 の入力（訂正 B、観察者は不明）、`Dq(P-B1, correction: amended)`、`Dt(A_ALL, true)`（**Z4**） | entries 1件＝`{0, confirmation, C3, []}`（生成側の項目がないので entity の付け先がない）。revision＝`{no_agent, [A]}`。流れ＝Q06 の流れ＋A `assumption:activity_coding_declared`＋L `revision:predecessor_identity`。M＝51 |
| V07 | Q25 の入力、`Dq(P-B1, correction: amended, reviewer: なし)`（確認者の型を宣言しない）、`Dt(A_ALL, true)`（**Z7**） | entries は空。revision＝`{no_provenance, [A]}`。流れ＝Q24 型の流れ（訂正・Provenance なし・観察者は失う）＋L `revision:predecessor_identity`（符号は使われないので仮定なし）。M＝51 |
| V08 | 出自が AI の訂正（B の origin＝ai_candidate `fiction:ai:B`、観察者は不明、B は day7 に確認）、`Dq(P-B1, correction: amended)`、`Dt(A_ALL, true)`（**Z5**） | P2-q の項目は生成（Device）と確認の2件。entries＝`{0, correction, C2, [{revision, {Observation, A}}]}`、`{1, confirmation, C3, []}`。revision＝`{carried, [A]}`。流れ＝(Q05 型：訂正・生成あり)の流れ＋R `revision:predecessor_identity`＋A 二つの仮定。M＝51 |
| V09 | 記録 A（day2）・A2（day3）をともに確認し、訂正 B が `[A, A2]` を訂正（観察者が人、day6、day7 に確認）、`Dq(P-B1, correction: amended, observer_type: Practitioner)`、`Dt(A_ALL, true)`（**Z2**） | entries の0番の entities＝`[{revision,{Observation,A}}, {revision,{Observation,A2}}]`（昇順）。revision＝`{carried, [A, A2]}`。流れは V04 と同じ。M＝56、観察の子 52、接地の子 47 |
| V10 | 連鎖：A（day2）→B（A を訂正、validity 3〜8、day4、観察者は不明、day5 に確認）→C（B を訂正、validity 4〜6、day6、観察者が人、day7 に確認）。q1 は day5（C が選ばれる）、`Dq(P-B1, correction: amended, observer_type: Practitioner)`、`Dt(A_ALL, true)`（**Z3**） | entries の0番の entities＝`[{revision,{Observation,B}}]`（A は付かない）。revision＝`{carried, [B]}`。`revision_history` は失うものに残る。流れは V04 と同じ。M＝56 |
| V11 | Q25 の ops で、参照時点を day4、問い合わせ q1 の時点も day4 にする（B はまだ見えない）、`Dq(P-B1, correction: amended, observer_type: Practitioner)`、`Dt(A_ALL, true)`（**Z9**） | 選ばれるのは A（原本）。P2-q の項目は確認 RA の1件（A の観察者は不明）。entries＝`{0, confirmation, C3, []}`。revision＝`{not_applicable, []}`。流れ＝Q01 の流れ＋A `assumption:activity_coding_declared`。M＝49、観察の子 45、接地の子 40 |
| V12 | Q25 の入力、`Dt({creation: C1, confirmation: C3}, true)`（訂正の符号なし）（**Z8**） | entries の0番＝`{0, correction, null, [{revision,{Observation,A}}]}`（生成の符号 C1 で代用しない）。1番＝`{1, confirmation, C3, []}`。revision＝`{carried, [A]}`。流れ＝V04 の流れ＋L `activity:correction`。M＝51 |
| V13 | 二つの出力先（P-B1・P-B2）、q1＝P-B1、q2＝P-B2、`Dq` は両方、`coding` は P-B2 だけ | q1：`coding.state`＝`not_declared`、entries・revision は null、P2-q の観察は projected。q2：`coded`、entries 1件。M＝79、観察の子 73、接地の子 65 |
| V14 | Q21 の入力（観察者が人で `Dq` に観察者の型がない→P2-q が依頼）、`Dt(A_ALL, true)`（**Z10**） | P2-q の行は needs_information。`coding.state`＝`not_evaluated`、entries・revision は null。M＝46 |
| V15 | Q12 の入力（表せない行）に `Dt(A_ALL, true)` | `coding.state`＝`not_evaluated`。M＝46 |
| V16 | Q13 の入力（q1＝P-B1 は `Dq` なし、q2＝P-B2 は宣言あり）、`coding` は P-B2 | q1：P2-q は not_declared、`coding.state`＝`not_evaluated`。q2：`coded`。M＝79 |
| V17 | Q06 の入力、`Dq(P-B1, correction: amended)`、`Dt({creation: C1}, 偽)`（**Z11**） | entries 1件＝`{0, confirmation, null, []}`。revision＝`{not_requested, [A]}`。流れ＝Q06 の流れ＋L `activity:confirmation`・`revision:predecessor_identity`（仮定なし）。M＝51 |
| V18 | 標準の入力、`Dt({}, 偽)`（空の宣言） | state `coded`。entries 1件＝`{0, confirmation, null, []}`。流れ＝Q01 の流れ＋L `activity:confirmation`。M＝46 |
| V19 | 出自が AI の原本 A（観察者は不明、確認あり）、`Dq(P-B1)`、`Dt(A_ALL, true)` | P2-q の項目は生成と確認の2件。entries＝`{0, creation, C1, []}`、`{1, confirmation, C3, []}`。revision＝not_applicable（flag が真でも原本には付かない）。流れ＝Q05 の流れ＋A `assumption:activity_coding_declared`。M＝46 |
| V20 | 観察者が装置の訂正（B の observer＝device）、確認あり、`Dq(P-B1, correction: amended)`（装置の観察者は型の宣言が要らない）、`Dt(A_ALL, true)` | entries の0番は correction（C2）で entity A。agent は Device（P2-q の項目）。revision＝carried。M＝51 |

## 2. 静的検査（N）。いずれも標準の入力に `Dt(A_ALL, true)` を足したものを壊す

| ID | 壊し方 | 期待 |
| --- | --- | --- |
| N01 | トップレベルの `operation`・`consumer`・`observation_request`・`coding`・`budget` の欠落（5）／余分な欄／`observation_request` が object でない | `missing_field`／`unknown_field`／`expected_object` |
| N02 | `consumer` の `profile`・`profile_spec_sha256`・`observation_profile`・`observation_profile_spec_sha256` が別の値 | `unsupported_profile`／`profile_spec_mismatch`／`observation_profile_mismatch`（状態は unsupported_profile）／同 |
| N03 | `operation`／`consumer.operations` が別 | `unsupported_operation` |
| N04 | `observation_request.schema_version` が別 | `observation_schema_mismatch`（unsupported_profile） |
| N05 | `observation_request.budget.max_steps` が0でない | `invalid_child_budget` |
| N06 | 下位の不正（P2-p の重複した対象〔`duplicate_target`〕、P2-q の重複した観察の宣言〔`duplicate_observation`〕）を入れ子の中に | 下位の符号をそのまま返す |
| N07 | `coding` が空／17件 | `empty_collection`／`item_limit`（resource_limit） |
| N08 | `activities` のキーが `revision`・`derivation`・`removal`・`amend` | `unknown_field`（R4 の語 `derivation` を含む） |
| N09 | `activities.<種類>` が：`code` の欠落／余分な欄／`system` が空／object でない | `missing_field`／`unknown_field`／`expected_nonempty_string`／`expected_object` |
| N10 | `revision` が：文字列 `derivation`／整数 1／null | `expected_boolean` |
| N11 | 同じ出力先の宣言が2件 | `duplicate_coding` |
| N12 | `coding` の出力先が P2-q の `observations` にない | `unresolved_observation` |
| N13 | `budget.max_steps` が bool／負／上限超過 | `invalid_step_budget`／`invalid_step_budget`／`step_budget_limit`（resource_limit） |
| N14 | `coding` の項目に余分な欄（`role: source`） | `unknown_field`（`role` は宣言できない） |
| N15 | `destination_ref` の `version` の欠落 | `missing_field` |

## 3. 資源（B）

| ID | 入力 | 期待 |
| --- | --- | --- |
| B01 | 標準の入力、M＝46（先払い後に 43、問い合わせの後に 45、最後の確定で 46）。予算は 0・1・42・43・44・45・46 | 予算が足りる行は V01 の期待、足りない行は全欄 null で `step_limit`。`incomplete` は未完了の問い合わせと（45 のとき）最後の確定 |
| B02 | 二問い合わせ（V13 の入力）、M＝79。予算は 0・73・74・75・76・77・78・79 | 同様。1行目は 76 以上、2行目は 78 以上で完了 |
| B03 | 計画の上限を超える大きな計画 | `resource_limit`、steps 100000、全欄 null、`not_certified` |

## 4. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1 | 全数：記録の場合（原本／訂正1件／訂正2件）×観察者（不明／人／装置）×出自（観察／AI）×確認者の型の宣言（あり／なし）×活動の宣言の部分集合（8）×revision（真／偽）。人の観察者には型を宣言する | 別計算と一致 |
| D2 | 訂正された記録のハッシュ：結果の台帳から取った記録を JSON で正規化して独立に計算 | `what.record_sha256` と一致。選ばれた記録のハッシュとは異なる |
| D3 | P2-q 単独の実行との差分 | 各行の `coding` を除くと一致。トップレベルも `observation_run` と型以外は一致 |
| D4 | 乱数（250要求） | 別計算と一致 |
| D5 | 料金・子の予算 | M＝2＋M_q＋2N。子の `reserved_steps`＝`steps_used`＝M_q |
| D6 | 活動の符号の文字列を替えても判定は変わらない | `system`・`code` 以外は不変 |

## 5. 検出すべき変異

宣言のない種類の符号を別の種類で代用する、訂正の項目を `creation` と呼ぶ、`activity_coding_declared` を常に足す、`activity:<種類>` を失うものに書かない、`revision` が偽でも entity を付ける、原本に entity を付ける、前の版でなく選ばれた記録のハッシュを `what` に入れる、1つ目の訂正された記録だけ付ける、順序を逆にする、`role` を `source` にする、agent のない確認の項目に entity を付ける（`no_agent` を `carried` にする）、`revision:predecessor_identity` を保持／失うものに書かない、`not_declared` を `coded` にする、`predecessors` を運べない行で空にする、先払いの省略、最後の確定の省略、`inferred_information` に値、`certified`、`activities` のキーの集合を広げる、`revision` の型の検査の削除、P2-q の行の複製を書き換える。

## 6. 前提と限界

- 期待は設計79から手で導いた値です。P2-q 以下の行の内容は、[44](44-p2-i-cases.md)・[64](64-p2-o-cases.md)・[68](68-p2-p-cases.md)・[71](71-p2-q-cases.md) に従います。
- 料金の数は、P2-i の計画の料金の式から手で導きました。実装の値と食い違ったときは、実装・式の読み・期待のどれが誤りかを調べて記録します。
- `required_paths` の fixture は配列の長さを確かめられないので、項目の数と entity の数は、添字ごとの確認と別計算の全数（D1・D4）で確かめます。ハッシュは fixture では確かめず、D2 で確かめます。
- 活動の符号は不透明で、符号の系の妥当性、`revision` 以外の役割、`entity.agent`、訂正の理由は扱いません。
