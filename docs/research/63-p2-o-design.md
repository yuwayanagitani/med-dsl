# P2-o：薄い臨床ライブラリ（操作 → 共通表現 → 出力先の要求）の意味設計

作成日：2026-10-21。状態：**作成者側の設計草案。runtime・native 仕様・宣言・実行用 fixture は未実装**。[選定62](62-p2-o-selection.md) の L1 を、利用者の確認（2026-10-21「それでいい。進めて」。U2・U3 は推奨どおり、第二段の実資料と CPC の版更新監査は後）を受けて設計します。手指定の期待は [64](64-p2-o-cases.md)。独立確認・評価用正解の凍結は未実施で、[運用方針29](29-review-repository-policy.md) に従います。語彙・値・単位はすべて架空で、外部資料・患者情報・実データは使いません。以下は内部契約の作業定義で、医学的な意味や外部標準（FHIR など）への適合を主張しません。

## 1. 問い

[vision](../vision.md) の応用目標「出力先が変わっても、入力と根拠付きの補助情報で出力先の要求を満たせる範囲で、医療者の操作は変わらない。足りない情報は推測で埋めず、追加の観察・確認を求める」を、これまでの P2 の部品の上で、外れ得る形で試します。問いは [62 の§4.3](62-p2-o-selection.md) の Q1〜Q5 です。

| ID | 問い |
| --- | --- |
| Q1 | 出力先の要求を、コードでなくデータの宣言として持てるか。出力先を足すとき、ライブラリの操作と共通表現を変えずに済むか |
| Q2 | 出力先の要求の版を上げたとき、既に情報がある入力では医療者への追加の依頼が0、ない入力では不足している項目の数だけになるか（K14 の P2 での実現） |
| Q3 | 出力ごとに、保持・喪失・追加が根拠つきで返り、出所（記録・確認・由来）が辿れるか |
| Q4 | `ai_candidate` の値が、要求を満たすことに使われず、追加情報の候補として提示されるだけか |
| Q5 | 既存の契約（七欄・主題 A〜H・クラス・継承）で足りるか。足りない場合の不足は何か |

## 2. 設計判断

| 判断 | 初回に採る設計 | 理由・見直す条件 |
| --- | --- | --- |
| LD1 | 専用の R5 の入口を一つ設ける。操作の列から P2-i の台帳を**ライブラリが組み立て**、P2-i と P2-f を固定版で呼ぶ。外部の台帳・hash・結果は受け取らない | 医療者は hash や ID の対応を扱わない。台帳の妥当性は P2-i の検査に委ねる |
| LD2 | 操作は3種類：`record`（記録）、`confirm`（確認）、`correct`（訂正）。内容 hash はライブラリが計算する | 62 の§4.1。確認が記録の内容を拘束する規則（TM-6）は P2-i のまま |
| LD3 | 出力先の要求は、**要求プロファイル**（JSON の宣言）として要求に添える。出力の種類は `line`・`exchange`・`trend` の3つ、要求の要素の種類は `value`・`context`・`trend` の3つ。新しい出力先は、既存の種類の組み合わせなら、データだけで足せる | Q1。種類を超える出力先は、native の変更が要る（限界として記録） |
| LD4 | 共通表現からの選択は **P2-i の再実行の診断**（`diagnostics.candidate_refs` と停止の理由）を使い、文脈（検体・方法）の要求は**出力先ごとに**判定する | P2-i は、検体・方法が未知なら換算を止める（P2-i 自身の方針）。K14 では、旧い出力先はこれを要求しない。選択（どの記録か）と、文脈の充足を分ける |
| LD5 | 値の換算と二時点の比較は P2-f の固定版へ委譲する。丸め（`line`）は、P2-j と同じ数式をライブラリに**再び述べ**、継承として宣言する。二時点の比較は、P2-m と同じ規則（独立な変数、文脈の一致）を再び述べる | P2-j・P2-m は P2-i の「文脈が既知」を前提にした行を使うので、K14 の旧い出力先（文脈を要求しない）の部品にならない。P2-n の `inherits` を実際に使う |
| LD6 | 結果は4種類：`satisfied`、`needs_information`（不足を推測で埋めず、追加の依頼を返す）、`not_representable`（出力先が共通表現の内容を表せない。失う区別を返す）、`unassessed`（能力・語彙の限界） | 62 の§4.2。優先は unassessed > not_representable > needs_information > satisfied |
| LD7 | 追加の依頼は、不足している（記録、要素）の組ごとに一つ。保留中の記録（確認前など）に不足の値があれば、**候補**として添えるが、満たしたことにはしない。AI 由来の候補は `origin_kind` を保つ | Q2・Q4 |
| LD8 | 認定は常に `not_certified`。推測で補った情報は常に空（`inferred_information=[]`） | 診断であり、保存や医学的な認定ではない |

