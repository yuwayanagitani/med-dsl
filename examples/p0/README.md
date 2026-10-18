# P0 の架空入力と期待結果の草案

契約：[`p0-draft-1`](../../docs/research/06-p0-contract.md)。状態：実装前の作成者草案。患者情報・実コード・外部用語マスターを含みません。これらは入力例と期待する結果の一部を具体化したもので、実行済みのテスト結果ではありません。

| ケース | ファイル | 確認すること |
| --- | --- | --- |
| P01 | [definition-extension.json](definition-extension.json) | 新 N を A と B の連言で定義する追加の保存認定 |
| P07 | [linked-observations.json](linked-observations.json) | 二つの検体・方法・結果の結合を保ち、誤った組合せを生成しない |
| P10 | [assertion-revision.json](assertion-revision.json) | 疑いと後の否定、対象時点と記録時点、訂正と履歴を分ける |

各ファイルの `request` だけを処理関数へ渡します。`expected` を入力資料・推論規則として渡してはいけません。将来の検証側が `expected.checks` の path（キー名・配列添字の配列）に対応する出力を読み、equals と照合します。未指定の項目を含む完全な結果の構造は、契約側でも別途検査します。

例えば P01 の JSON は認定票の一部を確認します。P01 の受入条件にある A(a),B(a) からの N(a) の問い合わせ等、各ケースの全条件をこの一ファイルだけで検証し終えるわけではありません。[P01〜P22 の受入表](../../docs/research/06-p0-contract.md) が全体の基準です。

[manifest.json](manifest.json) は三例の生バイト SHA-256・サイズを記録した**草案スナップショット**です。独立確認後の評価用正解の凍結ではありません。例を修正するときは fixture_version、理由、manifest を更新し、実装の出力に合わせて期待値を黙って変えません。

まだ実行用 CLI とケース検証器はありません。次の P0 実装で、request の読み込み、結果との比較、原入力不変、根拠の追跡を検証します。
