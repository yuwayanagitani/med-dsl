# P2-n：継承の欄の手指定期待

作成日：2026-10-21。状態：**作成者側の手指定。実装前に固定する**。[設計59](59-p2-n-design.md) の予測 N1〜N9 と反例 X1〜X7 に、具体的な宣言・例の組・期待を与えます。期待は設計文書とこれまでの設計・例の記述から手で導いたもので、registry や宣言の出力から作りません。実装の結果と食い違った場合は、実装・期待・設計のどれが誤りかを調べて記録し、期待を結果に合わせて黙って更新しません。独立確認・評価用正解の凍結は未実施です。

## 1. 手で挙げた継承の一覧（実装前の予測 N2・N3）

挙げ方：既存の設計文書（23〜57）の「と同じ」「継承」「再び述べる」の記述（grep で拾い、読んで判断）から、**実装を共有せず**、断片で観測が一致するはずのものを挙げました。呼び出し（import）で等しさが構成される関係（例：P2-m が P2-i の行を端点に使う）は継承ではなく依存で、挙げません。宣言を強制した後の監査（[59 の N2](59-p2-n-design.md)）で、この一覧との差を記録します。

証人の組は、**入力の構造が断片について等しい**既存の例どうしから選びました（出力を見て選んでいません。選ぶ前の根拠は、各例の入力と、例が持つ手指定の期待）。位置は結果の中の位置です。

| # | 継承する側 | 元 | 断片 | 義務 | 証人（元の例 ↔ 自分の例、位置）または欠落の理由 |
| --- | --- | --- | --- | --- | --- |
| 1 | p2-temporal-measurement | p2-temporal-assertion | 期間の分類（bounded の半開区間、unknown、unspecified）と、確認済みの unknown／unspecified の記録が阻害する理由 | TM-5 | `t13` ↔ `c13-unknown`、`t14` ↔ `c13-unspecified`（いずれも `results[0].reason_codes`） |
| 2 | p2-temporal-measurement | p2-measurement-binding | 文脈（method・specimen）の unknown／unspecified、および property・量種・単位の未知による停止の理由名 | TM-5 | `m16` ↔ `c17-method-unknown`、`m17` ↔ `c17-method-unspecified`、`m18` ↔ `c17-specimen-unknown`、`m19` ↔ `c17-specimen-unspecified`、`m32-property` ↔ `c19-property_ref`、`m32-kind` ↔ `c19-quantity_kind_ref`、`m32-unit` ↔ `c19-unit_ref`（`results[0].reason_codes`） |
| 3 | p2-temporal-display | p2-quantity-display | 10進の最近接偶数丸め（係数・文字列）と、丸めセルによる閾値の判定 | TD-5 | 丸め：`p03` ↔ `j02-5`、`p04` ↔ `j02-27`、`p05` ↔ `j02--5`、`p06` ↔ `j02--27`、`p10-5` ↔ `j06-5`、`p10-7` ↔ `j06-7`（`results[0].artifact.text`）。閾値：`p24-ge-0` ↔ `j24-13-0-ge`、`p24-lt-1` ↔ `j24-13-1-lt`（`results[0].question_results[0].projection_answer`） |
| 4 | p2-validity-refinement | p2-temporal-assertion | 適格な主張・訂正辺・半開区間による対象時点の判定（literal_state と採用集合）。精密化のない台帳で一致 | RF-7 | **欠落**：P2-e の例と台帳が構造的に等しい P2-k の例がない（`n01` は P2-e の経路の対照で、P2-e の要求）。全数の差分は検査が担う（21,920行） |
| 5 | p2-longitudinal-comparison | p2-measurement-binding | `matched_context`：property・specimen・method の一致と、不一致の理由 `different_*` | LC-10 | `m28` ↔ `l24`、`m29` ↔ `l22`、`m29-version` ↔ `l23`、`m30` ↔ `l21`、`m30-version` ↔ `l20`（`results[0].reason_codes`） |
| 6 | p2-temporal-display | p2-temporal-measurement | 全計画の料金 C（記録・確認・訂正辺・query の数からの式）を再び述べる | TD-10 | `c01` の `steps_used` ↔ `j01` の `results[0].projection_evidence.temporal_measurement_reserved_steps`（16）、`c06-5` の `steps_used` ↔ `j14-5` の同じ位置（21） |
| 7 | p2-longitudinal-comparison | p2-temporal-measurement | 全計画の料金 C を再び述べる | LC-6 | `c25` の `steps_used` ↔ `l01` の `results[0].comparison_evidence.temporal_measurement_reserved_steps`（27）、`c30` の `steps_used` ↔ `l04` の同じ位置（34） |
| 8 | p2-measurement-binding | p2-temporal-assertion | 記録・確認の可視性（`recorded_at ≤ as_of`）と、適格性（確定かつ可視の人の確認がある） | MB-2 | **欠落**：台帳の型が違い（測定の記録と主張）、構造的に等しい例の組がない。確信が低い候補（P2-g の設計は「P2-e の台帳は読みません」と書くが、規則は同形） |

