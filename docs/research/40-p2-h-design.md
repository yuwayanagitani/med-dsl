# P2-h：厳密な数量と表示の射影の意味設計

作成日：2026-10-20。状態：**作成者側の設計草案。runtime・native仕様・登録宣言・実行用fixtureは未実装**。[P2-gの結果39](39-p2-g-results.md) に続き、表示が保存する問いと失う区別を設計します。[手指定期待41](41-p2-h-cases.md)・[一次資料の確認40](40-sources.md) を併せて読みます。独立確認・評価用正解の凍結は未実施です。

## 1. 問いと今回の判断

問いは、**医療者が見る表示や接続先の桁数が変わっても、原値・確認対象・計算結果を上書きせず、表示だけに残る意味を限定できるか**です。表示の同一を、原値・記録・医学的同等性の同一へ読み替えません。

| 判断 | 初回の選択 | 理由・見直す条件 |
| --- | --- | --- |
| DP-D1 | 専用のR4射影としてP2-gのconvert結果を読む | 確認・訂正を再定義せず、失う区別と保存する問いを検査する。旧R4の四つ組用handlerは変更しない |
| DP-D2 | 閉じた単一点の領域だけを、小数点以下0〜6桁へ最近接偶数丸め | 区間の中点化・端点の内向き丸めを入れない。区間表示・有効数字・科学表記は別契約 |
| DP-D3 | 射影πの対象を**型付き表示artifactだけ**に固定 | 根拠hash・出自・別添えを含む応答全体と混同しない。原値との差もartifactへ混ぜない |
| DP-D4 | 表示の逆像となる数値セル上で一定の問いだけを保存範囲にする | 実際の原値でたまたま正答したことを、表示から答えられる証拠にしない |
| DP-D5 | 原要求の別添えと、そこから答えるsource_replayを分離 | 別添えが利用可能でも表示自身の保存範囲は広げない |
| DP-D6 | P2-gを親からの予約予算で一度実行し、各表示行も先払い | 子予算のリセット、行途中の表示・回答・完成根拠の漏出を防ぐ |
| DP-D7 | AI出自・未評価の不確かさ・臨床未評価を応答の根拠へ残す | 表示artifactがこれらを符号化したとは言わない。丸めセルは測定の不確かさではない |

