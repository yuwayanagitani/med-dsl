# P2-t：Provenance の activity の符号と revision の entity の意味設計

作成日：2026-10-21。状態：**作成者側の設計草案。runtime・native 仕様・宣言・実行用 fixture は未実装**。[P2-q の結果72](72-p2-q-results.md) と [設計70](70-p2-q-design.md) の範囲外だった Provenance の `activity` の符号と `entity`（revision）を、P2-q の上に足す設計です。利用者の指示（2026-10-21「revision の entity と activity の符号着手して」）に従います。FHIR への適合は主張しません。独立確認は未実施で、`independent_review` / `evaluation_frozen` は false のままです。構造の事実は、取得した FHIR R5 v5.0.0 のページ（台帳 [03-materials.json](03-materials.json)、Git 管理外）の読み取りに限ります。数値・識別子・符号の表はすべて架空です。

## 1. 問い

| ID | 問い |
| --- | --- |
| Q1 | 訂正の関係（選ばれた訂正記録が、どの記録の新しい版か）を、**向きと同一性を保って** Provenance の `entity` として運べるか。運べない行は、理由を区別して示せるか |
| Q2 | 活動の符号（`activity`）を、ライブラリが決めず**呼び出し側の宣言**として使い、宣言のない活動を別の符号で代用せず（推測せず）、運べなかったことを失うものに残せるか |
| Q3 | 訂正の関係を運べるかは、**誰が訂正したか**（Provenance の agent は 1..*）に依存する。観察者を「不明」と明示した訂正（P2-s）は、確認済みでも関係を運べないが、これを黙って落とさず区別して示せるか |
| Q4 | P2-q 以下を一つも変えず、合成として足せるか。取得した定義が版で変わる箇所（R4→R5 の `entity.role` の符号）に対して、符号の集合を宣言に預けずに済むか |

## 2. 取得した資料の読み取り（D03）

使う資料は、P2-p・P2-q で取得した FHIR R5 v5.0.0 の Provenance のページに、**新たに1ページ**を足したものです：`codesystem-provenance-entity-role.html`（HL7 自身が定義する小さな符号系。5つの符号の名前と定義）。台帳 [03-materials.json](03-materials.json) に `fhir-codesystem-provenance-entity-role-5.0.0`（21,969バイト、SHA-256 `1c038151…`、取得 2026-10-21 18:26 UTC）を記録し、Git 管理外の `data/research/r3/` に保存しました。D03 の選定（FHIR Provenance は R5 v5.0.0 を「生成・導出の由来」で参照）の範囲内で、HL7 作成部分（CC0）の定義の名前と意味を読み取りに使うだけです。第三者の用語（`activity` の例が名前を挙げる v3 の符号系や ISO のライフサイクルなど）の内容は取得せず、取り込んでいません。ページの本文も、そこから作った表も入れていません（以下は名前・濃度・型・短い言い換えのみ）。

| 事実 | 出典 | 目印 |
| --- | --- | --- |
| F-A1 `Provenance.activity` は 0..1 の CodeableConcept | `fhir-provenance-5.0.0` | `Activity that occurred` |
| F-A2 `activity` の束縛は Example（例示）。ページは符号系の候補を挙げるだけで、符号の集合を限らない | 同 | `Some potential code systems are` |
| F-E1 `Provenance.entity` は 0..*。活動に使われた実体 | 同 | `An entity used in this activity` |
| F-E2 `entity.role` は 1..1 の code で、`revision | quotation | source | instantiates | removal`。束縛は Required | 同 | `revision | quotation | source | instantiates | removal` |
| F-E3 `entity.what` は 1..1 の Reference(Any)（実体の同一性） | 同 | `Identity of entity` |
| F-E4 `revision`＝活動が**その実体の新しい版を作るために使った**実体（実体は古い版の側） | `fhir-codesystem-provenance-entity-role-5.0.0` | `An entity that is used by the activity to produce a new version of that entity` |
| F-E5 `target`＝活動が生成・更新した参照（新しい版の側） | `fhir-provenance-5.0.0` | `generated or updated by the activity` |
| F-V1 R4→R5 で、`entity.role` は符号 `derivation` が消え `instantiates` が加わった | 同 | `Remove code derivation Add code instantiates` |

