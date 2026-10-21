# P2-r：記録に観察者を足す変更の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計73](73-p2-r-design.md) の予測 Y1〜Y10 と反例 Z1〜Z8 に、具体的な入力と期待を与えます。期待は設計から手で導いた値で、runtime の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を実行結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。数値・識別子はすべて架空です。時刻 `dayN` は `2026-10-NNT00:00:00Z`。

## 0. 設計73の具体化

| ID | 決定 | 理由 |
| --- | --- | --- |
| R1 | 観察者の形は `{kind, ref}`。`kind` は `human`・`device`。拒否の符号：種類が別なら `invalid_observer`、欄の欠落は `missing_field`、余分な欄は `unknown_field`、空文字は `expected_nonempty_string`、object でないものは `expected_object`（いずれも invalid_input） | 既存の検査の符号をそのまま使う |
| R2 | 検査の位置は、記録の検査の中で `origin` の次 | 既存の項目の順序に従う |
| R3 | P2-o の確認の操作（`confirm`）が `observer` を持つと、既存の符号 `unknown_field` で拒否される（確認の欄の完全一致） | 確認は観察者を持たない |
| R4 | P2-q の新しい符号：`unsupported_observer_type`（unsupported_profile）。依頼 `{element: provenance, action: declare_observer_type, record_ref, property_ref: null}` | P2-q の既存の依頼の形（4欄） |
| R5 | P2-q の生成の Provenance の agent の順序：AI（出自が `ai_candidate`）、観察者 | 設計73のRD6 |
| R6 | 流れの項目 `observer`（保持または失う）と仮定 `assumption:observer_type_declared` | 設計73の§3.3 |

## 1. P2-i の実行例（O系列。標準は P2-i の標準の記録 `A`）

標準の `A` に `observer` を足す。問い合わせは標準（day5、`u_base`）。他の欄は P2-i の標準。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O01 | `A.observer`＝`{human, fiction:human:observer}` | ok、`computed`、領域 20。`results[0].binding_evidence.selected[0].record_observer`＝その観察者。`retained_source` は入力と同じ（観察者を含む） |
| O02 | `A.observer`＝`{device, fiction:device:meter}` | O01 と同じ形で、`record_observer` がその値 |
| O03 | 訂正の鎖（B は A を訂正、B の期間 [day4, day6)、値 3）で、B にだけ観察者 `{human, fiction:human:observer}`。問い合わせ day5 | 選択は B、領域 30、`record_observer`＝B の観察者。**訂正は元の観察者を継がない**（A に観察者があっても B の欄は B のもの。A に観察者を付け、B に付けないときは `record_observer` を出さない：O04） |
| O04 | A に観察者、B（訂正）には観察者なし。問い合わせ day5 | 選択は B。結果に `record_observer` は出ない（`binding_evidence.selected[0]` のキー集合に含まれない）。テストで確認 |
| O05 | A に観察者を付けて確認の hash を計算した後、観察者の `ref` を別の値に書き換える（再計算しない） | **invalid_input**、`[review_record_hash_mismatch]`（Z1。観察者は内容の一部） |
| O10 | `observer.kind`＝`robot` | invalid_input、`[invalid_observer]`（Z2） |
| O11 | `observer.ref`＝`""` | invalid_input、`[expected_nonempty_string]` |
| O12 | `observer` に `ref` がない | invalid_input、`[missing_field]` |
| O13 | `observer` に余分な欄 `extra` | invalid_input、`[unknown_field]` |
| O14 | `observer`＝null／文字列 | invalid_input、`[expected_object]` |

P2-i の既存の実行例は、観察者を持たないので、結果は変わらない（hash の値を除く）。

## 2. P2-o の実行例（O70系列）

P2-o の標準（[64 の§1](64-p2-o-cases.md)）の記録 `A` に `observer` を足す。

