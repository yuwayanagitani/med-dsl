# P2-k：精密化の手指定の正例・反例・期待

作成日：2026-10-20。状態：**実装前に固定した作成者側の期待**。[設計50](50-p2-k-design.md) の§6 の作業定義、§5.1 の入力不正、§8 の課金式から手で導出しました。**runtime の出力から期待を生成・更新しません**。独立確認・評価用正解の凍結は未実施です。数値・識別子・日付はすべて架空です。

## 1. 共通の設定

- 日付は `day(n) = 2026-10-nn T00:00:00Z`。区間は半開 `[day(s), day(e))`。
- 述語 `fiction:refinement:P@1`、個体 `fiction:refinement:u`、文脈 `fiction:refinement:context@1`。主張はすべて `confirmed`、出自 `observed`、既定の予算 100000。
- 主張 `A`：肯定、期間 `unknown`、記録 `day(2)`、確認 `review-A`（`day(2)`）。期間が `unspecified` の場合は明記。
- 精密化 `F1`：対象 `A`、期間 `[day(10), day(20))`、`confirmed`、記録 `day(5)`、確認 `FR1`（`day(6)`）。`target_sha256` と `refinement_sha256` は、台帳の実際の内容の hash（生成器が計算する）。誤りを試すもの（N04・N08）だけ `0` を並べた値にする。
- 既定の view：参照時点 `day(9)`、既定の問い：対象時点 `day(15)`。
- 「ブロック」は `status: unassessed`、`literal_state: null`、採用集合・根拠は `null`。「完了」は `status: ok`。
- 全ての正常な行で `certificate.status = not_certified`、`converted_to_base = false`、`clinical_assertions_added = []`、`meaning_mode = refined_temporal_literal_probe`。

| 略記 | 意味 |
| --- | --- |
| 肯 `[A]` | `positive_only`、`positive_assertion_refs = [A]`、否定・除去は空 |
| 空 | `neither`、肯定・否定・除去は全て空 |
| 阻害 R | 完了せず、`reason_codes = [R]`、`blocking_assertion_refs` は記載のもの |

## 2. 意味の条件 U

