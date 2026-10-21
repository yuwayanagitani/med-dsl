# P2-q：Observation の status・code の写像と Provenance への出力の実行例

[設計70](../../docs/research/70-p2-q-design.md)・[手指定期待71](../../docs/research/71-p2-q-cases.md) を75 JSON・1,249必須パスへ展開した、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価72](../../docs/research/72-p2-q-results.md) に記録します。

[P2-p の構造への写像の可否の診断](../p2-grounding/README.md)を一度だけ実行し、表せる行に、**呼び出し側の宣言**で `status`・`code`・確認者の型を適用します。ライブラリは `status` や `code` を決めません。宣言が足りないとき（訂正が選ばれたのに訂正の `status` がない、記録の性質が `code` の表にない）は、推測で補わず、宣言する人への依頼を返します。使った宣言は、仮定として流れの `added` に残ります。人の確認は Provenance（確認ごとに一つ、時刻順）として運び、AI 由来の記録だけが、先頭に生成の Provenance（Device）を持ちます。FHIR への適合は主張しません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-observation/q01.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-observation/q08.json
python3 -B -m unittest discover -s tests/p2 -p test_observation.py -v
```

- Q01〜Q07・Q11：宣言が足りて出せる行。標準（原本、確認者 Practitioner）、Provenance なし、確認者の型の違い、確認が2件、AI 由来の記録、訂正が選ばれたとき（`amended`／`corrected`）、使わない宣言は影響しない。
- Q15〜Q19：P2-p の期間の規約との併用、文脈の不在、`range` の対象、参照時点より後の確認は出さない。Q08〜Q10：宣言が足りない行（訂正の `status`、`code` の表、両方）は `needs_information` で、`status`・`code` を補わない。
- Q12〜Q14・Q18：P2-p の行が表せない・不足の行は判定せず（`not_evaluated`）、宣言のない出力先は `not_declared`。複数の出力先の宣言。
- N01〜N13：型・版・ハッシュ・子の要求（P2-p・P2-o の検査をそのまま返す）・許容外の `status` の写像・`code` の表の形と重複・許容外の確認者の型・宣言の重複と対象の欠落・予算。入力不正は予算に依らず同じ結果です。
- B01〜B03：共通予算。P2-p の全体の料金を先払いし、問い合わせごとに3、最後の確定1。標準は M＝42（P2-p の37＋2＋3）。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各 fixture は手指定の required_paths 期待を持ちます。Provenance の対象のハッシュは手で書けないので、例は各項目の活動・対象の記録・時刻・agent を個別に検査し、ハッシュの一致と項目の数は [テスト](../../tests/p2/test_observation.py) が別計算と比べます。[生成器](../../scripts/research/p2/gen_observation_fixtures.py) は native を import せず、射影・流れ・依頼・料金を手指定して展開します。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。医療上の真実・値の妥当性・FHIR への適合は評価していません。
