# 先行仕様・研究の調査メモ

更新日：2026-10-18。会話で挙がった候補と追加の一次資料を、調査の入口として整理したものです。包括的な文献レビューや優位性の検証はまだ行っていません。

調べる順序、決定事項、成果物、完了条件は [調査フェーズのロードマップ](roadmap.md) を参照してください。本ファイルは参照先と調査記録の方針を管理します。

[R1 の用途定義](research/01-use-case.md) と [R2 の一次比較](research/02-landscape.md) を完了しました。主用途はコード移行における意味の保持・喪失・追加の監査です。R2 では既存方式・研究を比較し、次に検証する基盤を HAPI FHIR と ROBOT に選定しました。実装の採用と性能の検証はこれからです。

R2 の検索方法、出典、参照版・コミット、確認できた範囲と取得できなかった資料は [出典・調査記録](research/02-sources.md) に記録しています。次の R3 は、最初の接続候補の資料・意味定義・対応表の入手性と利用条件の確認です。

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
| [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/) | 含意、知識の不足と否定の区別、採用する推論範囲。R1 では基本概念のみ確認 |
| [SKOS Reference](https://www.w3.org/TR/skos-reference/) | マッピング関係と推移性。R1 では近い対応の連鎖が同等性を保証しない点を確認 |
| [W3C PROV Overview](https://www.w3.org/TR/prov-overview/) | 由来、生成、導出の記録。R1 では概要のみ確認 |
| [OMOP CDM 5.4](https://ohdsi.github.io/CommonDataModel/cdm54.html) | 共通概念と原情報の併存。R1 では傷病情報の原コード保持を確認 |

## 計画を支える確認事項

FHIR R5 ConceptMap は、対応付けを入力から出力への方向を持つ関係として定義し、逆方向や別用途での利用が常に成立するとはしていません。したがって、最初の対象は方向と用途を含めて決定します。[公式仕様の Scope and Usage](https://hl7.org/fhir/R5/conceptmap.html#scope)

SNOMED CT には公式の合成文法があり、HAPI FHIR や Snowstorm には実装の公開資料があります。独自の表現や実行エンジンの要否は、これらの具体的な適合性を比較して判断する計画です。各候補で必要な変換を実現できるかは未検証です。[合成文法仕様](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-compositional-grammar-specification)、[HAPI FHIR](https://hapifhir.io/hapi-fhir/docs/server_jpa/terminology.html)、[Snowstorm](https://github.com/IHTSDO/snowstorm)

## 次に所在と内容を確かめる候補

- GALEN / GRAIL、Rector の臨床用語・合成モデルに関する詳細な仕様と後続評価。R2 で OpenGALEN の短報と Rector 1999 の抄録を確認。
- FMA、Terminologia Anatomica / TA2 と解剖学的参照モデル。
- 医学用語のラテン語・ギリシャ語由来の形態素解析。
- OWL / RDF、記述論理、臨床概念の合成と推論の適用範囲。R2 で論理差分の先行研究を確認し、個別記録の監査への適用は保留。
- LOINC、MEDIS、国内レセプト電算マスターの公式資料。
- 選定した実行基盤の対象版ごとの機能、導入条件、公開評価セット。R2 の文書・一部ソース確認と、今後の実行検証を区別する。

会話中の論文名・著者・年は一括して確認済みとはしません。R2 で照合した書誌と実際に読めた範囲は [出典・調査記録](research/02-sources.md) を参照し、それ以外を確定引用しません。ラテン語の構成を文法設計の着想にする案も、意味の一意性を保証する根拠とはせず、探索課題として扱います。

## 検証する仮説

1. 定義済みの意味と規則を使って、喪失・追加・矛盾を根拠付きで判定でき、移行の点検負担を改善できるか。
2. 既存の合成文法・概念モデル・用語サーバーで、意味差分の監査をどこまで実現できるか。
3. 新しい体系・版へ接続する際、比較ロジックを再利用でき、定義追加・モデル変更・再検証の量を抑えられるか。
4. 未解釈、未実装、根拠不足を比較不能として報告しつつ、有効に比較できる範囲を増やせるか。
5. 対応付けの目的、版、国・地域、臨床文脈を追加すると、曖昧さをどこまで減らせるか。

R1 で定めた H1〜H4 の評価対象は [用途定義](research/01-use-case.md) に記録しています。将来の体系への接続や機械的な差分判定は、実装・検証済みの機能ではありません。

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