| ID | 設定 | 期待 |
| --- | --- | --- |
| U01 | `[A]`（精密化なし）。k=day(9)、t=day(15) | 阻害 `validity_unknown`、ブロッキング `[A]`。`information_requests[0]`：`kind=validity_unknown`、`assertion_ref=A`、`requires=[bounded_validity, evidence, human_confirmation]`、`resolution_supported=true`。`pending_refinement_refs=[]` |
| U02 | `[A, F1, FR1]`。k=day(9)、t=day(15) | 完了、肯 `[A]`。`refinement_evidence=[{A, [10,20), [{F1, [FR1]}]}]`。`assertion_evidence[0]`：`validity=[10,20)`、`declared_validity={unknown}`、`review_refs=[review-A]`。`retained_refinements=[F1]`、`retained_refinement_reviews=[FR1]` |
| U03 | U02 に問い `q20`（t=day(20)）、`q25`（t=day(25)）。結果は q20、q25 の順 | 両方とも完了で空（終端は含まない。区間の外では A は適用されず、否定にならない）。除去は空 |
| U04 | U02 に問い `q09`（t=day(9)）、`q10`（t=day(10)）。q09、q10 の順 | q09：空。q10：肯 `[A]`（始点は含む） |
| U05 | `[A, F1(記録 day(5)), FR1(day(6))]`。k=day(5)、t=day(15) | 阻害 `validity_unknown`、ブロッキング `[A]`、`pending_refinement_refs=[F1]`（F1 は可視だが確認が k より後）。`information_requests[0].pending_refinement_refs=[F1]` |
| U06 | U05 の台帳に view `v04`（k=day(4)）・`v05`（k=day(5)）・`v06`（k=day(6)）、問い `q`（t=day(15)）。結果は v04、v05、v06 の順 | v04：阻害 `validity_unknown`、`pending=[]`（F1 はまだ記録されていない）。v05：阻害 `validity_unknown`、`pending=[F1]`。v06：完了、肯 `[A]`、`pending=[]`。**精密化の前の参照時点が精密化前の結果を再現する（Y3）** |
| U07 | `F1` を day(5)、`FR1` を day(5)（同時刻）。k=day(5)、t=day(15) | 完了、肯 `[A]`（確認は精密化以後、等しい時刻は許す。可視性は k 以下） |
| U08 | `[A, F1, FR1, F2, FR2]`：F2 は `[day(12), day(22))`、記録 day(7)、確認 `FR2` day(8)。問い `q15`、`q21` | 両方とも阻害 `validity_refinement_conflict`、ブロッキング `[A]`。`information_requests[0]`：`kind=validity_refinement_conflict`、`refinement_refs=[F1, F2]`、`resolution_supported=false`。**後から記録された F2 を優先しない** |
| U09 | U08 の記録の順序を逆にする：F2 を day(5)／確認 day(6)、F1 を day(7)／確認 day(8)。問い `q15`、`q21` | U08 と同じ結果（到着順に依らない。`refinement_refs=[F1, F2]` は ID の辞書順）。後勝ち（F1）にしない |
| U10 | `F1` が `suspected`（確認 `FR1` はある）。k=day(9) | 阻害 `validity_unknown`、`pending_refinement_refs=[F1]` |
| U11 | `F1` の出自が `ai_candidate`、確認なし。k=day(9) | 阻害 `validity_unknown`、`pending_refinement_refs=[F1]`。AI 由来は人の確認まで効かない。`retained_refinements=[F1]` |
| U12 | `[A, F1, FR1, F2, FR2]`：F2 は F1 と同一の区間 `[day(10), day(20))`、記録 day(7)、確認 day(8) | 完了、肯 `[A]`。`refinement_evidence[0].refinements=[{F1,[FR1]},{F2,[FR2]}]`（同一の区間は一つにまとめ、両方の根拠を残す） |
| U13 | `[A, F1, FR1, F2]`：F2 は `[day(12), day(22))`、記録 day(7)、**確認なし**。問い `q15`、`q21` | q15：完了、肯 `[A]`。q21：完了、空（F1 の区間の外）。両行で `pending_refinement_refs=[F2]`、`refinement_evidence` は F1 のみ |
| U14 | `[A, F1, FR1, B, review-B]`：B は否定、`[day(14), day(16))`、記録 day(7)、確認 day(7)、`revises=[A]`、`change_reason` あり。問い `q12`、`q15`、`q18` | q12：肯 `[A]`。q15：`negative_only`、否定 `[B]`、除去 `[A]`、`revision_evidence=[{B→A, [review-B]}]`。q18：肯 `[A]`。包含 `[14,16) ⊆ [10,20)` は成立 |
| U15 | U14 の記録で、F1 を day(9)、FR1 を day(9) に変更（B より後）。view `v08`（k=day(8)）、`v10`（k=day(10)）、問い `q12`、`q15`、`q18`。結果は v08 の3行、v10 の3行 | v08 の3行：阻害 `validity_unknown`（B は可視だが、A の期間が未確定なので訂正辺を評価しない）。v10 の3行：U14 と同じ（肯 `[A]`、`negative_only [B]` 除去 `[A]`、肯 `[A]`）。**精密化と訂正の記録の順序に依らない（Y4）** |
| U16 | `[A, B, review-B, F1, FR1]`：F1 は `[day(10), day(12))`、記録 day(8)、確認 day(8)。B は否定、`[day(14), day(16))`、記録 day(7)、確認 day(7)、`revises=[A]`。view `v07`（k=day(7)）、`v09`（k=day(9)）、問い `q`（t=day(15)） | v07：阻害 `validity_unknown`（F1 は未可視）。v09：阻害 `revision_outside_refined_validity`。`revision_conflicts=[{reviser_ref=B, target_ref=A, refinement_refs=[F1]}]`。**精密化後の区間が既存の訂正を含まないことは、参照時点ごとの診断になる（R4）** |
| U17 | `[A]` と、F1（確認なし）に必須能力 `fiction:unknown-capability` を加える | 阻害 `unknown_capability`、`missing_capabilities=[fiction:unknown-capability]`、`blocking_assertion_refs=[]`、`blocking_refinement_refs=[F1]`。A の阻害は報告しない（未知能力が先） |
| U18 | `[A]` と、否定の主張 X（`[day(7), day(8))`、記録 day(3)、確認なし）に必須能力 `fiction:unknown-capability` | 阻害 `unknown_capability`、`blocking_assertion_refs=[X]`。A の `validity_unknown` は報告しない |
| U19 | U02 の台帳に、F3（`[day(12), day(22))`、記録 **day(12)**、確認 day(13)）に未知能力を足す。k=day(9)、t=day(15) | 完了、肯 `[A]`（F3 は k より後なので可視でなく、未知能力の阻害にならない）。`retained_refinements=[F1, F3]` |
| U20 | A を**否定**にする（期間 `unknown`）。F1 は `[day(10), day(20))`。問い `q15`、`q25` | q15：`negative_only`、否定 `[A]`。q25：空（区間の外で否定は適用されず、肯定にも変わらない） |
| U21a | A の期間が `unspecified`、精密化なし | 阻害 `validity_unspecified`、ブロッキング `[A]`、`information_requests[0].kind=validity_unspecified` |
| U21b | U21a に F1 と FR1。t=day(15) | 完了、肯 `[A]` |
| U22 | 主張 `A1`（記録 day(2)）、`A2`（記録 day(3)、確認 day(3)）。いずれも肯定・期間 `unknown`。F1 は A1 のみを `[day(10), day(20))` に精密化 | 阻害 `validity_unknown`、ブロッキング `[A2]`。`refinement_evidence=null`（阻害した行） |
| U23 | A は期間 `unknown` だが**確認なし**（適格でない）。F1／FR1 は A を精密化。別の主張 B（肯定、`[day(5), day(25))`、記録 day(3)、確認 day(3)）。t=day(15) | 完了、肯 `[B]`。A は採用されず阻害にもならない。`refinement_evidence=[]`（適格でない対象に効いた精密化は根拠に載せない） |
| U24 | `A1`（期間 `unknown`、精密化なし）、`A2`（期間 `unknown`、記録 day(3)、確認 day(3)）、F2（対象 A2、`[day(10), day(12))`、記録 day(5)、確認 day(6)）、B（否定、`[day(14), day(16))`、記録 day(7)、確認 day(7)、`revises=[A2]`）。k=day(9) | 阻害 `validity_unknown`、ブロッキング `[A1]`。**包含の矛盾（B ⊄ [10,12)）は、より前の阻害があるうちは報告しない（停止の順序）** |
| U25 | U02 の台帳に、**未来の**精密化 F2（`[day(12), day(22))`、記録 day(12)、確認 day(13)）を足す。k=day(9)、t=day(15) | 完了、肯 `[A]`。U02 と同じ行（`refinement_evidence` は F1 のみ、`pending_refinement_refs=[]`）。未来の追加は完成した結果を変えない（RF-L1） |

