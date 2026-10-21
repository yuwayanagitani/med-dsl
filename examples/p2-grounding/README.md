# P2-p：構造への写像の可否の診断（FHIR R5 Observation への接地）の実行例

[設計67](../../docs/research/67-p2-p-design.md)・[手指定期待68](../../docs/research/68-p2-p-cases.md) を97 JSON・1,998必須パスへ展開した、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価69](../../docs/research/69-p2-p-results.md) に記録します。

[P2-o の薄い臨床ライブラリ](../p2-library/README.md)を一度だけ実行し、「満たされた」`exchange` の行が、出力先の構造（FHIR R5 Observation）で、**丸めず・閉じず・補わず**に表せるかを判定します。表せない行は理由と失う区別を返し、表せる行は射影と、失う区別・足した仮定を返します。構造の事実は、取得したページ（[台帳](../../docs/research/03-materials.json)）に結んだ仕様の表で、呼び出し側は変えられません。FHIR への適合は主張しません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-grounding/g01.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-grounding/p02.json
python3 -B -m unittest discover -s tests/p2 -p test_grounding.py -v
```

- G01〜G13：`quantity`（一つの値）。小数で書ける値は表せる（G01・G02・G04・G05・G06・G07・G09・G11）、書けない値（2/3、1/3）は丸めず表せない（G03・G08）、区間は中点に潰さず表せない（G10・G12・G13）。G20〜G28：`range`（両端を含む区間）。開いた端は閉じず表せない（G22〜G24・G26）。G30〜G34：桁数。18桁は表せ、19桁は表せない。G33・G34 は先頭の 0 を数えるかに依る境界で、保守側の解釈の例です。
- P01〜P06：期間。半開区間を、端の規約を宣言せずに期間へ出せない（P01）。`exclusive_end_as_last_second` を宣言したときだけ、end を1秒戻して出し、仮定を流れに残す（P02）。値が表せないときは仮定を足さない（P05）。部分訂正で選ばれた記録の期間（P06）。
- C01〜C06：文脈。method・specimen は存在か不在かで運び、unknown と unspecified は区別が落ちて不在になる（C01・C02）。運ぶ欄の選び方と順序（C03〜C06）。
- R01〜R04：P2-o が満たさなかった行を、そのまま通して `not_evaluated` と明示する（不足の依頼、表せない、評価不能、期間の外）。D01〜D04：対象を宣言していない出力先は `not_declared`（写像できるとは言わない）。複数の出力先、複数の対象。
- N01〜N12：型・版・ハッシュ・子の要求（P2-o の検査をそのまま返す）・対象の形・構造や値の型や規約の拒否・`line`/`trend` への対象・予算。入力不正は予算に依らず同じ結果です。
- B01〜B03：共通予算。P2-o の全体の料金を先払いし、問い合わせごとに3、最後の確定1。標準は M＝37（P2-o の32＋2＋3）。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各 fixture は手指定の required_paths 期待を持ちます。[生成器](../../scripts/research/p2/gen_grounding_fixtures.py) は native を import せず、状態・理由・射影・流れ・料金を手指定して展開します（P2-o の生成器の部品を使います）。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。医療上の真実・値の妥当性・FHIR への適合・`status`/`code`/Provenance の写像は評価していません。
