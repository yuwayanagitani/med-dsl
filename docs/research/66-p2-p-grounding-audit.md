# P2-p（第二段）：FHIR R5 の Observation・Specimen への接地の監査

作成日：2026-10-21。状態：**作成者側の監査。コードは変更していない**。[範囲選定62](62-p2-o-selection.md) の U2（第二段で実資料に接地するか）を、第一段（[P2-o の結果65](65-p2-o-results.md)）の後に進めた最初の作業です。薄い臨床ライブラリが使う概念（記録の値・文脈・時点・確度・確認）が、実在の構造定義に何として現れ、何が現れないかを調べました。**FHIR への適合は主張しません**。ここで確かめたのは、取得したページに書いてある構造・濃度（cardinality）・制約だけで、記録内容や医学的な正しさ、ページに書いていない部分の意味ではありません。独立確認は未実施です。

## 1. 取得と扱い（D03）

| 資料 | URL（最終 URL も同じ） | バイト数 | SHA-256 | 取得日時（UTC） |
| --- | --- | --- | --- | --- |
| FHIR Observation R5 v5.0.0 | `https://hl7.org/fhir/R5/observation.html` | 706,699 | `02beab65…`（先頭8桁） | 2026-10-21 11:28 |
| FHIR Specimen R5 v5.0.0 | `https://hl7.org/fhir/R5/specimen.html` | 365,066 | `01a005bd…` | 2026-10-21 11:28 |

- 両ページとも、D03（[03-data-access.md](03-data-access.md)）が「R5 v5.0.0 の HTML 定義を参照」と選定した範囲に入ります。Git 管理外の `data/research/r3/` に保存し、[台帳](03-materials.json) に `acquired_file_checks_passed`・`content_verified: false`・`commit_payload: false` で記録しました（ページ名「Observation／Specimen - FHIR v5.0.0」と目印の項目の存在を検査。公表ハッシュはなく、`not_available`）。
- **使い方は、構造・濃度・制約の読み取りに限ります**。第三者の用語（LOINC、SNOMED CT など、ページが束縛として名前だけ挙げるもの）の内容は取り込まず、写してもいません。利用条件は D03 の 2026-10-18 の確認（HL7 作成部分は CC0、第三者 IP は別条件）を引用するもので、今回は条件のページを再取得していません。
- このリポジトリには、ページの本文も、そこから作った対応表も入れていません。以下に書くのは、各要素の名前・濃度・型・ページの短い記述に限ります。
- **取得していないページ**（この監査では確かめられない部分）：データ型（Quantity、Range、Period、CodeableConcept）、値集合（Observation Status、Data Absent Reason）、Provenance、拡張。以下で「未確認」とするのは、これらに依る点です。

## 2. ページで確認できたこと（Observation）

| 要素 | 濃度・型（ページの表記） | ページの記述 |
| --- | --- | --- |
| status | 1..1 code（?! Σ） | `registered | preliminary | final | amended +`（全ての値は値集合のページにあり、未取得）。束縛は Required |
| code | 1..1 CodeableConcept | Type of observation。束縛は Example |
| value[x] | 0..1 | Actual result。13の型（Quantity、CodeableConcept、string、boolean、integer、Range、Ratio、SampledData、time、dateTime、Period、Attachment、Reference(MolecularSequence)） |
| dataAbsentReason | 0..1 CodeableConcept | Why the result is missing。規則 obs-6：`value[x]` が無いときだけ存在してよい |
| effective[x] | 0..1（dateTime／Period／Timing／instant） | Clinically relevant time/time-period for observation |
| issued | 0..1 instant | Date/Time this version was made available |
| performer | 0..* Reference | Who is responsible for the observation |
| method | 0..1 CodeableConcept | How it was done。束縛は Example |
| specimen | 0..1 Reference(Specimen | Group) | Specimen used for this observation。規則 obs-9：Group を指すときは、メンバーが検体だけ |
| referenceRange | 0..* | 下限・上限・文章のどれかが要る（obs-3） |

