# R3：出典・確認記録

確認日：2026-10-18。対象は [資料選定・利用条件](03-data-access.md)。技術仕様と利用条件を発行元の一次資料で確認し、続いて選定した CPC 二版と FHIR Procedure 二版の HTML を取得・初期検査しました。[実測結果](03-acquisition.md) を参照してください。保留した外部マスターの取得・契約や、全概念の意味の検証は行っていません。

## 方法

既存の WHO・HL7・SNOMED・MEDIS から公式の利用条件と配布ページへ進みました。`site.loinc.org license downloads`、`site.nlm.nih.gov RxNorm current prescribable content license`、`site.cdc.gov ICD-10-CM public domain` 等で補いました。第三者が付けた公開ライセンスや「無料データ」の紹介を、元データの許諾の根拠にはしていません。

確認段階は「公式文書を確認」「ファイルへの公開導線を確認」「実体取得・初期照合」「意味の検証」を分けます。選定 4 ファイルは第三段階まで完了しました。以下の公表版・更新日と、自分たちが実測したハッシュ・行数は区別しています。

## S01：RxNorm CPC の範囲と条件

発行主体：米国 National Library of Medicine。資料：[CPC の説明](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)、[RxNorm Terms of Service](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html)、[NLM Terms and Conditions](https://www.nlm.nih.gov/databases/download/terms_and_conditions.html)。表示された最終確認日は CPC 説明 2019-04-17、RxNorm 利用条件 2022-01-31。

確認：CPC は public domain・ライセンスと UTS ログイン不要と説明。収録対象・除外対象、三つの RRF ファイル、月次と週次の区別。RxNorm の NLM 作成部分と第三者由来部分、謝辞・推薦の否定・再配布時の版表示等の条件も確認しました。

適用：CPC 二版の初期選定。取得後、README の版と実際の出典集合を確認しました。古い説明を RxNorm 全体版すべてへの許諾と一般化せず、一般条件の外部内容への参照が第三者の権利まで許諾するとは扱いません。

## S02：RxNorm の固定配布先と版

[配布一覧](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html)、[2026-09-08 ノート](https://www.nlm.nih.gov/research/umls/rxnorm/docs/2026/rxnorm_releasenotes_full_09082026.html)、[2026-10-05 ノート](https://www.nlm.nih.gov/research/umls/rxnorm/docs/2026/rxnorm_releasenotes_full_10052026.html)。配布一覧の表示最終確認日 2026-09-30、ノートはそれぞれのリリース日。

確認：CPC の固定日付 URL は `https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_09082026.zip` と `https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_10052026.zip`。ブラウズで両リンクをたどると application/zip 非対応となりました。10 月 CPC の公表 MD5 は `a3bfab544c6a67c127ebcd10ab914aa9`。9 月版の値は未確認です。

適用：日付を固定した資料台帳。端末での再試行と待ち時間の延長により二版を取得し、10 月の公表 MD5 は一致しました。9 月の公表値は現行本文で未確認のため、計算値との独立照合は未実施です。二版の SHA-256・CRC・RRF 行数は実測しました。ノートは全体版のものであり、件数を CPC の集計に使いません。

## S03：RxNorm のファイル形式と関係の向き

[技術文書](https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html)。確認箇所：§12 のファイル一覧、§12.4・§12.5・§12.7 の列定義と周辺説明、CPC 用ファイルへの言及。

確認：概念・原子・出典・属性・関係を別に読む必要があり、RXNREL の REL は二番目から一番目への関係を説明する列です。適用：初回の内容検査手順。個別データの関係や医学的な同等性を確認したものではありません。全体版にある履歴ファイルが CPC にもあるとはしません。

## S04：FHIR のライセンスと版付きの定義

HL7 International。[R5 License and Legal Terms](https://hl7.org/fhir/R5/license.html)、[R4 の同文書](https://hl7.org/fhir/R4/license.html)。対象版：R4 v4.0.1、R5 v5.0.0。

確認：CC0、派生仕様・商標・推薦・適合の扱い、第三者の用語・知的財産は別条件であること。適用：HL7 が作成したリソースの構造・意味の定義。SNOMED CT・LOINC・ICD 等の収録物を CC0 で利用できるとはしません。ページ全体やパッケージをそのまま許諾済みデータとして取り込みません。

参照した構造定義の入口：[Observation](https://hl7.org/fhir/R5/observation.html)、[Specimen](https://hl7.org/fhir/R5/specimen.html)、[Procedure R4](https://hl7.org/fhir/R4/procedure.html)／[R5](https://hl7.org/fhir/R5/procedure.html)、[MedicationRequest](https://hl7.org/fhir/R5/medicationrequest.html)。状態・由来は既存調査の [Condition](https://hl7.org/fhir/R5/condition-definitions.html)・[Provenance](https://hl7.org/fhir/R5/provenance.html) も継続参照します。

今回の個別確認は、Observation の検体・方法、Procedure の時点と参加者を中心とした該当欄です。Procedure 二版の HTML はローカル保存し、ページ名・版・時点の項目とハッシュを記録しました。全リソース・全版差の精読、構造定義 JSON の実体取得、変換器の実行は未完了です。

## S05：WHO の利用条件

WHO。[ICD-11 License の案内](https://icd.who.int/docs/icd-api/license/)、[リンク先のデジタル版規約 PDF](https://icd.who.int/en/docs/icd11-license.pdf)、[ICD API ホーム](https://icd.who.int/icdapi)。PDF は 5 ページ、文書内 © WHO 2020。改訂日と今回対象版への適用関係は追加確認事項です。

確認：PDF §1.1 の対象内容、§1.2 のライセンス、§1.2.1 の別標準の開発・普及目的への制限を読めました。API ホームの「より開かれた」とする案内と、そのリンク先の ND 表記だけから適用条件を単純化していません。

適用：独自体系開発への用語・関係・派生物の取り込みを保留するプロジェクト判断。ICD の全版・各国修正版へ一律に同じ条件を当てた結論ではありません。ライセンスの全文解釈・個別許諾・WHO への問い合わせは未実施です。

## S06：WHO API の入手条件と対応版

[API v2 文書](https://icd.who.int/docs/icd-api/APIDoc-Version2/)、[対応する分類・版・言語](https://icd.who.int/docs/icd-api/SupportedClassifications/)。

確認：アカウント登録と OAuth 2 client credentials、JSON-LD、Foundation と MMS の違い。対応版一覧の ICD-10 2019、ICD-11 MMS 2026-01 の英語。言語コード一覧に日本語が載ることだけで、当該版に日本語の全内容があるとは判断しません。

適用：保留候補の入手手順の整理。認証情報の作成・API 実行・ローカル版の導入は未実施。二体系の API 提供を、公式の版固定対応表や変換機能の実在と同一視しません。

## S07：LOINC の利用条件と配布

Regenstrief Institute。[ライセンス](https://loinc.org/license)（表示更新 2026-08-06）、[配布一覧](https://loinc.org/downloads)（表示更新 2026-08-19）。一覧には 2.83、2026-08-19 リリースと表示。

確認：Licensed Materials の範囲、第 1 項の目的制限、第 2〜5 項の変更・文書・parts の扱い、第 9〜10 項の配布条件。ダウンロードにはログインが必要と記載されています。

適用：今回の独自体系開発にコード・定義・変更ファイル等を取得・転用する範囲を保留。ライセンスに open・free とあることを目的制限なしと読み替えません。登録・ダウンロード・個別許諾は未実施です。

## S08：SNOMED CT の入手と地域・主体

SNOMED International。[Get SNOMED CT](https://www.snomed.org/get-snomed)、[Vendor Introduction §7 Licensing](https://docs.snomed.org/snomed-ct-practical-guides/vendor-introduction-to-snomed-ct/7-licensing)。動的な公式案内であり、採用する契約・リリース版は未固定です。

確認：NRC・MLDS の導線、Affiliate・sub-license・National license の区別、地域別の条件と免除申請の存在。適用：利用主体・利用地域・契約・研究目的を確認するまでリリース本体を未選定とする判断。タイムゾーンから利用地を推定せず、研究なら自動で無償・自由利用としません。Affiliate Agreement 本文の全条項は未精読です。

## S09：MEDIS の利用案内と国内マスター

MEDIS-DC。[総合入口](https://www.medis.or.jp/4_hyojyun/medis-master/)、[利用案内](https://www.medis.or.jp/4_hyojyun/medis-master/riyou/)、[FAQ](https://www.medis.or.jp/4_hyojyun/medis-master/faq/)。

確認：医療機関以外での使用または配布に申請・許可が必要なマスターの列挙、FAQ の再配布・改変の説明とマスターごとの更新の案内、病名と請求傷病名の関係。利用案内と FAQ には改変配布について範囲が異なって見える記載があり、個別許諾の条件としては確定していません。

適用：病名・HOT・手術処置等の本体の利用は保留。臨床検査マスターは担当先が異なるため、同じ許諾条件と一括判断しません。申請・契約・本体取得は未実施です。

## S10：国内レセプト電算マスターの所在

厚生労働省。[診療報酬情報提供サービス](https://shinryohoshu.mhlw.go.jp/shinryohoshu/)、[ダウンロード入口](https://shinryohoshu.mhlw.go.jp/shinryohoshu/downloadMenu/)、[利用上の注意・FAQ](https://shinryohoshu.mhlw.go.jp/shinryohoshu/faq/)。

確認：基本マスターの公開導線、固有の著作権・無断改変の説明、傷病名 FAQ 問 3 の ICD 対応の位置付け、問 4 の旧傷病名と移行対応テーブルの所在説明。MEDIS マスターへのリンクと、このサイト固有の資料は分けました。

適用：国内制度・分類・改廃の追加調査候補。今回の研究用改変・非公開共有・派生対応表の条件は未確定で、ファイル・版・形式も未固定です。本体と対応表の行単位の確認は未実施。セッション ID を含む一時リンクは台帳に残さず、正規の入口 URL を記録しました。

## S11：ICD-10-CM の版別資料

米国 CDC/NCHS。[ICD-10-CM Files](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html)、[FY2025 配布ディレクトリ](https://ftp.cdc.gov/pub/health_statistics/nchs/Publications/ICD10CM/2025/)、[FY2026 配布ディレクトリ](https://ftp.cdc.gov/pub/health_statistics/nchs/publications/ICD10CM/2026/)。

確認：版別資料と XML 等の公開配布の所在。採否の判断を変えない範囲で探索を止め、個別ファイルの権利・今回の研究目的への適用までは確認していません。CDC の公開資料の一部に public domain 表示があっても、未確認の全ファイルへ一般化せず、今回の初期データには選定していません。

## 残る実施事項

選定二組の [実体取得・初期照合](03-acquisition.md) は完了しました。許諾条件を追加確認する候補は [R3 本文](03-data-access.md) に残しています。公式の記載値と自分たちの実測値を分け、次は取得資料の意味を使った R4 の評価設計へ進めます。