最近接偶数の規則は [W3C Functions and Operators 3.1 §4.4.5](https://www.w3.org/TR/xpath-functions-31/#func-round-half-to-even) と [Python 3.14 decimal](https://docs.python.org/3.14/library/decimal.html#decimal.ROUND_HALF_EVEN) で確認しました。選んだ桁数・零の表記・schema・認定範囲は本プロジェクトの作業定義です。FHIRや臨床表示への適合を主張しません。

## 2. 三案の比較と依存

| 案 | 検査できること | 判断 |
| --- | --- | --- |
| 裸の数値文字列を整形する | 表示関数だけ | 単位・量種・出自・確認を脱落させた入力が先に成立してしまう。初回の入口にはしない |
| P2-gの結果JSONを受け入れる | 保存済みの結果を整形する | 結果の自己申告・hashだけでは計算の正しさを検査できない。初回は受け付けない |
| **P2-gの計画を受け取り、予約予算で再実行する** | 確認対象と選択を固定し、その数値を射影する | **選定**。新しい臨床の採用を定義せず、元の人の確認はP2-gに委譲する |

依存はP2-g `p2-measurement-binding-draft-1`（仕様hash `7c2f731f2e24423f552bef8fb61efd5bdb74fac326279c7d7800639bb301a454`）と、そのP2-f `p2-quantity-literal-draft-1`（`84af2e771d1868471d0a8441021fde2a7253b1fc17f8ff9b807461e3df7f1f43`）です。P2-hのconsumer・native仕様で双方を固定します。単位・量種は引き続き数量profile/仕様hash内の局所名で、共有述語へ偽装登録しません。

新しい意味クラスを追加せず、共通4＋R4の3＋DP-1〜12の**19義務**を設計します。P2-gのR5診断が保存認定になったとは扱いません。P2-hの認定は表示に因子化できる限定した問いだけです。時間・概念分割とのJOINTを実装したとも扱いません。

## 3. 入口と静的な検証

以下は予約案で、現在のCLIは受け付けません。

| 項目 | 設計 |
| --- | --- |
| profile / 操作 | `p2-quantity-display-draft-1` / `project_measurement_displays` |
| 要求 / 結果 / artifact schema | `p2-display-request-draft-1` / `p2-display-result-draft-1` / `p2-display-artifact-draft-1` |
| 回答型 | `measurement_display_projection` |
| 要求の必須欄 | `schema_version, operation, consumer, measurement_plan, displays, retention, budget` |
| consumer | `profile, profile_spec_sha256, operations, measurement_profile, measurement_profile_spec_sha256, quantity_profile, quantity_profile_spec_sha256`。operationsは当該操作だけ |
| measurement_plan | **P2-g要求からbudgetだけを除いた計画**。schema/operation/consumer/source/views/queriesはそのまま。子のbudgetを利用者が別に指定する欄は設けない |
| 計画のqueries | 初回は全てconvert。compareはunsupported_profile。表示が参照しないconvertも計画どおり実行・課金する |
| displays | 1〜64件。`id, view_ref, query_ref, decimal_places, rounding_policy, required_capabilities, questions` |
| 表示の指定 | 参照view/queryは計画に存在するもの。decimal_placesは整数0〜6、policyは `fiction:decimal-half-even@1` のみ |
| questions | 各表示1〜16件、IDは表示内で一意。下記の3種類 |
| 表示を読む問い | `{id, kind: display_text}` |
| 正確な値を読む問い | `{id, kind: exact_value}` |
| 閾値の問い | `{id, kind: threshold, operator: lt/le/eq/ge/gt, threshold: {numerator, denominator}}` |
| retention | `none` または `source_bundle`。noneでも出自・内容参照の根拠は応答に残す |
| 共通上限 | 入力1 MiB・深さ64。予算は整数0〜100,000。閾値の分子/分母は各63bit以下、分母正。bool・小数の自動変換なし |

thresholdは**当該convertのtarget_unit_refで明示した単位**における数値です。異単位の閾値を黙って換算する機能はありません。別単位・単位文字列・臨床閾値の外部取込は初回の入力型に含めません。正確な値の問いも、換算後の厳密値が対象で、原入力の未約分表記とは別です。

構造・参照・hash・時刻・訂正・確認・依存版・入力数値の妥当性は、**全計画について予算前に検証**します。未参照・未来の不正も隠しません。検証用の子要求はbudget=0で構築し、型検証だけを行い、意味計算を呼びません。利用者が送ったP2-gの結果・certificate・artifactを根拠として受け付けません。

未対応policy/依存版/質問kindはunsupported_profile、欄・参照・型・hashの不正はinvalid_input、件数・サイズ・深さ等の静的上限はresource_limitです。decimal_placesの負数・boolはinvalid_input、6超の整数はunsupported_profileで、検証前に指数を計算しません。required_capabilitiesは当該表示profileが必須。未知の追加能力は、先払い済みの当該表示行をunassessedにします。P2-g側の能力検査を省く許可にはなりません。

## 4. 数学的な射影と逆像

P2-gの結果領域が閉じた一点なら、その有理数をxとします。magnitudeがintervalでも閉じた単一点なら処理でき、元の型は別添えに残します。非単一点の区間は `unassessed / unsupported_display_domain` とし、代表値を作りません。

```text
p = decimal_places, s = 10^p
z = s*x, a = floor(z), f = z-a
k = a       if f < 1/2
    a+1     if f > 1/2
    a       if f = 1/2 and a is even
    a+1     if f = 1/2 and a is odd
r = k/s
```

整数商・剰余の比較で決め、floatや、先に有限精度で割ったDecimalを経由しません。負数にもfloorを使う同じ式を適用します。k=0は正負を区別せず、p=1なら `0.0` です。p=0なら小数点なし、p>0なら末尾零を含む正確にp桁、ASCIIの符号・数字・小数点だけを使います。ロケール、桁区切り、指数表記は含めません。

**artifact = π(x; 型・表示方針)** は次の欄だけを持ちます。

```text
schema_version, profile, profile_spec_sha256,
quantity_profile, quantity_profile_spec_sha256, quantity_kind_ref, unit_ref,
rounding_policy, decimal_places, coefficient: k, text
```

unit_refは換算先の局所IDです。表示ID・原値・record ID・文脈・origin・source hash・原値との差はartifactへ入れません。表示方針とpも意味の一部なので、同じtextだけでartifact同一とは判定しません。hashは既存のcanonical JSONによるartifact全体のdigestとし、後段の符号化では**このartifactだけ**の復号一致を調べます。出所の根拠や原要求を足した応答全体はπの値ではありません。

表示に対応するセルFは、型と方針を固定したときの数学的な逆像です。

```text
L = (2*k-1)/(2*s), U = (2*k+1)/(2*s)
F(k,p) = [L,U]  if k is even
         (L,U)  if k is odd
```

負のk・零にも同じ式を用います。これは実数上で定義した丸め関数の逆像で、**測定誤差・真値の範囲・確率区間ではありません**。実装が受理する63bit入力と固定換算で到達できる原値の集合は、このセルの部分集合です。セル全体を使う判定は保存の十分条件で、受理可能な全原要求に対する必要十分な判定とは呼びません。out_of_scopeから直ちに、受理できる二原要求の衝突が存在すると推論しません。

表示上の桁数は方針として追加した情報です。外部の測定記録の有効数字や不確かさを復元・推定したものではありません。[FHIR R5の精度の扱い](https://hl7.org/fhir/R5/datatypes.html#decimal) と同じ機能を実装したとはしません。

## 5. 保存する問いと別添え

原値についての問いqが、同じartifactへ写る全ての値で同じ答えなら、artifactだけの問いq'へ因子化できます。初回は次の既知の十分条件を実装候補にします。

| 問い | projection_answer / 判定 |
| --- | --- |
| display_text | artifact.text / preserved。型付きartifactが前提で、裸の文字列から量を復元しない |
| exact_value | null / out_of_scope。初回テンプレートでは認定しない。入力上限を利用した個別の単射性は検査対象外 |
| threshold | 以下のセル全体の判定が一定ならbool / preserved。それ以外はnull / out_of_scope |

cをセルの両端の閉フラグとし、tを閾値とします。

| operator | 全てtrueになる条件 | 全てfalseになる条件 |
| --- | --- | --- |
| lt | U<t、またはU=tかつ開端 | L≧t |
| le | U≦t | L>t、またはL=tかつ開端 |
| eq | なし（セルの幅は正） | tがセルの外。開端上も外 |
| ge | L≧t | U<t、またはU=tかつ開端 |
| gt | L>t、またはL=tかつ開端 | U≦t |

projection_answer=falseと、答えがないnullを区別します。原値xとの比較を計算できても、それをprojection_answerへ流用しません。医学的な閾値・有意差・診断は扱いません。

retention=source_bundleではP2-h要求からbudgetだけを除いた部分を、その配列順・未約分表記を含めて `source_bundle.request_plan` に保持します。原数量・文脈・確認・view/query・表示方針・consumerの版を再現に使えます。実行予算は意味入力と分け、再実行時に指定します。これにより、十分な予算の大小で別添えの内容は変わりません。元の予算まで含む要求の完全なhash再現には、呼出側で原要求を保持する必要があります。**完成した表示行だけ**が、内部で完成した子の当該行と確認根拠を `source_evidence` に持てます。子の結果全体を各行に複製し、まだ未払いの表示行へ別の計算値を漏らすことはしません。

exact_value/thresholdについて、bundleを使った数値回答を別の `source_answer: {mode: source_replay, answer: ...}` に出せます。bundleがない場合とdisplay_textではsource_answer=nullです。projectionのout_of_scopeは変えません。`additional_source_used` は回答にsource_replayを実際に用いたときだけtrueで、bundleがあるだけではtrueにしません。根拠の追跡と、問いへ追加入力で答えたことを分けます。

P2-gの選択記録・内容hash・量の仕様hash・両origin・view/query・子要求hash・子のmeasurement_certificateは、保持モードによらず完成行の `projection_evidence` に残します。これはartifact外の出所情報です。根拠にはartifactのcanonical JSON bytes（base64）・digest・実際の復号一致を示すartifact_encodingも含めます。原値の差分や正確な値はこの根拠欄に紛れ込ませません。AI由来を表示で消さず、裸のartifactを確認済みの臨床主張として逆入力しません。

### 喪失の反例

同じ型・単位・方針・p=1で、x=121/100とy=124/100は同じartifact「1.2」になります。しかしq(v)=[v≧61/50]の原回答はfalse/trueです。qをartifactだけから正しく求める関数は存在しません。原要求の別添えや、その後の無損失JSON符号化を足しても、π自体がこの区別を保ったとは言えません。

初回は自動的な反例探索器を作らず、[P28〜P31](41-p2-h-cases.md) の二表示・二原要求で、artifact同一と原回答の相違を検査する計画です。**手指定した衝突の実証**と、一般の損失の自動判定を分けます。既存R4の列射影とは異なる関数ですが、因子化・反例・別添えという同じ義務を具体化します。

## 6. 結果と認定の範囲

表示行はID順で、`id, view_ref, query_ref, status, assessment_complete, reason_codes, artifact, artifact_sha256, rounding_cell, question_results, projection_evidence, source_evidence` を返す案です。各question結果は `id, status, projection_answer, source_answer, reason_codes`。out_of_scopeの理由はquery_out_of_scopeです。

各行は、表示自身の未知能力、対応する子の行の非computed、非単一点、丸めと問いの順に判定します。計画の子がokでも、対応行がunassessed/not_comparableなら、その理由を維持して表示も停止します。既知のtargetの次元不一致もP2-gのnot_comparableを保持します。P2-gがcomputedでも、表示の未知能力・非単一点領域では表示を作りません。支払い済みの意味上の停止はassessment_complete=trueで、questionはunassessed、回答と数値根拠はnullです。rootのokは手続きの完了を表します。

未払い行はassessment_complete=falseで、artifact・hash・セル・question_results・両evidenceを全てnullとします。原要求の別添えは元からある入力で、計算結果の公開とは区別します。完成済みの前の行は保持します。

rootの `certificate` は全処理と最終料金が完了し、全表示がcomputedで、**要求された全questionがpreserved**のときだけcertifiedにできます。scopeは表示ID・質問ID・artifact hashと `display_questions_only` に限定し、原値一般、記録ID・文脈・履歴、医学的真実、不確かさを除外します。他はnot_certifiedで、範囲外はquery_out_of_scope、意味上停止はその理由、資源停止はその理由を残します。別添えで答えられたことを認定条件に入れません。

認定は固定した丸めとセル判定の既知テンプレートに相対的で、任意の問いの保存判定ではありません。P2-gのnot_certifiedを上書きせず、source_evidenceには子の認定の範囲も区別して残します。rootでも `clinical_confirmation: not_evaluated, uncertainty_propagated: false, converted_to_base: false, clinical_assertions_added: []` を維持します。

## 7. 共有予算・上限・再現

P2-gの全計画完了料金Cは [設計37の§6](37-p2-g-design.md) に従って計画から求めます。表示が参照する部分だけに縮約せず、子が実際に読む全view/queryを数えます。時点ごとの可視性と適格な訂正辺を含め、native依存版と一緒に固定します。

```text
H = 1 + C + sum_display(8 + 2*N_questions) + 1
```

開始1、**子全体のCを先払い**してbudget=Cの子を一度呼び、表示行ごとの料金を先払いしてから丸め・問いの判定・根拠を公開し、最後の1で全体を確定します。Cを払えなければ子を呼びません。Cは親から支払った額で、追加のCとして二重計上しません。表示を複数作っても子を再実行・予算リセットせず、余りの返却やキャッシュ割引はありません。

最後の1を払えない場合は、完成行を保持してrootはresource_limit、certificateはnot_certified、incompleteに `{stage: completion, reason_codes: [step_limit]}` を載せます。未完成行もあれば表示IDで列挙します。子が別の資源上限で停止した場合もrootはresource_limitとして表示を一つも完成させず、子の途中の値を拾いません。静的な拒否は予算0でも同じで、不正な予算欄そのものを修復した要求との一致は求めません。

標準の子C=16、一表示一質問でH=28。二つの表示が同じ子の行を読む場合はH=38です。これは抽象的な固定課金で、CPU命令数ではありません。将来のC算定と子のsteps_usedの一致、子のbudget引数、0から完成直後までの掃引を別々に検査します。

P2-fの変換後の分子/分母77bit以下を前提に、10^6との積97bit以下、丸め整数97bit以下、セルの分子99bit以下、63bit閾値との交差積162bit以下という保守的上限を置きます。中間256bit、表示64文字以内を検査する案です。大きな値をfloatへ落として上限を回避しません。これは固定した倍率・pの範囲に限る上界です。

再現には原要求・双方のnative仕様・処理系・表示方針を保存します。並べ替えではroot/子の入力hashが変わり得るため、それぞれ原入力から照合し、意味の不変比較では区別します。Hs・記録/数量の内容hash・artifact hashを一緒に除去することはしません。source_bundleがあることは外部原文・測定過程・旧処理系の可用性の保証ではありません。方針やpを変えればartifactが変わり得ますが、原記録・確認hashを変更しません。

## 8. 導出・個別義務

| 導出 | 前提と結論 | 限界 |
| --- | --- | --- |
| DP-L1 | 半整数で偶数を選べば、偶数kのセルは両端閉、奇数kは両端開となる | 零の符号は今回の表記で統合。実測値の誤差モデルではない |
| DP-L2 | セル全体でqが一定なら、q'をartifactから定められる | 有限入力上限を含む全保存可能性の完全な判定ではない |
| DP-L3 | 同一artifactに写る受理可能な二原値のqが違えば、因子化するq'は存在しない | 反例の発見を自動化したという主張ではない |
| DP-L4 | 符号化がartifactを復元しても、先に失った区別は回復しない | 原要求の別添えを加えた拡大パケットは別の対象 |
| DP-L5 | P2-gと旧handlerを変えず専用schemaを追加すれば、旧経路の観測を保持できる構成になる | 実体・前後比較による回帰が必要。設計だけでは未検証 |

| 個別義務 | 内容 | 主な防護条件 |
| --- | --- | --- |
| DP-1 | 表示方針・型・双方の依存仕様と所有を固定 | P12/P33、N07/N08 |
| DP-2 | 有理数からの直接丸め、負数・半整数・大数 | P01〜P12、N05 |
| DP-3 | 表記・末尾零・零の符号を固定し原表記と分離 | P07/P09/P10/P14/P32/P33 |
| DP-4 | セルの端点・開閉、測定の不確かさとの分離 | P08/P09/P23/P24/P36 |
| DP-5 | artifactだけに因子化する問いに限定 | P22〜P26、P28 |
| DP-6 | 衝突・符号化・別添えを分け、範囲外を認定しない | P25〜P31 |
| DP-7 | 子料金Cの一致・一度の呼出・親の予約・最終料金 | B01〜B04、N11 |
| DP-8 | 行の原子性、最終確定前の認定禁止、完成行の保持 | B02〜B04 |
| DP-9 | 全計画の検証とP2-gの確認・訂正・未知の境界を維持 | P17〜P21/P34/P35、N06〜N09 |
| DP-10 | AI出自・原要求を保持し新しい臨床主張を作らない | P19/P31/P36 |
| DP-11 | 順序・snapshot・表示変更と原情報の独立 | P13/P32〜P35、N12 |
| DP-12 | 非単一点・未知能力・資源・不正・未対応を区別 | P15/P16/P21、N01〜N12 |

R4の3必須義務は§5〜6へ、共通の4義務は識別・停止・原情報・資源へ対応させます。DP-1〜12は今回の個別義務で、汎用義務の自動生成ではありません。

## 9. 次の実装への受入条件

1. P36/N12/B4を手指定期待として保持し、runtimeから正解を生成しない。今回の式の有限点検をruntime試験に数えない。
2. 専用native・handler・R4宣言・fixtureを作る。P2-g/P2-fと旧R4・旧基底は変更しない。変更が要る場合は理由と旧版を残して設計を見直す。
3. 丸めを整数商/剰余と別方式の参照計算で照合する。半整数と前後、負数、開閉、floatで潰れる大数、二重丸め、末尾零、零を含める。
4. セル上の閾値判定を証人点と比較し、preservedの健全性を検査する。範囲外に原回答を紛れ込ませる、逆像を測定誤差へ昇格する、別添えで全体を認定する変異を検出する。
5. 手指定の衝突でartifact同一・原回答相違・符号化後も非回復を実証する。自動衝突探索・有限入力全体の完全な保存判定とは区別する。
6. 子C・共有予算・最終料金・未完了の値と根拠を検査し、全予算を掃引する。最終料金だけ不足する場合も認定を返さない。
7. Python 3.11/3.14でAPI/CLI・生成器・新系列と既存231/52/8/P2 236件を回帰する。現663ファイルのsnapshotと3311eddを追加前の基準として保存してから、40/41・native・例・検査等を明示的に追加する。
8. 現在は設計段階で、runtime・固定対象・評価分母は変更しない。実装後に結果・hash・環境・制限を別文書へ記録し、その後の能力間の併用と原理の整理へ進む。

今回の終了点は意味設計と実装前の条件です。外部の小数字句・有効数字の取込、区間の安全な表示、実単位・臨床の閾値、FHIR出力、実画面、再取込・会計接続、標準化は未完了です。表示射影の研究は、変化に耐える医療コード体系の原理を検査する一段階で、最終目標の代替ではありません。
