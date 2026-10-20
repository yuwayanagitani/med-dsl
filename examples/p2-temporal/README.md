# 有効期間つきの主張（P2-e）

[意味設計](../../docs/research/31-p2-e-design.md) と [実装前の期待](../../docs/research/32-p2-e-cases.md) に基づく架空の実行例です。[台帳](manifest.json) はT20/N10/B4条件・61 JSON・462必須パスを管理します。内訳はT22/N31/B8 JSONで、N01の1件は旧P0経路の対照です。P0/P1や他のP2系列とは別に数えます。[実装・評価記録](../../docs/research/33-p2-e-results.md) を参照してください。

| 例 | 調べること |
| --- | --- |
| [T01](t01.json)〜[T03](t03.json) | 過去の対象期間を後から記録・確認した場合の知識の可視性 |
| [T07](t07.json)・[T08](t08.json) | 訂正の期間外では元の記録を残し、期間内だけを訂正する |
| [T09](t09.json) | 訂正の鎖。除かれた訂正元の辺も根拠へ残し、古い記録を復活させない |
| [T13](t13.json)・[T14](t14.json) | 期間不明・未指定の保留。全期間への補完はしない |
| [T18](t18.json) | 可視の未知能力は、未確認・期間外でも停止の理由になる |
| [B04](b04-6.json) | 共通予算で先行行だけが完了し、後続行は値nullのまま止まる |

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-temporal/t09.json
python3 -B -m unittest discover -s tests/p2 -p test_temporal.py -v
```

CLIは `p1-fixture-draft-1` の既存の例用の外枠から **requestだけ** を読みます。時間要求そのもののschemaは `p2-temporal-request-draft-1` です。`expected` を推論へ渡しません。

例は [生成器](../../scripts/research/p2/gen_temporal_fixtures.py) で再現できます。期待値は手指定で、runtimeの出力から生成しません。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。独立確認・評価用正解の凍結・臨床的妥当性の確認は未実施です。
