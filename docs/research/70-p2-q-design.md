# P2-q：Observation の status・code の写像と Provenance への出力の意味設計

作成日：2026-10-21。状態：**作成者側の設計草案。runtime・native 仕様・宣言・実行用 fixture は未実装**。[P2-p の結果69](69-p2-p-results.md) の範囲外だった `status`・`code`（Observation の必須の要素）と、確認・出自を運ぶ Provenance を、P2-p の上に足す設計です。利用者の指示（2026-10-21「status・code の写像と Provenance への出力を進めて」）に従います。FHIR への適合は主張しません。独立確認は未実施で、`independent_review` / `evaluation_frozen` は false のままです。構造の事実は、取得した FHIR R5 v5.0.0 のページ（台帳 [03-materials.json](03-materials.json)、Git 管理外）の読み取りに限ります。数値・識別子・写像の表はすべて架空です。

## 1. 問い

| ID | 問い |
| --- | --- |
| Q1 | ライブラリが持たない判断（確定した記録が FHIR のどの `status` に当たるか、`property_ref` がどの `code` に当たるか）を、**ライブラリが決めずに**、宣言を受けて使い、使ったことを仮定として残せるか |
| Q2 | 宣言が足りないとき（訂正の `status`、`code` の写像）、推測で補わず、**宣言する人への依頼**として返せるか。依頼の宛先は医療者でなく出力先の宣言の作り手 |
| Q3 | 人の確認と AI 由来の出自を、Provenance（誰が・いつ・何に対して）として運べるか。運べない区別は引き続き失うものに残るか |
| Q4 | P2-p を変更せず、合成として足せるか。必要な義務は既存の主題で足りるか（主題の外の義務は何件出るか） |

## 2. 設計判断

| 判断 | 初回に採る設計 | 理由・見直す条件 |
| --- | --- | --- |
| QD1 | **合成の専用 R5 を新設する**。P2-p の `run_grounding` を固定版で一度だけ呼び、その行（`grounding.state`＝`representable`）に、status・code・Provenance を足す。P2-p・P2-o・P2-i・P2-f は変更しない | P2-p の設計67は status・code・Provenance を範囲外とした。draft を上げず、既存の変更は登録の入口だけ |
| QD2 | **`status` の写像は呼び出し側の宣言**：`status.original`（選ばれた記録が訂正でないとき）と `status.correction`（訂正のとき、省略可）。値は取得したページの定義から導いた許容集合に限る：`original` は `final` だけ、`correction` は `amended`・`corrected` のどちらか | ページの定義は「final＝完了で追加の行為が要らない」「amended＝final の後の変更（更新・訂正を含む）」「corrected＝final の後の誤りの訂正」。ライブラリの `correct` の理由は自由文で、更新か誤りの訂正かを区別できない。選ぶのは宣言する人 |
| QD3 | `status` の写像を使った行は、`added` に `assumption:status_mapping:<original|correction>:<値>` を残す。ライブラリは「人が確認した記録」を「完了で追加の行為が要らない」と読む判断をしない。宣言が読んだと記録する | 原情報を消さず、不明な属性を補って確定しない（AGENTS.md） |
| QD4 | **`code` の写像は呼び出し側の表**：`code_map` の各項目 `{property_ref, system, code}`。ライブラリは文字列を検査せず（非空のみ）、符号の系の内容（LOINC など第三者の用語）を知らず、取り込まない。使った行は `added` に `assumption:code_mapping_declared` | 第三者用語の内容を扱わない（D03） |
| QD5 | 選ばれた記録の `property_ref` が `code_map` にない、または訂正が選ばれて `status.correction` がないとき、その行は **`needs_information`**（理由 `required_information_missing`）で、依頼を返す。依頼は `{element, action, record_ref, property_ref}`：`code`／`declare_code_mapping`、`status`／`declare_correction_status`。出力と流れは null | P2-o の「足りない情報は推測で埋めず依頼する」と同じ規則を、宣言に当てる |
| QD6 | **Provenance は `provenance.reviewer_type` を宣言したときだけ出す**。許容は、ページの `agent.who` の型の一覧（Practitioner、PractitionerRole、Organization、CareTeam、Patient、Device、RelatedPerson）のうち人に当たる `Practitioner`・`PractitionerRole`・`Patient`・`RelatedPerson` | ライブラリの確認者は人（reviewer_kind が human）。人の型の選択は宣言する人 |
| QD7 | 出す Provenance は2種：①**確認**（選択に見える確認ごと。`recorded`＝確認の時刻、agent＝確認者〔宣言した型・ライブラリの参照〕）、②**生成**（記録の出自が `ai_candidate` のときだけ。`recorded`＝記録の時刻、agent＝Device〔出自の参照〕）。どちらも `target`＝Observation（記録の id とハッシュ） | Provenance の agent は 1..* で必須なので、誰か分からない生成は出せない（観察者が不明な記録の生成の Provenance は出さない） |
| QD8 | 訂正の関係（Provenance の entity の revision）は出さない。`revision_history` は失うものに残す | ページに制約の記述が少なく、どの活動に付けるか判断が要る。次の段階 |
| QD9 | 流れは P2-p の表せる行の流れから規則で作り直す（§6）。認定は常に `not_certified`、推測で補った情報は常に空、FHIR への適合は主張しない | P2-p と同じ |

