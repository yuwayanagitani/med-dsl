# P1 の設計例

契約草案：[p1-design-draft-1](../../docs/research/11-p1-contract.md)。**未実装・未実行の設計資料**です。[20件の受入条件](../../docs/research/11-p1-cases.md) のうち8件を JSON に具体化しました。P0 の実行用 fixture と schema を分け、各ファイルには `execution_state=not_implemented` を明記しています。

| ケース | 設計例 | 固定する期待条件 |
| --- | --- | --- |
| H01 | [finite-forecast.json](finite-forecast.json) | 予測確率7/10を型付きで返すが、発生の臨床主張を追加しない |
| H03 | [correlated-forecast.json](correlated-forecast.json) | 同じ世界での事象の交差は3/10。独立性を仮定した9/25にしない |
| H07 | [event-reification.json](event-reification.json) | 旧四項関係の結合と公開binding、原台帳の根拠を保持 |
| H10 | [split-witness.json](split-witness.json) | 別々の事象から検体・方法・結果を取る誤翻訳の反例 |
| H13 | [model-coverage-counterexample.json](model-coverage-counterexample.json) | モデル内の式の対応があっても旧モデルを失う反例 |
| H14 | [existential-witness.json](existential-witness.json) | 存在の含意と、名前付き B(a) の含意を分ける参考モデル |
| H17 | [lossy-composition.json](lossy-composition.json) | 同じ値集合へ写る二旧記録で、元の結合の回答が異なる |
| H18 | [finite-check-only.json](finite-check-only.json) | 1/2要素だけの一致で、3要素を含む全モデルの保存を認定しない |

JSON の input は概念上の入力、expected は作成者の期待条件です。実行 request と response の完全な schema ではなく、P1-a 以降で具体化します。P0 CLI の `--fixture` へは渡しません。予定 handler も planned と明示し、profile/仕様ハッシュを認識する実装が存在するとはしていません。

[manifest.json](manifest.json) は設計例の生バイト SHA-256・サイズと、依存する契約草案・P0 P07 のハッシュを記録します。実装結果に合わせて期待条件を黙って変更せず、変更時は理由・case_version・manifest を更新します。独立確認後の評価用正解の凍結とは別です。

全例が架空です。P0 の37例・22ケースと、P1 の20受入条件・8設計例を別の分母にします。P1 の実行済みケース数は0で、合格率は未評価です。有理数の算術や反例モデルの手作業の確認を、P1 処理系の実行結果とは数えません。
