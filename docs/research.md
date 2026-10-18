# 先行仕様・研究の調査メモ

更新日：2026-10-18。会話で挙がった候補と追加の一次資料を、調査の入口として整理したものです。包括的な文献レビューや優位性の検証はまだ行っていません。

調べる順序、決定事項、成果物、完了条件は [調査フェーズのロードマップ](roadmap.md) を参照してください。本ファイルは参照先と調査記録の方針を管理します。

[最終目標](vision.md) は、未来永劫、原理的に変化に耐えうる医療コード体系の確立です。[R1](research/01-use-case.md) では目的の階層を整理し、コード移行の意味の監査を中間目標に位置付けています。[R2 の一次比較](research/02-landscape.md) は主にその中間用途に関する調査です。HAPI FHIR と ROBOT は移行実験の候補で、体系の原理やコアの選定ではありません。

R2 の検索方法、出典、参照版・コミット、確認範囲は [出典・調査記録](research/02-sources.md) に残しています。[R2b の基礎調査](research/02b-change-model.md) では、変化 8 分類、不変条件の候補 8 項目、三つの設計案、形式的な比較方法を整理しました。[14 件の机上例・反例](research/02b-cases.md) と [一次資料の確認記録](research/02b-sources.md) も用意しています。

保守的拡張、用途に応じた論理差分、institution、知識改訂の先行理論を調べました。資料の確認済み範囲と、本プロジェクトの作業定義・導出は区別しています。採用仕様・永続性の証明・実行検証は未完了です。

[R3 の資料・条件確認](research/03-data-access.md) で、RxNorm CPC の二版と FHIR の版付き定義を初期材料に選定し、[4 ファイルの取得・初期照合](research/03-acquisition.md) を完了しました。[出典](research/03-sources.md) と [取得状態・実測値の台帳](research/03-materials.json) を残しています。WHO・LOINC 等の内容を独自体系開発に取り込む条件は保留します。

[R4 の評価設計](research/04-evaluation.md) では、体系の原理と中間用途を分け、[14 原理ケース・架空 40 ケース](research/04-cases.md) の期待結果草案と指標を用意しました。CPC 9 月→10 月を主実験とし、[実資料の部分追跡](research/04-material-probes.md) と [一次資料の確認範囲](research/04-sources.md) を残しました。独立確認・正解凍結・実行は未完了です。

[R5 の設計比較](research/05-model-study.md) で、定義追加・意味モジュール・コア改訂を分ける構成と、役割付き事象・主張・採用判断の分離を研究用に選びました。[原理と小さな導出](research/05-principles.md)、[原著・仕様の追加確認](research/05-sources.md) を残しています。条件内の保存と意味の引き継ぎを示す入口で、全将来の意味への対応・実行性能の証明ではありません。

[R6](research/06-prototype-brief.md) で最初の P0 の範囲と着手条件を決め、[意味・入出力・22 件の受入契約](research/06-p0-contract.md) と [三つの架空 JSON 例](../examples/p0/README.md) を作成しました。[P0-a の実行記録](research/07-p0-a-results.md) では、事実照合と主張選択、草案 P07/P10 との一致と開発テストを記録しています。[P0-b](research/08-p0-b-results.md) で S1/S2 の認定と定義推論を追加し、共有記号・循環・新規所属データの境界を検証しました。[P0-c](research/09-p0-c-results.md) で主張・否定・未知能力のケースを具体化し、18 ケースの 27 JSON と停止理由を検証しました。次は P0-d の比較と 22 ケース全体の評価です。草案との工学的な一致と、独立確認後の評価用正解による検証を分けます。

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

最終目標に向けて、まず以下を形式化・調査します。現在は成立を確認した性質ではありません。

- どの範囲の将来変化を定義し、何を不変条件として要求できるか。
- 新しい概念・関係・領域を受け止める仕組みと、既存の意味の保存をどう両立させるか。
- 定義・知識・コア仕様の改訂を、過去の記録や複数の解釈とどう共存させるか。
- 表現の普遍性と、機械的な検証・推論・差分計算をどの範囲で実現できるか。

以下は中間用途に関する仮説です。これらの成功だけで最終目標の達成とはしません。

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
