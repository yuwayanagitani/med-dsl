# P2-p：出力先の構造への写像の可否の診断（FHIR R5 Observation への接地）の意味設計

作成日：2026-10-21。状態：**作成者側の設計草案。runtime・native 仕様・宣言・実行用 fixture は未実装**。[接地の監査66](66-p2-p-grounding-audit.md) で確認した、ライブラリの値・時点・文脈・確認・出自と FHIR R5 Observation の構造との食い違いのうち、**取得したページの記述だけで判定できるもの**を、診断として実装する設計です。利用者の確認前に実装には進みません。FHIR への適合は主張しません。独立確認は未実施で、`independent_review` / `evaluation_frozen` は false のままです。数値・単位・識別子・出力先の要求は架空で、構造の事実だけ、取得したページ（台帳 [03-materials.json](03-materials.json)）から取りました。

## 1. 問い

| ID | 問い |
| --- | --- |
| Q1 | ライブラリが「満たされた」と判定した出力を、実在の構造（FHIR R5 Observation の `value[x]`・`effective[x]`・`method`・`specimen`）が**情報を落とさず・足さず**に表せるかを、機械的に判定できるか |
| Q2 | 表せないときの理由（開いた端、小数で書けない有理数、桁数、区間の数量への押し込み、期間の端の扱い）を区別して返し、近い値に丸めたり、端を閉じたりしないか |
| Q3 | 出せるときに、失う区別（文脈の三状態、確認、出自）と、足す仮定（期間の端の規約）を、根拠つきで流れ（flows）に残せるか |
| Q4 | 構造の事実（閉区間だけ、18桁、期間の端を含む）を、出典のページとハッシュに結んだ**仕様の表**として持ち、要求に埋め込まずに済むか |
| Q5 | P2-o を変更せず、合成の拡張として足せるか。必要な義務は既存の主題で足りるか |

## 2. 設計判断

| 判断 | 初回に採る設計 | 理由・見直す条件 |
| --- | --- | --- |
| GD1 | **合成の専用 R5 を新設する**。P2-o の `run_library` を固定版で一度だけ呼び、その行（`satisfied` の `exchange`）に対し、構造への写像の可否を判定する。P2-o の実装・仕様・宣言・例は変更しない | 構造の語彙を P2-o に足すと、P2-o の版を上げ、141の例と宣言・台帳の hash を再固定することになる（P2-l の手順）。合成なら既存の変更は登録の入口だけ。見直す条件：判定が P2-o の内部状態を要るとき |
| GD2 | 構造の事実は**native 仕様の表**に持つ（§4）。各行に、出典のページ id とその SHA-256、ページ上の目印の語を持たせる。要求は構造の**名前**（`fhir-r5-observation`）と、出力先ごとの選択（値の型、期間の規約、運ぶ文脈の欄）だけを持つ | 構造の事実を呼び出し側が書き換えられないようにする。構造が増えたら仕様の版を上げる |
| GD3 | 写像の可否は4つの判定：**値**（`quantity`／`range`）、**期間**（規約）、**文脈の運び方**、**運ばないもの**（確認・出自）。いずれも**丸めない・閉じない・補わない**。表せなければ `not_representable` で理由を返す | 原情報を消さず、不明な属性を補って確定しない（AGENTS.md） |
| GD4 | 期間の端の規約は**呼び出し側の宣言**でだけ使う。`undeclared`（既定）なら、半開区間 [start, end) は表せない（FHIR の Period は end を含む）。`exclusive_end_as_last_second` を宣言したときだけ、end を1秒戻した値で表し、**仮定を足したこと**を流れに残す。ライブラリの時刻は秒の粒度なので、この規約は秒の粒度の上でだけ正確 | 66 の G6。規約を作成者が決めて黙って使うと、情報を足すことになる |
| GD5 | 文脈 method・specimen は**存在か不在か**で運ぶ。known なら運び、unknown／unspecified は不在として運び、**区別が落ちたこと**を流れの `lost` に残す | 66 の G3・G4。拡張で運べるかは、拡張の定義のページが未取得で未確認 |
| GD6 | 構造 `fhir-r5-observation` では、人の確認と出自の種類は**運べない**（66 の G8・G9：Provenance が担う）。常に `lost` に残す。Provenance への出力は範囲外 | Observation と Provenance の組を出力先とする設計は、次の段階 |
| GD7 | 判定は `satisfied` の `exchange` の行だけに行う。他の状態の行は、P2-o の行をそのまま通し（`grounding` は `not_evaluated`）、`line`・`trend` の出力先に対象を宣言した要求は静的に拒否する | 比較不能を差分なしとして扱わない。通した行は、判定していないと明示する |
| GD8 | 宣言のない出力先（`exchange` で対象が宣言されていない）は、行を通し、`grounding` は `not_declared`。**判定していない**と明示し、写像できるとは言わない | 同上 |
| GD9 | 認定は常に `not_certified`。推測で補った情報は常に空。構造への適合は主張せず、出力の名前は `target_projection`（構造の要素名に沿うが、資源ではない） | 診断であり、FHIR の資源の生成ではない |

