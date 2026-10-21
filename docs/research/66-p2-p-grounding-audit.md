# P2-p（第二段）：FHIR R5 の Observation・Specimen への接地の監査

作成日：2026-10-21（同日に、データ型・値集合・Provenance・拡張のページの取得後に更新）。状態：**作成者側の監査。コードは変更していない**。[範囲選定62](62-p2-o-selection.md) の U2（第二段で実資料に接地するか）を、第一段（[P2-o の結果65](65-p2-o-results.md)）の後に進めた最初の作業です。薄い臨床ライブラリが使う概念（記録の値・文脈・時点・確度・確認）が、実在の構造定義に何として現れ、何が現れないかを調べました。**FHIR への適合は主張しません**。ここで確かめたのは、取得したページに書いてある構造・濃度（cardinality）・制約だけで、記録内容や医学的な正しさ、ページに書いていない部分の意味ではありません。独立確認は未実施です。

## 1. 取得と扱い（D03）

| 資料 | URL | バイト数 | SHA-256（先頭8桁） | 取得（UTC） |
| --- | --- | --- | --- | --- |
| Observation R5 v5.0.0 | `hl7.org/fhir/R5/observation.html` | 706,699 | `02beab65` | 2026-10-21 11:28 |
| Specimen R5 v5.0.0 | `…/specimen.html` | 365,066 | `01a005bd` | 同 |
| Datatypes（Quantity・Range・Period・CodeableConcept ほか） | `…/datatypes.html` | 1,665,071 | `d826e181` | 同 11:35 |
| observation-status の符号系ページ | `…/codesystem-observation-status.html` | 25,780 | `1952e015` | 同 |
| data-absent-reason の値集合ページ | `…/valueset-data-absent-reason.html` | 33,004 | `2e3d8775` | 同 |
| Provenance | `…/provenance.html` | 277,558 | `3124befd` | 同 |
| Extensibility | `…/extensibility.html` | 156,299 | `41f6d38e` | 同 |

- 全て、最終 URL も同じ（リダイレクトなし）。D03（[03-data-access.md](03-data-access.md)）が「R5 v5.0.0 の HTML 定義を参照」と選定した FHIR 本体の範囲です。Git 管理外の `data/research/r3/` に保存し、[台帳](03-materials.json) に `acquired_file_checks_passed`・`content_verified: false`・`commit_payload: false` で記録しました（ページ名「… - FHIR v5.0.0」と目印の項目の存在を検査。公表ハッシュはなく、`not_available`）。台帳の検査は、既存の Procedure・CPC を含む11件がすべて通っています。
- **使い方は、構造・型・濃度・制約と、符号の名前の確認に限ります**。第三者の用語（LOINC、SNOMED CT など、ページが束縛として名前だけ挙げるもの）の内容は取り込まず、写してもいません。status と data-absent-reason の符号は HL7 自身が定義する小さな集合で、**名前と意味の把握のため読んだだけ**で、このプロジェクトの語彙には取り込んでいません。利用条件は D03 の 2026-10-18 の確認（HL7 作成部分は CC0、第三者 IP は別条件）を引用するもので、条件のページ自体は再取得していません。
- このリポジトリには、ページの本文も、そこから作った対応表も入れていません。以下に書くのは、各要素の名前・濃度・型・ページの短い記述と、私の言い換えに限ります。
- **まだ取得していないページ**：Quantity の comparator の値集合、拡張そのものの定義（data-absent-reason の拡張がどの要素に付けられるか）、Observation Status 以外の値集合、Group、Device。以下で「未確認」とするのは、これらに依る点です。

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

ライブラリの概念を左に、ページで確認できた要素を右に置きます。「損失」は、ライブラリからこの構造へ出すときに、ページの要素だけでは表せない区別です。最初の版（取得2ページ）の未確認の多くは、データ型・値集合・Provenance・拡張の取得で確認できました。変わった行に ※ を付けます。

