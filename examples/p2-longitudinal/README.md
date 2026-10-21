# P2-m：縦断比較（同じ slot の二時点の測定を比べる）の実行例

[設計56](../../docs/research/56-p2-m-design.md)・[手指定期待57](../../docs/research/57-p2-m-cases.md) を103 JSON・2020必須パスへ展開した、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価58](../../docs/research/58-p2-m-results.md) に記録します。

P2-i の期間つき数量の計画を固定版で再検証・一度だけ再実行し、同じ view の二つの時点の換算領域を、P2-f の比較へ渡します。二時点の値は**独立な変数**で、同じ記録が二つの時点で選ばれても共有参照（常に等しい）にしません。関係は算術の関係（less／equal／greater の集合）で、増減・悪化・改善・臨床的有意性の意味を持ちません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-longitudinal/l01.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-longitudinal/l20.json
python3 -B -m unittest discover -s tests/p2 -p test_longitudinal.py -v
```

- L01〜L13：関係（点・幅・開閉・符号・単位）。L02 は同じ記録の幅のある領域を二時点で比べても certain な関係を作らないこと、L07・L08 は接する区間の端、L12・L13 は目標単位が違っても同じ量なら `equal` であることを調べます。
- L20〜L28：比較可能性。部分訂正で method・specimen・property が変わると `not_comparable`、選ばれなかった記録の違いは影響しません（L27）。
- L30〜L38：端点が止まる場合（期間外、競合、期間不明、未知能力、次元の違い）。理由は二端点の和集合で、端点の行を保持します。比較自身の未知能力は端点を公開しません（L35）。
- L40〜L45：参照時点より後の記録の非干渉、二つの view、順序の入れ替え、同じ組の重複、三点の比較（推移を導かない）、AI 由来の保持。
- L50〜L53：接続面の閉包。P2-i が計算した換算領域が、P2-f の入力の上限（63bit）を超えると、元のリテラルへ切り替えずに resource_limit で止まります。目標単位が元の単位なら通ります。
- N01〜N11：型・参照・方針・時刻の順序・別 slot・pin・計画の不正。入力不正は予算に依らず同じ結果です。
- B01〜B05：共通予算。全計画の料金 C の先払い、比較ごとの18、最後の確定1。標準は C=27、一比較で47、二比較で65、部分訂正の組で54です。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各 fixture は手指定の required_paths 期待を持ちます。[生成器](../../scripts/research/p2/gen_longitudinal_fixtures.py) は native を import せず、関係・理由・料金を手指定して展開します。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。医療上の真実・期間や値の妥当性・臨床的な変化の解釈・実コードへの変換は評価していません。