## 3. 入口と型（予約名）

| 項目 | 予約する型・範囲 |
| --- | --- |
| profile / operation | `p2-structure-grounding-draft-1` / `run_structure_grounding` |
| request / result | `p2-grounding-request-draft-1` / `p2-grounding-result-draft-1` |
| 回答型 | `structure_grounding_projection` |
| 要求 | `schema_version, operation, consumer, library_request, targets, budget` |
| consumer | 自己の `profile, profile_spec_sha256, operations`、P2-o の `library_profile, library_profile_spec_sha256`。operations は当該一操作のみ |
| library_request | P2-o の要求そのもの（予算欄はこの拡張が決める。要求の予算は外側だけ）。P2-o の検査をそのまま受ける |
| targets | `{destination_ref{id,version}, structure, value, period, context_fields}` の配列。`structure`：`fhir-r5-observation` のみ。`value`：`quantity`／`range`。`period`：`{end_convention}`（`undeclared`／`exclusive_end_as_last_second`）か省略（期間は運ばない）。`context_fields`：`method`・`specimen` の部分集合 |

結果は問い合わせ id 順の `results[]`。各行は P2-o の行の全欄（`status`・`reason_codes`・`selection`・`elements`・`requests`・`output`・`flows`・`assessment_complete`）に加えて `grounding`、`base_status` を持つ。トップレベルには P2-o の結果（`library`、台帳の要約）と `steps_used`、`certificate`（常に `not_certified`）、`inferred_information`（常に空）。

## 4. 構造の事実の表（native 仕様に入れる）

出典は台帳の項目（SHA-256 は台帳が持つ）。仕様の各行は、出典の id・ページ上の目印の語・事実の記述（短い言い換え）だけを持つ。ページの本文は入れない。

| 事実 | 出典（台帳 id） | 目印 |
| --- | --- | --- |
| F-R1 Range の low・high は両端を含む。端に comparator は付かない。端が欠けると、その端は不明 | `fhir-datatypes-5.0.0` | `inclusive` |
| F-R2 Quantity の `value` は decimal。decimal は小数表現を持つ有理数で、桁は18まで | 同 | `18 digits` |
| F-R3 Period の start は含み、end も含む | 同 | `inclusive boundary` |
| F-R4 Observation の `value[x]` は 0..1、型に Quantity・Range を含む。`dataAbsentReason` は `value[x]` が無いときだけ | `fhir-observation-5.0.0` | `dataAbsentReason` |
| F-R5 Observation の `method`・`specimen` は 0..1。`method` に欠落の理由の要素はない | 同 | `specimen` |
| F-R6 Observation の `effective[x]` は dateTime／Period／Timing／instant | 同 | `effective[x]` |
| F-R7 確認・署名などの追加の状態は Provenance で表す（status の `final` の記述） | `fhir-codesystem-observation-status-5.0.0` | `Provenance` |

**判断の分かれる点**：F-R2 の「18桁」の数え方（先頭の 0 を数えるか）は、ページの記述だけでは決まらない。保守側に数える（`0.5` は2桁）。境界の例は「解釈に依る」と明記し、正確に FHIR が許す境界とは主張しない（I1）。

## 5. 判定

行の `output.converted_domain` を [lo, hi]（開閉つき、約分した有理数）とする。

### 5.1 値

| `value` | 条件 | 満たさないときの理由 |
| --- | --- | --- |
| `quantity` | lo = hi で両端が閉じている | `interval_not_representable_as_quantity` |
| `range` | 両端が閉じている（lo = hi も可） | `open_boundary_not_representable` |
| 共通 | 端が約分した分母の素因数が 2 と 5 だけ（有限小数） | `not_decimal_representable` |
| 共通 | 端の小数表記の桁（符号と小数点を除く。先頭の 0 を数える）が18以下 | `digits_exceed_limit` |

理由は、満たさない条件の全てを整列して返す（和集合）。端の判定は lo と hi の両方に行う。

### 5.2 期間

選択された記録の `validity`（有界の半開区間 [s, e)）について：`period` が省略されれば運ばない（`lost` に `validity`）。`end_convention` が `undeclared` なら `period_end_convention_undeclared`。`exclusive_end_as_last_second` なら Period = [s, e − 1秒]（両端を含む）で、`added` に `assumption:end_convention:last_second`、`assumption:second_granularity`。