**判断の分かれる点**：（1）訂正記録を FHIR の `revision` と読むのは、定義（新しい版を作るために使った実体）に照らした作成者の読みで、別の読み（`source`＝活動の入力）もあり得る。（2）ページは、`entity` を「事業上の要請がない限り使わない」とも述べる（削除の記録の文脈）。この拡張では、ライブラリが訂正の関係を保持する要請（訂正・追加情報を保つ設計）を事業上の要請と置く。（3）F-V1 のとおり符号の集合は版で変わるので、`role` の値は宣言に預けず、拡張が F-E2 の集合のうち `revision` に固定する（版が変わればこの事実の表が変わり、静的に検出される）。

## 3. 設計判断

| 判断 | 初回に採る設計 | 理由・見直す条件 |
| --- | --- | --- |
| TD1 | **合成の専用 R5 を新設する**。P2-q の `run_observation` を固定版で一度だけ呼び、その行に `coding` を足す。P2-q 以下は変更しない。P2-q の行の欄は一つも書き換えず、そのまま通す | P2-q の設計は revision と activity の符号を「次の段階」とした。P2-q を draft-4 に上げる選択もあるが、下位の層を変えない合成の性質を測るため |
| TD2 | 宣言は `coding`：`{destination_ref, activities?, revision?}` の配列。`destination_ref` は P2-q の `observations` に宣言された出力先。`activities`＝`{creation?, correction?, confirmation?}`、各項目は `{system, code}`（非空の文字列）。`revision`＝真偽値（省略は偽） | 活動の符号は宣言する人の判断。キーの集合は P2-t 自身の語彙（閉じている） |
| TD3 | **活動の符号は不透明**：ライブラリは `system`・`code` の内容を検査せず、そのまま出力に載せる（F-A2：束縛は Example で、ページが符号を限らない。第三者の符号系の内容は取り込まない） | 判定は文字列に依らない（X10 と同型）。符号の系の妥当性は範囲外 |
| TD4 | Provenance の項目の**種類**：確認の項目は `confirmation`。生成側の項目（記録の出自が AI か、観察者が分かるときだけ P2-q が出す）は、選ばれた記録が訂正なら `correction`、そうでなければ `creation`。項目の符号は、その種類の宣言だけで決める。**宣言がなければ符号は null**（別の種類の符号で代用しない） | 活動は 0..1（F-A1）なので、宣言のない活動は「符号なし」が正しい出力。依頼は出さない（足りない必須情報ではない） |
| TD5 | 符号を付けられなかった種類は、失うもの `activity:<種類>` に残す。宣言した符号が一つも使われなかったときは、仮定 `assumption:activity_coding_declared` を足さない（使っていない宣言は痕跡を残さない） | 失うものの報告を、実際に起きたことに結ぶ |
| TD6 | **revision の entity**：宣言 `revision` が真で、選ばれた記録が訂正（`revises` が空でない）で、その生成側の項目がある（agent が分かる）とき、その項目に `entities` を付ける。`role`＝`revision`（F-E2 の集合から固定）、`what`＝`{type: Observation, record_ref, record_sha256}`。**訂正された記録（直接の前の版）ごとに一つ**、`record_ref` の昇順。向きは F-E4・F-E5：`target`（新しい版）＝選ばれた訂正記録、`entity.what`＝訂正された側 | 向き・同一性・多重度を固定する。FHIR の資源の id は作らない（`what` はライブラリの同一性〔記録の参照とハッシュ〕で、P2-q の `target` と同じ形） |
| TD7 | `what` の `record_sha256` は、訂正された記録の内容に結ぶハッシュ。**P2-i の記録のハッシュ関数**（`_record_hash`）で計算し（P2-o が確認のハッシュに使うのと同じ関数）、選ばれた記録のハッシュを同じ関数で再計算して P2-q の `selection.record_sha256` と一致することを照合する。食い違えば内部の矛盾として停止（`record_hash_mismatch`） | 下位の結果に前の版のハッシュが出ていないため。下位を変えずに、結ばれた値を自己検証する |
| TD8 | `revision.state`（優先順）：`not_applicable`（選ばれた記録が訂正でない）→`not_requested`（宣言が偽）→`no_provenance`（P2-q の宣言に確認者の型がなく Provenance が出ていない）→`no_agent`（Provenance は出るが、この訂正に生成側の項目がない＝出自が AI でなく、観察者が不明）→`carried`。`predecessors`＝訂正記録の `revises` の昇順（訂正のとき、運べたかに依らず）。訂正でなければ空 | 運べない理由を区別する。訂正された記録の参照を示すのは、台帳の事実の報告で、運べたことの主張ではない |
| TD9 | 行の `coding.state`：P2-q の行が `projected` でない→`not_evaluated`、`coding` の宣言がない→`not_declared`、それ以外→`coded`。`not_evaluated`・`not_declared` の行の `entries`・`revision` は null。P2-q の `observation` は常にそのまま通す | P2-q の状態の優先と同型 |
| TD10 | 流れ（§5）。認定は常に `not_certified`、推測で補った情報は常に空、FHIR への適合は主張しない | P2-q と同じ |
| TD11 | 要求の `observation_request`（P2-q の要求）の `budget.max_steps` は 0 で、子の予算はこの拡張が決める | P2-q の `grounding_request` と同型 |

