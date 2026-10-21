# R3：資料の入手元・版・利用条件

確認日：2026-10-18（2026-10-21 に、選定済みの FHIR Observation・Specimen の2ページを追加取得。[03-acquisition.md](03-acquisition.md)）。状態：資料・条件の確認に続き、選定 4 ファイルの実体取得・初期照合を完了しました。RxNorm 10 月版は公表 MD5 と一致し、9 月版と FHIR は公表ハッシュ未確認の範囲を明示しています。全概念・版間対応の意味検証は未実施です。[取得・検査結果](03-acquisition.md)、[出典](03-sources.md)、[資料台帳](03-materials.json) を参照してください。

[最終目標](../vision.md) に向け、意味を定義する資料、変更を追う資料、記録の文脈を定義する資料を選びます。取得しやすい一体系を普遍的な基礎にせず、[R2b の三案と反例](02b-change-model.md) を検討する材料として扱います。

## 1. D03：今回の選定

最初の実データ取得候補は、NLM の **RxNorm Current Prescribable Content（CPC）2026-09-08 版と 2026-10-05 版**です。薬剤の名前・属性・関係と版差を調べるために使います。公式資料が public domain・ログイン不要と説明しているサブセットを選び、第三者語彙を含む RxNorm 全体版とは区別します。[CPC の説明](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)、[配布一覧](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html)