## 3. 入口と型

以下は予約名です。現在のCLIが受理するschemaではありません。自己 native 仕様 hash は実装時に確定します。

| 項目 | 予約する型・範囲 |
| --- | --- |
| profile / operation | `p2-clinical-library-draft-1` / `run_clinical_library` |
| request / result | `p2-library-request-draft-1` / `p2-library-result-draft-1` |
| 回答型 | `clinical_library_projection` |
| 要求 | `schema_version, operation, consumer, library, destinations, views, queries, budget` |
| consumer | `profile, profile_spec_sha256, operations, temporal_measurement_profile, temporal_measurement_profile_spec_sha256, quantity_profile, quantity_profile_spec_sha256`。operations は当該一操作のみ |
| library | `ref, slots, operations`。slots は `{id, subject_ref}`（1〜64）、operations は0〜256 |
| destinations | 要求プロファイル（1〜16）。`(id, version)` で一意 |
| views | `{id, as_of}`（1〜64）。参照時点（UTC秒精度） |
| queries | 1〜32件。§6 |
| 共通上限 | 1 MiB・深さ64、整数予算0〜100000。bool・生小数・NaN は自動変換しない |

静的検査（予算の前）は、操作の形、組み立てた台帳の P2-i による検査（budget=0）、プロファイルの形と参照を行います。

## 4. 操作と台帳

操作は共通の欄 `id`（一意）、`kind` を持ち、`kind` ごとに次の欄を**すべて**持ちます（未知の欄は拒否。`record_sha256`・`quantity_ref` など hash を表す欄は受け付けません）。

| kind | 欄 |
| --- | --- |
| `record` | `slot_ref, property_ref, specimen, method, validity, value, certainty, recorded_at, origin`、任意で `capabilities`（既定は空の配列） |
| `correct` | `record` の欄に加え `corrects`（訂正する記録の id の配列、1件以上）、`reason` |
| `confirm` | `record_ref, reviewer_ref, recorded_at` |

- `specimen`・`method`：P2-g／P2-i と同じ `{kind: known, ref, version}`／`{kind: unknown}`／`{kind: unspecified}`。
- `validity`：P2-i と同じ `bounded`（`start`・`end`）、`unknown`、`unspecified`。
- `value`：`{magnitude, unit_ref, quantity_kind_ref}`。`magnitude` は P2-f の点または区間。
- `origin`：`{kind, ref}`。`kind` は `observed`／`judgment`／`imported`／`ai_candidate`。
- 台帳への写像：各 `record`／`correct` は P2-i の記録と、`quantity:<id>` を ref とする数量の包み（P2-f のリテラル。リテラルの出自は `observed`・`judgment`→`literal`、`imported`→`imported_literal`、`ai_candidate`→`ai_candidate`、ref は操作の `origin.ref`）に写る。`confirm` は、人の確認（`reviewer_kind=human`、`outcome=confirmed`）で、記録の内容 hash を拘束する P2-i の確認に写る。確認の id は操作の id。
- 操作の順序は意味を持たない（時刻は操作の `recorded_at`）。台帳の配列は操作の順に保たれる。

## 5. 出力先の要求プロファイル

```json
{"id": "dest:numeric-exchange", "version": "2",
 "output": {"kind": "exchange"},
 "elements": [{"element": "value", "form": "domain", "unit_ref": "u_base"},
              {"element": "context", "field": "property", "requires": "known"},
              {"element": "context", "field": "method", "requires": "known"}]}
```

