# 拡張の宣言（P2-a、`p2-extension-manifest-draft-2`）

既存の handler 10件への後付けに、P2-b・P2-c・P2-e・P2-f・P2-g・P2-h・P2-i・P2-j・P2-k・P2-m・P2-oで追加した11件を加え、計21件の **拡張契約の宣言** があります。書式・検査・限界は [P2-a の実行契約](../docs/research/20-p2-a-contract.md)、結果は [P2-a の結果](../docs/research/21-p2-a-results.md) と [追加作業](../docs/research/22-p2-a-hardening.md)、P2-b は [23](../docs/research/23-p2-b-design.md)・[24](../docs/research/24-p2-b-results.md)、P2-c は [25](../docs/research/25-p2-c-design.md)・[26](../docs/research/26-p2-c-results.md)、P2-eは [31](../docs/research/31-p2-e-design.md)・[33](../docs/research/33-p2-e-results.md)、P2-fは [34](../docs/research/34-p2-f-design.md)・[36](../docs/research/36-p2-f-results.md)、P2-gは [37](../docs/research/37-p2-g-design.md)・[39](../docs/research/39-p2-g-results.md)、P2-hは [40](../docs/research/40-p2-h-design.md)・[42](../docs/research/42-p2-h-results.md) にあります。状態は作成者側の草案で、[運用方針](../docs/research/29-review-repository-policy.md) に従って内部検証を進めます。`independent_review` はfalseです。

宣言は作成者の主張で、**意味の正しさの証拠ではありません**。検査が確かめるのは、必須項目がそろっていること、実体（仕様の hash・実装・例）と食い違わないこと、所有する名前が衝突しないこと、防護例が宣言どおりの結果を返すことです。この系列は P1 の20条件・80 JSON・417必須パス、231開発テスト、レビュー系列とは別の分母です。

| 宣言 | クラス | 内容 | 依存 |
| --- | --- | --- | --- |
| [p0-positive](p0-positive.json) | BASE | P0 の基底（採用・問い合わせ・比較）と核の不変条件 | － |
| [p0-definitions](p0-definitions.json) | R1 | 定義の追加（S1/S2）の保存的拡張の認定 | p0-positive |
| [p1-finite-forecast](p1-finite-forecast.json) | R2 | 有限予測（読み取り専用の意味モジュール） | p0-positive |
| [p1-events](p1-events.json) | R3 | 四項関係の事象化（役割付き事象への表現の改訂） | p0-positive |
| [p1-handover-host](p1-handover-host.json) | HOST | 引き継ぎ操作の共有の前段（識別・仕様と P0 実体の固定） | p0-positive, p1-events |
| [p1-event-chain](p1-event-chain.json) | COMP | 事象化＋改名の鎖の認定（既知テンプレート） | p1-handover-host, p1-events |
| [p1-projection](p1-projection.json) | R4 | 既知の射影と、その実際の出力だけを保存する符号化 | p1-handover-host |
| [p1-reference](p1-reference.json) | R3 | 参考意味：同じ語彙での文集合の恒等テンプレートと有限モデルの反例 | p1-handover-host |
| [p1-absence](p1-absence.json) | R5 | 欠落を否定に変える方針変更の診断（閉世界の仮定） | p1-handover-host |
| [p1-replay](p1-replay.json) | R5 | 原保存・旧処理系の可用性と、新側の保証の分離（点検） | p1-handover-host, p1-event-chain |
| [p2-concept-split](p2-concept-split.json) | R6 | 概念の分割：候補集合と情報要求（公理つき読み取りモジュール。P2-b） | p0-positive |
| [p2-split-combination](p2-split-combination.json) | JOINT | 概念の分割の併用：保存性の判定と併用での候補集合（記号を共有し得る拡張の合成。P2-c） | p0-positive, p2-concept-split |
| [p2-temporal-assertion](p2-temporal-assertion.json) | R5 | 有効期間と参照時点、部分訂正の方針診断。臨床主張・保存認定なし | p0-positive |
| [p2-quantity-literal](p2-quantity-literal.json) | R2 | 点・有限区間の厳密換算と比較。臨床状態を読み書きしない | p0-positive |
| [p2-measurement-binding](p2-measurement-binding.json) | R5 | 内容を指定した確認・訂正・文脈の点検を数量計算へ結ぶ。臨床主張・保存認定なし | p0-positive, p2-quantity-literal |
| [p2-quantity-display](p2-quantity-display.json) | R4 | 型付き表示へ因子化する問い、丸めセル、原情報の別添え。臨床の認定なし | p0-positive, p2-quantity-literal, p2-measurement-binding |
| [p2-temporal-measurement](p2-temporal-measurement.json) | R5 | 明示された期間つき数量主張の内容指定確認・部分訂正・換算。表示・臨床認定なし | p0-positive, p2-quantity-literal |
| [p2-temporal-display](p2-temporal-display.json) | R4 | I計画の再実行、型付き表示だけの問い、原値・記録・両時点・期間の別回答 | p0-positive, p2-quantity-literal, p2-temporal-measurement |
| [p2-validity-refinement](p2-validity-refinement.json) | R5 | 確認済みの期間不明記録を、確認した期間で精密化する（記録についての記録。元の記録は消さない） | p0-positive |
| [p2-clinical-library](p2-clinical-library.json) | R5 | 医療者の操作（記録・確認・訂正）から台帳を組み立て、出力先の要求（宣言）の充足を診断する薄い臨床ライブラリ（P2-o）。臨床の認定・推測で補った情報なし | p0-positive, p2-quantity-literal, p2-temporal-measurement |
| [p2-longitudinal-comparison](p2-longitudinal-comparison.json) | R5 | 同じ slot の二時点の期間つき数量を、独立な変数として比べる（P2-iの端点とP2-fの比較）。臨床の傾向・有意性なし | p0-positive, p2-quantity-literal, p2-temporal-measurement |

