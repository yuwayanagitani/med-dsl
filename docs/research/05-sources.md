# R5：一次資料の追加確認と適用範囲

確認日：2026-10-18。[R2b の記録](02b-sources.md) を引き継ぎ、設計選択に必要な部分を追加確認しました。[比較](05-model-study.md) と [小さな導出](05-principles.md) は本プロジェクトの判断で、先行研究の結果をそのまま MedDSL 全体の保証にはしません。

## 原著の追加確認

| ID | 一次資料 | 今回確認した箇所 | 設計への反映・限界 |
| --- | --- | --- | --- |
| R5-S01 | Cuenca Grau ほか、2008、[Modular Reuse of Ontologies: Theory and Practice](https://www.cs.man.ac.uk/~horrocks/Publications/download/2008/CHKS08a.pdf) | §5.1–5.2、Definitions 24・25、Proposition 27（pp.294–295）。§5.4、Definition 32、Propositions 33・34（pp.297–298）。§5.6、Example 37（p.301）と周辺 | 十分条件、同じクラス内の併用と異なる条件の併用、構文的近似を区別。S1・S2 は本プロジェクトのさらに小さな構成で、この locality 判定器の実装ではない |
| R5-S02 | Goguen・Burstall、1992、[Institutions: Abstract Model Theory for Specification and Programming](https://courses.grainger.illinois.edu/cs522/sp2016/InstitutionsAbstractModelTheory.pdf) | §4.1、Definition 32、Definitions 34・Proposition 35（pp.125–126）、導入 pp.124–125 | 文とモデルの対応、推論を移すためのモデル側の条件を確認。C1 の e/r は独自の範囲付き契約。原著の morphism の向き・圏論的構造と同一と称しない |

R5-S01 の p.294・p.298、R5-S02 の p.125・p.126 は、以前取得した原著をローカルで画像化し、抽出テキストと数式を照合しました。PDF のページ番号では各 22・26、31・32 ページです。OCR/文字抽出だけの誤読を避けた範囲をここに限定し、原著全ページを読んだとはしません。作業用ファイルはリポジトリへ同梱していません。

R5-S01 の一般的な証明・実験全体、R5-S02 の全構成と各命題の形式検算は未完了です。R2b の Konev ほかの問い合わせ差分、Jung ほかの計算可能性の区別も引き継ぎますが、その未読部分まで今回確認したとはしません。AGM 原著は引き続き抄録確認までで、具体的な改訂演算の採用根拠にはしません。

## 既存仕様の確認

| ID | 固定した一次資料・確認箇所 | 用途・限界 |
| --- | --- | --- |
| R5-S03 | [OWL 2 Structural Specification、2012-12-11、§3.1–3.4](https://www.w3.org/TR/2012/REC-owl2-syntax-20121211/#Ontology_IRI_and_Version_IRI) | 系列と版・依存先の参照分離。意味保存や将来の取得可能性の保証にはしない |
| R5-S04 | [PROV-O、2013-04-30、wasDerivedFrom / wasRevisionOf](https://www.w3.org/TR/2013/REC-prov-o-20130430/#wasRevisionOf) | 由来・改訂の再利用候補。現在の主張の採用・医学的な真偽の決定規則ではない |
| R5-S05 | [RDF 1.1 Concepts、2014-02-25、§1.1・§4](https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/)、[RDF 1.1 Semantics、同日、§10](https://www.w3.org/TR/2014/REC-rdf11-mt-20140225/#rdf-datasets) | 参照共有・dataset の構造と、graph name だけからの意味推定の限界。交換形式の候補で、採用は未決定。RDF 1.1 を現在の唯一・最新の仕様とは主張しない |
| R5-S06 | [SHACL、2017-07-20、§1.5](https://www.w3.org/TR/2017/REC-shacl-20170720/#entailment) | 検証と推論前提、未対応の推論方式による failure。検証器の実行・採用は未実施 |
| R5-S07 | [openEHR BASE Release 1.2.0、Architecture Overview、§4.1.1–4.1.2](https://specifications.openehr.org/releases/BASE/Release-1.2.0/architecture_overview.html) | 参照モデル・領域定義・テンプレートの分担を再確認。MedDSL の全構成と同じとはしない |

FHIR の ConceptMap・未知修飾・版差は [R4 の記録](04-sources.md) に従います。外部用語データの利用条件も D03 のままで、標準仕様の比較を利用条件保留中の用語の取り込みへ広げません。

## 根拠の区別

S1・S2 のモデル構成、S3 の有限回合成、C1 のモデル被覆と合成、R1 の履歴と採用の分離、U1 の射影後の区別回復の限界は、今回の研究用の手作業の導出です。C1-a は型付き四項関係と役割付き事象の間の文・モデル対応を具体的に構成した例、G1 は有限の役割付き記録と問い合わせの対応例、Prob-1 は二状況の有限確率の説明例です。医学的な実証、一般の言語間翻訳の構成、AI の臨床性能の根拠ではありません。

三案への K ケースの適用と、40 ケースのファミリーへの対応は机上比較です。得点・速度・保守工数を実測した結果はありません。R6 の試作仕様と、その後の実行で、どの契約を実際に満たせたかを別に残します。