予測した数：項目 **8**、証人のある項目 **6**（証人は計 **26**：#1 が2、#2 が7、#3 が8、#5 が5、#6 が2、#7 が2）、欠落 **2**（#4・#8）。

## 2. 列挙・独立への影響の期待（N4・N5）

`affected()` の列挙（変更するファイル → 列挙される拡張）。継承の導入前の列挙は括弧内。

| 変更するファイル | 導入後に列挙される拡張 | 導入前 |
| --- | --- | --- |
| `src/med_dsl/measurement.py`（P2-g） | p2-measurement-binding、p2-quantity-display、p2-temporal-measurement（#2）、p2-longitudinal-comparison（#5）、p2-temporal-display（P2-i への依存と #3）の**5件** | MB・QD の2件 |
| `src/med_dsl/temporal.py`（P2-e） | p2-temporal-assertion、p2-temporal-measurement（#1）、p2-validity-refinement（#4）、p2-measurement-binding（#8）と、その依存・継承の先 p2-quantity-display、p2-temporal-display、p2-longitudinal-comparison の**7件** | TA の1件 |
| `src/med_dsl/display.py`（P2-h） | p2-quantity-display、p2-temporal-display（#3）の**2件** | QD の1件 |
| `src/med_dsl/temporal_measurement.py`（P2-i） | p2-temporal-measurement、p2-temporal-display、p2-longitudinal-comparison の**3件**（変化なし。依存で既に含まれる） | 同じ |
| `src/med_dsl/quantity.py`（P2-f） | p2-quantity-literal と、その依存先 5件の**6件**（変化なし） | 同じ |

`independent_pairs`：基底を除く19拡張の171組のうち、独立は **144**（導入前は150）。減る6組は、依存・読み取りで結ばれていなかった (TM, TA)、(TM, MB)、(TD, QD)、(VR, TA)、(LC, MB)、(MB, TA)。(TD, TM)・(LC, TM) は既に依存で結ばれている。

## 3. 検査の期待（X1〜X5）

出発点は、同梱の宣言の一つ（`p2-longitudinal-comparison`）を読み込み、次のとおり書き換えた宣言。拒否の理由は、登録時の検査の順（書式 → 実体 → 防護例 → registry の規則）で最初のもの。