### 5.3 文脈と運ばないもの

`context_fields` の各欄が known なら運ぶ。unknown／unspecified なら不在として運び、`lost` に `context_state_distinction:<欄>`。常に `lost` に `human_confirmation`・`origin_kind`（GD6）。

### 5.4 状態の優先

P2-o の行が `satisfied` でなければ、その行を通す（GD7）。`satisfied` の行は、5.1〜5.2 のいずれかを満たさなければ `not_representable`（理由は和集合、`output` は null、`base_status` は `satisfied`）。5.3 は表せるときの損失の報告で、状態を変えない。

## 6. 出力と流れ

表せる行の `grounding.projection`：`value`（`quantity` なら `{decimal}`、`range` なら `{low, high}`、小数の文字列。精度の意味づけはしない）、`unit_ref`（コードの系は運ばない）、`period`（運ぶとき）、`absent`（不在として運んだ文脈の欄）、`context`（known の欄の `ref`・`version`）。`grounding.flows_delta`：`lost`・`added`（§5）。行の `flows` は P2-o の `exchange` の流れに `flows_delta` を足したもの。表せない行の `flows` は、理由ごとの失う区別の表（`interval_bounds`、`exact_value`、`interval_width`、`validity_end`）。

## 7. 資源

M = 2 + M_lib + 3N（N は問い合わせ数）。M_lib は P2-o の全体の料金で、子の予算は M_lib を先払いして使い切ったことを照合する。判定の自前の料金は、問い合わせごとに3（値・期間・文脈）。子が資源停止なら、未完了行は5つの値の欄（`grounding`・`output`・`flows`・`requests`・`selection`）を null にする。入力不正は予算に依らない。

## 8. 七欄と義務の主題（H1・H2・H5 の実験）

| 欄 | 内容 |
| --- | --- |
| 前提 | 構造の事実は取得したページの記述。FHIR の適合・医学的意味は扱わない |
| 版 | 自己と P2-o の profile・仕様 hash を consumer が固定。構造の事実の表は出典の SHA-256 を持つ |
| 確認対象 | 確認は作らない。人の確認は運べないものとして `lost` に残す |
| 情報の選択 | P2-o の選択をそのまま使う。再選択しない |
| 問い | 「この出力先の構造は、この行の出力を、情報を落とさず・足さずに表せるか」 |
| 保持・喪失・追加 | §5・§6 |
| 資源・停止 | §7。停止の順序：P2-o の停止 → 静的検査 → 値 → 期間 → 文脈 |

義務（17：共通4＋R5の3＋GR-1〜10）と主題：GR-1（A）自己・P2-o の版と実体を固定、構造の事実の出典のハッシュを仕様に持つ。GR-2（B）確認を作らず、人の確認を運べないものとして残す。GR-3（C）P2-o の選択を再選択しない。GR-4（E）停止の順序と状態の優先。GR-5（F）料金・原子性。GR-6（H）丸めない・閉じない・補わない（仮定は宣言した規約だけで、流れに残る）。GR-7（I）値・期間の判定規則。GR-8（I）失う区別と足す仮定の報告。GR-9（I）構造の事実が出典の目印と一致する（ページが手元にあれば検査）。GR-10（I）判定していない行を、写像できると言わない。予測（H2）：GR-1〜6 が A〜H、GR-7〜10 が意味固有。**GR-9（外部の資料に結んだ事実）が既存の主題に収まらない可能性がある**。継承の宣言は不要の見込み（再述する他拡張の規則がない）。

## 9. 実装前に固定する予測と反例

### 9.1 予測

| ID | 予測 | 外れた場合に分かること |
| --- | --- | --- |
| W1 | 既存の実装・仕様・宣言・旧実行例を一つも変えずに実装できる（変更は登録の入口：host、評価・検査の一覧、固定対象、再固定の連鎖、宣言の表） | 合成の方針 |
| W2 | 値の判定は手導出の規則に一致する。有限の格子（分母 1〜40、分子 −60〜60、4通りの開閉、点・区間）の全数で、`quantity`／`range` の可否と理由が規則どおり | 5.1 の規則 |
| W3 | P2-o の行を通す場合（`satisfied` 以外）、P2-o の行と一致する。表せる行の P2-o の欄（選択・要素・出力）は P2-o の行と同一 | 合成の透明性 |
| W4 | 端の規約を宣言しないと、半開区間は全て `period_end_convention_undeclared`。宣言すると端が1秒戻り、仮定が `added` に出る | GD4 |
| W5 | `lost` の `context_state_distinction:*` の数は、`context_fields` のうち、選択された記録で known でない欄の数に等しい。`human_confirmation`・`origin_kind` は常に `lost` | GD5・GD6 |
| W6 | 料金 M = 2 + M_lib + 3N が全要求で成り立つ。P2-o の実費は M_lib | 資源 |
| W7 | 呼び出し側が構造の事実を変えられない（要求に事実の欄がない）。出典の目印が手元のページに存在する | Q4 |
| W8 | 義務は R5 と必須欄で足りる。クラスも書式も増えない。**GR-9 は既存の主題に収まらない** | H2・H5 |
| W9 | `affected()`：P2-o の変更が、依存によってこの拡張を列挙する | 依存の効果 |
| W10 | 「18桁」の境界の例は、保守側の解釈に依る。ページだけでは決まらないことが、例に明記される | I1 |

