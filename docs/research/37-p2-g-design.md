# P2-g：数量と測定主張を結ぶ契約の意味設計

作成日：2026-10-20。状態：**作成者側の設計草案。runtime・native仕様・登録宣言・実行用fixtureは未実装**。[P2-fの結果36](36-p2-f-results.md) の次の判断を具体化します。[手指定期待38](38-p2-g-cases.md)・[一次資料の確認](37-sources.md) と合わせて読みます。独立確認と評価の凍結は未実施です。以下は本プロジェクトの作業定義で、外部標準への適合仕様ではありません。

## 1. 問いと設計判断

問いは、**数量の数値的な意味を保ちながら、何の測定について、どの版の記録を、どの確認に基づいて計算したかを固定できるか**です。計算の成功を、医学的妥当性や臨床的同等性へ読み替えません。

| 判断 | 初回に採る設計 | 理由・限界 |
| --- | --- | --- |
| MB-D1 | 測定の枠slot、個々の記録版、数量リテラル、確認、計算結果を分離 | 同じ値・同じJSON・同じ測定の枠でも、同じ記録版とは限らない |
| MB-D2 | 確認対象に、文脈・出自・訂正辺・数量の内容hashを含める | 確認後の参照先差替えで、古い確認を使い回さない |
| MB-D3 | 初回は専用台帳・方針を持つ **R5の診断** | 型付き内容全体への確認とslot単位の選択は新しい意味。旧基底の採用結果だけを読むR2とは言えない |
| MB-D4 | 比較は明示した `matched_context` 方針だけ | 個体・測定対象・検体・方法・対象時点の一致を要求する限定的な数値点検。縦断比較や医学的比較可能性一般を定義しない |
| MB-D5 | 未知の文脈を区別して停止。明示訂正と新たな確認で精密化できる | 同じ不明値どうしを一致とせず、訂正前の由来も保持する |
| MB-D6 | 量計算はP2-fの固定版へ明示的に委譲。変数の同一性は選ばれた測定記録版で決める | 同じ区間リテラルを使う別測定を、自己比較へ潰さない |
| MB-D7 | 原snapshotと版を固定し、共有予算から下位計算へ予約分を支払う | 最新参照による過去の再解釈と、子計算ごとの予算のリセットを防ぐ |

例として、Aが「2 u_ten」、Bが「3 u_ten」への訂正であっても、Bの確認前にAを除きません。Bの確認後はBを選べますが、Aの内容・確認・過去の計算根拠は残ります。数量は架空の単位・量種だけを使います。