## 3. 入口と型（予約名）

| 項目 | 予約する型・範囲 |
| --- | --- |
| profile / operation | `p2-observation-projection-draft-1` / `run_observation_projection` |
| request / result | `p2-observation-request-draft-1` / `p2-observation-result-draft-1` |
| 回答型 | `observation_projection` |
| 要求 | `schema_version, operation, consumer, grounding_request, observations, budget` |
| consumer | 自己の `profile, profile_spec_sha256, operations`、P2-p の `grounding_profile, grounding_profile_spec_sha256` |
| grounding_request | P2-p の要求そのもの。`budget.max_steps` は 0（子の予算はこの拡張が決める）。P2-p・P2-o の検査をそのまま受ける |
| observations | `{destination_ref, status{original, correction?}, code_map[{property_ref, system, code}], provenance?{reviewer_type}}` の配列（最大16）。`destination_ref` は P2-p の対象に宣言された出力先 |

結果は問い合わせ id 順の `results[]`。各行は P2-p の行の全欄に加えて `observation`：`{state, status, code, provenance}`。`state`：`projected`／`needs_information`／`not_evaluated`／`not_declared`。`status`＝`{state: original|correction, code}`、`code`＝`{system, code}`、`provenance`＝配列（各項目 `{activity: confirmation|creation, target{type: Observation, record_ref, record_sha256}, recorded, agents[{who{type, identifier}}]}`）。`projected` 以外の行の `status`・`code`・`provenance` は null。

## 4. 構造の事実の表（native 仕様に入れる）

出典は台帳の項目（SHA-256 は台帳が持つ）。各行は出典の id・ページ上の目印の語・事実の短い言い換え。

| 事実 | 出典 | 目印 |
| --- | --- | --- |
| F-S1 `final`：観察は完了で追加の行為が要らない。released・signed などは Provenance で表す | `fhir-codesystem-observation-status-5.0.0` | `The observation is complete and there are no further actions needed` |
| F-S2 `amended`：final の後に変更された（更新・訂正を含む） | 同 | `Subsequent to being Final, the observation has been modified subsequent` |
| F-S3 `corrected`：final の後に誤りを訂正するために変更された | 同 | `to correct an error in the test result` |
| F-S4 Observation の `status` は 1..1 | `fhir-observation-5.0.0` | `registered | preliminary | final | amended` |
| F-S5 Observation の `code` は 1..1（CodeableConcept） | 同 | `Type of observation (code / type)` |
| F-S6 CodeableConcept は文章と符号の列のどちらかまたは両方 | `fhir-datatypes-5.0.0` | `a text description and/or a list of Codings` |
| F-P1 Provenance の `agent` は 1..*、`who` は 1..1 で型の一覧を持つ | `fhir-provenance-5.0.0` | `The agent that participated in the event` |
| F-P2 Provenance の `target` は 1..*（通常は版つきの参照） | 同 | `usually version specific` |
| F-P3 Provenance の `recorded` は 0..1 の instant（活動の記録時刻） | 同 | `When the activity was recorded / updated` |

**判断の分かれる点**：（1）人の確認を `final` と対応づけるのは、ライブラリでなく宣言の判断（QD2・QD3）。（2）許容する `status` を `original`→`final` だけにしたのは、ページの定義の保守的な読み（`registered`＝結果がまだない、`preliminary`＝未検証の可能性、`cancelled`＝測定が行われなかった、は、確認済みの値を持つ記録に矛盾すると読んだ）。この読みは作成者のもので、別の読みもあり得る。

## 5. 判定

P2-p の行が `representable` で、その出力先に `observations` の宣言があるときだけ判定する。選ばれた記録（`selection.record_ref`）を台帳（P2-p の結果の `ledger`）から引き、`revises` が空でなければ訂正。