## 4. 入口と型（予約名）

| 項目 | 予約する型・範囲 |
| --- | --- |
| profile / operation | `p2-provenance-coding-draft-1` / `run_provenance_coding` |
| request / result | `p2-provenance-request-draft-1` / `p2-provenance-result-draft-1` |
| 回答型 | `provenance_coding` |
| 要求 | `schema_version, operation, consumer, observation_request, coding, budget` |
| consumer | 自己の `profile, profile_spec_sha256, operations`、P2-q の `observation_profile, observation_profile_spec_sha256` |
| coding | 最大16。§3 の TD2 |

結果は P2-q の結果の全欄（`results[]` の各行は P2-q の行の全欄）に加えて、各行の `coding` と、トップレベルの `observation_run`（`{input_sha256, reserved_steps, steps_used}`）。`coding`＝`{state, entries, revision}`。`entries[]`＝`{index, kind, activity, entities}`（`index` は P2-q の `observation.provenance[]` の添字、`activity`＝`{system, code}` か null、`entities[]`＝`{role, what}`）。`revision`＝`{state, predecessors}`。未完了の行は `coding` も null。

## 5. 流れ（`coding.state` が `coded` の行だけ）

P2-q の行の流れ（保持 R、失う L、足す A）に対して：

- 符号を付けた項目が一つ以上あれば A に `assumption:activity_coding_declared`。
- 符号を付けられなかった項目の種類ごとに L に `activity:<種類>`。
- 選ばれた記録が訂正のとき：`revision.state` が `carried` なら R に `revision:predecessor_identity` と A に `assumption:revision_role_declared`。そうでなければ L に `revision:predecessor_identity`。
- `revision_history`（P2-q が失うものに持つ）は変えない（連鎖の全体と訂正の理由は運ばない）。

`coded` でない行は、P2-q の流れをそのまま通す。各配列は整列する。

## 6. 資源

M＝2＋M_q＋2N（M_q は P2-q の全体の料金、N は問い合わせ数）。子の予算は M_q を先払いして使い切ったことを照合する。自前の料金は問い合わせごとに2（activity・entity）。子が資源停止なら、未完了行は値の欄（P2-q の欄と `coding`）を null にする。入力不正は予算に依らない。

## 7. 七欄と義務の主題

| 欄 | 内容 |
| --- | --- |
| 前提 | 活動の符号は宣言（作り手の判断）、revision の読みは作成者の読み。ページの定義は読み取り。FHIR の適合・医学的意味は扱わない |
| 版 | 自己と P2-q の profile・仕様 hash を consumer が固定。構造の事実の表は出典の SHA-256 を持つ |
| 確認対象 | 確認も agent も作らない。P2-q が出した項目に符号と実体を足す |
| 情報の選択 | P2-q の選択をそのまま使う |
| 問い | 「P2-q の Provenance の項目に、宣言した活動の符号と、訂正の関係を付けられるか。付けられない理由は何か」 |
| 保持・喪失・追加 | §5 |
| 資源・停止 | §6。停止の順序：P2-q の停止→静的検査→activity→entity |

