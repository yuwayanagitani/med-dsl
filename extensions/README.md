# 拡張の宣言（P2-a、`p2-extension-manifest-draft-1`）

既存の handler 10件に後付けで書いた宣言と、P2-b・P2-c で新しい意味能力のために書いた宣言 2件（計 12件）の、**拡張契約の宣言**です。書式・検査・限界は [P2-a の実行契約](../docs/research/20-p2-a-contract.md)、結果は [P2-a の結果](../docs/research/21-p2-a-results.md) と [追加作業](../docs/research/22-p2-a-hardening.md)、P2-b の設計と結果は [23](../docs/research/23-p2-b-design.md)・[24](../docs/research/24-p2-b-results.md)、P2-c は [25](../docs/research/25-p2-c-design.md)・[26](../docs/research/26-p2-c-results.md)、設計は [P2 の研究設計](../docs/research/19-p2-design.md) にあります。状態：**作成者（AI-001）の草案・独立確認前**（`independent_review` は false。true の主張は登録時に拒否されます）。

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

[index.json](index.json) は上の一覧と、各宣言の sha256 です。登録は基底から順に行い、依存が先に登録されていることが必要です。

```bash
python3 scripts/research/check-extensions.py            # 12件を登録し、宣言した防護例をすべて評価する
python3 scripts/research/check-extensions.py --strict   # 防護例のない義務（現在3件、すべて理由つき）があると失敗する
python3 scripts/research/check-extensions.py --json     # 機械可読
python3 -m unittest discover -s tests/p2 -v             # P2 系列のテスト。tests/ 直下の discover には含まれない
```

## 読むときの注意

- 宣言の `evidence` は、その義務の**今ある証拠の強さ**です。拡張全体の強さは最も弱い義務で決まり、`hand_derivation`（手作業の導出）と `finite_check`（有限照合）の義務を持つ拡張が、一般の保存を示したことにはなりません。
- クラス JOINT（併用：記号を共有し得る拡張の合成）は P2-c で加えました。R2・R6 の義務に、構造の再計算・独立な併用の分解・共有記号の併用の全体での再判定・鎖の範囲と非回復・範囲の明示・個別と併用の差の開示を加えたものです（[設計 25 の §5](../docs/research/25-p2-c-design.md)）。
- クラス R6（公理つき読み取りモジュール）は P2-b で加えました。R2 の義務に、公理の宣言・旧データでの無矛盾・結論の健全性と完全性・結論は公理に相対・範囲・情報要求を加えたものです（[設計 23 の §4](../docs/research/23-p2-b-design.md)）。
- 防護例（`guards`）は、既存の例と、拒否・境界のために作った [examples/p2/](../examples/p2/manifest.json)、概念の分割の [examples/p2-split/](../examples/p2-split/manifest.json)、その併用の [examples/p2-splits/](../examples/p2-splits/manifest.json) の例を引きます。防護例がない義務は 3 件で、`guard_gap` に理由があります（旧モデルの拡張は構文の十分条件で保証される／事象化の被覆は手作業の導出／鎖に損失のある段がない）。理由は作成者の主張で、独立の確認は受けていません。
- 宣言（`extensions/*.json`）、宣言が引く防護例・検査・オラクル（`examples/p2/`、`examples/p2-split/`、`examples/p2-splits/`、`examples/review/`、`tests/review/`、`tests/p2/`、`tests/audits/`）、`check-extensions.py` は、P1-d の固定対象（`examples/p1-evaluation/manifest.json`）に含まれます。変更すると、固定対象の再固定（明示的な `--create-snapshot`）が要ります。例外は `scripts/research/audit-preservation.py` だけで、固定対象の hash を定数に持つため、載せると循環します（固定対象の hash が変われば `tests/audits` が検出します）。固定対象は同じリポジトリのファイルなので、改ざんを防ぐものではなく、変更を見落とさないための関門です。`extensions/index.json` の hash は、索引と宣言の不整合を見つけるためのものです。
- 実装や仕様を変えたときに再検証が要る範囲は、`affected()`（[実行契約 20 の §5](../docs/research/20-p2-a-contract.md)）が列挙します。
- 宣言は `data/research/review-001/scripts/gen_extension_manifests.py`（Git管理外）で生成しましたが、**正本はこのディレクトリの JSON** です。
- すべて架空の識別子・例だけを参照します。外部の体系・患者情報・実データは含みません。