1. **status**：訂正でなければ `original`、訂正なら `correction`（宣言がなければ依頼）。
2. **code**：出力の `context.property_ref` を `code_map` で引く（なければ依頼）。
3. **provenance**：宣言があれば、選択の `review_refs` の各確認について確認の Provenance（時刻順、同時刻は id 順）。記録の出自が `ai_candidate` なら、先頭に生成の Provenance。
4. 依頼があれば行は `needs_information`（依頼は `(element, record_ref)` で整列、`code` が先）。なければ `projected`。

`state` の優先：宣言なし→`not_declared`、P2-p の行が `representable` でない→`not_evaluated`、依頼あり→`needs_information`、それ以外→`projected`。`not_declared`・`not_evaluated` の行は P2-p の行をそのまま通す。

## 6. 流れ（表せる行）

P2-p の `representable` の行の流れ（保持 R、失う L、足す A）から：

- R′＝R ∪ {`context:property`}、さらに Provenance を出すとき {`human_confirmed`, `record:identity`}、生成の Provenance を出すとき {`origin_kind`}
- L′＝L から上の追加を除く（`quantity_kind`・`review:identity`・`revision_history` は残る）
- A′＝A ∪ {`assumption:code_mapping_declared`, `assumption:status_mapping:<original|correction>:<値>`}、Provenance を出すとき {`assumption:reviewer_type_declared`}

各配列は整列する。

## 7. 資源

M＝2＋M_g＋3N（M_g は P2-p の全体の料金、N は問い合わせ数）。子（P2-p）の予算は M_g を先払いして使い切ったことを照合する。自前の料金は問い合わせごとに3（status・code・provenance）。子が資源停止なら、未完了行は値の欄（P2-p の7欄と `observation`）を null にする。入力不正は予算に依らない。

## 8. 七欄と義務の主題

| 欄 | 内容 |
| --- | --- |
| 前提 | status・code の対応は宣言（作り手の判断）。ページの定義は読み取り。FHIR の適合・医学的意味は扱わない |
| 版 | 自己と P2-p の profile・仕様 hash を consumer が固定。構造の事実の表は出典の SHA-256 を持つ |
| 確認対象 | 確認は作らない。選択に見える人の確認を Provenance に運ぶ |
| 情報の選択 | P2-p の選択をそのまま使う |
| 問い | 「この行を Observation と Provenance として出すために、宣言は足りているか」 |
| 保持・喪失・追加 | §6 |
| 資源・停止 | §7。停止の順序：P2-p の停止→静的検査→code→status→provenance |

義務（18：共通4＋R5の3＋QR-1〜11）と主題：QR-1（A）自己・P2-p の版と実体、出典のハッシュ。QR-2（B）確認を作らず、見える確認を Provenance に運ぶ。QR-3（C）P2-p の選択を再選択しない。QR-4（E）停止の順序と状態の優先。QR-5（F）料金・原子性。QR-6（H）推測で補わない：宣言のない写像は依頼になり、使った宣言は仮定として残る。QR-7（I）status の許容集合と選択の規則。QR-8（I）code の写像と依頼。QR-9（I）Provenance の項目の規則。QR-10（I）流れの規則。QR-11（I）構造の事実が出典に結ばれる。予測（H2）：QR-1〜6 が A〜H、QR-7〜10 が意味固有、**QR-11（外部の資料に結んだ事実）は既存の主題に収まらない**（P2-p の GR-9 と同じ）。継承は宣言しない見込み。

## 9. 実装前に固定する予測と反例

### 9.1 予測

| ID | 予測 | 外れた場合に分かること |
| --- | --- | --- |
| X1 | 既存の実装・仕様・宣言・旧実行例を一つも変えずに実装できる | 合成の方針 |
| X2 | 宣言が足りない行は、全て `needs_information` で、推測で補った `status`・`code` を持たない。宣言が足りれば `projected` | QD5 |
| X3 | 使った写像は全て `added` に仮定として残る。Provenance を出さないとき、`human_confirmed`・`origin_kind` は失うものに残る | QD3・QD4・§6 |
| X4 | 訂正が選ばれた行だけが `correction` を使う。選ばれなかった訂正（過去の対象時点）は影響しない | 選択の透明性 |
| X5 | 確認ごとに Provenance が一つ。複数の確認は時刻順。AI 由来の記録だけが生成の Provenance を持つ | QD7 |
| X6 | 料金 M＝2＋M_g＋3N が全要求で成り立つ。P2-p の実費は M_g | 資源 |
| X7 | 許容外の写像（`original`→`amended`、`correction`→`final`、`Device` の確認者など）は静的に拒否される | QD2・QD6 |
| X8 | 義務は R5 と必須欄で足りる。**QR-11 は既存の主題に収まらない** | H2（四つ目の主題の外の義務） |
| X9 | `affected()`：P2-p の変更（とその依存元）が、この拡張を列挙する | 依存の効果 |
| X10 | 宣言の写像の内容（`system`・`code` の文字列）はライブラリの判定に影響せず、そのまま出力に載る | QD4 |