### 9.2 反例（64 に相当する期待の文書に具体値を固定）

| ID | 内容 | 試すこと |
| --- | --- | --- |
| Z1 | `u_third` の 1 → 2/3 `u_base` を `range` へ | 小数に丸めない。`not_decimal_representable` |
| Z2 | 半開区間 [1,2) を `range` へ | 端を閉じない。`open_boundary_not_representable` |
| Z3 | 区間 [1,2] を `quantity` へ | 中点に潰さない。`interval_not_representable_as_quantity` |
| Z4 | 小数で書けるが桁が多い値（19桁と、境界の桁） | `digits_exceed_limit`。境界は解釈に依ると明記 |
| Z5 | 期間の規約が `undeclared`、`exclusive_end_as_last_second` | 前者は表せない。後者は仮定を足したと明示 |
| Z6 | method が unknown と unspecified | どちらも不在。区別を失ったと明示 |
| Z7 | 対象を宣言していない出力先 | `not_declared`（写像できるとは言わない） |
| Z8 | `line`・`trend` の出力先に対象を宣言 | 静的に拒否 |
| Z9 | P2-o が `needs_information` の行 | 行を通す。`grounding` は `not_evaluated` |

## 10. 受入条件

1. 期待・予測・反例を、runtime より先に別の文書で固定し、実行結果から期待を更新しない。
2. 専用 native・module・R5 宣言・fixture・独立な別計算を追加する。P2-o・P2-i・P2-f・P2-j・P2-m・旧核は変更しない（W1）。
3. 別計算は、有限小数の判定・桁数・約分を自前で持ち、P2-f の区間の別計算を再利用する。
4. 有限格子の全数、乱数、P2-o の行との差分、料金、予算の掃引、入力の不変性、型破損、変異（端を閉じる、丸める、規約の黙った使用、区別の損失の欠落、確認の損失の欠落、不足の行の誤った変更、先払いの省略）を検査する。
5. Python 3.11／3.14 で、全テスト系列、版比較つき統合評価、旧い22,052件の挙動 digest を回帰する。分母の変更は旧い値を履歴として残す。
6. 追加前は `4d505d3`（台帳の追加の後）。件数・hash・予測の結果・残る穴を結果の文書に残す。`independent_review` / `evaluation_frozen` は false。

## 11. 範囲外

Provenance への出力、`status`・`code`（必須の要素）の写像、値のない記録（`dataAbsentReason`）、検体の状態（Specimen の `status`・`condition`）、Quantity の `comparator`、コードの系（UCUM など第三者の符号）、`Timing`・`instant`、FHIR の資源としての生成と適合の検査、他の資源（Procedure など）、拡張による欠落の理由の運び方（拡張の定義が未取得）。これらは次の段階で、必要なページの取得の確認を取ってから扱う。

今回の設計で新たに参照した外部資料は、66 で取得した HL7 FHIR R5 v5.0.0 のページ（台帳に記録）で、構造・型・濃度・制約の読み取りに限ります。第三者の用語の内容は取り込んでいません。この設計は、構造への写像の一つの診断で、実際の医療者の負担が減ることの証明でも、FHIR への適合の主張でもありません。

## 12. 利用者に確認すること

| ID | 確認 | 推奨 |
| --- | --- | --- |
| U1 | この設計（合成の専用 R5、値・期間・文脈の3判定、Provenance は範囲外）で実装に進んでよいか | 進める |
| U2 | 期間の端の規約 `exclusive_end_as_last_second` を、初回の宣言可能な規約として入れてよいか（他の規約は入れない） | 入れる（秒の粒度の上でだけ正確と明記） |
| U3 | 「18桁」の保守側の解釈を、境界の例とともに入れてよいか | 入れる（解釈に依ると明記） |