[Observationの項目](https://hl7.org/fhir/R5/observation-definitions.html) は値・測定対象・主体・対象時刻・方法・検体を分けています。本設計も数値だけでは文脈を表せないという比較材料にしますが、FHIRの状態や欄を本方針へ自動対応させません。測定対象の指定については [VIM 2.3](https://jcgm.bipm.org/vim/en/2.3.html) を参照しました。

## 2. 旧契約と分類の境界

[P2-f](34-p2-f-design.md) は未確認の量リテラルでも数学的に計算できます。P2-gは、その値を含む測定主張の記録版について、内容を特定した人の確認と選択条件を要求します。P2-fの計算結果に確認済みという印を後付けする設計にはしません。

旧 [ledger.select_view](../../src/med_dsl/ledger.py) の確認は旧主張への参照です。旧原子に数量IDだけを加えて、別表の値・方法を変更可能にしたまま確認を流用すれば、確認対象の内容を拘束できません。一方、数量版のhashを旧原子そのものへ入れるだけでは、値の訂正で原子が変わり、同じ原子に限る旧 `supersedes` では訂正できません。この二つを隠れた仕様変更で埋めず、専用の型付き台帳と方針へ分けます。

初回はR5の7必須義務と測定固有のMB-1〜12を設計します。JOINTは現在、R2/R6の基底読み取りと公理の併用を前提にするため、そのラベルだけを付けて今回の確認対象の変更を認定しません。汎用クラスの追加は行いません。

旧要求の保存対象は、従来妥当だったP0/P1/P2-e/P2-f等の要求です。翻訳と回答対応は恒等、観測は意味・根拠・停止・採用情報（実装識別 `certifier` を除く）です。新handlerの追加は旧経路の非干渉として検査します。新しい記録をP0へ自動取込したり、結果を `supported` 等へ変換したりはしません。

期間による部分訂正は使わず、P2-eの方針・台帳は読みません。P2-eとの意味上の合成、医学的な有効期間、一般の臨床採用は別の課題です。

## 3. 初回の入力断片

以下は実装に向けた予約名です。現在のCLIは受け付けません。

| 項目 | 設計 |
| --- | --- |
| profile | `p2-measurement-binding-draft-1` |
| request / result / source schema | `p2-measurement-request-draft-1` / `p2-measurement-result-draft-1` / `p2-measurement-ledger-draft-1` |
| 操作 / 回答型 | `evaluate_measurements` / `measurement_literal_projection` |
| 方針 | `fiction:reviewed-measurement-record@1` |
| 要求 | `schema_version, operation, consumer, source, views, queries, budget` |
| consumer | `profile, profile_spec_sha256, operations, quantity_profile, quantity_profile_spec_sha256`。操作は当該一操作のみ |
| source | `schema_version, ref, slots, quantities, records, reviews`。全参照は同梱したsnapshot内で解決し、外部へ取得しに行かない |
| slots | `{id, subject_ref}`。1〜64件。同じslotの全記録はこの主体に一致。slotの同一性は入力側の明示主張で、値の一致から推定しない |
| quantities | `{ref, profile, profile_spec_sha256, literal}`。0〜64件。literalはP2-fの数量そのもの、`literal.id = ref` |
| records | 下記の測定記録。0〜64件、IDはsource内で一意 |
| reviews | 下記の内容を指定した確認。0〜128件 |
| views | `{id, as_of, policy_ref}`。1〜64件。厳密なUTC秒精度で記録・確認の可視性を選ぶ |
| convert query | `{id, kind: convert, slot_ref, target_unit_ref}` |
| compare query | `{id, kind: compare, left_slot_ref, right_slot_ref, comparison_scope: matched_context}` |
| 上限 | queries 1〜64件、1 MiB・深さ64、整数予算0〜100,000。boolを整数としない |

量の依存版は `p2-quantity-literal-draft-1`、native仕様の生バイトSHA-256は `84af2e771d1868471d0a8441021fde2a7253b1fc17f8ff9b807461e3df7f1f43` に固定します。wrapper・consumer・実体を照合し、違うprofile/hashを最新版で代用しません。R5の実装時にはP2-fと基底への依存、P2-fを読むこと、実装・契約・共有入口のpinを宣言します。共有の単位登録表は作りません。

### 3.1 測定記録と文脈

各記録は `id, kind: measurement, slot_ref, subject_ref, property_ref, specimen, method, effective_at, quantity_ref, certainty, recorded_at, origin, required_capabilities, supersedes` を持ちます。訂正辺がある場合だけ非空の `change_reason` を必須とします。`certainty` は `confirmed / suspected`。originは旧主張と同じ四種の `kind` と非空refです。必須能力にはP2-gのprofileを含めます。

| 文脈 | 初回の型・意味 |
| --- | --- |
| property_ref | 下記の閉じた架空表の参照。未収録の非空参照は未知の測定対象として停止する |
| specimen / method | `{kind: known, ref, version}`、`{kind: unknown}`、`{kind: unspecified}`。knownは参照と版の明示であり、現実の同一性の認証ではない |
| effective_at | `{kind: instant, at: UTC時刻}`、`{kind: unknown}`、`{kind: unspecified}`。測定の対象時点で、記録時刻や確認時刻から補わない |
| quantity_ref | `{ref, sha256}`。同梱したquantity wrapperの内容hashと一致する必要がある |
| supersedes | 同じslotの厳密に前の記録IDの配列。自己・未解決・別slotを拒否。全記録版の訂正で、期間内だけの訂正ではない |

初回のproperty表は `fiction:measurement:property:A@1 → k_a`、`fiction:measurement:property:A-other@1 → k_a`、`fiction:measurement:property:B@1 → k_b` の三つです。AとA-otherは同じ量種でも別の測定対象です。既知の対象と既知の量種が食い違う場合は入力不正、未知の対象・量種は意味を補わず停止します。量種・単位の次元の矛盾はP2-fと同様に入力不正です。property表もこのprofile・仕様hash内の局所名で、基底の述語や外部の検査コードとして輸出しません。

refとversionは非空文字列で、表示名や単位から補正・同義判定しません。`not_applicable`、期間、時刻の精度が異なる表現、数値がない測定、撤回・明示否定は専用表現が必要なため初回は `unsupported_profile`。欠落・null・既知の型の不正は `invalid_input` です。

同じslotの訂正では、主体を維持した上で、値、対象、検体、方法、対象時点の修正・不明情報の精密化を明示できます。全て新しい記録ID・内容hash・確認が必要です。別の測定を同じslotだと判断する処理、主体の訂正、slotの結合は未対応です。対象時点の医学的妥当性や、記録時刻に対する前後関係は推定しません。

### 3.2 確認が拘束する内容とhash

確認は `id, record_ref, record_sha256, reviewer_ref, reviewer_kind: human, recorded_at, outcome: confirmed` を持ちます。対象記録以後に記録されていることを必須とします。疑いの記録は確認があっても適格にしません。AI由来は確認なしで採用せず、確認後も記録と数量の双方の出自を残します。

hashは既存の `validation.canonical_bytes`（JSONのキーを整列、空白なし、UTF-8、NaN禁止）を入力にSHA-256を計算する、プロジェクト内部の方式です。RFC等への適合は主張せず、Unicodeや未約分数値を正規化しません。

```text
Hq(q) = H(quantity wrapperの全項目)
Hr(a) = H({binding_profile, binding_spec_sha256, source_ref, record: a})
Hs(S) = H(sourceの四表をそれぞれ識別子順に整列したsnapshot)
```

quantity_refのhashはHq、確認のhashはHrに一致させます。Hrは記録の文脈・出自・訂正辺に加え、数量のprofile・仕様・原値・単位・不確かさ・出自をHq経由で拘束します。slotの主体との一致も検証するため、slot表だけを差し替えて意味を変えられません。source自体はhashを内包しません。Hsの整列キーはslots/records/reviewsではid、quantitiesではrefです。

配列全体の並べ替えは四表の順序だけならHsと記録のhashを変えません。記録やquantity literalの内部の能力配列、訂正辺の配列順はhashの内容に含めます。内部の並べ替えをする場合も古い確認のまま使い回さず、この初回方式の制限として扱います。元の要求hashと保持する原入力は並べ替えません。

**hashの整合は本人確認・電子署名・内容の真実性・改ざん耐性を証明しません。** 記録と確認を一緒に捏造した入力は、この構造検査では検出できません。永続ストアでの同じIDの書換え禁止や認証も未実装です。過去の再現には元snapshot・仕様・処理系を別に保持する必要があります。[FHIRの版を指定した参照](https://hl7.org/fhir/R5/references.html#literal) は比較材料であり、本hash方式との同一視はしません。

## 4. 可視性・選択・停止

構造・型・全参照・全hash・訂正順序は入力全体について予算前に検査します。未来の不正記録を無視して成功とする契約ではありません。

queryが参照するslotの集合をSとし、同じslotの自己比較では一つにまとめます。参照時点kについて次を定義します。

```text
V(S,k) = {a | a.slot_ref ∈ S かつ a.recorded_at <= k}
E(S,k) = {a ∈ V | a.certainty = confirmed かつ
                  時点kまでに見えるhuman/confirmedの内容一致確認がある}
D(S,k) = {b | a ∈ E(S,k) かつ b ∈ a.supersedes}
A(s,k) = {a ∈ E(S,k) | a.slot_ref = s かつ a.id ∉ D(S,k)}
```

訂正元自身が後に除かれても、その適格な訂正辺を取り消しません。未確認の訂正は元を除きません。適格でない中間記録を通じて、祖先を推移的に除くこともしません。二つの確認済み記録が残る場合は、値が等しくても競合とします。最新時刻・最小ID・同じ数値で一つにしません。

| 順位 | 条件 | 行の結果 |
| --- | --- | --- |
| 1 | Vに未知能力の記録、またはVのいずれかが指す数量に未知能力 | `unassessed / unknown_capability`。保留・訂正済みも対象。未参照slotや未来の記録の未知能力は含めない |
| 2 | いずれかのslotで候補数が1でない | `unassessed`。0なら `no_adopted_measurement`、2以上なら `unresolved_measurement_conflict`。異なるslotの両理由は整列して併記 |
| 3 | 選ばれた記録の未知property、検体・方法・対象時点のunknown / unspecified、選ばれた数量やtargetの未知量種・単位 | `unassessed`。該当する理由を全て整列して併記。同じ不明値どうしでも一致にしない |
| 4 | compareの既知の文脈が一致しない | `not_comparable`。相違した各欄を理由として併記 |
| 5 | 上記なし | 数値処理へ。P2-fの正確な換算・区間比較を行い `computed` |

能力の理解集合は記録についてP2-gだけ、数量についてP2-fだけです。未知能力は、数字の換算だけには影響しないと推測して落としません。未知の型・方針・profile・操作は `unsupported_profile`、静的な上限超過は `resource_limit` に区別します。

情報不足の理由名は `unknown_property`、`specimen_unknown / specimen_unspecified`、`method_unknown / method_unspecified`、`effective_time_unknown / effective_time_unspecified`、量について `unknown_quantity_kind / unknown_unit`。比較不能は `different_subject / different_property / different_specimen / different_method / different_effective_time`。順序は文字列の昇順に固定します。

## 5. 文脈を合わせた計算と変数の同一性

`matched_context` は、主体・property_ref・specimenのref/版・methodのref/版・対象の瞬間が全て一致することだけを要求します。異なる時点の推移、別検体の比較、方法差の補正はこの方針では扱いません。これらが医学的に比較不能だと一般化する判定でも、全欄が一致すれば医学的に同等だという判定でもありません。

量の委譲では、選んだ**記録版**ごとに、新しい局所数量IDを与えた作業用入力を作ります。同じ記録版を二回読むときだけ同じIDを使います。元の数量・IDは保持し、対応表を根拠に含めます。二記録が同じquantity wrapperを参照しても、別の測定変数として区間の直積を比較します。

例：別slotの記録A・Bが同じ `[1,2]` のwrapperを参照すると、関係集合は `less,equal,greater`。AをAと比較すると `equal`。quantity_refや内容hashだけで重複を除く実装は前者を誤ってequalにします。この橋渡しは、共有リテラルを測定ごとの領域記述として実体化する**新しい作業定義**で、旧P2-fの同一IDの意味を変更したものではありません。相関、明示的な別名関係、確率的独立性を追加したとは扱いません。

量の入力上限、点・区間、不確かさの未評価、丸めや外部単位の未対応はP2-fのままです。適合するpropertyが同じなら量種も同じであることを入力検証します。入力不正を文脈不一致の後に隠しません。

## 6. 回答・再現・共有予算

値の欄 `converted_domain, relation_set, certain_relation`、完成根拠 `binding_evidence, calculation_evidence` はcomputed以外でnullです。支払い済みの停止行には理由と `diagnostics`（阻害記録・候補・相違欄等）だけを返せます。予算打切りの行ではdiagnosticsもnullです。

`binding_evidence` はsourceのHs、binding/quantity仕様hash、方針、as_of、query条件、選んだslot/record/Hr/quantity_ref/Hq、可視の確認ID、作業用数量IDとの対応を含めます。`calculation_evidence` は子の入力hashと数学的根拠を保持し、元の両出自に辿れるようにします。元sourceは一度だけ保持します。計算結果を新しい測定記録・確認として台帳に書き戻しません。

rootは `converted_to_base: false, clinical_assertions_added: [], clinical_confirmation: not_evaluated, uncertainty_propagated: false, review_verification: structural_only` とし、certificateはnot_certifiedです。人の確認記録による選択と、医学的妥当性・確認者本人の認証を区別します。

行には `assessment_complete` を設け、意味上停止しても全検査を終えた行はtrue、予算で未完了ならfalseです。rootの `incomplete` は後者だけを列挙します。rootのokは評価手続きの完了を意味し、全行で値が出たことを意味しません。

課金は以下を**計算前に先払い**します。viewとqueryはID順、キャッシュ割引なしです。

```text
C = 1 + N_slots + N_quantities
    + Σview [N_records + N_reviews
             + Σquery (2 + |V(S,k)| + Σa∈E(S,k)|a.supersedes| + R(query))]
R(convert) = 8
R(compare) = 12
```

2は行の開始と確定、RはP2-fの要求開始・数量準備・一演算を含む予約料金です。変換は1数量で8、別記録の比較は2数量で12。同一記録の比較でも12を払い、子の実費11との差1は同一性の橋渡しの予約分として返却しません。意味上停止する行もRを払います。

子へ無条件の100,000を配らず、親が支払い済みのRだけを子の上限にします。子のstepsはその予約に含め、二重計上しません。行全体の支払い前に子を呼ばず、子が資源停止した場合も完成値・根拠を公開しません。作業用入力にもP2-fのサイズ・深さ上限を適用し、同じ大きなliteralを別記録用に複製して1 MiBを超える場合はresource_limitにします。切詰めや同一IDへの統合で通さず、先に完成した別の行は保持します。親の `steps_used` は式の予約分を含む課金量で、子の実費の単純和とは異なります。

一slot・一数量・一記録・一確認・一view・一convertの標準例は16。二slot・二数量・二記録・二確認のcompareは25、一slotの自己compareは20、標準例にconvertを二つ置くと27です。これは実測ではなく、実装時に照合する設計値です。

## 7. 条件つきの導出と証明義務

以下は作成者による手作業の導出です。hashの衝突を別の内容の同一視に使わないという前提を置き、認証・永続保存・任意の将来の意味の証明は含めません。

| 導出 | この断片で言えること・範囲 |
| --- | --- |
| MB-L1：確認対象の固定 | quantity wrapperが変わればHq、記録の文脈・数量参照が変わればHrが変わるため、古いhashの確認は不一致となる。記録と確認を一緒に偽造する攻撃は対象外 |
| MB-L2：可視性 | Eは記録と確認の両時刻がk以下のものだけ。構造が妥当な未来の記録・確認の追加について、同じ方針・依存版で双方の計算が完了するなら、過去の選択・数値結果は変わらない。source hash・保持一覧・予算量の一致は含めない |
| MB-L3：訂正と競合 | 除去集合Dは全適格記録の辺から作るので、訂正元が除かれても対象は自動復活しない。適格でない中間記録の辺は使わず、残った複数候補は等値でも競合 |
| MB-L4：別測定と同一参照 | 局所数量IDが選択記録版に単射なら別記録を自己比較に潰さず、同じ記録を二度参照した場合だけ同一変数となる。別記録間の相関までは表さない |
| MB-L5：未知と文脈 | 一致判定は必要欄が全て既知の後だけ。unknown/unspecifiedの辞書の一致や同じslotだけでは、完成値に到達しない |
| MB-L6：再現と旧非干渉 | 元snapshot・query・view・依存版・処理系が保持される範囲で同じ記録版を再選択できる。保存先や旧実装の可用性は保証しない。新handlerが旧経路を変更しないことは別に回帰する |

| 追加義務 | 内容 | 防護する条件 |
| --- | --- | --- |
| MB-1 | 参照・内容hash・確認対象を連鎖して拘束（L1） | N03〜N04、M34、M36 |
| MB-2 | 人の確認・確定性・両時刻の可視性（L2） | M02〜M08 |
| MB-3 | slot単位の訂正・競合・非復活（L3） | M09〜M15、N06 |
| MB-4 | unknown / unspecifiedの保持と精密化（L5） | M16〜M21、M33 |
| MB-5 | 限定した文脈一致と医学的同等性の分離 | M24、M27〜M31 |
| MB-6 | 記録版と数値変数の同一性（L4） | M25〜M26、M32 |
| MB-7 | 可視の保留・訂正済みも含む能力の検査、slot範囲の分離 | M22〜M23 |
| MB-8 | 量の固定版・厳密演算・未対応の境界 | M01、M32、M35、N07〜N10 |
| MB-9 | 両出自と未評価の不確かさを保持し、臨床主張を生成しない | M07〜M08、M24、M35 |
| MB-10 | 共有予算からの予約、原子的な完成値と根拠 | B01〜B04 |
| MB-11 | 再現根拠と旧要求の非干渉（L6） | M36、N12 |
| MB-12 | 全体の構造検証・決定性・依存と再検証対象の識別 | N01〜N12、B04 |

R5の必須欄だけでは、型付き確認や変数の割当の正しさは決まりません。MB-1〜12を個別に検査する予定で、これらを汎用の証明義務として自動導出したとは扱いません。

## 8. 実装前後の受入条件と再開点

1. [M36/N12/B4](38-p2-g-cases.md) を実装より先の期待として保持し、実行結果から正解を更新しない。今回の有限照合は選択式の設計点検だけで、接続runtimeの実証ではない。
2. 専用のnative仕様・handler・R5宣言・実行例を作る。数量moduleと旧核の意味を変更しない。必要なAPIの調整は旧22,052出力等の回帰と変更理由を伴う。
3. 宣言はR5の7義務とMBの12義務、計19義務を明示し、独立確認・評価凍結はfalse。防護例のない義務が生じた場合は理由を残し、既存の3件と分ける。
4. 確認対象の差替え、確認時刻の無視、latest-wins、最終採用元だけの訂正辺、未知情報の一致扱い、literal IDでの別測定の統合、子予算のリセット、完成根拠の早期漏出の変異を検出する。
5. 選択は到達時刻順の状態更新による参照計算と照合し、三記録までの全訂正辺・確定性・確認の可視性を有限列挙する。量のadapterは二slotの共有区間・自己比較・各文脈差・未知の組合せで別に照合する。
6. 全sourceの検証は予算前、行は料金全体の先払い後にだけ完成させる。予算0から完成直後まで掃引し、旧 `p2_checks` に新しい根拠欄と完了状態を加える。
7. Python 3.11/3.14で新経路・CLI・既存231/52/8/P2 222件を回帰し、統合評価の分母を明示的に増やす。旧値は履歴の期待として残す。
8. 今回は文書だけで、P2-fまでの516ファイルの固定対象・runtime・台帳・期待は変更しない。実装時に37/38・native仕様・新例・参照計算・検査・生成器を新たに固定対象へ加え、e69a628を追加前の基準として残す。

直近の次作業は、手指定期待の実行例への展開と、この断片の最小実装です。実世界の医療者に同じ確認操作を追加要求するUIを作ったという意味ではありません。将来のライブラリで既存の記録・確認操作をどのように対応させるかは、別に負担と意味を評価します。

実体系への無損失取込、臨床の判断・検証、認証と署名、永続台帳、主体の訂正、撤回、部分訂正、縦断比較、検体・方法の同等性推論、相関・測定不確かさ、表示の丸め、基底へ戻す橋渡し、標準化は未解決です。有限の接続設計を、変化に耐える医療コード体系の最終目標の達成とは扱いません。
