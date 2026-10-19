# P1 の共通評価台帳

[manifest.json](manifest.json) は、P1-a/b/c の全20条件・80 JSON・417必須パスと、別枠のP0回帰22条件・37 JSON・221必須パスを固定します。元のJSONや期待値はコピーせず、既存パスを生バイトで固定します。元の8設計JSONは実行入力にしません。

これは作成者草案の snapshot です。独立確認・評価用正解の凍結は未完了です。[評価契約](../../docs/research/15-p1-d-contract.md) に意味層、認定範囲、対象ファイル、停止と分母を定めます。

```bash
python3 scripts/research/evaluate-p1-d.py --cli
```

固定実体の不一致では評価前に停止します。結果は `data/research/p1-d/latest/results.json`（Git管理外）。変更理由を確認して新たな作成者snapshotを作る開発用操作は `--create-snapshot` で、通常の評価では呼びません。結果の一致に合わせて期待値を自動更新する機能はありません。