[index.json](index.json) は上の一覧と、各宣言の sha256 です。登録は基底から順に行い、依存が先に登録されていることが必要です。

```bash
python3 scripts/research/check-extensions.py            # 20件を登録し、宣言した防護例と継承の証人をすべて評価する
python3 scripts/research/check-extensions.py --strict   # 防護例のない義務（現在3件、すべて理由つき）があると失敗する
python3 scripts/research/check-extensions.py --json     # 機械可読
python3 -m unittest discover -s tests/p2 -v             # P2 系列のテスト。tests/ 直下の discover には含まれない
python3 scripts/research/evaluate-p2.py                 # 統合評価：登録・P2 の例・共通予算・版の比較を、固定した分母と照合（P2-d）
```

## 継承（`inherits`、P2-n）

宣言の書式を draft-2 に上げ、`inherits` を必須の項目にしました（空配列は「継承なし」の明示。draft-1 の宣言は拒否されます）。継承とは、拡張 X が拡張 Y の意味の断片を**実装を共有せず**に再び述べ、その断片で観測が一致することの宣言です（実装の import で共有するのは「依存」で、継承ではありません）。項目は `{from, fragment, obligation, witnesses, witness_gap}` で、`obligation` は継承の主張を担う自分の義務、`witnesses` は元の拡張の既存の例と自分の既存の例の組と、結果の中の同じ意味の位置です。登録時に両方を評価して値が一致することを確かめます。証人がなければ理由（`witness_gap`）を書きます。元の拡張が影響を受けると、継承する側も `affected()` に列挙され、継承で結ばれた組は `independent_pairs()` で独立とされません。契約は [実行契約 20 の §8](../docs/research/20-p2-a-contract.md)、設計は [59](../docs/research/59-p2-n-design.md)、期待は [60](../docs/research/60-p2-n-cases.md) です。

| 継承する側 | 元 | 断片 | 義務 | 証人 |
| --- | --- | --- | --- | --- |
| p2-clinical-library | p2-longitudinal-comparison | 二時点の値を独立な変数として比べた関係の集合と、文脈が一致しないときの扱い | CL-7 | 5 |
| p2-clinical-library | p2-temporal-display | 10進の最近接偶数丸め（係数・文字列）の数式の再述 | CL-7 | 8 |
| p2-clinical-library | p2-temporal-measurement | P2-i の全計画の料金 C の再述 | CL-7 | 3 |
| p2-longitudinal-comparison | p2-measurement-binding | matched_context：property・specimen・method の一致と、不一致の理由 diffe… | LC-10 | 5 |
| p2-longitudinal-comparison | p2-temporal-measurement | P2-i の全計画の料金 C の再述 | LC-6 | 2 |
| p2-measurement-binding | p2-temporal-assertion | 記録・確認の可視性（recorded_at が参照時点以前）と、適格性（確定かつ可視の人の確認がある） | MB-2 | 欠落（理由つき） |
| p2-quantity-literal | p1-finite-forecast | 有理数の入力の検査：整数・正の分母の形（invalid_rational）と、分子・分母の63bit上限（ratio… | QT-2 | 4 |
| p2-temporal-display | p2-quantity-display | 10進の最近接偶数丸め（係数・文字列）と、丸めセルによる閾値の判定 | TD-5 | 8 |
| p2-temporal-display | p2-temporal-measurement | P2-i の全計画の料金 C（記録・確認・訂正辺・query の数からの式）の再述 | TD-10 | 2 |
| p2-temporal-measurement | p2-temporal-assertion | 期間の分類（bounded の半開区間、unknown、unspecified）と、確認済みの unknown／un… | TM-5 | 2 |
| p2-temporal-measurement | p2-measurement-binding | 文脈（method・specimen）の unknown／unspecified と、property・量種・単位の… | TM-5 | 7 |
| p2-validity-refinement | p2-temporal-assertion | 適格な主張・訂正辺・半開区間による対象時点の判定（literal_state と採用集合） | RF-7 | 欠落（理由つき） |

## 読むときの注意