### 紙の上の対照 CT01（実装しない）

U03 の台帳（A の期間 `unknown`、F1 が `[day(10), day(20))` を主張）を、精密化ではなく**部分訂正**（M2：不明は任意の区間を含むとみなし、F1 を `A` を訂正する bounded な記録とする）として扱う案。

| 時点 | M1（採用） | M2（採らない） |
| --- | --- | --- |
| t=day(15)（区間の内側） | 肯 `[A]` | A は F1 に覆われ、訂正された元記録を除く。**A の期間が不明でも、この時点で A は無関係になる**。F1 自体の極性が結果になる |
| t=day(25)（区間の外側） | 空（A は適用されない） | `unassessed`（A の期間がなお不明で、この時点で適用されるか分からない） |

この差が、契約が「記録の期間を後から別の記録が確定する」枠（M1）を持つかを試す。M2 はコードに実装せず、期待だけを残す。**実装済みの断片に数えない。**

## 3. 構造・不正・境界の条件 N

基準は U02 の台帳。指定のないものは、変更した項目だけが誤り。期待は `status` と、指定があれば `reason_codes`。

| ID | 変更 | 期待 |
| --- | --- | --- |
| N01 | P2-e の要求（`examples/p2-temporal/t13.json`）をそのまま評価 | 旧経路：完了、`results[0].reason_codes=[validity_unknown]`、`information_requests[0].resolution_supported=false`（P2-k を載せても変わらない） |
| N02 | A の期間を `bounded`（`[day(1), day(30))`）にして F1 を残す（hash は再計算） | `invalid_input` / `refinement_target_not_unresolved` |
| N03 | F1 の `assertion_ref` を存在しない ID にする | `invalid_input` / `unresolved_assertion` |
| N04 | F1 の `target_sha256` を `0`×64 にする | `invalid_input` / `refinement_target_hash_mismatch` |
| N05a | F1 の記録時刻を A と同じ `day(2)`（確認は day(6)） | `invalid_input` / `refinement_not_after_target` |
| N05b | F1 の記録時刻を A より前の `day(1)` | `invalid_input` / `refinement_not_after_target` |
| N06a | F1 の期間を `{kind: unknown}` | `invalid_input` / `invalid_refinement_validity` |
| N06b | F1 の期間を `{kind: unspecified}` | `invalid_input` / `invalid_refinement_validity` |
| N07a | F1 の期間を `{kind: open_end, start: day(10)}` | `unsupported_profile` / `unsupported_validity` |
| N07b | F1 の期間の `start` と `end` が等しい | `invalid_input` / `invalid_validity_interval` |
| N07c | F1 の期間の `start` が `end` より後 | `invalid_input` / `invalid_validity_interval` |
| N07d | F1 の期間の `end` を欠く | `invalid_input`（欄の欠落） |
| N07e | F1 の期間が存在しない日付 `2026-02-30T00:00:00Z` | `invalid_input` |
| N08 | FR1 の `refinement_sha256` を `0`×64 にする | `invalid_input` / `refinement_review_hash_mismatch` |
| N09 | 精密化 F2 の `assertion_ref` が精密化 F1 の ID（精密化の精密化） | `invalid_input` / `unresolved_assertion` |
| N10a | 方針を P2-e の `fiction:confirmed-scoped-revision@1` にする | `unsupported_profile` |
| N10b | consumer の profile を未知にする | `unsupported_profile` |
| N10c | 操作を未知にする | `unsupported_profile` |
| N10d | consumer の操作一覧を未知にする | `unsupported_profile` |
| N11 | consumer の仕様 hash を `0`×64 | `unsupported_profile` / `profile_spec_mismatch` |
| N12 | 台帳の schema を P2-e の `p2-temporal-ledger-draft-1` にする | `unsupported_profile` / `unsupported_refinement_ledger` |
| N13 | FR1 の記録時刻を F1 より前（`day(4)`） | `invalid_input` / `review_precedes_refinement` |
| N14 | FR1 の `refinement_ref` を存在しない ID にする | `invalid_input` / `unresolved_refinement` |
| N15 | F1 の必須能力から profile を除く（hash 再計算） | `invalid_input` / `missing_refinement_capability` |
| N16 | 精密化の ID を重複させる | `invalid_input` / `duplicate_identifier` |
| N17a | FR1 の `reviewer_kind` を `ai` | `invalid_input` / `invalid_review` |
| N17b | FR1 の `outcome` を `rejected` | `invalid_input` / `invalid_review` |
| N18 | 期間 `unknown` の主張 B が、期間 `unknown` の A を訂正する | `unsupported_profile` / `unsupported_revision_scope` |
| N19 | 期間が `bounded` の B が、期間 `unknown` の A を訂正する。精密化なし | 完了：阻害 `validity_unknown`（台帳は受理される。訂正辺は評価しない） |
| N20a | F1 の `change_reason` を欠く | `invalid_input` |
| N20b | F1 に未知の項目を足す | `invalid_input` |