ページには「Changes from R4」があり、R5 での変更に `Observation.specimen: Added Target Type Group`、`Observation.value[x]: Add Types Attachment, Reference(MolecularSequence)` があります。また、`value[x]` と `code` の使い方の組が複数あることを述べた後、**具体的な型は「プロファイルと実装ガイドで定める」ことが期待される**と書いています（10.1.5.4.3）。

## 3. ページで確認できたこと（Specimen）

| 要素 | 濃度・型 | ページの記述 |
| --- | --- | --- |
| status | 0..1 code（?!） | `available | unavailable | unsatisfactory | entered-in-error` |
| type | 0..1 CodeableConcept | Kind of material that forms the specimen |
| subject | 0..1 Reference | 検体の由来 |
| collection.method | 0..1 CodeableConcept | Technique used to perform collection |
| collection.collected[x] | 0..1（dateTime／Period） | Collection time |
| condition | 0..* CodeableConcept | State of the specimen |
| processing.method | 0..1 CodeableConcept | 処理の段階の方法 |

## 4. 対応の監査

ライブラリの概念を左に、ページで確認できた要素を右に置きます。「損失」は、ライブラリからこの構造へ出すときに、ページの要素だけでは表せない区別です。

| ID | ライブラリの概念 | 対応する要素 | 確認できたこと | 損失・追加・未確認 |
| --- | --- | --- | --- | --- |
| G1 | 値（点・有限区間、単位） | `value[x]`（Quantity／Range） | `value[x]` の型の一覧にある | 区間の開閉（半開区間など）を Range が表せるかは、Range・Quantity のデータ型のページに依り**未確認**。表せないなら、`not_representable`（`interval_bounds`）の実例になる |
| G2 | 値が無い記録 | `dataAbsentReason` | `value[x]` が無いときだけ存在してよい（obs-6） | ライブラリの `record` は値を必須とするため、「値が無い理由つきの記録」を操作で作れない。FHIR 側にあってライブラリ側にない状態 |
| G3 | 文脈 method の三状態（known／unknown／unspecified） | `method`（0..1） | `method` は存在か不在かで、`dataAbsentReason` は `value[x]` にだけ付く（obs-6） | `unknown` と `unspecified` の区別を、この構造だけでは表せない（拡張は未取得で**未確認**）。FHIR 側へ出すと区別が落ちる |
| G4 | 文脈 specimen の三状態 | `specimen`（0..1 Reference(Specimen|Group)） | 同上 | 同上。R5 で Group が対象に加わった（R4 と比べた変更として確認）。ライブラリの `specimen` は「ref と版」で、Specimen の `type`（材料の種類）か参照かは、ライブラリ側で定義が曖昧（要整理） |
| G5 | 要求「method が known」「specimen が known」 | `method`・`specimen` が**任意**（0..1） | FHIR 本体はどちらも要求しない。具体的な使い方は「プロファイルと実装ガイドで定める」と書いてある | 設計63の「要求は出力先の宣言で、記録には属さない」と整合する。ただし**根拠は、この一文と濃度が任意であること**に限る |
| G6 | 時点の区間 `validity`（その量の主張が成り立つ半開区間） | `effective[x]`（観察の臨床上関係する時点） | 両方とも時点・区間を持つ | 意味が同じとは言えない（主張の有効期間と観察の時点）。対応づけには判断が要る。`Period` の端の扱いは**未確認** |
| G7 | `recorded_at`（記録の時刻） | `issued`（この版が利用可能になった時刻） | 近い名前の要素がある | 同じ意味とは確認できない。**未確認** |
| G8 | 確度 `confirmed`／`suspected`、人の確認、訂正 | `status`（1..1。`final`・`amended` など） | `status` は必須で、値の一部がページに出ている | 値の全体は値集合のページで、**未取得**。人の確認（誰がどの内容を確認したか）は `performer` の語義（responsible）とは別で、Provenance は**未取得** |
| G9 | 出自 `ai_candidate`／`observed` | （対応する要素を、取得したページで確認できない） | － | 出自の種類を運ぶ要素はない（拡張・メタデータは未確認）。FHIR 側へ出すと出自の種類が落ちる可能性 |
| G10 | 性質 `property_ref` | `code`（1..1） | `code` は必須で、型の表記は CodeableConcept | 対応づけは**仮定**（ライブラリの `property_ref` は架空の不透明な参照）。`code` の使い方も組み合わせが複数あるとページが書く |
| G11 | `method`（観察の方法） | Observation.`method` と Specimen.`collection.method`（採取の技術）が別に存在 | 両方がページにある | ライブラリの `method` は観察の方法。採取の方法は区別されない（別の欄がない） |
| G12 | 検体の状態 | Specimen.`status`（`unsatisfactory` を含む）、`condition` | ページにある | 要求「specimen が known」は、検体の質が不適でも満たされる。「検体の状態」を要求する要素の種類がライブラリにない |
| G13 | （ライブラリになし） | `status`（1..1）、`code`（1..1） | 必須の要素 | 構造として必須の要素に当たる要求の要素の種類が、ライブラリの語彙（`value`・`context`・`trend`）にない。そのまま書くと `unsupported_requirement_element` になる |