| 出力の種類 | 要素 | 出力 |
| --- | --- | --- |
| `line`（記録画面の一行） | `value`（`form=single_point`、`unit_ref`、`decimal_places` 0〜6）1つ。`context` は任意 | 丸めた文字列 |
| `exchange`（数値の交換） | `value`（`form=domain` または `single_point`、`unit_ref`）1つ。`context` は任意 | 厳密な換算領域と文脈、出自の種類、人の確認 |
| `trend`（縦断の要約） | `trend`（`context_match`：`property`・`specimen`・`method` の部分集合、1つ以上）1つのみ | 二時点の値の関係の集合 |

- `context`：`field` は `property`・`specimen`・`method`、`requires` は `known` のみ。`specimen`・`method` は `kind=known` のとき満たされる。`property` は、P2-i の語彙にあるとき満たされる（なければ語彙の限界で `unassessed`）。
- 未知の出力の種類・要素の種類・形・フィールド・`requires` は `unsupported_profile`。構造の誤り（欠落・型・重複・種類と要素の組み合わせの矛盾）は `invalid_input`。
- 要求プロファイルは宣言だけを持つ。出力先の名前（id）で処理を分岐しない（Q1）。

## 6. 問い合わせと評価

| 種類 | 欄 |
| --- | --- |
| `line`・`exchange` | `id, view_ref, slot_ref, destination_ref, target_at`。`destination_ref` は `{id, version}` |
| `trend` | `id, view_ref, slot_ref, destination_ref, from_at, to_at`。`from_at` は `to_at` より厳密に前 |

評価は、問い合わせごとに次の順で行い、**最初に当てはまる段階の結果**になります。

1. **選択**：P2-i の計画（全 view・全問い合わせ。`trend` は2本）を一度だけ再実行し、該当の行を読む。
   - 未知能力 → `unassessed`（`unknown_capability`）。
   - 選択の段階の理由（`validity_unknown`・`validity_unspecified`・`no_adopted_measurement`・`unresolved_measurement_conflict`）→ `needs_information`。依頼は§7。
   - それ以外（文脈・語彙の理由、または計算できた行）→ 候補が一意。`candidate_refs` の唯一の記録を選択とする。
2. **要素**：要求プロファイルの要素を順に判定する。`context` は選択された記録の欄を見る。`value` は、選択された記録のリテラルを P2-f で目標の単位へ換算し（計算できた領域に対して）形を見る。`trend` は §6.1。
3. **集約**：要素の状態 `met`／`unmet`／`unrepresentable`／`unassessed` のうち、unassessed があれば `unassessed`、なければ unrepresentable があれば `not_representable`、なければ unmet があれば `needs_information`（理由 `required_information_missing`）、すべて met なら `satisfied`。

| 要素の結果 | 状態 | 理由 |
| --- | --- | --- |
| `context` の specimen／method が known でない | `unmet` | 理由は集約で `required_information_missing` |
| `context` の property が P2-i の語彙にない | `unassessed` | `unknown_property` |
| `value` の量種・単位が語彙にない | `unassessed` | `unknown_quantity_kind`／`unknown_unit` |
| `value` が目標単位と次元が合わない | `unrepresentable` | `unit_not_convertible` |
| `value` が `single_point` で、換算領域が閉じた一点でない | `unrepresentable` | `value_not_a_single_point` |
| `value` の丸めの文字列が64文字を超える | 資源停止 | `display_text_limit`（P2-j と同じ） |

### 6.1 `trend`

両端点を§6 の1で選択する。どちらかが選択の段階で止まれば、理由の和集合で `needs_information`（または `unassessed`）。両方選ばれたら、`context_match` の各欄について：

1. specimen／method が known でない端点があれば `unmet`（`required_information_missing`）。property が語彙になければ `unassessed`。
2. 全欄が known で、二つの記録の欄の値が異なれば `unrepresentable`（`contexts_differ`。異なる欄とその両側の値を要素に残す）。
3. 一致すれば、両端点のリテラルを別の ID（`endpoint:from`・`endpoint:to`）に写して P2-f の比較（独立な変数）へ渡し、関係の集合と、一つに定まればその関係を返す。次元・量種の不一致は `unrepresentable`（`incompatible_dimension`／`incompatible_quantity_kind`）。

