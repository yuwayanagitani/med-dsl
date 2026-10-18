# R2b：出典・調査記録

調査・確認日：2026-10-18。対象：変化・不変条件・意味を保つ拡張・知識改訂・表現能力と計算の境界。[結果](02b-change-model.md)、[例・反例](02b-cases.md) と対応します。包括的レビュー、論文の全証明の検算、実装評価は未実施です。

## 検索と採否

R2 で確認した論理差分・OWL・openEHR・FHIR を入口に、原著、著者・所属大学の提供原稿、標準化団体の固定版を優先しました。検索結果の紹介記事・百科事典・商用転載は探索に使えても、結論を支える出典には採用していません。

| 検索式・入口の例 | 確認したいこと | 採用・保留 |
| --- | --- | --- |
| `Konev Ludwig Walther Wolter logical difference EL 2012 conservative extension` | 何を同じ意味・差分とするか、問い合わせによる違い | S01。R2 の抄録確認から本文 §3 へ進んだ |
| `Modular Reuse of Ontologies: Theory and Practice pdf` | 安全な拡張・モジュールと十分条件 | S02。原著の導入と貢献一覧を確認 |
| `Institutions abstract model theory specification 1992 satisfaction condition pdf` | 固定した論理に依存しない意味の記述 | S03。1992 年原著の定義を確認 |
| `Conservative Extensions in Guarded and Two-Variable Fragments` | 通常の推論と保存判定の計算可能性の差 | S04。本文導入で定義と結果の範囲を確認 |
| `On the logic of theory change Partial meet Cambridge` | 撤回・改訂を扱う先行理論 | S05。出版社の抄録まで。具体的な演算採用は保留 |
| `site.w3.org OWL 2 profiles decidability`、OWL 2 の公式目次 | 言語断片・推論課題・版参照 | S06・S07。固定された第二版を参照 |
| `site.hl7.org/fhir/R5 extensibility modifierExtension`、`condition verificationStatus` | 未知の意味を無視する問題、訂正と確認状態 | S08・S09。R5 固定ページ |
| openEHR BASE 1.2.0、PROV-O の公式目次 | 安定した情報モデルと領域定義の分離、改訂の由来 | S10・S11。対象節のみ |

## 確認範囲と適用上の限界

### S01：用途に応じた論理差分