### 9.2 反例（71 に具体値を固定）

| ID | 内容 | 試すこと |
| --- | --- | --- |
| Z1 | 訂正が選ばれ、`status.correction` の宣言がない | 推測で `amended` を入れず、依頼 |
| Z2 | `code_map` に選ばれた記録の性質がない | 推測で補わず、依頼 |
| Z3 | `status.original` に `amended` | 静的に拒否 |
| Z4 | 確認者の型に `Device` | 静的に拒否 |
| Z5 | 同じ記録に2件の確認 | Provenance が2件、時刻順 |
| Z6 | AI 由来の記録 | 生成の Provenance（Device）が先頭。人の確認も別に出る |
| Z7 | P2-p が表せない行（2/3） | 判定しない（`not_evaluated`）。宣言が足りなくても依頼は出ない |
| Z8 | 宣言のない出力先 | `not_declared`（P2-p の行のまま） |
| Z9 | 観察者が不明な記録（出自 observed） | 生成の Provenance は出さない（出せない）。出自の種類は失う |

## 10. 受入条件

1. 期待・予測・反例を、runtime より先に別の文書（71）で固定し、実行結果から期待を更新しない。
2. 専用 native・module・R5 宣言・fixture・独立な別計算を追加する。P2-p・P2-o・P2-i・P2-f・旧核は変更しない（X1）。
3. 別計算は、P2-p の別計算（行の基）を再利用し、status・code・Provenance・流れ・料金は自前で持つ。
4. 宣言の全数（status の許容集合×訂正の有無×code_map の有無×reviewer_type）、確認の数、出自、乱数、P2-p 単独の実行との差分、料金、予算の掃引、入力の不変性、型破損、変異（推測で補う、仮定の欠落、確認の欠落・重複、生成の誤出力、訂正の取り違え、依頼の欠落、先払いの省略）を検査する。
5. Python 3.11／3.14 で、全テスト系列、版比較つき統合評価、旧い22,052件の挙動 digest を回帰する。分母の変更は旧い値を履歴として残す。
6. 追加前は `1c4ac98`、固定対象1,617ファイル、manifest `28e6495c9f2ad5b43722e6d2c9d8f9994dfe19c291ff697d1b8a5838e4143a39`、束 `47191fe4f5f0b5e5a1a15d633c9cf53baa576866a21e7bdc47bbec742aeb286c`。件数・hash・予測の結果・残る穴を結果の文書に残す。`independent_review` / `evaluation_frozen` は false。

## 11. 範囲外

Provenance の `entity`（revision）、`activity` の符号、Provenance の `agent.type`・`role`、`onBehalfOf`、署名、`status` の `registered`・`preliminary`・`cancelled`・`entered-in-error`・`unknown`、Observation の `category`・`subject`・`performer`・`effective[x]` 以外の要素、`code` の符号の系の検証、FHIR の資源（JSON）としての生成と適合の検査、他の構造。

今回の設計で新たに参照した外部資料はなく、P2-p の準備で取得した HL7 FHIR R5 v5.0.0 のページ（台帳に記録）を、構造・定義の読み取りに限って使いました。第三者の用語の内容は取り込んでいません。この設計は、Observation と Provenance への写像の宣言と使用の診断の一つの断片で、FHIR への適合の主張でも、実際の医療者の負担が減ることの証明でもありません。

## 12. 利用者に確認すること

| ID | 確認 | 推奨 |
| --- | --- | --- |
| U1 | status・code の写像をライブラリが決めず、宣言する人に委ねる（足りなければ依頼）方針 | 委ねる |
| U2 | `status` の許容集合を、`original`→`final` だけ、`correction`→`amended`／`corrected` だけに限る（ページの定義の保守的な読み） | 限る（読みは作成者のものと明記） |
| U3 | Provenance は、確認ごと（確認者の型を宣言）と、AI 由来の生成（Device）だけにして、revision の entity は出さない | 出さない（次の段階） |

利用者の指示は「進めて」だったため、推奨どおりに実装へ進みます。異なる判断があれば、実装後の結果に反映します。