- 宣言の `evidence` は、その義務の**今ある証拠の強さ**です。拡張全体の強さは最も弱い義務で決まり、`hand_derivation`（手作業の導出）と `finite_check`（有限照合）の義務を持つ拡張が、一般の保存を示したことにはなりません。
- クラス JOINT（併用：記号を共有し得る拡張の合成）は P2-c で加えました。R2・R6 の義務に、構造の再計算・独立な併用の分解・共有記号の併用の全体での再判定・鎖の範囲と非回復・範囲の明示・個別と併用の差の開示を加えたものです（[設計 25 の §5](../docs/research/25-p2-c-design.md)）。
- クラス R6（公理つき読み取りモジュール）は P2-b で加えました。R2 の義務に、公理の宣言・旧データでの無矛盾・結論の健全性と完全性・結論は公理に相対・範囲・情報要求を加えたものです（[設計 23 の §4](../docs/research/23-p2-b-design.md)）。
- 防護例（`guards`）は、既存の例と、拒否・境界のために作った [examples/p2/](../examples/p2/manifest.json)、概念の分割の [examples/p2-split/](../examples/p2-split/manifest.json)、その併用の [examples/p2-splits/](../examples/p2-splits/manifest.json) の例を引きます。防護例がない義務は 3 件で、`guard_gap` に理由があります（旧モデルの拡張は構文の十分条件で保証される／事象化の被覆は手作業の導出／鎖に損失のある段がない）。理由は作成者の主張で、独立の確認は受けていません。
- 宣言（`extensions/*.json`）、宣言が引く防護例・検査・オラクル（`examples/p2/`、`examples/p2-split/`、`examples/p2-splits/`、`examples/review/`、`tests/review/`、`tests/p2/`、`tests/audits/`）、`check-extensions.py` は、P1-d の固定対象（`examples/p1-evaluation/manifest.json`）に含まれます。変更すると、固定対象の再固定（明示的な `--create-snapshot`）が要ります。例外は `scripts/research/audit-preservation.py` だけで、固定対象の hash を定数に持つため、載せると循環します（固定対象の hash が変われば `tests/audits` が検出します）。固定対象は同じリポジトリのファイルなので、改ざんを防ぐものではなく、変更を見落とさないための関門です。`extensions/index.json` の hash は、索引と宣言の不整合を見つけるためのものです。
- 実装や仕様を変えたときに再検証が要る範囲は、`affected()`（[実行契約 20 の §5](../docs/research/20-p2-a-contract.md)）が列挙します。
- 生成器は [scripts/research/p2/](../scripts/research/p2/README.md) に追跡しています。時間の宣言はR5の必須7義務にTE-1〜8、量の宣言はR2の必須9義務にQT-1〜8を加えます。手指定資料へのpinは再検証依存であり、実行用の要求にその文書hashを埋め込むという意味ではありません。**正本はこのディレクトリのJSON** です。
- すべて架空の識別子・例だけを参照します。外部の体系・患者情報・実データは含みません。

P2-iの契約と内部評価は [43](../docs/research/43-p2-i-design.md)・[45](../docs/research/45-p2-i-results.md) に記録します。

P2-jの契約と内部評価は [46](../docs/research/46-p2-j-design.md)・[48](../docs/research/48-p2-j-results.md) に記録します。

P2-oの契約と内部評価は [63](../docs/research/63-p2-o-design.md)・[65](../docs/research/65-p2-o-results.md) に記録します。この宣言はP2-iの選択とP2-fの換算・比較に依存し、P2-j（丸め）、P2-m（関係と文脈）、P2-i（料金）の規則を再び述べるので、P2-nの `inherits` で継承を宣言しています。要求プロファイル（出力先の版）は架空です。

P2-lの契約と内部評価は [53](../docs/research/53-p2-l-design.md)・[55](../docs/research/55-p2-l-results.md) に記録します。数量の宣言を draft-2 に上げ（単位表の改訂）、依存する4件の宣言の版と依存の版を draft-2 に更新しました。数量の宣言には継承の差分の義務 VR-1 があります。

P2-mの契約と内部評価は [56](../docs/research/56-p2-m-design.md)・[58](../docs/research/58-p2-m-results.md) に記録します。この宣言はP2-iの選択とP2-fの比較に依存し、P2-gの比較可能性（`matched_context`）の観点を期間の記録について再び述べます。P2-gは読まないので依存は宣言せず、P2-nで足した `inherits` で継承（断片の一致と証人）を宣言します（P2-m の時点では、P2-gの変更は `affected()` にP2-mを含めませんでした）。

P2-kの契約と内部評価は [50](../docs/research/50-p2-k-design.md)・[52](../docs/research/52-p2-k-results.md) に記録します。この宣言は P2-e の意味を継承しますが実装は共有せず、継承は精密化のない要求を P2-e の実装に流す差分の検査で確認しています。P2-n 以後は、この継承を `inherits` に宣言しています（P2-e の例と台帳が構造的に等しい P2-k の例がないので、証人は欠落として理由を書いています）。
