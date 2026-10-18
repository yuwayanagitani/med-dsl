# R2 の出典・調査記録

確認日：2026-10-18。対象は [R2 の一次比較](02-landscape.md)。以下は探索的な資料調査で、体系的レビューや実行ベンチマークではありません。

## 調査方法

R1 の7つの架空例と、長期目標の臨床ライブラリ・AI 利用を問いの出発点にしました。既知の公式仕様を直接確認し、先行研究を検索しました。検索で見つけた第三者の解説は探索の手掛かりに留め、根拠は公式仕様、開発元の資料、原著の本文・抄録に限定しました。

主な検索式は次のとおりです。検索日はすべて同日です。

| 問い | 検索式の記録 | 採否 |
| --- | --- | --- |
| 論理差分の先行研究 | `"logical difference" "EL" terminologies Konev 2008` | Konev ほかの JAIR 論文の著者公開情報を採用。検索に使った年と論文の発行年を混同しない |
| 変化の説明と実装 | `"Ecco" "logical differences" ontologies Goncalves`、`site.ceur-ws.org "Comparing ontologies with ecco"` | CEUR の原著を採用。第三者の要約を根拠にしない |
| 共通参照モデルの歴史 | `"OpenGALEN: open source medical terminology and tools"` | PMC に収録された原著を採用。現在の運用実績は判断しない |
| 用語体系の設計要件 | `"Desiderata for controlled medical vocabularies" Cimino 1998`、`"Clinical terminology: why is it so hard" Rector 1999` | 原著の書誌・抄録・取得できた本文断片を採用。実装性能の証拠にはしない |
| 医療コードの構造 | `site.medis.or.jp 標準病名マスター ICD-10 病名管理番号`、`site.loinc.org six axes component property time system scale method` | 発行元の案内・FAQ・構造説明を採用。マスター本体は取得しない |
| 合成と制約 | `site.docs.snomed.org "MRCM" "postcoordinated" domain range` | SNOMED International の公式仕様を採用 |
| ICD の接続 | `site.icd.who.int/icdapi/docs2 foundation linearization postcoordination codeinfo` | WHO の API とコーディングツールの説明を採用 |
| 推論の実装 | `site.robot.obolibrary.org reason diff explain` | 開発元のコマンド文書を採用。機能は未実行 |
| 地域差と他領域 | `site.bfarm.de "ICD-10-GM" "German Modification" English`、`site.docs.snomed.org national extension international edition UK US`、`site.whocc.no atc structure principles five levels` | BfArM、SNOMED International、WHO の説明を採用 |

## 規格・データの参照記録

ローリングページは確認日時点の表示を読みました。表の版は今回参照した仕様・文書の版で、実データを取得した版ではありません。各資料の最新性、対象実装との一致、個別の利用条件は必要な段階で再確認します。

