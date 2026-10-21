# P2-l：版の更新の手指定の期待

作成日：2026-10-21。状態：**実装前に固定した作成者側の期待**。[設計53](53-p2-l-design.md) の改訂（単位表）から、変更される期待・追加例・版の手順の期待・`affected()` の予測を、手で導出しました。**runtime の出力から期待を生成・更新しません**。数値・識別子はすべて架空です。独立確認・評価用正解の凍結は未実施です。

## 1. 改訂（draft-1 → draft-2）

| 単位 | draft-1 | draft-2 |
| --- | --- | --- |
| `u_third` | 次元 [1,0]、倍率 1/3 | 次元 [1,0]、倍率 2/3 |
| `u_hundred` | なし | 次元 [1,0]、倍率 100/1 |

数量の計算規則・停止・課金・入力の形は変えません。換算は `値 × (元の単位の倍率) ÷ (目標の単位の倍率)`（基底の単位に対する倍率で求める）で、`u_base` の倍率は 1、`u_ten` は 10、`u_half` は 1/2 です。

## 2. 変更される期待（宣言した変更）：6件

`u_third` を使う旧入力は6件だけです（P2-f の3件、P2-h・P2-i・P2-j の各1件）。要求は同一で、期待が次のとおり変わります。

| 例 | 要求 | draft-1 の期待 | draft-2 の期待（手で導出） |
| --- | --- | --- | --- |
| `p2-quantity/q03` | 点 1 `u_third` を `u_base` へ換算 | 1/3 | 1×(2/3)÷1 = **2/3**（下端・上端とも閉じた単一点） |
| `p2-quantity/q04` | 点 1 `u_base` を `u_third` へ換算 | 3/1 | 1×1÷(2/3) = **3/2** |
| `p2-quantity/q08` | 区間 [3,3] `u_third` を `u_base` へ換算 | [1,1] | 3×(2/3) = **[2,2]**（閉じた単一点） |
| `p2-display/p12` | 点 1 `u_third` を `u_base` へ換算し、小数点以下2桁の表示 | 1/3 → k=33、文字列 `0.33` | 2/3 → 66.666…を最近接偶数に丸めて **k=67、文字列 `0.67`**（表示の丸めセルは k=67 の中心 67/100 の両側、奇数なので両端開） |
| `p2-temporal-measurement/c22-third` | 点 1 `u_third` を `u_base` へ換算（対象時点 day(5)） | 1/3 | **2/3** |
| `p2-temporal-display/j07` | p12 と同じ（期間つき） | k=33、`0.33` | **k=67、`0.67`** |

`p2-display/p08`（1/3 を `u_base` で表示）は `u_third` を使わないので、`0.33` のまま変わりません（継承の差分の対照）。

## 3. 追加例：1件

| 例 | 要求 | 期待 |
| --- | --- | --- |
| `p2-quantity/q25` | 点 3 `u_hundred` を `u_base` へ換算 | 3×100÷1 = **300**（下端・上端とも 300/1、閉じた単一点）。他の欄は Q01〜Q08 と同じ構造（計算済み・理由なし・基底へ変換しない・認定しない） |

追加後の P2-f の系列：条件 Q25／N12／B4、JSON 80件、必須パスは Q25 が Q01〜Q08 と同数（13）なので **609＋13 = 622**。他の4系列（P2-g・P2-h・P2-i・P2-j）の例の数と必須パスの数は変わらない。

## 4. 版の手順の期待

旧版 = 追加前のコミット `906766d`、新版 = 実装後のコミット。比べる系列は `p2-quantity`・`p2-measurement`・`p2-display`・`p2-temporal-measurement`・`p2-temporal-display`。

| 番号 | 期待 |
| --- | --- |
| V1・V2 | 旧版の木で統合評価が合格し、旧い分母のまま（19宣言・239義務・420防護例・P1／P0 の分母・P2 の各系列）。manifest は `183c3303…`、束は `ace08ccf…`（P2-k の最終の値） |
| 旧入力の数 | 5系列の合計 **682件**（79＋137＋145＋151＋170）。新版は **683件**（Q25 が追加） |
| V4 | 旧入力を新版へそのまま渡すと、各入力の結果は「同一」または「`unsupported_profile`／`profile_spec_mismatch` での拒否」のどちらか。**それ以外 0**。拒否が大半を占める（自分の仕様の hash を固定した consumer を持つため） |
| V5 | 同じ ID の入力は、hash の値を除いて要求が同一（**682件すべて**）。期待も、6件を除いて同一（**676件**）。6件は §2 の期待に変わる。欠落 0、追加 1（Q25） |
| V6 | 旧版の木での旧入力の結果と、新版の木での再生成した入力の結果は、hash の値と `certifier` を除いて、6件だけが違う。違う経路は、換算の結果の欄と、表示の欄に限られ、§2 に対応する |
| V8 | Q25 の要求の `u_hundred` を保ったまま、pin を旧版の値にして旧版の木へ渡す：行は `unassessed`、理由 `unknown_unit`、換算の値は `null`。新しい pin のまま旧版の木へ渡す：`unsupported_profile` ／ `profile_spec_mismatch` |
| R1（置換での再固定） | `p2-temporal-measurement/c01` の要求で旧い数量 pin を新しい値に文字列置換して新版へ渡すと、**`ok` にならない**（確認が拘束する内容の hash が合わない） |

## 5. `affected()` の予測（実測と比べる）

変更したファイルを `src/med_dsl/quantity_spec.json` とします（意図した編集）。

**予測する列挙**（宣言から機械的に求まる）：

- 再検証する拡張：`p2-quantity-literal`・`p2-measurement-binding`・`p2-quantity-display`・`p2-temporal-measurement`・`p2-temporal-display` の**5件**。
- 再生成が要る実体（`embedded_in` の和）：`src/med_dsl/measurement_spec.json`・`display_spec.json`・`temporal_measurement_spec.json`・`temporal_display_spec.json`、`src/med_dsl/quantity.py`・`measurement.py`・`temporal_measurement.py`、実行例5系列。

**実際に再固定が要る範囲**（手で導出）：上の実体に加えて、`src/med_dsl/display.py`・`temporal_display.py`（各自の仕様の hash の定数）、`extensions/p2-*.json` の5宣言と `extensions/index.json`（仕様の hash を書いている）、`examples/p1-evaluation/manifest.json`（固定対象の台帳）。

**予測**：`affected()` の列挙は、実際の範囲より小さい。不足するのは `display.py`・`temporal_display.py`・宣言5件と索引（宣言が自分の仕様の hash を持つ実体と、末端の拡張の自分の定数を、`embedded_in` として表せないため）。台帳は `lock` として別に列挙される。

## 6. コストの測定（予測は置かず、実測を記録する）

旧版から新版への差分の、変更ファイル数・追加行・削除行、変更した実行例のファイル数を記録します。設計53 の Z6 は「意味の変更が6入力でも、約680ファイルが書き換わる」です。