構造の不正・未対応は、予算 0 でも同じ結果です。

## 4. 予算の条件 B

U02 の台帳（主張1・確認1・精密化1・精密化の確認1・view 1・問い 1・訂正辺 0）の課金は、設計50の§8 の式から `1 + (1+1+1+1) + (1 + 1 + 1 + 0 + 1) = 9`。

| ID | 設定 | 期待 |
| --- | --- | --- |
| B01 | U02、予算 0 | `resource_limit`、`steps_used=0`、行は `unassessed`・`literal_state=null`・`reason_codes=[step_limit]`、値なし |
| B02-below | U02、予算 8 | `resource_limit`、`steps_used=8`、行は値なし |
| B02-exact | U02、予算 9 | 完了、`steps_used=9`、肯 `[A]` |
| B02-above | U02、予算 10 | 完了、`steps_used=9` |
| B03-below | U14 の台帳（主張2・確認2・精密化1・確認1・可視の主張2・可視の精密化1・適格な訂正辺1）、問い `q15` のみ、予算 12 | `resource_limit`、`steps_used=12`、行は値なし。必要な課金：`1 + (2+2+1+1) + (1+2+1+1+1) = 13` |
| B03-exact | 同、予算 13 | 完了、`steps_used=13`、`negative_only`、否定 `[B]`、除去 `[A]` |
| B04-9 | U02 に問い `q2`（t=day(15)）を足し、予算 9 | `resource_limit`、`steps_used=9`。行0は完了（肯 `[A]`）、行1は値なし。全体の必要な課金は `1 + 4 + 4 + 4 = 13` |
| B04-13 | 同、予算 13 | 完了、`steps_used=13`、両行とも肯 `[A]` |
| B05 | 構造不正（N04）を予算 0 で | `invalid_input`（予算に依らない） |

## 5. 比較の方針（別計算と有限列挙の設計）

- **別計算**：実装の関数を呼ばず、各主張の有効な期間を精密化から数え、区間の差引きで除去を求める。時刻は数値へ変換して比較する。
- **有限列挙**：未確定の主張1件（肯定／否定）、精密化 0〜2 件（区間3通り、確認状態：なし／通常／遅延／suspected）、部分訂正の有無（bounded な主張 B が A を訂正、区間3通り）。参照時点4点、対象時点6点。
- **乱数**：seed `20261020`。1〜4記録、精密化 0〜3、未確定・未指定・競合・未知能力・未来の追加を含む。
- **意味変異**：設計50の§11 の10種。

数値の予算の境界（B 系列の steps）は設計式から手で導き、実装の測定値で上書きしません。