| ID | 書き換え | 期待 |
| --- | --- | --- |
| X1-1 | `inherits` を削る | `missing_field`（`inherits`） |
| X1-2 | `schema_version` を draft-1 にする | `unsupported_manifest_schema` |
| X1-3 | `inherits` を配列にしない／要素に未知の項目／必須項目の欠落／空の `fragment`・`from` | `invalid_inherits`／`invalid_inheritance` |
| X2-1 | `from` が自分の id | `self_inheritance` |
| X2-2 | `from` が登録されていない拡張 | `unresolved_inheritance` |
| X2-3 | 同じ `from` と `fragment` の組が2つ | `duplicate_inheritance` |
| X2-4 | 二つの拡張が互いを継承する | どちらも解決できず拒否（先に登録されるものがない） |
| X3-1 | `obligation` が宣言にない id | `inheritance_obligation_missing` |
| X3-2 | `obligation` の `checks` が空 | `inheritance_obligation_without_checks` |
| X4-1 | 証人の値が一致しない例の組 | `inheritance_witness_mismatch` |
| X4-2 | 証人の位置が結果にない | `inheritance_witness_unresolved` |
| X4-3 | `from.example` が元の拡張の例でない／`to.example` が自分の例でない | `witness_example_not_owned` |
| X4-4 | 証人の形が不正（`path` が空、`example` が文字列でない） | `invalid_witness` |
| X5-1 | 証人が空で `witness_gap` がない／空の理由 | `unexplained_witness_gap` |
| X5-2 | 証人があるのに `witness_gap` がある | `witness_gap_with_witnesses` |
| X5-3 | 空の `inherits` | 登録される（継承なしの明示） |

登録は全か無かで、拒否された宣言は登録の状態を変えない。

## 4. 実験の期待（N6〜N9）

**E1 元の断片の変更（N6）**。P2-g の `measurement.py` の `matched_context` の判定を次のように壊した木で、P2-g の登録、P2-m の登録、P2-m と P2-g の差分の検査（324対）の結果を記録する。壊し方は断片の中だけにする。

| 壊し方 | 期待 |
| --- | --- |
| d1 `different_method` を出さない | P2-g 自身の防護例が検出して拒否する（P2-m の段階で確認済み）。P2-m は `unresolved_inheritance`。差分の検査も失敗 |
| d2 `different_specimen` を出さない | P2-g が登録され（防護例が覆わない場合）、P2-m の証人（`m29` ↔ `l22`）が拒否する |
| d3 `different_property` を出さない | 同上（`m28` ↔ `l24`） |
| d4 specimen の ref だけを比べ、version を見ない | P2-g が登録され、証人（`m29-version` ↔ `l23`）が拒否する |
| d5 `different_subject` の判定を壊す（断片の外） | 証人は拒否しない。差分の検査も一致のまま（対照） |

予測：クラス「元の防護例に捕まらず、証人が捕まえる」に1件以上、クラス「どの証人にも捕まらず、差分の検査だけが捕まえる」に1件以上が入る。d1 はクラス「元が捕まえる」。

**E2 疑いの探索（N8）**。継承の疑いを、依存・読み取りの関係がない拡張の組のうち、実装モジュールが**識別子らしい文字列定数**（8文字以上、英小文字・数字・下線で、下線を含む）を3つ以上共有するものとして求める。核のモジュールが持つ定数と、拡張自身の id・profile の語は除く。宣言した継承の組に対する再現率（見つかる割合）と適合率（疑いのうち宣言した継承の割合）を記録する。予測：再現率は0.5以上、適合率は0.5未満。

**E3 契約の版の更新の検証（N7・N9）**。

| 検査 | 期待 |
| --- | --- |
| 旧い（draft-1）の20宣言を新しい registry に渡す | 20件とも `unsupported_manifest_schema` で拒否 |
| 新しい宣言から `schema_version` と `inherits` を除いたもの | 旧い宣言（直前のコミット `3c16f68` の木）の `schema_version` を除いたものと、20件とも同一 |
| 版の比較の道具（P2-l の記録の検証）を、修正前の道具で実行する | 旧い木の宣言を作業ツリーの registry が拒否して失敗する（N7 の前段） |
| 修正後（木ごとの registry） | P2-l の記録の検証が再び通る |

## 5. 前提と限界

- 一覧と期待は、設計文書の記述と例の手指定の期待から手で導いた値で、独立確認を受けていません。一覧は網羅を主張しません。監査で予測外の継承が出ることを予測しています（N2）。
- 証人は、断片の一致の有限の証拠です。継承の真偽（本当に再び述べたものか）は検査できず、偽りの宣言（継承がないのに宣言する、継承があるのに宣言しない）を排除しません（X7）。
- 証人にできるのは、結果の中の位置の値が等しい場合だけです。差を伴う継承（精密化の追加など）は、断片を差の外に取れる範囲で扱います。
