# P0 の架空入力と期待結果の草案

契約：[`p0-draft-1`](../../docs/research/06-p0-contract.md)。期待結果は作成者草案です。[P0-b](../../docs/research/08-p0-b-results.md) で 9 ケース・13 JSON の指定チェックとの一致を確認しました。独立確認・臨床評価は未実施で、患者情報・実コード・外部用語マスターを含みません。

| ケース | ファイル | 確認すること |
| --- | --- | --- |
| P01 | [definition-extension.json](definition-extension.json)・[definition-entailment.json](definition-entailment.json) | 新 N↔A∧B の保存認定と、A(a),B(a) からの N(a) の根拠 |
| P02 | [subtype-extension.json](subtype-extension.json)・[subtype-entailment.json](subtype-entailment.json) | 旧 A⊑B へ新 N⊑A を追加。A(a) から B(a) は支持するが N(a) は作らない |
| P03 | [unsafe-inclusions.json](unsafe-inclusions.json)・[unsafe-entailment.json](unsafe-entailment.json) | 追加 A⊑N,N⊑B は未認定。A(a) から旧 B(a) が増える具体例 |
| P04 | [shared-symbol-extensions.json](shared-symbol-extensions.json) | 同じ新 N の二重所有を併用時に検出。各単独認定との対比はテスト内でも確認 |
| P05 | [cyclic-definitions.json](cyclic-definitions.json) | 循環定義は未認定。危険の証明とはしない |
| P07 | [linked-observations.json](linked-observations.json) | 二つの検体・方法・結果の結合を保ち、誤った組合せを生成しない |
| P10 | [assertion-revision.json](assertion-revision.json) | 疑いと後の否定、対象時点と記録時点、訂正と履歴を分ける |
| P19 | [membership-before.json](membership-before.json)・[membership-added.json](membership-added.json) | 新 N(a) の観察を加えると旧 A(a),B(a) の支持が増える。旧データ固定の認定とは分ける |
| P20 | [duplicate-definition.json](duplicate-definition.json) | 同じ新 N に S1/S2 の二定義を与える入力を拒否 |

各ファイルの `request` だけを処理関数へ渡します。CLI の `--fixture` も同じ動作です。`expected` を入力資料・推論規則として渡してはいけません。テスト側が `expected.checks` の path（キー名・配列添字の配列）に対応する出力を読み、equals と照合します。未指定の項目は別の意味・境界テストで確認します。[P01〜P22 の受入表](../../docs/research/06-p0-contract.md) が全体の基準です。

[manifest.json](manifest.json) は 13 例の生バイト SHA-256・サイズを記録した**草案スナップショット**です。初期 P01/P07/P10 の三ファイルは変更せず、P0-b で十ファイルを追加しました。追加例の期待値は開発中に記述し、最初の一括照合前に明記しました。独立確認後の評価用正解の凍結ではありません。例を修正するときは fixture_version、理由、manifest を更新し、実装の出力に合わせて期待値を黙って変えません。

```bash
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/definition-extension.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/definition-entailment.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/linked-observations.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p0/assertion-revision.json
python3 -m unittest discover -s tests
```

compare は未実装で、P0 全体の合格とはしません。CLI の入力不正の例 P04/P20 は終了コード 2、正常に処理した未認定 P03/P05 は 0 です。トップレベル status、certificate.status、各 query の status をそれぞれ確認します。
