# P2-t：Provenance の activity の符号と revision の entity の実行例

[設計79](../../docs/research/79-p2-t-design.md)・[手指定期待80](../../docs/research/80-p2-t-cases.md) を73 JSON・1,533必須パスへ展開した、架空データだけの作成者草案です。独立確認・評価用正解の凍結は未実施です。現在の結果と制限は [内部評価81](../../docs/research/81-p2-t-results.md) に記録します。

[P2-q の Observation の写像](../p2-observation/README.md)を一度だけ実行し、出せた行の Provenance の項目に、**呼び出し側の宣言**で活動の符号（`activity`）を付け、宣言したときは訂正の関係を `entity`（役割 `revision`）として運びます。活動の符号は不透明な宣言で、ライブラリは内容を検査せず、宣言のない種類は別の種類の符号で代用せず null のままにして、失うものに残します。訂正の関係は、選ばれた訂正記録の**生成側の項目**（agent が分かるとき）に、訂正された記録ごとに一つ（記録の参照と、独立に計算できるハッシュ）付きます。観察者が不明で出自が AI でない訂正は、確認済みでも運べません（`no_agent`）。FHIR への適合は主張しません。

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-provenance/v04.json
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-provenance/v06.json
python3 -B -m unittest discover -s tests/p2 -p test_provenance.py -v
```

- V01〜V03・V18・V19：原本の行。宣言した種類の符号が付く、使われない宣言は痕跡を残さない（V02）、種類ごとに別の符号の系、空の宣言（V18）、AI 由来の原本は生成の項目が `creation`（V19）。`revision` が真でも原本には付かない（`not_applicable`）。
- V04・V05・V08〜V10・V12・V20：訂正の行。訂正の項目が `correction` で、訂正された記録を entity として運ぶ（V04）。`revision` が偽なら運ばない（V05）。AI 由来（V08）・装置の観察者（V20）でも運ぶ。二つの記録を訂正すると entity が昇順で2つ（V09）。連鎖では直接の前の版だけ（V10）。訂正の符号だけ宣言がなければ null で、生成の符号で代用しない（V12）。
- V06・V07・V11：運べない行と、訂正が選ばれない行。観察者が不明の訂正は `no_agent`（V06）、確認者の型の宣言がなければ Provenance が出ず `no_provenance`（V07）、過去の時点では訂正は選ばれず `not_applicable`（V11）。
- V13〜V16：`coding` の宣言のない出力先は `not_declared`、P2-q が出せなかった行（観察者の型の依頼、表せない行、宣言のない出力先）は `not_evaluated`。複数の出力先。
- N01〜N15：型・版・ハッシュ・子の要求（P2-q 以下の検査をそのまま返す）・許容外の種類（R4 の語 `derivation` を含む）・符号の形・`revision` が真偽値でない・重複・対象の欠落・宣言できない欄（`role`）・予算。入力不正は予算に依らず同じ結果です。
- B01〜B03：共通予算。P2-q の全体の料金を先払いし、問い合わせごとに2、最後の確定1。標準は M＝46（P2-q の42＋2＋2）。

[manifest.json](manifest.json) は全ファイルのバイト数・sha256、各 fixture は手指定の required_paths 期待を持ちます。entity のハッシュは手で書けないので、例は役割・型・訂正された記録の参照を個別に検査し、ハッシュの一致と項目の数は [テスト](../../tests/p2/test_provenance.py) が独立な計算で確かめます。[生成器](../../scripts/research/p2/gen_provenance_fixtures.py) は native を import せず、状態・符号・流れ・料金を手指定して展開します。生成するとJSONと台帳を書き換えるため、再現検査はコピーした木で行います。医療上の真実・符号の妥当性・FHIR への適合は評価していません。