関係の語は P2-f のまま（`less`／`equal`／`greater`）で、臨床的な増減・有意性の意味を持たない（P2-m と同じ）。

## 7. 追加の依頼

`needs_information` の行は、不足ごとに依頼を持つ。依頼は `{element, action, record_ref, records, candidates, slot_ref, target_at, ends}` の欄を**すべて**持つ（使わない欄は `null`／空配列）。

| 不足 | `element` | `action` | 備考 |
| --- | --- | --- | --- |
| 期間が unknown／unspecified の適格な記録が阻害 | `selection` | `refine_validity` | `records`：阻害する記録 |
| 採用できる記録がない。可視で、確定の確度で、確認がなく、対象時点を覆う記録がある | `selection` | `confirm_pending` | `records`：その記録 |
| 採用できる記録がない。上に当てはまる記録がない | `selection` | `record_and_confirm` | `slot_ref`・`target_at` |
| 適格な候補が複数 | `selection` | `resolve_conflict` | `records`：候補 |
| 選択された記録の specimen／method が known でない | `context:specimen`／`context:method` | `confirm_candidate` または `observe_and_record` | `record_ref`：その記録。`candidates`：可視で確認がなく確度が確定で対象時点を覆い、その欄が known の保留中の記録（`{record_ref, origin_kind, proposed}`）。あれば `confirm_candidate`、なければ `observe_and_record` |

- `trend` では `ends`（`from`・`to` の整列した配列）を持つ。同じ記録の欄は一つの依頼にまとめる。依頼は要素の順、同じ要素では `record_ref` の順に整列する。
- 依頼は `needs_information` の行にだけ入る。他の状態の行は空配列。候補（保留中の記録）は、満たしたことに使わない。

## 8. 出力と流れ

| 種類 | `output` |
| --- | --- |
| `line` | `{text, coefficient, unit_ref, decimal_places, rounding_policy}`。丸めは `fiction:decimal-half-even@1`（最近接偶数。P2-j と同じ数式） |
| `exchange` | `{converted_domain, unit_ref, quantity_kind_ref, context, origin, human_confirmed}`。`context` は `{property_ref, specimen, method}`（記録の値のまま。unknown も保つ）、`origin` は `{record, quantity}`（出自の kind）、`human_confirmed` は `true` |
| `trend` | `{relation_set, certain_relation, direction, from_at, to_at, assumptions}`。`direction=from_relative_to_to`、`assumptions=[independent_time_variables]` |

`flows`（出力に渡る・渡らない区別）は、出力の種類ごとの固定の表で、`satisfied` の行に付く。`not_representable` の行には、理由ごとの失う区別を付ける。値は [64](64-p2-o-cases.md) の§3 に固定する。`selection`（選択された記録の出所）は出力の外で、ライブラリが保持する。

## 9. 資源

```text
M = 1 + C + Σquery fee + 1
C   = P2-i の全計画の料金（設計43の§6。trend は問い合わせ2本分）
fee = 6 + 8   （line・exchange：P2-f の換算を予約）
    = 6 + 12  （trend：P2-f の比較を予約）
```

開始1、C を先払いして budget=C で P2-i を一度だけ実行（実費が C と一致しなければ停止）、問い合わせを id 順に先払い（払い戻しなし）、最後の確定1。子の P2-f の呼び出しは、予約を使い切る（換算8、比較12）。C が上限を超えれば P2-i を呼ばず、全行を未完了にする。未完了の行の `selection`・`elements`・`requests`・`output`・`flows` は null。標準の一つの `line` 問い合わせは C=16、fee=14 で M=32。標準の `trend` は C=27、fee=18 で M=47。

## 10. 七欄と義務の主題（H1・H2・H5 の実験）