| ID | ライブラリの概念 | 対応する要素 | 確認できたこと | 損失・追加・未確認 |
| --- | --- | --- | --- | --- |
| G1 ※ | 値（点・有限区間、単位） | `value[x]`（Quantity／Range） | Range の low・high は**両端とも含む**（閉）。low・high が欠けると、その端は不明で、範囲全体も不明。端に comparator は付けられず、範囲外の測定は comparator つきの Quantity を使う。Quantity は decimal の `value`、`comparator`（0..1）、`unit`、`system`、`code` を持つ。decimal は**18桁以内の小数表現を持つ有理数**で、精度に意味がある | ①開いた端（半開区間など）は Range で表せない（`interval_bounds` の損失の実例）。②小数で書けない有理数（1/3 など）は decimal で正確に表せない。ライブラリの値は正確な有理数で、精度の概念を持たない。③ comparator は片側の限界で、区間とは別の概念。comparator の値集合は未取得で**未確認** |
| G2 | 値が無い記録 | `dataAbsentReason` | `value[x]` が無いときだけ存在してよい（obs-6）。値集合は15の符号（unknown、not-asked、asked-unknown、not-performed、masked など）。**理由の種類が細かい** | ライブラリの `record` は値を必須とするため、「値が無い理由つきの記録」を操作で作れない。FHIR 側にあってライブラリ側にない状態 |
| G3 ※ | 文脈 method の三状態（known／unknown／unspecified） | `method`（0..1） | `method` は存在か不在か。`dataAbsentReason` は `value[x]` にだけ付く（obs-6）。拡張は要素に付けられるが、primitive が値の代わりに拡張を持てる、という記述である。data-absent-reason の拡張の対象となる要素の定義は**未取得** | `unknown` と `unspecified` の区別を、取得したページの要素では運べない。`value[x]` の理由には「知らない」「聞かなかった」の区別があるのに、`method` にはない非対称が確認できた |
| G4 | 文脈 specimen の三状態 | `specimen`（0..1 Reference(Specimen|Group)） | 同上。R5 で Group が対象に加わった（Observation のページの「Changes from R4」） | 同上。ライブラリの `specimen` は「ref と版」で、Specimen の `type`（材料の種類）か参照かは、ライブラリ側で定義が曖昧（要整理） |
| G5 | 要求「method が known」「specimen が known」 | `method`・`specimen` が**任意**（0..1） | FHIR 本体はどちらも要求しない。具体的な使い方は「プロファイルと実装ガイドで定める」と書いてある | 設計63の「要求は出力先の宣言で、記録には属さない」と整合する。根拠は、この一文と濃度が任意であること |
| G6 ※ | 時点の区間 `validity`（半開区間 [start, end)） | `effective[x]`（Period） | Period の start は**含み**、end も**含む**（「end の値に一致する日時を含む」）。end が無いと継続中、start が無いと start は不明 | ライブラリの半開区間と、FHIR の両端を含む区間は**境界の扱いが違う**。変換には日時の粒度の規則が要る（例：end の日付全体が含まれる）。意味（主張の有効期間と観察の時点）も同じとは言えない |
| G7 | `recorded_at`（記録の時刻） | `issued`（Observation）／`recorded`（Provenance） | 近い名前の要素がある | 同じ意味とは確認できない（版の公開時刻と、活動を記録した時刻）。対応づけは判断が要る |
| G8 ※ | 確度 `confirmed`／`suspected`、人の確認 | `status`（1..1）と Provenance | status の値は、registered、preliminary、final、amended、corrected、cancelled、entered-in-error、unknown。`final` の説明は、released・signed などの追加の状態は**Provenance で表す**と述べる。Provenance は、対象（`target`、通常は版つき）・活動・**agent（誰が・どの役割で）**・entity・signature を持つ | `suspected` は preliminary に近いが、同じとは確認できない。「誰が、どの内容を確認したか」は Provenance の agent と target（版つき）で運ぶ構造がある。内容 hash による拘束はない（版つきの参照まで） |
| G9 ※ | 出自 `ai_candidate`／`observed` | Provenance の `agent.who`（Device などを指せる）、`agent.type`・`role` | agent に Device を指せる。type・role は符号の束縛が Example | 出自の種類を運ぶ専用の要素はない。agent の種類（人／Device）で**表すことはできる**が、「AI の候補」という意味は束縛に依存する（Example）。Observation 自身には出自の要素がない |
| G10 | 性質 `property_ref` | `code`（1..1） | `code` は必須。型は CodeableConcept | 対応づけは**仮定**。`code` の使い方の組み合わせが複数あるとページが書く |
| G11 | `method`（観察の方法） | Observation.`method` と Specimen.`collection.method`（採取の技術）が別 | 両方がページにある | ライブラリの `method` は観察の方法。採取の方法は区別されない |
| G12 | 検体の状態 | Specimen.`status`（available／unavailable／unsatisfactory／entered-in-error）、`condition` | ページにある | 要求「specimen が known」は、検体が不適でも満たされる。「検体の状態」を要求する要素の種類がライブラリにない |
| G13 | （ライブラリになし） | `status`（1..1）、`code`（1..1） | 必須の要素 | 構造として必須の要素に当たる要求の要素の種類が、ライブラリの語彙（`value`・`context`・`trend`）にない。そのまま書くと `unsupported_requirement_element` になる |
| G14 ※ | 訂正（`corrects`／`revises`、非復活、元の記録を消さない） | Provenance の `entity.role = revision`、`status = amended／corrected` | Provenance の entity の role に revision がある。corrected は「final の後に誤りを訂正」、amended は「更新や訂正を含む」 | 訂正の関係を運ぶ構造はある。ライブラリの「訂正の期間は元の期間に含まれる」「元の記録は消えない」に当たる制約はページにない |

