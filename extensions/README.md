# 拡張の宣言（P2-a、`p2-extension-manifest-draft-1`）

既存の handler 10件に後付けで書いた、**拡張契約の宣言**です。書式・検査・限界は [P2-a の実行契約](../docs/research/20-p2-a-contract.md)、結果は [P2-a の結果](../docs/research/21-p2-a-results.md)、設計は [P2 の研究設計](../docs/research/19-p2-design.md) にあります。状態：**作成者（AI-001）の草案・独立確認前**（`independent_review` は false。true の主張は登録時に拒否されます）。

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

[index.json](index.json) は上の一覧と、各宣言の sha256 です。登録は基底から順に行い、依存が先に登録されていることが必要です。

```bash
python3 scripts/research/check-extensions.py            # 10件を登録し、防護例95件を評価する
python3 scripts/research/check-extensions.py --strict   # 防護例のない義務（現在24件、すべて理由つき）があると失敗する
python3 scripts/research/check-extensions.py --json     # 機械可読
python3 -m unittest discover -s tests/p2 -v             # 39テスト。tests/ 直下の discover には含まれない
```

## 読むときの注意

- 宣言の `evidence` は、その義務の**今ある証拠の強さ**です。拡張全体の強さは最も弱い義務で決まり、`hand_derivation`（手作業の導出）と `finite_check`（有限照合）の義務を持つ拡張が、一般の保存を示したことにはなりません。
- 防護例（`guards`）がない義務は、`guard_gap` に理由を書いてあります。「テストで検査」「別の防護例が担う」「構造の性質」「該当なし」の区別は [結果 21 の §3-5](../docs/research/21-p2-a-results.md) にあります。
- 宣言を変えたら、`index.json` の sha256 を更新します（不一致はテストが検出します）。ただし宣言（`extensions/*.json`）、`tests/p2`、`check-extensions.py` は P1-d の固定対象（`examples/p1-evaluation/manifest.json`）に**含まれません**。固定されているのは `src/med_dsl/extensions.py` だけです。`index.json` の hash は偶発的な不整合を見つけるもので、同じディレクトリで宣言と索引の両方を書き換えれば通ります。宣言の改ざん防止にはなりません。
- 実装や仕様を変えたときに再検証が要る範囲は、`affected()`（[実行契約 20 の §5](../docs/research/20-p2-a-contract.md)）が列挙します。
- 宣言は `data/research/review-001/scripts/gen_extension_manifests.py`（Git管理外）で生成しましたが、**正本はこのディレクトリの JSON** です。
- すべて架空の識別子・例だけを参照します。外部の体系・患者情報・実データは含みません。