| 欄 | P2-o の決定 |
| --- | --- |
| 前提 | 医療者の操作は記録・確認・訂正の3つ。共通表現は P2-i の台帳。出力先の要求は宣言。意味の正しさ・医学的妥当性・画面・AI の生成は扱わない |
| 版 | 自己の profile と native 仕様 hash を固定し、P2-i と P2-f の profile・hash を consumer が固定する。要求プロファイルは `(id, version)` |
| 確認対象 | 人の確認は `confirm` 操作が P2-i の内容指定の確認として作る。出力先は確認を作らない。AI 由来は人の確認まで保留 |
| 情報の選択 | 参照時点 `as_of` の view と対象時点。選択は P2-i の再実行の診断。後勝ちで解決しない |
| 問い | 「出力先 D（版 v）の要求は、この台帳で参照時点 k・対象時点 t に満たされるか」。満たされる／不足（依頼）／表せない／評価不能 |
| 保持・喪失・追加 | 出力ごとの `flows` と、`selection` の出所。AI 由来の種類を保つ |
| 資源・停止 | §9。停止の順序は§6 |

### 10.1 義務（19：共通4＋R5の3＋CL-1〜12）と主題の割当

| 義務 | 内容 | 主題 |
| --- | --- | --- |
| CL-1 | 自己・P2-i・P2-f の版と実体を固定する。外部の台帳・hash・結果・操作の hash を受け付けない | A |
| CL-2 | 操作から台帳を組み立て、確認が記録の内容を拘束する。台帳の妥当性を P2-i の再実行で検査する | B |
| CL-3 | 参照時点以前の操作だけで選び、妥当な未来の操作が完成した結果を変えない | C |
| CL-4 | 訂正・競合・非復活が出力先の評価へそのまま伝わる。後勝ちで解決せず、競合は依頼にする | D |
| CL-5 | 停止の順序（能力 → 選択 → 要素 → 集約）を固定し、状態の優先を守る | E |
| CL-6 | 全計画 C・問い合わせごとの fee・子の予約の使い切り・原子性・最後の確定を照合する | F |
| CL-7 | P2-j の丸め、P2-m の関係と文脈の規則、P2-i の料金の式を再び述べた部分が、元と一致する（継承の宣言と証人） | G |
| CL-8 | 推測で補った情報は常に空。AI 由来の候補は要求を満たさず、出自の種類を保つ | H |
| CL-9 | 出力先の要求を宣言として持ち、出力先の id で処理を分岐しない。未知の種類を拒否する | I（意味固有） |
| CL-10 | 追加の依頼が、不足ごとに一つで、満たされた行や表せない行には出ない。要求の版を上げた差が、不足の数に等しい | I |
| CL-11 | 表せない（`not_representable`）と不足（`needs_information`）を分け、失う区別を返す | I |
| CL-12 | 出力ごとの保持・喪失・追加と、選択された記録の出所を、全ての出力で保つ | I |

予測（H2）：12の個別義務のうち、A〜H に8（CL-1〜8）、意味固有に4（CL-9〜12）。**CL-9（要求を宣言で持つこと）は、既存の主題のどれにも収まらない可能性がある**（宣言を解釈する側の義務）。収まらなければ、新しい主題を記録する。

## 11. 実装前に固定する予測と反例

### 11.1 予測

| ID | 予測 | 外れた場合に分かること |
| --- | --- | --- |
| V1 | 既存の拡張の実装・仕様・宣言・旧実行例を一つも変えずに実装できる（変更は登録点：host の振り分け、評価・検査の一覧、固定対象、再固定の連鎖、宣言の表）。新しいクラスも宣言の書式の変更も要らない | K2・H5 |
| V2 | 要求プロファイルを足すだけで、新しい出力先が動く（D-E の例が、ライブラリの変更なしに通る）。未知の種類は拒否される | Q1：要求がコードに漏れている |
| V3 | D-B の版を v1 → v2 → v3 と上げたとき、全数の台帳の族で、依頼の数の差が「選択された記録で新しく要求される欄が known でない数」に等しい。情報が揃う台帳では0 | Q2 |
| V4 | `ai_candidate` の保留中の記録は、要求を満たすことに使われず、依頼の候補としてだけ現れる。人の確認の後は、満たされ、出自の種類が出力に残る | Q4 |
| V5 | 出力があるすべての行に `selection` があり、`exchange` の出力は出自の種類と人の確認を持つ。`flows` の表が出力の種類と一致する | Q3 |
| V6 | R5 と必須欄で宣言・登録は足りる。クラスは増えない。12の個別義務のうち8が A〜H、4が意味固有で、**CL-9 が既存の主題に収まらない** | Q5・H2 |
| V7 | 継承の宣言3項目（P2-j の丸め、P2-m の関係と文脈、P2-i の料金）に、既存の例だけで証人が付き、登録時に全て一致する | P2-n の機構が実際に使える |
| V8 | P2-m で見つかった接続面の閉包（P2-i の出力が P2-f の入力の上限を超える）は再発しない（比較は元のリテラルで行う）。丸めの文字列の上限（64文字）は残る | 設計の違いで閉包が避けられる |
| V9 | 料金 M = 2 + C + Σfee が全要求で成り立つ。P2-i の実費は C、P2-f の実費は予約と一致 | F |
| V10 | P2-g の `affected()`：P2-j の変更が、継承によってこの拡張を列挙する | P2-n の機構の効果 |

