# P1-a の実行例

全て架空データ・作成者草案です。H01〜H06・H20 の7条件を31 JSON、141個の必須パスで具体化しました。独立確認・評価用正解の凍結は未完了です。[設計例8件](../p1/README.md) は別の形式で、そのまま実行するものではありません。

```bash
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-a/finite-forecast.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-a/correlated-forecast.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-a/report-revisions.json
python3 scripts/research/evaluate-p1-a.py --cli
```

[実行契約](../../docs/research/12-p1-a-contract.md) と [結果・制限](../../docs/research/12-p1-a-results.md) を参照してください。profile/spec hash は処理系に固定した native handler と照合します。`p1-fixture-draft-1` の request だけを処理し、expected は計算へ渡しません。

| 条件 | JSON数 | 主な入力と期待 |
| --- | --- | --- |
| H01 | 1 | 7/10、型・対象・期間・モデル・台帳の確認根拠 |
| H02 | 3 | 確率1、同じモデルでの未確認・疑い。確認されても臨床事実を生成しない |
| H03 | 3 | 相関のある連言3/10と周辺3/5、別モデル・期間の事象参照を拒否 |
| H04 | 6 | 分母0・世界/事象/所属の重複・未宣言世界・総和不正 |
| H05 | 2 | 確認・訂正の時点、複数根拠、別モデルを平均しない |
| H06 | 11 | profile・固定仕様・artifact hash・操作の不一致、未知能力と自己申告 |
| H20 | 5 | 予算0・途中停止・ちょうど完了・共通予算・63 bit超過 |

manifest の各ファイルの生バイト SHA-256・サイズを全件照合してから評価します。API と CLI を各2回実行し、必須パス、入力保持、同一入力の再実行を検査します。記録は Git 管理外の `data/research/p1-a/` に出力します。全20条件の完了・認定器の実装・臨床性能の証明ではありません。
