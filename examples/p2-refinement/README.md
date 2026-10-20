# 確認済みの期間不明記録の精密化（P2-k）

[意味設計](../../docs/research/50-p2-k-design.md) と [実装前の期待](../../docs/research/51-p2-k-cases.md) に基づく架空の実行例です。[台帳](manifest.json) はU25/N20/B5条件・66 JSON・721必須パスを管理します。内訳はU26/N31/B9 JSONで、N01の1件は旧い P2-e の経路の対照です。P0/P1や他のP2系列とは別に数えます。

| 例 | 調べること |
| --- | --- |
| [U01](u01.json)・[U02](u02.json) | 精密化の前は期間不明で止まり、確認済みの精密化の後は、精密化した区間で適用される |
| [U03](u03.json)・[U04](u04.json) | 半開境界。区間の外では記録は適用されず、否定にも全期間にもならない |
| [U05](u05.json)〜[U07](u07.json) | 記録と確認の可視性。精密化の前の参照時点は、精密化の前の結果を再現する |
| [U08](u08.json)・[U09](u09.json) | 異なる適格な精密化は競合。後から記録されたものを優先しない |
| [U10](u10.json)・[U11](u11.json) | suspectedとAI由来の精密化は、人の確認まで効かない |
| [U14](u14.json)〜[U16](u16.json) | 精密化と部分訂正。順序に依らず、矛盾は参照時点ごとの診断になる |
| [U17](u17.json)〜[U19](u19.json) | 未知能力は、確認前の精密化も落とさない。未来の記録は影響しない |
| [N04](n04.json)・[N08](n08.json) | 確認は対象と精密化の内容hashを拘束する |
| [B04-9](b04-9.json) | 共通予算で先行行だけが完了し、後続行は値nullのまま止まる |

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-refinement/u14.json
python3 -B -m unittest discover -s tests/p2 -p test_refinement.py -v
```

CLIは `p1-fixture-draft-1` の既存の例用の外枠から **requestだけ** を読みます。精密化要求そのもののschemaは `p2-refinement-request-draft-1` です。`expected` を推論へ渡しません。

例は [生成器](../../scripts/research/p2/gen_refinement_fixtures.py) で再現できます。期待値は手指定で、runtimeの出力から生成しません（hashは台帳の内容から標準の正規化SHA-256で計算します）。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。独立確認・評価用正解の凍結・臨床的妥当性の確認は未実施です。
