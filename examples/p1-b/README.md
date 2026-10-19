# P1-b の実行例

全て架空データ・作成者草案です。H07〜H12 の6条件を22 JSON・150必須パスで具体化しました。独立レビュー・評価用正解の凍結は未完了です。元の [P1 設計例](../p1/README.md) は設計形式のまま保持しています。

```bash
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-b/reify-events.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-b/restore-events.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-b/linked-observations.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-b/split-witness.json
python3 scripts/research/evaluate-p1-b.py --cli
```

[実行契約](../../docs/research/13-p1-b-contract.md) と [結果・制限](../../docs/research/13-p1-b-results.md) を参照してください。CLI は `p1-fixture-draft-1` の request だけを処理し、expected を計算へ渡しません。

| 条件 | JSON数 | 主な期待 |
| --- | --- | --- |
| H07 | 4 | 事象化、完全な履歴の読み戻し、旧回答と実際の役割表での問い合わせ |
| H08 | 2 | 同じ key を統合せず、同じ四つ組の複数根拠を保持 |
| H09 | 1 | 新事象の件数・同一性は旧 Q の保証対象外 |
| H10 | 1 | 別々の事象から役割を取る誤翻訳に反例、not_certified |
| H11 | 6 | 方法の欠落・複数値、ID衝突、原主張参照・ハッシュの不正を拒否 |
| H12 | 8 | 四つ組の否定、AIの保留、確認時点、衝突、文脈、明示訂正、未知能力 |

比較例の target は作成者が独立に記述した入力です。runtime の出力から期待結果を作っていません。事象の名前は新鮮であれば任意で、生成例の `urn:med-dsl:event:…` だけに限定しません。

manifest の生バイトハッシュ・サイズ・6条件の全ファイルを照合してから、API/CLI 各2回、必須パス、入力保持、再実行を検証します。記録は Git 管理外の `data/research/p1-b/`。全モデルの保存認定は実装しておらず、有限照合が一致しても certificate は not_certified です。
