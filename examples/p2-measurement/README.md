# P2-g：内容指定の確認と数量計算への接続

[設計37](../../docs/research/37-p2-g-design.md)・[実装前の手指定期待38](../../docs/research/38-p2-g-cases.md) を137 JSON・1425必須パスへ展開しています。[結果39](../../docs/research/39-p2-g-results.md) に内部検証と限界を記録します。全て架空データです。

| 条件 | JSON / 必須パス | 内容 |
| --- | --- | --- |
| M01〜M36 | 65 / 1071 | 内容hash、確認の可視性、訂正、競合、未知、文脈、変数、再現 |
| N01〜N11 | 60 / 120 | 構造・参照・hash・型・訂正・量の依存・未対応・静的上限 |
| B01〜B04 | 12 / 234 | 予算0、換算16、二slot比較25、自己比較20、二換算27と途中停止 |

N12の旧出力比較、順序、別snapshot、選定した変異は専用テストで確認します。N10のnativeファイル不整合と、N11のサイズ・深さ・子入力の複製上限もAPIのテストで補います。期待は文書38から手指定し、runtimeの出力では更新しません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-measurement/m01.json
python3 -B -m unittest discover -s tests/p2 -p test_measurement.py -v
```

確認は内容全体に対する構造的照合に限ります。同じ数量を参照する別測定は別変数で、同じ記録版だけが自己比較です。数学的関係を医学的同等性や旧基底の支持へ変換しません。`--fixture` はrequestだけを実行へ渡します。独立確認・評価用正解の凍結は未実施です。