検査・検体・処置・処方・主張の文脈には、**HL7® FHIR® R4 v4.0.1 と R5 v5.0.0 のリソース定義**を選びます。最初の版間比較には Procedure を使い、他領域も参照します。FHIR の仕様は CC0 ですが、埋め込まれた第三者の用語・コードへの権利は別なので、外部のコード表や例を一括取得する方法は初期範囲に含めません。[FHIR のライセンス、第三者コンテンツ](https://hl7.org/fhir/R5/license.html)

| 区分 | 決定 | 範囲・状態 |
| --- | --- | --- |
| 最初の用語データの一組 | RxNorm CPC 2026-09-08 → 2026-10-05 | 同一体系の版間の比較候補。薬剤の定義・関係の検証材料 |
| 最初の構造定義の一組 | FHIR Procedure R4 v4.0.1 → R5 v5.0.0 | コア・情報モデルの版差の比較候補。HTML の対象箇所は確認済み |
| コミットするもの | 自分たちの調査結果、出典、版、取得状態、確認手順、架空例 | 今回は外部マスター・対応表・仕様全文を同梱しない |
| ローカル取得した資料 | 選定した CPC 二版、FHIR Procedure の二版の HTML | サイズ・ハッシュ・README またはページの版・初期構造を確認。意味の検証は別段階 |
| 追加の条件確認へ回すもの | WHO ICD、LOINC、SNOMED CT、MEDIS、国内請求マスター、ICD-10-CM | 所在の確認と、今回の開発目的での利用可否を区別する |
| まだ決めないこと | 最初の実験の主領域・用途・補助入力・合格条件 | D04・D05 を R4 で決める。データ選定だけで変換仕様を確定しない |

この選定は、コード体系の採用や薬剤への対象限定を意味しません。ICD-10 → ICD-11 は追加確認が必要な候補として残し、当面の研究は上記の版差と架空の形式例で進められるようにします。

## 2. 原理の検証に使う資料

| 材料 | 発行主体・対象 | 取得形式・認証・版 | 検証したいこと |
| --- | --- | --- | --- |
| RxNorm CPC | 米国 NLM、米国で処方可能な薬剤を中心とするサブセット、英語 | 固定日付の ZIP、UTF-8・パイプ区切り RRF。CPC はログイン不要。今回二版を固定 | 成分・強度・剤形等の構成、関係の方向、追加・欠落を意味変更と区別する方法 |
| FHIR Observation・Specimen | HL7、検査・観察と検体の記録構造 | R5 v5.0.0 の HTML 定義を参照。機械処理時には選定した構造定義の JSON 等を取得 | [K09](02b-cases.md) の検体・検査法・結果の結び付き。実測値と分類コードの役割の違い |
| FHIR Procedure | HL7、処置事象・参加者・時点 | R4 v4.0.1／R5 v5.0.0。版ごとの定義を参照 | K09・K12：役割と事象、項目名・許容型・意味の変更 |
| FHIR MedicationRequest | HL7、処方の依頼・状態・対象者 | R5 v5.0.0。用語本体とは別に構造を参照 | 薬剤概念と、誰へのどの依頼かを区別すること |
| FHIR Condition・Provenance | HL7、主張の確認状態と由来 | R5 v5.0.0。R1・R2b から継続参照 | K07・K08・K11：主張、対象者、確認状態、生成・導出の由来 |
| R2b の形式例 | 本プロジェクト、架空の語彙と主張 | [K01〜K14](02b-cases.md)。外部コード表を使わない | 保存条件・拡張の併用・意図した訂正の原理を先に検討する |

FHIR では Observation の `method`・`specimen` 等、Procedure の参加者や時点を資料上で確認できます。これは構造と意味の定義を調べる材料です。FHIR の型・制約への適合だけで、記録内容や医学的判断の正しさを確認したことにはしません。[Observation](https://hl7.org/fhir/R5/observation.html)、[Specimen](https://hl7.org/fhir/R5/specimen.html)、[Procedure](https://hl7.org/fhir/R5/procedure.html)、[MedicationRequest](https://hl7.org/fhir/R5/medicationrequest.html)

実際の版差の入口として、Procedure の時点は R4 の `performed[x]`、R5 の `occurrence[x]` に定義され、R5 には `Timing` の選択肢があります。旧版の選択肢を名前だけ置換する実装で新版の全表現を扱えると判断せず、対象型と意味を次の評価設計で具体化します。[FHIR R4 Procedure](https://hl7.org/fhir/R4/procedure.html)、[FHIR R5 Procedure](https://hl7.org/fhir/R5/procedure.html)

## 3. RxNorm CPC 二版をどう使うか

### 入手元と再現単位

配布元は [NLM の一覧](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html) です。選定したファイルは以下です。`current` を含む可変 URL は再現性の基準に使いません。

| 版 | 固定ファイル | 公表されている照合値 | 今回の取得状態 |
| --- | --- | --- | --- |
| 2026-09-08 | [RxNorm_full_prescribe_09082026.zip](https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_09082026.zip) | 現行ページ本文からは未確認 | 取得済み。SHA-256・MD5 を計算し、CRC・README の版・RRF 全行の初期構造を確認 |
| 2026-10-05 | [RxNorm_full_prescribe_10052026.zip](https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_10052026.zip) | MD5 `a3bfab544c6a67c127ebcd10ab914aa9` | 取得済み。公表 MD5 と一致。SHA-256・CRC・README の版・RRF 全行の初期構造を確認 |

10 月版は発行者の表示 MD5 と手元で計算した値が一致しました。二版のサイズ・自前の SHA-256・MD5・RRF 行数は [台帳](03-materials.json) に記録しました。9 月版の自前ハッシュは、独立した公表値との一致とは区別します。

公式の CPC 説明は `RXNCONSO`・`RXNSAT`・`RXNREL` の三つのデータファイルを挙げています。廃止・抑制された内容は対象外と説明されているため、CPC 内で見つからなくなった項目を、それだけで概念の廃止や置換先が確定した事例にしません。月次版を比較し、週次更新は初期比較に混ぜません。[CPC の収録範囲と更新](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)

### データを読む際の確認点

| 対象 | 初回に確認すること | 誤った扱いの例 |
| --- | --- | --- |
| 名前・コード | `RXCUI`、原子単位の `RXAUI`、出典 `SAB`、語型 `TTY`、名称、抑制状態等 | 名称の一致だけで概念を同一視する |
| 属性 | 属性名・値・出典、どの概念・原子に結び付くか | 強度の値だけを抜き、対象や単位を落とす |
| 関係 | 概念と原子の参照、`REL`・`RELA` の意味と方向 | 列 1 から列 2 への辺と決めつける |
| 版差 | 追加・欠落・名称・属性・関係を別々に比較し、変更根拠を確認する | 欠落＝廃止、同じ ID＝全関係が不変、とみなす |
| サブセット | 実際の `SAB`、収録ファイル、README、対象範囲 | CPC の説明を全体版の第三者語彙に適用する |

`RXNREL` の公式仕様は、`REL` を二番目の概念・原子から一番目への関係として説明します。具体的な方向は `RELA` と出典も含めて確認し、単純な列順から決めません。[技術文書 §12.4・§12.5・§12.7](https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html)

両月の全体版リリースノートは大きな変更なしと記載しています。これを CPC の差分ゼロと解釈せず、全体版の収録件数を CPC の件数として使いません。[9 月のノート](https://www.nlm.nih.gov/research/umls/rxnorm/docs/2026/rxnorm_releasenotes_full_09082026.html)、[10 月のノート](https://www.nlm.nih.gov/research/umls/rxnorm/docs/2026/rxnorm_releasenotes_full_10052026.html)

これは、公式の版間対応表が付くことを確認した選定ではありません。初期案は二版の定義・属性・関係の比較であり、欠落項目の置換を自動確定する機能は含めません。置換・廃止の意味を確定する資料が不足するケースは、R4 で期待結果未確定として分けます。

## 4. 予定用途に対する条件とプロジェクトの扱い

以下は、確認できた条項と、それを踏まえた今回の作業範囲です。閲覧可能、無償、非公開、コードのみ、という条件だけで開発・共有・派生物への許諾を判断しません。

| 対象 | 公式資料で確認した条件 | 今回の判断・未解決事項 |
| --- | --- | --- |
| RxNorm CPC | public domain・ライセンス不要と説明。RxNorm の利用条件には出典の謝辞、推薦を示さないこと、再配布時の最新版または旧版明示等がある | 選定二版の研究用ローカル取得・比較を進める。旧版は研究用の固定資料と明示。今回は生データを共有しない。全体版は別判断。[CPC](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)、[利用条件](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html) |
| FHIR の HL7 作成部分 | CC0。派生仕様を FHIR 本体と誤認させず、HL7 の推薦・適合を勝手に名乗らない。第三者 IP は別条件 | 構造・状態・関係の定義を資料として選定。外部用語の内容を取り込む前に分離する。[ライセンス](https://hl7.org/fhir/R5/license.html) |
| WHO ICD-11 等 | リンク先のデジタル版規約 §1.2 は CC BY-ND 3.0 IGO、§1.2.1 は別標準の開発・普及目的での利用を制限。コード・URI・関係等も対象に列挙 | 本プロジェクトへの意味定義・派生語彙・対応データの取り込みは保留。API の存在は許諾の代わりにしない。適用する版と研究目的での扱いを追加確認。[規約](https://icd.who.int/en/docs/icd11-license.pdf) |
| LOINC | License 第 1 項に、患者の観察等を識別する別標準の開発・普及を目的とする利用への制限。Licensed Materials には Changes File 等も含む | コード・定義・変更ファイルを独自体系開発の材料として取得・転用する初期候補から外す。適合する利用範囲または別途の許諾を確認してから再検討。[ライセンス](https://loinc.org/license) |
| SNOMED CT | Affiliate／sub-license 等の手続き、利用地域に応じた条件がある。研究での免除も自動適用ではない | 利用主体・地域・契約・版と、今回の研究目的・派生物の扱いが未確認。用語リリース本体は未選定・未取得。[入手案内](https://www.snomed.org/get-snomed)、[ライセンス案内](https://docs.snomed.org/snomed-ct-practical-guides/vendor-introduction-to-snomed-ct/7-licensing) |
| MEDIS の病名・HOT・手術処置等 | 利用案内は医療機関以外での使用または配布に申請・許可が必要とする。FAQ の改変・再配布の説明と、利用案内の改変配布の説明は範囲の確認が必要 | 個人研究を医療機関内利用と同一視しない。今回の主体・使用目的・共有範囲での許諾を確認するまで本体の取得・転用を保留。[利用案内](https://www.medis.or.jp/4_hyojyun/medis-master/riyou/)、[FAQ](https://www.medis.or.jp/4_hyojyun/medis-master/faq/) |
| 国内レセプト電算マスター | 診療報酬情報提供サービスに配布導線がある。固有 FAQ は掲載情報の著作権と無断改変に言及 | 政府サイトだから自由に改変・再配布可能と決めず、マスターごとの適用条件と派生対応表を追加確認。今回のデータ採用は保留。[配布入口](https://shinryohoshu.mhlw.go.jp/shinryohoshu/downloadMenu/)、[利用上の注意](https://shinryohoshu.mhlw.go.jp/shinryohoshu/faq/) |
| 米国 ICD-10-CM | CDC に年次・年度途中のリリース一覧と XML 等の公開配布がある | WHO ICD-10、MEDIS の ICD 対応とは別の資料として扱う。今回の目的での条件・個別ファイルの権利範囲の確認を残し、未取得。[CDC の一覧](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html) |

WHO の API ホームにはライセンスがより開かれたという案内がありますが、そのリンク先と PDF には上記の条項がありました。案内の文言だけから制限が解消されたと判断しません。ICD-10 の各版、ICD-11 の規約、第三者由来の内容の条件を一括扱いせず、将来採用する際の対象版・文書を確認します。[API ホーム](https://icd.who.int/icdapi)、[リンク先](https://icd.who.int/docs/icd-api/license/)

この保留は取得・転用に関するものです。公開されている仕様や条件の確認は続けられます。自分たちの原理・架空例の研究は、保留した外部用語の取得を待つ必要がありません。

## 5. 中間用途の候補と対応資料の状態

| 候補 | 実在を確認したもの | まだ確認できていないもの | 次の扱い |
| --- | --- | --- | --- |
| RxNorm CPC 二版 | 固定配布先、形式説明、利用条件、月次ノート。実体取得・初期照合も完了 | 概念・属性・関係ごとの差、欠落の理由、置換の期待結果 | 初期検査の行数差を意味差分と同一視せず、評価を設計 |
| FHIR Procedure R4 → R5 | 両版の定義、時点の項目と許容型の差 | 全項目の意味保存、変換実装、臨床運用での妥当性 | 構造変更の評価材料として選定 |
| WHO ICD-10 → ICD-11 | API の版一覧には ICD-10 2019 と ICD-11 MMS 2026-01 がある。OAuth 2 client credentials、JSON-LD 等を使う仕様がある | 今回の開発目的での許諾、公式対応表の固定ファイル・対象版・方向・用途、取得実行 | API に二体系があることを変換機能の確認とせず、初回の必須材料から外す |
| 国内の旧傷病名 → 現行傷病名 | 公式 FAQ に旧傷病名管理ファイルと移行対応テーブルの案内がある | 固定したファイル・版・方向・再配布や派生物の条件、項目ごとの意味関係 | 国内の変更履歴の追加候補。MEDIS と請求マスターの条件を分けて確認 |

WHO の仕様・対応版は [API 文書](https://icd.who.int/docs/icd-api/APIDoc-Version2/) と [対応一覧](https://icd.who.int/docs/icd-api/SupportedClassifications/)、国内の移行資料の所在は [傷病名マスター FAQ の問 4](https://shinryohoshu.mhlw.go.jp/shinryohoshu/faq/) で確認しました。対応表の所在の説明を読めたことと、各行の意味を確認したことは区別します。

## 6. 取得後に残す記録と実施状況

取得時は、発行元 URL、最終 URL、版・公開日、取得日時、ファイル名、バイト数、SHA-256、公開照合値、条件の出典と確認日を記録します。機械処理前にアーカイブの内容、README、出典・依存語彙、形式を確認します。秘密情報や認証ヘッダーは記録しません。

保存先は既存の `.gitignore` が除外する `data/` またはリポジトリ外の作業領域とします。生データ、展開物、API の生応答、実データ由来の対応表・キャッシュは、利用範囲を記録したローカル資料として分けます。除外設定は利用許諾の代わりにはしません。

当初は名前解決に失敗しましたが、再試行と待ち時間の延長で CPC 二版・FHIR Procedure 二版の HTML を取得できました。4 ファイルの取得日時・最終 URL・サイズ・SHA-256、CPC の CRC・README の版・RRF 全行の列数と出典、FHIR のページ名・版・時点の項目を記録しました。[詳細と再検査手順](03-acquisition.md) を参照してください。外部本体は Git 管理外です。

初期照合と、意味・医学的妥当性の検証は区別します。R4 では取得した資料を使って期待結果を設計し、具体的な概念・属性・関係の意味を確認します。取得先が変わる、実体が公式説明と異なる、条件が改訂される、今回の二版では必要な変化を観察できない場合は、D03 の版・範囲を見直します。

## 7. R4 へ引き渡すこと

1. R2b の K01〜K14 を原理の共通課題とし、CPC の薬剤概念・関係、FHIR の検査・処置・確認状態に対応させる。
2. 表記差、収録範囲の差、属性・関係の差、定義の改訂、コアの構造変更を分け、意味の喪失・追加と機械的なファイル差を混同しない。
3. 実資料で正答を確認できたケースと架空の形式例を別に管理する。コード・名称の一致だけを期待結果の根拠にしない。
4. 初期の領域・方向・補助入力・確認者・指標を D04・D05 として具体化する。WHO・LOINC 等の保留解消を、その開始条件にしない。

データの扱いに関する D03 を整理した段階であり、表現能力・永続性・変換性能の実証を完了したものではありません。
