# P2-h：厳密な数量と型付き表示の射影

[設計40](../../docs/research/40-p2-h-design.md)・[手指定期待41](../../docs/research/41-p2-h-cases.md) を145 JSON・2128必須パスへ展開しています。[実装・内部評価42](../../docs/research/42-p2-h-results.md) に範囲と結果を記録します。全て架空データです。

| 条件 | JSON / 必須パス | 内容 |
| --- | --- | --- |
| P01〜P36 | 76 / 1601 | 直接丸め、セルの開閉、問いの因子化、別添え、衝突、型、出自、snapshot |
| N01〜N11 | 52 / 120 | 型・参照・hash・依存・未対応・静的上限。N12は旧挙動・順序・変異の専用テスト |
| B01〜B04 | 17 / 407 | 子料金16、表示込み28、二表示38、最後の料金不足、完成行の保持 |

期待は文書41から手指定し、runtimeから生成していません。NaN等の生JSON、深さ・サイズ・native実体・下位資源停止は専用テストで補います。表示の根拠と原要求の別添えはartifactの外に置きます。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-display/p01.json
python3 -B -m unittest discover -s tests/p2 -p test_display.py -v
```

P2-gを予約予算で再実行してから、一点の厳密値を0〜6桁へ直接丸めます。区間を代表値にせず、表示のセルを測定の不確かさにしません。別添えから原値を読めても、表示の問いの認定範囲は広がりません。`--fixture` はrequestだけを実行へ渡します。独立確認・評価の凍結は未実施です。