義務（17：共通4＋R5の3＋PT-1〜10）：PT-1（A）自己・P2-q の版と実体。PT-2（C）P2-q の行をそのまま通す。PT-3（I）活動の符号の規則と閉じた語彙。PT-4（I）revision の entity（向き・同一性・多重度・付ける場所）。PT-5（I）revision の状態と優先。PT-6（I）流れ。PT-7（F）料金・原子性。PT-8（E）停止の順序と状態の優先。PT-9（H）推測で補わない（agent・確認・符号を作らない）。PT-10（主題の外）構造の事実が出典に結ばれる。

## 8. 実装前に固定する予測と反例

### 8.1 予測

| ID | 予測 | 外れた場合に分かること |
| --- | --- | --- |
| T1 | P2-q 以下の実装・仕様・宣言・旧実行例を一つも変えずに実装できる。変更は登録の入口（host.py の import と登録の各1行）と、手で持つ一覧（P2-q の追加と同じ11か所）、台帳と検証器の1行だけ | TD1 |
| T2 | P2-t の結果の各行から `coding` を除くと、同じ P2-q の要求への P2-q 単独の結果の行と一致する（全 fixture と乱数） | TD1・PT-2 |
| T3 | 活動の符号は宣言した種類の符号だけが使われる。宣言のない種類は null で代用なし、失うものに `activity:<種類>`。使われなかった宣言は流れに痕跡を残さない | TD3〜TD5 |
| T4 | revision の entity は、`revision.state` が `carried` の行だけに付く。訂正された記録ごとに一つ、昇順。`what.record_sha256` は訂正された記録の独立に計算したハッシュと一致する。連鎖（A→B→C）で C が選ばれても、付くのは直接の前の版 B だけ | TD6・TD7 |
| T5 | **確認済みの訂正でも、観察者が不明（かつ出自が AI でない）なら `no_agent`**：訂正の関係は運べず、失うものに残る。観察者を足すと運べる | Q3 |
| T6 | 出自が AI の訂正は、観察者が不明でも `carried`（agent は Device）。観察者が人でも、型の宣言がなければ P2-q の依頼で停止し、`coding` は `not_evaluated` | TD8・TD9 |
| T7 | 料金 M＝2＋M_q＋2N が全要求で成り立つ。1問い合わせの標準で M＝46（M_q＝42）、2問い合わせで79（M_q＝73） | TD11・§6 |
| T8 | 許容外の宣言（`activities` のキー `revision`・`derivation`・`removal`、`revision` に文字列・数、`system`・`code` が空）は静的に拒否される | TD2 |
| T9 | 義務は R5 と必須欄で足りる。**PT-10 は既存の主題に収まらない**（P2-p の GR-9、P2-q の QR-11 と同じ。主題の外の義務は5件目）。登録は24宣言・335義務・517防護例、独立な組は 209／253（P2-t と依存関係にある5拡張〔P2-q・P2-p・P2-o・P2-i・数量〕を除く17組が増える） | H2 |
| T10 | `affected()`：P2-q の仕様の変更は P2-q と P2-t を列挙し、P2-i・P2-o・P2-p の仕様の変更が列挙する集合は、それぞれ P2-t を1つ加えた集合になる | 依存の効果 |

### 8.2 反例（80 に具体値を固定）