| ID | 変更 | 期待 |
| --- | --- | --- |
| O70 | `A.observer`＝`{human, fiction:human:observer}`、出力先 `P-A1`（`line`） | satisfied、text `20.0`。`selection.record_observer`＝その観察者。M＝32 |
| O71 | `A.observer`＝`{device, fiction:device:meter}`、出力先 `P-B1`（`exchange`） | satisfied、領域 20。`selection.record_observer`＝その観察者 |
| O72 | 訂正 B（64 の O30 の B）にだけ観察者。`P-B1`、対象 day5 と day3 の2問い合わせ | day5：選択 B、`record_observer`＝B の観察者。day3：選択 A、`record_observer` は出ない。M は2問い合わせの値（C＝1＋1＋2＋〔2＋2＋2×13〕＝34、M＝1＋34＋28＋1＝64） |
| N03-observer-kind | `A.observer.kind`＝`robot` | invalid_input、`[invalid_observer]`（P2-i の符号をそのまま返す） |
| N03-observer-confirm | 確認の操作に `observer` | invalid_input、`[unknown_field]`（R3） |
| N03-observer-ref | `A.observer.ref`＝`""` | invalid_input、`[expected_nonempty_string]` |

## 3. P2-q の実行例（Q20系列）

P2-q の標準（[71 の§1](71-p2-q-cases.md)）に、記録 `A` の `observer` を足す。`provenance` の宣言は `reviewer_type`＝`Practitioner`（標準）。基の流れは標準の `flows_q`（71 の§1.2）。M＝42。

| ID | 変更 | 期待 |
| --- | --- | --- |
| Q20 | `A.observer`＝`{human, fiction:human:observer}`、`provenance.observer_type`＝`PractitionerRole` | projected。`provenance`＝2件：先頭 `{activity: creation, target: {type: Observation, record_ref: A}, recorded: day2, agents: [{who: {type: PractitionerRole, identifier: fiction:human:observer}}]}`、次に confirmation（Q01 と同じ）。流れ：Q01 の流れに `observer` を保持に足し、added に `assumption:observer_type_declared` を足す（`assumption:reviewer_type_declared` は Q01 のとおり残る）。`origin_kind` は lost のまま |
| Q21 | `A.observer`＝human、`observer_type` の宣言なし（Z5） | needs_information、依頼 `[{element: provenance, action: declare_observer_type, record_ref: A, property_ref: null}]`、`output`・`flows`＝null。型を推測しない |
| Q22 | `A.observer`＝`{device, fiction:device:meter}`、`observer_type` の宣言なし | projected。creation の agent＝`{who: {type: Device, identifier: fiction:device:meter}}`。流れ：`observer` を保持に足す。`assumption:observer_type_declared` は**足さない**（型の宣言を使っていない） |
| Q23 | 出自 `{ai_candidate, fiction:ai:A}` と観察者 human、`observer_type`＝`Practitioner`（Z6） | creation の agents＝2件、先頭が Device（`fiction:ai:A`）、次が Practitioner（`fiction:human:observer`）。流れ：`origin_kind` と `observer` を保持に足す。added に `assumption:observer_type_declared` |
| Q24 | `A.observer`＝human、`provenance` を宣言しない（Z7） | projected。`provenance`＝[]。流れ：Q02 の流れに `observer` を失うものに足す |
| Q25 | 訂正 B が選ばれ（71 の Q06 の台帳）、B にだけ観察者 human、`observer_type`＝`Practitioner`、`status.correction`＝`amended`。M＝47 | creation の対象 record_ref が `B`、recorded が B の記録時刻（day6）。次に B の confirmation（day7） |
| N14-observer-type-device | `provenance.observer_type`＝`Device` | unsupported_profile、`[unsupported_observer_type]` |
| N14-observer-type-organization | 同 `Organization` | 同 |

## 4. 版の検査の期待（V1〜V8）

