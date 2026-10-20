# P2-g：測定の文脈・版・由来の一次資料の確認

確認日：2026-10-20。状態：**公開仕様の対象箇所を閲覧**。[D03](03-data-access.md) に従い、外部マスター・パッケージ・仕様全文・実データを取得して同梱する作業とは分けます。設計37と期待38の型・hash・確認・採用・比較方針は本プロジェクトの作業定義です。

## 1. 比較した資料

| ID | 主体・資料・参照版 | 確認した範囲と事実 | 本プロジェクトの判断 |
| --- | --- | --- | --- |
| MS1 | HL7、[FHIR R5 v5.0.0 Observation定義](https://hl7.org/fhir/R5/observation-definitions.html) | code/subject/value、effective[x]/issued、method/specimen。値とは別に測定対象・主体・対象時刻・方法・検体の項目がある。issuedは当該版の利用可能時刻で、対象時刻とは別 | 数値だけの一致と文脈を分ける。FHIRのstatusやissuedを本方針の人の確認へ自動変換しない |
| MS2 | HL7、[FHIR R5 v5.0.0 References §2.1.3.0.3](https://hl7.org/fhir/R5/references.html#literal) | 特定のリソース版への参照と、監査・由来における利用の説明 | 再現根拠ではlatestだけを参照しない。ただしFHIRの履歴参照と独自の内容hashを同一方式とはしない |
| MS3 | HL7、[FHIR R5 v5.0.0 Provenance定義](https://hl7.org/fhir/R5/provenance-definitions.html) | target、occurred[x]、recorded、agent。targetは通常版を指定するが例外もあり、活動時刻と記録時刻を分ける | 対象版・由来・時刻を保持する比較材料。FHIRのProvenanceが本設計の確認や署名検証をそのまま実現するという判断はしない |
| MS4 | W3C、[PROV-O Recommendation 2013-04-30](https://www.w3.org/TR/2013/REC-prov-o-20130430/) | Entity、wasDerivedFrom、wasRevisionOf、§4.3のqualified derivation/revision。派生と改訂の関係を表す語彙 | 改訂と計算による派生を別の関係として記録する。本プロジェクトの採用優先順位や競合解消をPROVから導いたとはしない |
| MS5 | JCGM、[VIM3 2.3 measurand](https://jcgm.bipm.org/vim/en/2.3.html)、定義・注記つきオンライン版 | 測ろうとする量の指定に量の種類と、量を担う対象の状態等が関わることを注記1で確認 | quantity_kindやunitだけで、何の測定かまで指定できたとしない。医学的な測定対象モデルの網羅性は未評価 |

MS1は対象箇所に限定した比較です。component、基準範囲、解釈、非数値の観察、各国の実検査コード、全FHIR検索・更新APIの評価はしていません。MS2/3の参照が解決できること、MS4の語彙を使うことだけで、内容が正しい・署名が認証された・旧処理系が利用可能だとは判断しません。

## 2. 今回の設計で独自に決めたこと

slotと不変な記録版の分離、quantity wrapperのhashを含む内容全体への確認、confirmedと人の可視の確認の両要件、全適格訂正辺からの除去、同じ文脈だけを扱う比較方針、別記録へ異なる数値変数を割り当てる規則、予約による共有予算は本プロジェクトの判断です。上記仕様がこれらを一括して要求・保証しているとは扱いません。

FHIR Observationのfinal等の状態を、人が本契約の内容全体を確認した証拠として取り込みません。将来の取込では、外部の状態・確認・署名・版と本契約の対応、その根拠と不足を別に設計する必要があります。

## 3. 利用範囲と残る調査

今回は発行主体の公開HTMLの閲覧だけです。外部の例、検査マスター、単位表、FHIRパッケージ、PROVの仕様全文を保存・再配布せず、記録は独自の日本語要約とリンクに限ります。FHIRの第三者用語、WHO・LOINC・SNOMED CT等の保留範囲はD03のままです。公開・ライセンスの方針も変更しません。

版を明示した資料の比較であり、最新標準の網羅や本方式の優位性、適合性、臨床運用上の安全性を実証した調査ではありません。認証・永続保存・実体系への対応・医療者の既存操作との対応は、接続runtimeの初回検証とも分けて今後調べます。