| ID | 内容 | 試すこと |
| --- | --- | --- |
| Z1 | 観察者が人の訂正（確認済み）、`revision` が真 | 生成側の項目に revision の entity が1つ付く（`what`＝訂正された記録） |
| Z2 | 訂正が二つの記録を訂正する | entity が2つ、`record_ref` の昇順 |
| Z3 | 訂正の連鎖 A→B→C、C が選ばれる | entity は B だけ。A は付かない。`revision_history` は失うものに残る |
| Z4 | 観察者が不明の訂正（出自は観察、確認済み） | `no_agent`。確認の項目に entity を付けない。`predecessors` は台帳の事実として出る |
| Z5 | 出自が AI の訂正 | `carried`。生成側の項目の agent は Device |
| Z6 | `revision` が偽 | `not_requested`。entity なし。失うものに `revision:predecessor_identity` |
| Z7 | P2-q の宣言に確認者の型がない | Provenance が出ないので `no_provenance` |
| Z8 | 訂正の符号だけ宣言がなく、生成の符号はある | 生成側の項目（訂正）の符号は null。生成の符号で代用しない。entity は付く |
| Z9 | 過去の時点で、訂正より前の記録が選ばれる | `not_applicable`。訂正は影響しない |
| Z10 | 宣言のない出力先／P2-q の行が表せない・足りない | `not_declared`／`not_evaluated` |
| Z11 | 使われない種類の符号だけを宣言 | 仮定を足さない。何も付かない種類は失うものに残る |
| Z12 | 許容外の宣言（R4 の語 `derivation` を種類に、`revision` に文字列） | 静的に拒否 |

## 9. 受入条件

1. 期待・予測・反例を、runtime より先に別の文書（80）で固定し、実行結果から期待を更新しない。
2. 専用 native・module・R5 宣言・fixture・独立な別計算を追加する。P2-q 以下・旧核は変更しない（T1）。
3. 別計算は、P2-q の別計算（行の基）を再利用し、`coding`・流れ・料金・ハッシュは自前で持つ。ハッシュは記録を JSON で正規化して独立に計算する。
4. 宣言の全数（活動の部分集合×revision×記録の場合〔原本／訂正〕×観察者×出自×確認者の型の宣言）、訂正の連鎖と多重度、乱数、P2-q 単独の実行との差分、料金、予算の掃引、入力の不変性、型破損、変異（符号の代用、種類の取り違え、flag の無視、向きの取り違え、前の版でなく選ばれた記録のハッシュ、agent のない項目への付与、順序、流れの欠落、先払いの省略）を検査する。
5. Python 3.11／3.14 で、全テスト系列、版比較つき統合評価、旧い22,052件の挙動 digest を回帰する。分母の変更は旧い値を履歴として残す。
6. 追加前は `c229c5c`、固定対象1,744ファイル、manifest `0bbefd611fac624f2bc891d9b40e26088e9a80f7062ae3dc314738ebe6c58c69`、束 `4b4b83d4f86c68d6466421dcbdc90876b44b5efc0b697bdeb8f65cbf916bd669`。件数・hash・予測の結果・残る穴を結果の文書に残す。`independent_review` / `evaluation_frozen` は false。

## 10. 範囲外

Provenance の `entity` の他の役割（`quotation`・`source`・`instantiates`・`removal`）、`entity.agent`、`activity` の符号の系の検証と内容、`agent.type`・`role`、`onBehalfOf`、署名、`occurred[x]`、`basedOn`、`patient`・`encounter`、Observation の `derivedFrom` などの記録間の関係、FHIR の資源（JSON）としての生成と適合の検査、訂正の理由（自由文）と連鎖の全体の運搬。

この設計は、訂正の関係と活動の符号を Provenance へ運ぶ宣言と使用の診断の一つの断片で、FHIR への適合の主張でも、`revision` が訂正の唯一の読みであることの主張でもありません。最終目標は変化に耐える医療コード体系そのものの確立であり、この有限の設計はその一つの検査です。

## 11. 利用者に確認すること

| ID | 確認 | 推奨 |
| --- | --- | --- |
| U1 | P2-q を変更せず、合成の専用 R5 として足す（P2-q を上げる選択もある） | 合成 |
| U2 | 活動の符号は宣言（不透明）、revision は宣言で opt-in し、`role` は拡張が `revision` に固定する（`source` など他の読みは範囲外） | そのとおり |
| U3 | FHIR R5 の `provenance-entity-role` の符号系ページ1つを、D03 の選定の範囲内で取得した（Git 管理外、台帳に記録） | 取得済み |

利用者の指示は「着手して」だったため、推奨どおりに実装へ進みます。異なる判断があれば、実装後の結果に反映します。