確認できた対応は、要素の存在と濃度の読み取りまでです。**意味が同じであることは、どの行でも確認していません**（G1、G3、G6、G7、G8、G9、G10 は、取得していないページや仮定に依る）。

## 5. わかったこと

1. **要求を出力先の宣言にする設計は、ページの記述と矛盾しない。** FHIR 本体は method・specimen を任意とし、使い方をプロファイルに任せている。ただしこれは設計の正しさの証明ではなく、一つの資料との整合に過ぎない。
2. **ライブラリの三状態（known／unknown／unspecified）は、この構造の存在・不在の二状態より細かい。** FHIR へ出すときに落ちる区別があり得る（G3・G4・G9）。`flows` の `lost` に載せるべき候補で、実装前に、拡張とデータ型のページで確かめる必要がある。
3. **ライブラリにあって構造にない状態、構造にあってライブラリにない状態の両方がある。** 値のない記録（G2）、検体の状態（G12）、必須の `status`・`code`（G13）はライブラリの語彙で表せない。逆に、確度・確認・出自（G8・G9）は、取得したページの要素では運べない。
4. **R5 の変更を、要求の版の更新として読める。** `specimen` の対象に Group が加わったことは、「specimen が known」の意味が版で広がる例になる（ただし、R4 のページは今回取得していない。変更は R5 のページの「Changes from R4」の記述で確認した）。

## 6. 次に判断すること

次の候補と、作成者の推奨です。

| 候補 | 内容 | 推奨 |
| --- | --- | --- |
| A | ここで止める（監査の記録だけ）。次は CPC の版の監査（U3）へ | ○ 既に有益な知見は得た。コードを変えないので、確認の負担が小さい |
| B | **P2-p**：要求の要素の種類に `status`・`code` に当たるものを足し、G3・G4・G9 の損失を `flows.lost` に載せる、FHIR の構造に接地した出力先の宣言を実装・評価する。取得していないページ（データ型、値集合、拡張、Provenance）が前提になるので、先にそれらの取得の確認を取る | 次の段階。データ型のページを取得してからが良い（G1・G6・G7 の確認ができる） |
| C | 取得するページを増やす（Quantity・Range・Period・CodeableConcept のデータ型、Observation Status の値集合、Provenance）だけを先に行い、監査の未確認を減らす | B の前提。D03 の範囲（HL7 作成部分）なので、取得の前に確認を取る |

推奨は **C → 監査の更新 → B の設計**の順です。いずれも着手前に利用者の確認を取ります。

## 7. 限界

- ページを読んだのは作成者一人です。HTML の本文から要素の表を取り出して読んだもので、ページ内の注釈や例の全てを読んだわけではありません。
- 対応の意味は、どの行も検証していません。「確認できた」は、名前・濃度・型・短い記述がページにあることだけです。
- 第三者の用語（LOINC、SNOMED CT など）の内容と利用条件は扱っていません。FHIR の型・制約への適合を主張せず、実データ・患者情報も含みません。
