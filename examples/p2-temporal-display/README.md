# P2-j：期間つき数量から型付き表示を作る実行例

[設計46](../../docs/research/46-p2-j-design.md)・[手指定期待47](../../docs/research/47-p2-j-cases.md) を170 JSON・2670必須パスへ展開した、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価48](../../docs/research/48-p2-j-results.md) に記録します。

Iの元計画を再検証・一度だけ再実行し、期間・部分訂正・内容指定確認・両時点の根拠を表示artifactの外に保持します。表示の丸めは厳密有理数から直接行い、幅のある領域を一点へ潰しません。

七種類の問いのうち、display_textと全丸めセル上で一定のthresholdだけを認定対象にします。exact_value、selected_record、target_at、as_of、validityは保守的にout_of_scopeです。source_bundleがあれば原情報からの回答も別に返しますが、表示だけの認定範囲は広げません。時点を固定した入力族にも普遍的な喪失を証明したという意味ではありません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-temporal-display/j01.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-temporal-display/j35-source_bundle.json
python3 -B -m unittest discover -s tests/p2 -p test_temporal_display.py -v
```

- J01〜J36：数値、型、時間選択、訂正・確認、未知、原回答の衝突、保持・符号化・認定範囲。各条件の変種を含みます。
- N01〜N12：型・参照・hash・依存・精度・問い・上限・予算。型破損、native実体、JSONの生小数、旧確認・旧経路は専用検査でも点検します。生小数は共通fixtureローダーが読み取り時に拒否するため、JSON fixtureには入れません。
- B01〜B04：共通予算、全計画と一回の子呼出、表示行の先払い、最後の確定料金。子の部分的な資源停止と後の行の資源停止は注入検査です。

標準は子16＋開始1＋表示10＋確定1＝28。27では表示行が完成してもrootはresource_limit・認定なしです。七質問では40、二表示では38、部分訂正の二query二表示では56、二viewでは59です。未完成のartifact/hash/cell/questions/両根拠は全てnullです。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各fixtureは手指定のrequired_paths期待を持ちます。[生成器](../../scripts/research/p2/gen_temporal_display_fixtures.py) はnativeをimportせず、係数・文字列・回答を手指定して展開します。期待の訂正は [結果48](../../docs/research/48-p2-j-results.md) に残します。医療上の真実・期間や閾値の妥当性・人の認証・実コードへの変換は評価していません。
