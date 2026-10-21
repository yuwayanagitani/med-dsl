# P2-s：任意の項目を必須にする版の更新の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計76](76-p2-s-design.md) の予測 S1〜S10 と反例 W1〜W8 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・識別子はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。

## 0. 設計76の具体化

| ID | 決定 | 理由 |
| --- | --- | --- |
| T1 | 観察者の拒否の符号：欠落 `missing_field`、`kind` が別 `invalid_observer`、`unknown` に `ref` があれば `unknown_field`、`human`・`device` に `ref` がなければ `missing_field`、空文字 `expected_nonempty_string`、余分な欄 `unknown_field`、object でなければ `expected_object`（いずれも invalid_input） | 既存の検査の符号をそのまま使う |
| T2 | 移行の規則：旧入力の全ての記録（台帳）と操作 `record`・`correct`（ライブラリ）に、`observer: {kind: unknown}` を足す。他の欄・値は変えない。生成器の既定の変更で行う | 手編集をしない |
| T3 | 移行後の例の期待は、旧入力の期待と、次を除いて同一：(a) 結果の根拠の `record_observer`（常に出る）、(b) 期待の中に写した入力（`retained_source` など）に観察者が入ること、(c) 下の§1・§2で個別に決めた例 | 宣言した変更だけ |
| T4 | 比較器に、宣言の種類 `required_field` を足す：`request_leaf`（要求で全ての入力に加わる項目の名前）、`result_leaf`（結果・期待に現れる項目の名前）、`substitution_refusal`（旧入力を pin の置換だけで渡したときの拒否の状態と理由）。許容される差は、最後の経路の要素が宣言した名前で、新版にだけ現れる項目に限る | 設計76の SD8 |
| T5 | `unknown` の観察者の P2-q での扱い：agent も依頼も流れの変化も、観察者のない記録と同じ | 設計76の SD4 |

## 1. P2-i の実行例（O系列。標準は P2-i の標準の記録 `A`）

P2-r の O 系列（O01〜O05・O10〜O14）は、入力に必須の観察者が加わる（人・機器の観察者を使う例は変わらない。観察者を持たない旧い形の例は、既定で `unknown` を持つ）。次の例を足し、一つの期待を変える。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O20 | 記録 `A` から `observer` を除く（確認の hash は再計算する） | invalid_input、`[missing_field]`（W1。補完しない） |
| O21 | `A.observer`＝`{kind: unknown}`（明示） | ok、`computed`、領域 20、`results[0].binding_evidence.selected[0].record_observer`＝`{kind: unknown}` |
| O22 | `A.observer`＝`{kind: unknown, ref: fiction:x}` | invalid_input、`[unknown_field]`（W3） |
| O23 | 標準（観察者は既定の `unknown`） | `record_observer`＝`{kind: unknown}`。**常に出る**（SD2） |
| O04（期待の変更） | A に人の観察者、B（訂正）は既定の `unknown`。問い合わせ day5 | 選択は B。`record_observer`＝`{kind: unknown}`（A の人の観察者を継がない。W6） |

人の観察者で `ref` がない（O12）、空の `ref`（O11）、余分な欄（O13）、`kind` が `robot`（O10）、観察者が null／文字列（O14）、確認の後の書き換え（O05）の期待は、変えない。

## 2. P2-o の実行例

| ID | 変更 | 期待 |
| --- | --- | --- |
| O73 | 操作 `record` の `observer`＝`{kind: unknown}`（明示）、出力先 `P-A1` | satisfied、text `20.0`。`selection.record_observer`＝`{kind: unknown}`。M＝32 |
| N03-observer-missing | 操作 `record` から `observer` を除く | invalid_input、`[missing_field]`（W2。ライブラリは補完しない） |
| N03-observer-unknown-ref | `observer`＝`{kind: unknown, ref: x}` | invalid_input、`[unknown_field]`（P2-i の符号をそのまま返す） |

既存の例（O70〜O72、N03-observer-\*）は変えない。操作を省略した旧い形の例は、既定で `unknown` を持つ。

## 3. P2-q と再固定のみの拡張