Boris Konev, Michel Ludwig, Dirk Walther, Frank Wolter. **The Logical Difference for the Lightweight Description Logic EL**. Journal of Artificial Intelligence Research 44 (2012), 633–708. DOI: 10.1613/jair.3552。[著者投稿原稿 arXiv:1401.5850](https://arxiv.org/abs/1401.5850)、[PDF](https://arxiv.org/pdf/1401.5850)。2012 年の論文と、2014 年の arXiv 登録を区別します。

確認：抄録、§3 の定義 3・5・7、例 4・8・9、補題 10 と周辺説明。語彙を指定した包含関係・個別データ・連言問い合わせの差分の区別を確認しました。PDF の本文 pp.640–642 に相当します。全 76 ページを精読したものではありません。

適用：R2b の比較範囲、K05 の動機。対象の EL 系言語と制約下での結果であり、任意の医療記録・論理・すべての OWL 2 EL への性能保証として使いません。アルゴリズム、証明全体、実験表、CEX の実行は未検証です。

### S02：安全な再利用とモジュール

Bernardo Cuenca Grau, Ian Horrocks, Yevgeny Kazakov, Ulrike Sattler. **Modular Reuse of Ontologies: Theory and Practice**. JAIR 31 (2008), 273–318。[著者所属機関の原著 PDF](https://www.cs.man.ac.uk/~horrocks/Publications/download/2008/CHKS08a.pdf)。

確認：抄録と §1、pp.273–275。保守的拡張、安全性、モジュール、十分条件としての locality の位置付けを確認しました。全 46 ページの証明・評価は未精読です。抽出テキストには文字化けがあり、貢献一覧 p.275 は画像でも照合しました。

適用：十分条件の成立と不成立を非対称に扱う評価方針。具体的な locality 定義・判定手順・計算量・最新ツールの挙動は未検証で、MedDSL で実現した保証とはしません。

### S03：論理体系を抽象化する institution

Joseph A. Goguen, Rod M. Burstall. **Institutions: Abstract Model Theory for Specification and Programming**. Journal of the ACM 39(1) (1992), 95–146. DOI: 10.1145/147508.147524。[大学が提供する原著 PDF](https://courses.grainger.illinois.edu/cs522/sp2016/InstitutionsAbstractModelTheory.pdf)。

確認：抄録、§1 の導入、§2.1 Definition 1 と前後、特に pp.101–102 の語彙・文・モデル・充足条件。p.102 の式は画像でも照合しました。全 52 ページの証明、§4 の論理体系間の構成は精読していません。

適用：設計案 B と、文の対応・モデルの対応を分けて要求する着想。原著の一般的な結果を MedDSL 案へ適用する証明はありません。同著者の `pps/ins.pdf` も探索中に取得しましたが、1992 年原著と別の 73 ページの資料であり、本調査の根拠に混同していません。

### S04：保存判定と推論の決定可能性の違い

Jean Christoph Jung, Carsten Lutz, Mauricio Martel, Thomas Schneider, Frank Wolter. **Conservative Extensions in Guarded and Two-Variable Fragments**. ICALP 2017 の full version、[arXiv:1705.10115v1](https://arxiv.org/abs/1705.10115v1)（2017-05-29）。

確認：抄録、§1、PDF pp.1–2。演繹的保守性とモデル保守性の区別、FO²・GF とその共通部分 GF² に関する結果の範囲。全 33 ページの技術的証明は検算していません。

適用：通常の推論が決定可能なら保存判定も決定可能、と推定しない根拠。本文の論理断片と定義を離れた一般的不可能性や、MedDSL の最終目標の不可能性を主張する資料にはしません。

### S05：知識の撤回・改訂

Carlos E. Alchourrón, Peter Gärdenfors, David Makinson. **On the logic of theory change: Partial meet contraction and revision functions**. The Journal of Symbolic Logic 50(2) (June 1985), 510–530. DOI: [10.2307/2274239](https://doi.org/10.2307/2274239)。

確認：[出版社の抄録・書誌](https://www.cambridge.org/core/journals/journal-of-symbolic-logic/article/abs/on-the-logic-of-theory-change-partial-meet-contraction-and-revision-functions/7ED837BAD5FB6D9A7C77906D73527F9C)。命題を除く撤回、命題を導入する改訂、partial meet contraction の研究であることまで。本文・公準・証明は未読です。出版社のオンライン公開日 2014-03-12 と、論文の刊行年 1985 を混同しません。

適用：保存と訂正を別の研究問題にする根拠。臨床の採用判断、時系列、複数主体の記録を AGM で扱えると確定したものではありません。

### S06：言語の表現力と推論課題

W3C. **OWL 2 Web Ontology Language Profiles (Second Edition)**. Recommendation, 2012-12-11。[固定版](https://www.w3.org/TR/2012/REC-owl2-profiles-20121211/)。

確認：§1、§2.1、§5 Table 10。プロファイルが表現を制限し、推論課題ごとに計算上の性質を示すこと。表にある open の記述は当該版の記載であり、2026 年現在の未解決問題一覧として扱っていません。

適用：意味を表せる範囲と、判定する課題を分ける方針。EL・QL・RL の採用、すべての問い合わせの高速性、保守的拡張の判定可能性はここから決めません。Direct Semantics の公式文書も参照先を確認しましたが、今回その全意味論を採用・検証していません。

### S07：定義と参照する版

W3C. **OWL 2 Web Ontology Language Structural Specification and Functional-Style Syntax (Second Edition)**. Recommendation, 2012-12-11。[固定版](https://www.w3.org/TR/2012/REC-owl2-syntax-20121211/)。

確認：§3.1–3.4 の ontology IRI、version IRI、過去版、imports。適用：I1・I2 の参照方針の先例。参照先が残ることの運用保証や、版間の意味が一致することの証明としては使いません。

### S08：理解できない拡張の処理

HL7 International. **FHIR R5 v5.0.0, Extensibility**。[固定ページ](https://hl7.org/fhir/R5/extensibility.html)。

確認：§2.1.5.0.1–0.3、特に modifier extension と処理側の扱い。定義の存在と、利用側が適切に処理できることの区別を確認しました。

適用：I7・K13。FHIR の「用途上無視できる拡張」と、論理学的な保守的拡張の条件を同じものとは扱いません。FHIR に未知拡張の仕組みがあることは、MedDSL に全将来の意味を表現できる証拠ではありません。

### S09：疑い・確認・否定と記録の状態

HL7 International. **FHIR R5 v5.0.0, Condition Detailed Descriptions**。[Condition.verificationStatus](https://hl7.org/fhir/R5/condition-definitions.html#Condition.verificationStatus)。

確認：verificationStatus の定義・列挙と modifier としての位置付け、evidence の説明。適用：C6 の状態区別の先例。複数主体・時点の採用判断を解決する仕組みとしては未検証です。

### S10：安定したモデルと領域定義の分離

openEHR. **BASE Release 1.2.0, Architecture Overview**。[固定リリース](https://specifications.openehr.org/releases/BASE/Release-1.2.0/architecture_overview.html)。

確認：§4.1.1–4.1.2。参照モデル、archetype、template と専門領域の定義の分担、個別のアプリケーション開発が残る点。適用：領域定義と臨床ライブラリの境界の先例。コアが永久に改訂不要だという証明や、全接続先で操作変更が不要という保証とはしません。

### S11：改訂・導出の由来

W3C. **PROV-O: The PROV Ontology**. Recommendation, 2013-04-30。[固定版](https://www.w3.org/TR/2013/REC-prov-o-20130430/)。

確認：wasDerivedFrom、wasRevisionOf、invalidatedAtTime の定義と周辺例。適用：I4・I5 の由来の記録の先例。PROV の invalidation を、そのまま臨床的な否定や現在の信頼度と同一視しません。

## 再確認と残る調査

PDF 原稿は作業用ディレクトリへ一時取得し、ページ区切り付きで本文を抽出しました。特定箇所の数式・文字化けは上記のページ画像で照合しています。原著ファイルや外部の用語マスターはリポジトリへ同梱していません。全文を取得できたことと、全ページを読んだことを区別しました。

[R3](03-data-access.md) で初期材料と利用条件を整理しました。次は R4 の評価例へ対応させます。R5 で必要な部分について、S02 の十分条件の正式な定義、S03 の体系間の対応、知識改訂と文脈付き主張の意味論を精読します。これらの未読部分や今回の簡単な導出を、検証済みの仕様・実装の根拠にはしません。