| 検査 | 期待 |
| --- | --- |
| V1・V2 | 旧版 `dc0aabe` が履歴にあり、新版の祖先。旧版の木で統合評価が合格し、記録した分母（23宣言・313義務・495防護例）、manifest・束の hash を再現 |
| V3 | 版の記録の宣言：D-1（P2-i に任意の項目 `observer`〔`added_field`〕）、D-2（P2-o が `selection.record_observer` を出す〔`added_field`〕）、D-3（P2-q が生成の Provenance・観察者の型・依頼を持つ〔`added_field`〕）、D-4（意味の変更のない再固定：P2-j・P2-m・P2-p）。再固定する pin：`temporal_measurement.py` ほか6モジュールの `SPEC_SHA256`（`temporal_measurement`、`temporal_display`、`longitudinal`、`clinical_library`、`structure_grounding`、`observation_projection`） |
| V4 | 旧入力のうち、P2-i の仕様を pin する系列（P2-i・P2-j・P2-m・P2-o・P2-p・P2-q）の入力は全て `profile_spec_mismatch`（unsupported_profile）で拒否される。それ以外の系列の入力は旧版と同一。黙った再解釈 0 |
| V5 | 再生成した入力は旧入力と、hash の値を除いて同一。期待は、hash の値と宣言した追加（O・O70・Q20 の各系列の新しい入力）を除いて同一。欠落 0 |
| V6 | 旧版の結果と新版の結果（再生成した入力どうし）の差は、hash の値を除いて 0（旧入力は観察者を持たない）。差が出る入力は新しい入力だけ |
| V7 | `affected(["src/med_dsl/temporal_measurement_spec.json"])` は6拡張を列挙する。実際の再固定の範囲との差（生成器・宣言・索引・台帳）を一覧にする |
| V8 | 新しい入力（観察者を持つ O01）を旧版の木へ渡すと、新しい pin のままでは `profile_spec_mismatch`、旧い pin に置換すると `unknown_field`（記録の項目）で拒否され、黙って無視されない |

## 5. 差分・不変性の検査（有限）

| ID | 検査 | 期待 |
| --- | --- | --- |
| D1 | 観察者の全数（なし／human／device）×確認の有無×訂正の鎖の位置 | `record_observer` は、選ばれた記録が観察者を持つときだけ出る。持たなければキーが出ない |
| D2 | 観察者の hash への算入：観察者の有無・値を変えた記録の確認の hash | 全て異なる。観察者のない記録の hash は、独立に計算した値（仕様の hash を含む payload）と一致 |
| D3 | 乱数の台帳（観察者の有無・種類を混ぜる） | P2-i の別計算（選択）と一致。観察者は選択に影響しない |
| D4 | P2-o の乱数の要求 | 観察者は選択・要素・出力・料金に影響せず、`selection.record_observer` だけが増える |
| D5 | P2-q の宣言の全数（観察者 なし／human／device × `observer_type` なし／4種 × Provenance 宣言あり／なし × 出自 observed／ai_candidate） | 別計算と一致。依頼は、宣言ありで human かつ型なしのときだけ |
| D6 | 料金 | P2-i・P2-o・P2-p・P2-q の料金は変わらない（観察者は課金の対象でない） |

## 6. 検出すべき変異

観察者を hash に含めない、`record_observer` を常に出す（null）、訂正が元の観察者を継ぐ、確認の操作が観察者を受理する、`kind` の検査の削除、型を推測する（人の観察者に既定の型を入れる）、観察者のない記録に生成の Provenance を出す、AI 由来の記録で観察者を落とす、観察者の流れの項目の欠落、`observer_type` の許容外の受理。

## 7. 前提と限界

- 期待は設計73から手で導いた値です。P2-i・P2-o・P2-q の既存の行の内容は、[44](44-p2-i-cases.md)・[64](64-p2-o-cases.md)・[71](71-p2-q-cases.md) に従います。
- 観察者の同一性・資格・履歴は扱いません。`kind` は2種だけです。
- 版の記録の宣言と予測は作成者の主張です。旧入力が行使しない新版の変更（観察者）は、旧入力の比較では見えません。
