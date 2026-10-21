# P2-o：薄い臨床ライブラリ（操作 → 共通表現 → 出力先の要求）の実行例

[設計63](../../docs/research/63-p2-o-design.md)・[手指定期待64](../../docs/research/64-p2-o-cases.md) を141 JSON・2417必須パスへ展開し、P2-r（[設計73](../../docs/research/73-p2-r-design.md)・[手指定期待74](../../docs/research/74-p2-r-cases.md)）で観察者の例6 JSONを足し、P2-s（[設計76](../../docs/research/76-p2-s-design.md)・[手指定期待77](../../docs/research/77-p2-s-cases.md)）で操作の観察者を必須にして3 JSONを足し、150 JSON・2559必須パスとした、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価65](../../docs/research/65-p2-o-results.md) に記録します。

医療者の三つの操作（記録・確認・訂正）から P2-i の台帳を組み立て、**出力先の要求（宣言）**が満たされるかを診断します。結果は四つ：`satisfied`（出力を返す）、`needs_information`（足りない情報の依頼を返す）、`not_representable`（出力先が表せない。失う区別を返す）、`unassessed`（能力・語彙の限界）。AI 由来の候補は要求を満たさず、依頼の候補としてだけ現れます。推測で補った情報は常に空です。出力先の要求は宣言（データ）で、出力先の名前では処理を分岐しません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-library/o01.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-library/o10.json
python3 -B -m unittest discover -s tests/p2 -p test_library.py -v
```

- O01〜O09：`line`（一行の出力先）。丸め（O02-\*。最近接偶数、正負・桁・単位の違い）、区間は表せない（O03）、単位が違えば表せない（O05）、未知の単位は評価不能（O06）、`exchange` は区間を保つ（O07）。O08・O09 は集約の優先（表せない要素と足りない要素が並ぶ行）。事前に固定した表の外に、実装中に足しました（[64](../../docs/research/64-p2-o-cases.md) §4.7）。
- O10〜O15：要求の版の更新（K14）。同じ台帳に v1→v2→v3 の出力先を当てると、足りない欄ごとに依頼が一つ増えます。AI 候補は依頼に現れるだけで、人の確認の後に満たされ、出自の種類が出力に残ります。
- O20〜O27：選択の段階の依頼。期間の外（O20）、確認前（O21）、確度が疑い（O22）、競合（O23）、期間不明（O24）、未知の能力（O25）、AI 由来の記録（O26・O27）。理由ごとに依頼の行動が違います。
- O70〜O73：観察者（P2-r・P2-s）。操作の `observer`（P2-s 以後は必須。不明は明示の `{kind: unknown}`）を台帳へそのまま渡し、選択の根拠に `record_observer` を常に出す（訂正は元の観察者を継がない）。N03-observer-\*：欠落（補完しない）、不正な観察者、`unknown` に参照、確認の操作の観察者の拒否。
- O30：部分訂正で選択が変わる。O40〜O49：`trend`（二時点の比較）。文脈の不一致は表せない（`contexts_differ`）、端点ごとの依頼を一つにまとめる（`ends`）。
- O50〜O53：データだけで足す出力先と、未知の要素・出力の種類・欄・条件・形の拒否。O60〜O62：三つの出力先を一つの要求に、配列の順序の入れ替え、参照時点より後の操作。
- N01〜N08：型・参照・版・ハッシュの受付・出力先の形・時刻の順序・pin・予算の欠落や不正。入力不正は予算に依らず同じ結果です。
- B01〜B04：共通予算。全計画の料金 C の先払い、問い合わせごとの fee（`line`・`exchange` は14、`trend` は18）、最後の確定1。標準は M=32（`line` 一問い合わせ）。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各 fixture は手指定の required_paths 期待を持ちます。[生成器](../../scripts/research/p2/gen_library_fixtures.py) は native を import せず、状態・理由・依頼・出力・料金を手指定して展開します。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。医療上の真実・値の妥当性・臨床の手順・実コードへの変換・実際の画面の質問は評価していません。要求プロファイル（出力先の版）は架空です。