| 資料 | 版・確認範囲 | 支える内容・残る確認 |
| --- | --- | --- |
| [HL7 ConceptMap](https://hl7.org/fhir/R5/conceptmap.html) | R5 / 5.0.0。Scope、構造、R4 との差の記述 | 対応の方向・条件・意味関係・独自プロパティ。実装ごとの対応は未確認 |
| [HL7 `$translate`](https://hl7.org/fhir/R5/conceptmap-operation-translate.html) | R5 / 5.0.0。操作の入出力 | 対応候補を問い合わせる契約。意味差分エンジンの性能は示さない |
| [HL7 Condition](https://hl7.org/fhir/R5/condition.html) | R5 / 5.0.0。用途、構造、確度・時間等 | 記録文脈の参照。全臨床状況をこれ一つで表す決定はしていない |
| [HL7 Provenance](https://hl7.org/fhir/R5/provenance.html) | R5 / 5.0.0。用途・構造 | 由来を記録する候補。AI の確認状態への具体的な対応は未設計 |
| [WHO API v2](https://icd.who.int/docs/icd-api/APIDoc-Version2/) | API v2 の概説。URI、線形化、版指定 | Foundation と MMS の区別。実 API 呼び出しは未実施 |
| [WHO の組み合わせ説明](https://icd.who.int/docs/codingtool/en/Postcoordination/) | コーディングツールの利用説明 | 対象概念に適用可能な軸。任意の属性を無制限に結合する扱いにしない |
| [CDC ICD-10-CM](https://www.cdc.gov/nchs/icd/icd-10-cm/index.html) | 案内ページ、表示日 2026-07-02 | ICD-10 からの臨床修正版という系統。データ本体は未取得 |
| [BfArM ICD-10-GM](https://klassifikationen.bfarm.de/icd-10-gm/kode-suche/htmlgm2026/index.htm) | 2026 年版の入口と構成 | 地域・版の区別。個別の診療・償還規則は未調査 |
| [SNOMED CT 合成文法](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-compositional-grammar-specification) | 公式概要。ローリング文書 | 構造化された式の仕様。厳密な実装対象の文法版は後続で固定 |
| [SNOMED CT MRCM](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-machine-readable-concept-model/6-considerations) | Considerations の制約・検証の説明 | 属性、値域、個数、内容種別ごとの規則。RF2 は未取得 |
| [SNOMED CT 国別版](https://docs.snomed.org/snomed-international-documents/snomed-ct-glossary/n/national-edition) | 公式用語集の定義と例 | 国際版と拡張の依存関係。各国の最新リリースの採用状況ではない |
| [MEDIS の案内](https://www.medis.or.jp/4_hyojyun/medis-master/)、[FAQ](https://www.medis.or.jp/4_hyojyun/medis-master/faq/) | 公開案内。病名マスターの更新表示は 2026-10-01 | マスターの役割と連携。利用条件の具体的判断と実データ取得は R3 |
| [LOINC 構造](https://loinc.org/kb/faq/structure) | 六主軸の公式説明 | 項目定義の軸。結果値との結び付けは別途設計 |
| [NLM RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html) | 正規化された名称、用語型、関係の説明 | 成分・含量・剤形等のモデル。配布データは未取得 |
| [WHO ATC](https://www.who.int/tools/atc-ddd-toolkit/atc-classification) | 分類の構造説明 | 五段階の分類。薬剤全般の意味を一意に表すモデルと決めない |
| [OHDSI 語彙](https://ohdsi.github.io/CommonDataModel/vocabulary.html) | Mapping of Concepts、Maps to、Losses in Mapping | 同等／より一般的な概念への対応、複数対応、損失。掲載例を最新版の正解表には使わない |
| [OMOP CDM](https://ohdsi.github.io/CommonDataModel/cdm54.html) | 5.4、Condition Occurrence の関連項目 | 標準概念と原コードを保持する構造。最新版としての選定ではない |
| [NLM UMLS Metathesaurus](https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/index.html) | 公式概要 | 概念中心の名称統合。個別語彙の利用条件・対応精度は未確認 |
| [openEHR Architecture Overview](https://specifications.openehr.org/releases/BASE/latest/architecture_overview.html) | 表示 BASE Release 1.2.0、節 4.1〜4.2、10 の関連記述 | 安定した情報モデルと臨床内容・テンプレートの分離。特定の画面・会計への適合は未確認 |
| [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/) | Second Edition、基本概念と開世界の説明 | 含意と知識不足の区別。実装する論理の範囲は未選定 |
| [SHACL](https://www.w3.org/TR/shacl/) | 2017 Recommendation、検証と結果の仕様 | 制約検証と報告。推論や医学的正しさの保証とは分ける |
| [PROV Overview](https://www.w3.org/TR/prov-overview/) | 2013 Working Group Note | 由来・導出の枠組み。採用時は規範文書も確認 |

## 原著の書誌・確認範囲

| 文献 | 識別子・版 | 今回の確認と限界 |
| --- | --- | --- |
| J. J. Cimino, 1998, *Desiderata for Controlled Medical Vocabularies in the Twenty-First Century* | Methods Inf Med 37(4–5):394–403。[PMCID PMC3415631](https://pmc.ncbi.nlm.nih.gov/articles/PMC3415631/)、[PMID 9865037](https://pubmed.ncbi.nlm.nih.gov/9865037/) | 公式収録元の検索取得による抄録と本文断片。再オープンは閲覧確認画面になったため、本文全体を通読済みとはしない |
| A. L. Rector, 1999, *Clinical terminology: why is it so hard?* | Methods Inf Med 38(4–5):239–252。[PMID 10805008](https://pubmed.ncbi.nlm.nih.gov/10805008/) | 公式検索で得た書誌・抄録。再オープンは閲覧確認画面。本文の主張や現在の状況へ拡大解釈しない |
| A. L. Rector, J. E. Rogers, P. E. Zanstra, E. van der Haring, 2003, *OpenGALEN: Open Source Medical Terminology and Tools* | AMIA Annu Symp Proc 2003:982。[PMCID PMC1480228](https://pmc.ncbi.nlm.nih.gov/articles/PMC1480228/) | 公式収録元の検索取得で短報本文を確認。再オープンは閲覧確認画面。現在の稼働や保守の証拠にはしない |
| B. Konev, M. Ludwig, D. Walther, F. Wolter, 2012, *The Logical Difference for the Lightweight Description Logic EL* | JAIR 44:633–708、DOI `10.1613/jair.3552`。[著者公開版](https://arxiv.org/abs/1401.5850) は 2014 年登録 | 書誌・抄録を確認。論理と問い合わせの限定、実装・適用の報告まで。証明・性能値は今回検証していない |
| R. S. Gonçalves, B. Parsia, U. Sattler, 2013, *Comparing ontologies with ecco* | ISWC Posters & Demonstrations、CEUR Vol.1035。[原著 PDF](https://ceur-ws.org/Vol-1035/iswc2013_demo_13.pdf) | 全4ページの抽出本文を確認。差分分類と例の説明を参照。表の再計算やプログラムの再現実験は未実施 |

## 実装の参照位置

コミットは GitHub API の `repos/<owner>/<repo>/commits/HEAD` から確認し、HAPI のファイルは同じ SHA の Contents API で読みました。導入・ビルド・テスト実行はしていません。ソース確認と文書確認を区別します。

| 実装 | 固定コミット | 確認した範囲 |
| --- | --- | --- |
| HAPI FHIR | `ebdb17fa2c85f8eb0da1e438f97edefb3dca6a91` | [文書](https://hapifhir.io/hapi-fhir/docs/server_jpa/terminology.html) と `TermConceptMappingSvcImpl.java` の変換入口、`TermConceptMappingSvcImplR5Test.java` の基本変換テスト。条件付き対応等は未検証 |
| Snowstorm | `28cb0a0997a245045109f24c1707e2098f7ea785` | [README](https://github.com/IHTSDO/snowstorm/blob/28cb0a0997a245045109f24c1707e2098f7ea785/README.md) の API と利用機能の説明。処理の実装内部は未確認 |
| ROBOT | `37d514d2ac8970b6ce7b9f5cfe83ba08dc97e9d8` | [reason](https://robot.obolibrary.org/reason)、[explain](https://robot.obolibrary.org/explain)、[diff](https://robot.obolibrary.org/diff) の公式文書。SHA は参照位置の記録で、当該版との一致と動作は未検証 |

## 取得できなかった資料と保留

- FMA：Rosse & Mejino, 2003、DOI `10.1016/j.jbi.2003.11.007`、[PMID 14759820](https://pubmed.ncbi.nlm.nih.gov/14759820/)。検索で書誌・抄録相当の情報を得たが、PubMed の本文表示と PDF の取得を確認できなかった。形式的な被覆・利用条件の判断には採用しない。
- TA2：[公式前付け](https://fipat.library.dal.ca/wp-content/uploads/2021/08/FIPAT-TA2-Front-Matter.pdf) の検索取得テキストで書名・発行主体等を確認。直接オープンと本体の取得は未完了。解剖学用語とオントロジーの同等性を判断しない。
- BfArM の英語案内は取得エラーとなったため、2026 年版の公式ドイツ語入口を参照した。
- ResearchGate、Wikipedia、検索サービスによる自動要約は、原著の所在を探す入口に留め、比較の根拠には採用しなかった。
- ICD・SNOMED CT・MEDIS 等の実マスター、公式対応表、AI 用の患者データ、公開評価セットは取得していない。利用条件と評価対象は R3〜R4 で確認する。

## 中間用途の再現計画

HAPI FHIR の対応表による直接変換を比較基準にし、ROBOT 等で扱える論理・問いを限定して意味の照合を検討します。同じ原情報・補助情報・定義を与え、候補、項目別差分、根拠、比較不能、有効な比較範囲、事前定義の作業量を比較する計画です。実行対象の版、依存関係、利用条件、評価ケースは後続段階で固定します。

この計画は移行支援という中間用途の評価です。体系そのものの最終目標は [目標と設計原則](../vision.md) を参照してください。後続の [R2b](02b-change-model.md) で変化・不変条件・拡張原理の基礎調査を整理しました。上記の既存調査を原理の確立済みの根拠とはしません。