確認できた対応は、要素の存在・型・濃度・短い記述の読み取りまでです。**意味が同じであることは、どの行も確認していません**（G6・G7・G8・G9・G10・G14 は、判断や仮定に依る）。

## 5. わかったこと

1. **要求を出力先の宣言にする設計は、ページの記述と矛盾しない。** FHIR 本体は method・specimen を任意とし、使い方をプロファイルに任せている。ただしこれは設計の正しさの証明ではなく、一つの資料との整合に過ぎない。
2. **ライブラリの三状態（known／unknown／unspecified）は、`method`・`specimen` の存在・不在の二状態より細かい。** 一方、FHIR は `value[x]` の欠落には15種類の理由（「知らない」「聞かなかった」「実施しなかった」など）を持つ。**欠落の区別の細かさが要素ごとに非対称**で、ライブラリは文脈にだけ三状態を持ち、値の欠落を持たない。
3. **ライブラリにあって構造にない状態と、構造にあってライブラリにない状態の両方がある。** 値のない記録（G2）、検体の状態（G12）、必須の `status`・`code`（G13）はライブラリの語彙で表せない。逆に、開いた端の区間・小数で書けない有理数（G1）、半開区間（G6）、三状態（G3・G4）は FHIR の要素にそのまま載らない。
4. **確認と出自は、Observation でなく Provenance が担う構造になっている**（G8・G9・G14）。したがって、FHIR へ出すときは Observation 一つでなく、Observation と Provenance の組を考える必要がある。出力先の宣言が複数のリソースを要求する形を、ライブラリの語彙は想定していない。
5. **R5 の変更を、要求の版の更新として読める。** `specimen` の対象に Group が加わったことは、「specimen が known」の意味が版で広がる例になる（R4 のページは今回取得していない。変更は R5 のページの「Changes from R4」の記述で確認した）。

## 6. 次に判断すること

| 候補 | 内容 | 推奨 |
| --- | --- | --- |
| A | ここで止める（監査の記録だけ）。次は CPC の版の監査（U3）へ | － |
| B | **P2-p**：FHIR の構造に接地した出力先の宣言を実装・評価する。設計は [67](67-p2-p-design.md) | 設計を作成した。実装の前に利用者の確認を取る |

## 7. 限界

- ページを読んだのは作成者一人です。HTML の本文から要素の表と注釈を取り出して読んだもので、ページ内の全ての注釈や例を読んだわけではありません。
- 対応の意味は、どの行も検証していません。「確認できた」は、名前・濃度・型・短い記述がページにあることだけです。
- 第三者の用語（LOINC、SNOMED CT など）の内容と利用条件は扱っていません。FHIR の型・制約への適合を主張せず、実データ・患者情報も含みません。
