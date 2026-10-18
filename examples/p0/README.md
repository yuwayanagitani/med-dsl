# P0 の架空入力と期待結果の草案

契約：[`p0-draft-1`](../../docs/research/06-p0-contract.md)。期待結果は作成者草案です。P0-a で P07/P10 を実行し、指定チェックとの一致を確認しました。[結果](../../docs/research/07-p0-a-results.md) を参照してください。独立確認・臨床評価は未実施で、患者情報・実コード・外部用語マスターを含みません。

| ケース | ファイル | 確認すること |
| --- | --- | --- |
| P01 | [definition-extension.json](definition-extension.json) | 新 N を A と B の連言で定義する追加の保存認定 |
| P07 | [linked-observations.json](linked-observations.json) | 二つの検体・方法・結果の結合を保ち、誤った組合せを生成しない |
| P10 | [assertion-revision.json](assertion-revision.json) | 疑いと後の否定、対象時点と記録時点、訂正と履歴を分ける |

各ファイルの `request` だけを処理関数へ渡します。CLI の `--fixture` も同じ動作です。`expected` を入力資料・推論規則として渡してはいけません。テスト側が `expected.checks` の path（キー名・配列添字の配列）に対応する出力を読み、equals と照合します。未指定の項目は別の意味・境界テストで確認します。

例えば P01 の JSON は認定票の一部を確認します。P01 の受入条件にある A(a),B(a) からの N(a) の問い合わせ等、各ケースの全条件をこの一ファイルだけで検証し終えるわけではありません。[P01〜P22 の受入表](../../docs/research/06-p0-contract.md) が全体の基準です。

[manifest.json](manifest.json) は三例の生バイト SHA-256・サイズを記録した**草案スナップショット**です。独立確認後の評価用正解の凍結ではありません。例を修正するときは fixture_version、理由、manifest を更新し、実装の出力に合わせて期待値を黙って変えません。

P07/P10 は次のコマンドで実行できます。P01 は check_extension の実装待ちで、終了コード 3 と operation_not_implemented を返します。P0 全体が合格したという意味ではありません。

```bash
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/linked-observations.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/assertion-revision.json
```
