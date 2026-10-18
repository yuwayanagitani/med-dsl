# 先行仕様・研究の調査メモ

更新日：2026-10-18。会話で挙がった候補と追加の一次資料を、調査の入口として整理したものです。包括的な文献レビューや優位性の検証はまだ行っていません。

調べる順序、決定事項、成果物、完了条件は [調査フェーズのロードマップ](roadmap.md) を参照してください。本ファイルは参照先と調査記録の方針を管理します。

## 最初に読む一次資料

以下の公式ページは 2026-10-18 に確認しました。リンク先の確認と個々の機能・適合性の検証は区別し、詳細仕様、対象版、利用条件は各調査で記録します。

| 資料 | 調べること |
| --- | --- |
| [WHO ICD API](https://icd.who.int/icdapi) | Foundation と線形化、版の指定、複合表現、対応リソースの対象範囲 |
| [HL7 FHIR R5 ConceptMap](https://hl7.org/fhir/R5/conceptmap.html) | 対応の方向、用途、意味関係、条件、複数候補、`$translate`。R4 との差も確認する |
| [HL7 FHIR R5 `$translate`](https://hl7.org/fhir/R5/conceptmap-operation-translate.html) | 入出力、候補と結果の解釈、条件情報、対象版の指定 |
| [SNOMED CT 合成文法](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-compositional-grammar-specification) | 合成表現の構文。概念モデルによる妥当性検証と区別して調べる |
| [OHDSI OMOP Common Data Model](https://ohdsi.github.io/CommonDataModel/) | 標準概念、語彙間の関係、Athena の提供範囲、版管理 |
| [OHDSI 語彙構築の説明](https://ohdsi.github.io/CommonDataModel/vocabulary.html) | 概念と関係の管理、マッピングの意味と制約 |
| [NLM UMLS](https://www.nlm.nih.gov/research/umls/index.html) | 概念統合と対応関係の範囲、異なる語彙の粒度、ライセンス条件 |
| [openEHR Specifications](https://specifications.openehr.org/) | 情報モデルと知識モデルの分離、ADL、用語の束縛、臨床文脈 |
| [HAPI FHIR 用語サービス文書](https://hapifhir.io/hapi-fhir/docs/server_jpa/terminology.html) | 対応表の取り込み、変換操作、採用版ごとの機能と実行条件 |
| [SNOMED International Snowstorm](https://github.com/IHTSDO/snowstorm) | 用語サーバーの責務、合成・検索・対応付けの機能範囲、必要データと導入条件 |

## 計画を支える確認事項

FHIR R5 ConceptMap は、対応付けを入力から出力への方向を持つ関係として定義し、逆方向や別用途での利用が常に成立するとはしていません。したがって、最初の対象は方向と用途を含めて決定します。[公式仕様の Scope and Usage](https://hl7.org/fhir/R5/conceptmap.html#scope)

SNOMED CT には公式の合成文法があり、HAPI FHIR や Snowstorm には実装の公開資料があります。独自の表現や実行エンジンの要否は、これらの具体的な適合性を比較して判断する計画です。各候補で必要な変換を実現できるかは未検証です。[合成文法仕様](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-compositional-grammar-specification)、[HAPI FHIR](https://hapifhir.io/hapi-fhir/docs/server_jpa/terminology.html)、[Snowstorm](https://github.com/IHTSDO/snowstorm)

## 次に所在と内容を確かめる候補

- GALEN / GRAIL、Rector の臨床用語・合成モデルに関する研究。
- FMA、Terminologia Anatomica / TA2 と解剖学的参照モデル。
- 医学用語のラテン語・ギリシャ語由来の形態素解析。
- OWL / RDF、記述論理、臨床概念の合成と推論。
- LOINC、MEDIS、国内レセプト電算マスターの公式資料。
- 実行可能な用語サーバー、対応付けエンジン、公開評価セット。

会話中の論文名・著者・年は未確認なので、書誌情報をそのまま確定引用しません。ラテン語の構成を文法設計の着想にする案も、意味の一意性を保証する根拠とはせず、探索課題として扱います。

## 検証する仮説

1. 中間表現を介すると、単純な対応表よりも複合概念の保持や変換根拠の説明が改善するか。
2. 既存の合成文法・概念モデル・用語サーバーで、どこまで要件を満たせるか。
3. 網羅性を広げた場合、入力・確認・保守の負担はどう変化するか。
4. 対応付けの目的、版、国・地域、臨床文脈を追加すると、曖昧さをどこまで減らせるか。

「既存方式は静的辞書だけ」「公式対応なら常に完全一致」「コード識別子だけなら自由に配布できる」「外部注入なら権利問題を解決できる」といった会話中の断定は、採用済みの事実として扱いません。

## 調査結果に残す項目

各調査結果には以下を記録します。未確認の項目は空欄にせず、未確認と記します。

| 項目 | 内容 |
| --- | --- |
| 問い | ロードマップの段階と、どの決定に必要な調査か |
| 出典 | 資料名、発行主体・著者、URL または識別子、公開日・版、確認日 |
| 対象 | 体系・版・国・地域・用途、実装の場合はリリースやコミット |
| 方法 | 検索式、資料の採否理由、再現手順、使った入力と補助情報 |
| 確認結果 | 資料に記載された事実、実際に確認した挙動、自分の解釈を分ける |
| 適用範囲 | 限界、例外、利用条件、他の資料との不一致 |
| 状態 | 資料確認済み／仮説／検証済み／保留。結果から決めた事項は別記 |
| 次の行動 | 未解決の疑問、次に見る資料、見直す条件 |

既存方式との差は、比較対象と具体例を示せた段階で README に反映します。調査した事実と、今後調べる予定の項目を混ぜません。