P2-q の例は、台帳の記録に既定で `unknown` を持つようになる以外は変えない（S10）。Q05（AI 由来）は、観察者が `unknown` なので、生成の Provenance の agent が AI の1件だけ（観察者の agent を足さない）。Q01 は、生成の Provenance を出さない。この2点は例の期待と、P2-q のテストで確認する。P2-j・P2-m・P2-p の例は、記録に既定で `unknown` を持つ以外は変えない。

## 4. 版の検査の期待（V1〜V8）

| 検査 | 期待 |
| --- | --- |
| V1・V2 | 旧版 `ab4c358` が履歴にあり、新版の祖先。旧版の木で統合評価が合格し、記録した分母（23宣言・316義務・498防護例）、manifest・束の hash を再現 |
| V3 | 版の記録の宣言：D-1（`required_field`：P2-i の記録の `observer`〔`request_leaf: observer`、`result_leaf: record_observer`、`substitution_refusal: invalid_input／missing_field`〕）、D-2（`added_field`：新しい入力 O20〜O22 ほか）、D-3（意味の変更のない再固定）。再固定する pin：6モジュールの `SPEC_SHA256` |
| V4 | 旧入力は、pin を持つものは `profile_spec_mismatch` で拒否され、pin に届く前に結果が決まるものは同一。変更 0 |
| V4′ | 旧い pin を新しい値へ置換した入力（各系列の先頭3件）は、**全て `invalid_input`／`missing_field`**。受理 0（S3） |
| V5 | 移行した入力は旧入力と、hash の値と `observer` の追加を除いて同一。期待は `observer` を含む写しと、O04 と追加を除いて同一 |
| V6 | 旧版の結果と新版の結果（移行した入力どうし）の差は、`record_observer` の追加だけ。料金は変わらない |
| V7 | `affected(["src/med_dsl/temporal_measurement_spec.json"])` は6拡張を過不足なく列挙する。過小は P2-r と同じ9件（宣言6件とモジュール3件） |
| V8 | 新版の入力のうち、`unknown` を含む入力は、旧版の木で `invalid_observer`（旧い pin に替えた場合）。人・機器の観察者だけの入力は旧版が受理する。新しい pin のままならすべて pin で拒否 |

## 5. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1 | 観察者（`unknown`／human／device）×訂正の鎖の2記録の全数 | `record_observer` は常に出て、選ばれた記録のもの。訂正は継がない |
| D2 | 観察者の hash への算入：観察者の種類・値を変えた記録の確認の hash | 全て異なる。`unknown` も内容の一部 |
| D3 | 観察者の形の全数（欠落、各種の不正、`unknown` の ref の有無） | T1 の符号 |
| D4 | P2-o の全数：操作の観察者（欠落／`unknown`／human／device）× 確認の操作の観察者 | 欠落は拒否。確認の操作は `unknown_field` |
| D5 | P2-q：観察者（`unknown`／human／device）×出自×型の宣言×Provenance の宣言 | 別計算と一致。`unknown` は観察者がない場合と同じ |
| D6 | 料金 | 変わらない |

## 6. 検出すべき変異

必須の検査の削除（観察者がなくても受理）、補完（欠落を `unknown` で補う）、`unknown` に `ref` を許す、`unknown` を `human` と同じに扱う、`record_observer` を `unknown` のとき出さない、`unknown` から観察者の agent を作る、`unknown` で依頼を出す、確認の操作が観察者を受理する。比較器：許容する差の判定の緩め（宣言した名前以外を許す、削除を許す）、置換の拒否の理由の照合の削除。

## 7. 前提と限界

- 期待は設計76から手で導いた値です。P2-i・P2-o・P2-q の既存の行の内容は、[44](44-p2-i-cases.md)・[64](64-p2-o-cases.md)・[71](71-p2-q-cases.md)・[74](74-p2-r-cases.md) に従います。
- `unknown` は「観察者が分からない」の一つの値で、聞いていない・聞いたが分からない、の細分はしません。
- 版の記録の宣言と予測は作成者の主張です。移行は有限の旧入力に基づき、一般の移行の正しさの証明ではありません。