### 11.2 反例の候補（64 に具体値を固定）

| ID | 内容 | 試すこと |
| --- | --- | --- |
| Y1 | 方法が未知の記録を、方法を要求しない出力先（v1）と要求する出力先（v2）へ | v1 は満たされ（unknown を保つ）、v2 は不足を一つ依頼する。推測で補わない |
| Y2 | 保留中の AI 候補が方法を持つ | 候補として依頼に出るだけで、満たされない |
| Y3 | 幅のある値を一行の出力先へ | 表せない（値を一点に潰さない）。不足ではない |
| Y4 | 部分訂正で文脈が変わる二時点の要約 | 表せない（`contexts_differ`）。slot 全体や最新の記録で文脈を代用しない |
| Y5 | 未知の要求の要素・出力の種類 | `unsupported_profile`（出力先の名前では分岐しない） |
| Y6 | 同じ入力を、出力先の順序・操作の順序を替えて | 結果の意味は同じ |
| Y7 | 参照時点より後の操作を足す | 完成した結果は変わらない |
| Y8 | 確認前の記録・競合・期間不明 | 依頼になる（選択の段階の理由ごとに行動が異なる） |

## 12. 受入条件

1. [64](64-p2-o-cases.md) の期待・予測・反例を、runtime より先に保持し、実行結果から期待を更新しない。
2. 専用 native・module・R5 宣言・fixture・独立な別計算を追加する。P2-i・P2-f・P2-g・P2-j・P2-m・旧核は変更しない（V1）。
3. 別計算は P2-i の別計算（区間差引き）と P2-f の別計算を再利用し、要素の判定・依頼・集約・丸め・料金を自前の独立実装で持つ。
4. 小さな全数の列挙（文脈の状態・保留中の候補・選択の種類・出力先の版）、乱数、要求の版の差（V3）、出力先を足す検査（V2）、予算の掃引、入力の不変性、変異（要素の判定の省略、推測の補完、AI 候補の昇格、後勝ち、優先の入れ替え、先払いの省略）を検査する。
5. Python 3.11／3.14 で、全テスト系列、版比較つき統合評価、旧い22,052件の挙動 digest を回帰する。分母の変更は旧い値を履歴として残して明示的に更新する。
6. 追加前は `39ec6e9`、固定対象1,359ファイル、manifest `4b4d4f8118be4195b6bcf56125e00c2bb992fa54cb44404cc828412a32ad22da`、束 `527725eb639b3ab0569695d511943836c3281fb25a5d4be09cc7fcd1eb31bb4a`。件数・hash・予測の結果・残る穴を結果の文書に残す。`independent_review` / `evaluation_frozen` は false。

## 13. 範囲外

画面・UI、LLM、DSL の文字列構文、実マスターの変換器、永続化、請求の確定、診断や治療上の判断、複数患者の集計、FHIR など外部仕様への適合（第二段で扱う場合も、適合の主張はしない）、出力先の要求の自動導出、操作の取り消し・撤回、確度の変更、`line` 以外の丸め方針。

今回新たに参照した外部仕様・マスター・臨床データはありません。この断片は、薄い臨床ライブラリの一つの実演で、医療者の負担が実際に減ることの証明ではありません。最終目標は変化に耐える医療コード体系そのものの確立であり、この有限の設計はその一つの検査です。
