# R6：P0 の意味・入出力・受入条件

作成日：2026-10-18。契約版：`p0-draft-1`。状態：P0 全体の研究仕様。P0-a〜d の実装と作成者草案による全22ケースの照合は [最新の実行記録](10-p0-d-results.md) にあります。独立確認後の評価は未完了です。期待結果は作成者草案です。[短い試作仕様と D07](06-prototype-brief.md) を入口にします。

## 1. 三つの操作

CLI は `PYTHONPATH=src python3 -m med_dsl <request.json>`、草案例は `--fixture <fixture.json>` で request だけを読みます。ライブラリの `evaluate(request)` を同じ入口で使い、入力を変更せず結果を返します。check_extension、query、compare を実装済みです。P0-d で指定した支持問い合わせの前後比較を追加しました。

| operation | 入力 | 主な出力 |
| --- | --- | --- |
| `check_extension` | `base_package`, `extension` | 保存の認定 `certificate`、旧語彙・新記号・依存版・十分条件と適用範囲。未認定でも危険とは断定しない |
| `query` | `package`, `contexts`, `ledger`, `views`, `queries` | 各参照時点での採用・保留・訂正・衝突、問い合わせ結果と根拠 |
| `compare` | `before`, `after`, `view`, `queries` | 同じ Q の回答差・根拠・未評価範囲。両 snapshot は `package/contexts/ledger` を持つ |

すべて `schema_version="p0-request-draft-1"` と `budget` を必須にします。operation にないトップレベル項目は入力不正です。ファイル・ネットワーク・時刻の暗黙取得はせず、依存物を入力内で解決します。外部 master の候補生成や ConceptMap `$translate` の実装は含めません。

## 2. 定義パッケージと保存認定

`package` は `ref`, `profile`, `predicates`, `definitions`, `inclusions`, `dependencies` を持ちます。`ref` は不変な版付き参照、`profile` は `p0-positive-1`、predicate は `ref` と順序付きの `roles` を持ちます。アリティは roles の長さで、役割名の重複は不可です。包摂は単項述語に限ります。

| 項目 | 形式・制限 |
| --- | --- |
| `definitions` の S1 | `{kind:"defined", symbol:N, all_of:[A,B,…]}`。新しい単項 N と同じ変数に対する正の連言との同値。右辺は一つ以上、同じ項目の重複不可 |
| `definitions` の S2 | `{kind:"subtype", symbol:N, parent:A}`。空でもよい新しい単項 N の包含 `N⊑A` |
| `inclusions` | `{sub:A, super:B}`。既存パッケージでは単項包含として解釈。追加パッケージの一般的な包含は構文上受け取れても自動認定の対象外 |
| `dependencies` | `{ref, sha256}`。指定参照と実体ハッシュを照合。最新版へ自動解決しない。P0 の依存実体は request 内のパッケージ集合で与える |

最初の三例は依存なしです。依存ありの request は操作共通の `dependency_packages` 配列を持ち、空の場合は省略可とします。同じ参照で異なる実体、未解決・循環する依存は入力不正です。profile 自体の版も照合します。check_extension では旧側の依存閉包を先に単独検証し、extension の参照は旧側と追加側の和で解決します。旧側が追加側の新語彙を暗黙に参照することは許しません。

`extension` は同じ項目を持ち、旧 package の内容を置き換えず追加します。認定には、次の条件を**全モジュールの依存閉包**で要求します。

1. 新記号は旧語彙に存在せず、各記号の導入主体と定義は一つだけ。
2. 各新記号には S1 または S2 の定義がちょうど一つあり、役割は単項。右辺の述語とも役割名が一致すること。同じ symbol への複数定義は、重複 ID として入力不正にする。
3. 右辺・parent の参照が解決でき、定義の依存は全体で非循環。順序が違うだけなら依存順へ並べ直してよい。
4. 一般の追加包含、旧記号の再定義、新しい存在・非空条件、暗黙の制約追加がない。
5. 保証は旧データを固定した旧語彙の文に対するもの。新概念への所属データ追加・採用方針の変更はこの認定の保証外。

S1/S2 の混合は、この順序で旧モデルへ新記号を拡張できる場合に限ります。同じ新 N を S1 と S2 の両方で導入する更新は認定しません。`N↔A` と `N⊑B` を二枚の個別認定だけで併用して `A⊑B` を暗黙追加する抜け道を防ぎます。

認定結果は `certified / not_certified`。参照・構文の不正は操作全体の `invalid_input` です。`not_certified` は非保存の証明ではありません。原理上の根拠は [R5 の S1/S2](05-principles.md) です。認定票には `method`, `old_signature`, `introduced`, `base_sha256`, `extension_sha256`, `scope`, `reason_codes` を必須にします。method は `p0-s1-s2-dag-1`、scope は旧データ固定・論理プロファイル・保証対象を明示します。保証は定義理論の保存で、ledger の採用方針・追加記録まで含めた全回答の不変性ではありません。

## 3. 主張と文脈

文脈は `ref, subject_ref, effective_at, purpose`。P0 の日時はすべて有効な暦日時の `YYYY-MM-DDTHH:MM:SSZ` に限定し、期間・小数秒・時刻推測・別時差の暗黙変換は扱いません。subject と対象時点と purpose が異なる文脈を自動統合しません。二検体などの複数事象は、同じ文脈でも引数内の明示的な事象 ID で区別します。

`ledger` は `ref, assertions, reviews` を持ちます。

assertion/review のローカル ID は ledger の版付き参照と組み合わせて識別します。異なる ledger の `h1` を同じ主張とみなしません。query/view の ID は一つの request 内で一意にします。定義・文脈・由来の ref は名前空間を持つ参照として照合します。

| 要素 | 必須項目 |
| --- | --- |
| assertion | `id, context_ref, atom, polarity, certainty, recorded_at, origin, supersedes, required_capabilities` |
| atom | `predicate, args`。args は役割順の参照文字列。引数数が役割数と一致すること |
| polarity | `positive / negative`。欠落から negative を作らない |
| certainty | `confirmed / suspected`。新しい状態を勝手に confirmed へ変えない |
| origin | `kind, ref`。kind は `observed / judgment / imported / ai_candidate`。いずれも原情報の参照を持つ |
| review | `id, assertion_ref, reviewer_ref, reviewer_kind, recorded_at, outcome`。P0 の outcome は `confirmed`、reviewer_kind は `human` |
| supersedes | 置換する旧 assertion ID の配列。空でなければ `change_reason` も必須 |

確認記録は assertion と別の記録です。AI が生成したことだけを根拠に確認済みへ自動昇格させません。P0 は入力された架空の確認記録を前提として参照整合を検査し、確認者の本人性・権限を実認証する機能は持ちません。実運用では、確認記録の発行主体を保証する接続層が別に必要です。

`view` は `id, as_of, policy_ref`。初期 policy_ref は `fiction:confirmed-explicit-revision@1` のみです。選択は次の順序とします。

1. `recorded_at <= as_of` の主張と、その時点までの確認記録だけを使う。
2. 人の確認記録があり certainty=confirmed の主張を採用候補とする。疑い・未確認 AI 候補は履歴に残して保留する。生成元が AI でも、別の人の確認記録が揃った後の採用は、その根拠を残して区別する。
3. 採用候補からの明示的な supersedes により旧主張を現採用から外す。置換先も同じ context と符号を除いた atom を持ち、置換元より後に記録されていること。将来・未確認の訂正では旧主張を外さない。
4. 訂正の連鎖では、参照時点までに有効になった置換関係の対象をすべて外す。後の訂正で古い旧主張を黙って復活させない。
5. 未解消の肯定・否定の衝突は報告する。多数決、最新優先、AI の信頼度による自動裁定はしない。

返却する `views` の各要素に `id, visible_assertions, adopted_assertions, pending_assertions, superseded_assertions` を記録し、各 ID の集合はソートします。原 ledger は変更しません。adopted/pending/superseded は相互に重ならず、訂正済みの疑いを pending に残しません。adopted は方針の条件で選ばれた記録であって真理の宣言ではなく、衝突や未知能力があれば後述の問い合わせを停止します。`retained_assertions` は入力全体の ID 一覧で、参照時点で見えていた主張一覧とは別です。

## 4. 問い合わせの意味を二層に分ける

**主張の支持と、任意の論理体系における真偽を同一にしません。** P0 の結果名を、R4 の一般の Entails/Refutes と無条件に同一視しないことを契約に含めます。

| 層 | P0 の意味 |
| --- | --- |
| 正の計算 | 採用した肯定 atom と、単項包含・S1 の正の連言定義から得る有限の Horn 閉包。各文脈を分け、引数にない事象・個体を生成しない |
| 否定記録 | 採用した negative assertion の検索。これを任意の古典論理の否定推論器へ投入せず、対偶・背理・未記載からの否定を行わない |
| 衝突 | 正の閉包と同じ context・同じ atom の否定記録がある場合。該当文脈の確定回答を止め、双方の根拠を返す |

S1 の計算は `N→A`, `N→B`, `A∧B→N` に対応します。定義依存が非循環でもこの実行規則には往復があるため、単純な再帰展開を無制限に繰り返さず、有限の atom 集合の固定点として計算します。保存認定の範囲と、実装する問い合わせ断片も別に宣言します。P0-b の query は循環包含・循環定義も有限の固定点として計算できますが、循環定義に保存認定は発行しません。各 view・context の閉包を完了してから衝突を調べ、同じ view・context の後続質問には閉包を再利用します。打切った閉包は再利用しません。

query は `id, context_ref, atoms, required` を持ちます。atoms は一つ以上の正の atom パターン、定数は参照文字列、変数は `{var:"result"}` です。同じ変数は同じ参照に結合し、変数の直積を根拠なく生成しません。query 中の変数はすべて返す集合の意味とし、重複 binding を除きます。参照文字列の同一性だけで結合し、別参照間の同一人物・同一事象を暗黙に推論しません。未束縛変数の返却、同一文脈を越えた暗黙の結合、集約、OR、一般の NOT は対象外です。

| result.status | 条件 |
| --- | --- |
| `supported` | 正の問い合わせの binding が閉包にある。ground query の成功 binding は `[{}]` |
| `opposed` | 単一の ground atom の問い合わせで、採用した同一 atom の否定記録があり、正の支持はない |
| `undetermined` | 対応断片で完了したが支持 binding がなく、上記の明示的な否定支持もない。一般の古典論理での非含意を保証する名前ではない |
| `conflict` | 該当文脈に未解消の支持・否定の衝突がある。bindings は返さず衝突根拠を返す |
| `unassessed` | 必要能力が未知、式が断片外、資源上限に到達。理由を必ず付ける。空の正常回答としない |

複数 atom の論理的否定を P0 は判定しないため、結合が見つからないだけなら opposed にしません。negative assertion から定義を通じた対偶を計算しないので、「その否定が古典論理でも導けない」とも主張しません。R4 の論理差分成績を集計するには、対応する意味プロファイルと期待値を別途確認する必要があります。

`required=true` で supported にならない場合、記録の利用者へ返す情報要求を別に付けます。undetermined は `needs_information`、conflict は `needs_resolution`、unassessed は `needs_capability_or_completion`。情報要求を「その検査法は存在しない」等の臨床的な否定に変えません。

未知の `required_capabilities` を持つ可視主張がある文脈は、その意味上の影響を判断できないため unassessed とします。未知の否定修飾を削除して肯定を返しません。表示専用として無視できる項目は、既知の意味契約で確認したものだけに限ります。

この停止は保留・訂正済みを含む全ての可視主張を対象にし、未来の主張は対象にしません。未知修飾が訂正や主張選択の意味まで変えるかを判断できないため、既存方針で訂正済みになったことだけを理由に無視しません。停止は該当文脈に限定し、別文脈の回答を止めません。P0-c は不足能力の `missing_capabilities` に加え、その能力を必要とする可視主張 ID の和を `blocking_assertion_refs` としてソートして返します。単に未知の名前を原情報として保持できることは、意味を理解できることではありません。

## 5. 前後比較と出力

compare は同じ view の参照時点・方針と同じ Q を二つの snapshot に適用します。新旧の context 参照を対応付ける場合は `context_map` を明示し、subject/effective_at/purpose の一致を確認します。初期例では同じ context_ref を使います。

P0-d の snapshot は `package, contexts, ledger` だけを持ちます。`view` は共通の一つで、各 query の context_ref は before 側を指します。context_map の形式は `[{before_ref, after_ref}]`。省略した参照は同じ参照へ対応し、明示対応は存在する参照間で一対一に限ります。暗黙の同一参照への対応も含めて合流を拒否し、subject_ref/effective_at/purpose の一致を検査します。同じ context_ref のメタデータを変える入力も拒否します。Q の述語・役割・引数は左右両方で妥当であることを要求し、片側の未宣言語彙を自動注入しません。

両側のパッケージ参照と supplied dependency_packages を一つのレジストリで照合します。各側の推論はその側の明示依存閉包だけで実行し、他方の理論を暗黙に混ぜません。同じ package ref の異なる実体を拒否し、異なる package 版でも同じ predicate ref の roles と明示定義は構造が一致することを要求します。一般包含を別版で追加・除去することとは分けます。明示定義の構造比較は論理的同値の完全判定ではなく、同じ all_of の並べ替えも同一構造とはしません。

同じ ledger ref に異なる実体を与えることも入力不正です。台帳を変更した snapshot は別の版付き参照にします。異なる台帳の同じローカル h1 を同一主張として統合しません。両側を検証し終えてから計算するため、計算予算 0 でも入力不正を先に返します。

前では支持され後では支持されない binding を `lost`、後で新たに支持される binding を `added` とします。これは**指定した支持問い合わせの差**で、外部コード全体の意味差分や、医学的な新事実の有無とは別です。左右いずれかが unassessed/conflict ならその問い合わせを比較不能として残し、lost/added を空集合と断言しません。追加の補助情報・原記録を使う場合は別 snapshot として B0/B1 を分けます。

compare の `scope` は `positive_query_bindings`。before/after にそれぞれ query の結果・採用履歴・定義根拠と、package_ref・ledger_ref・snapshot_sha256 を返します。snapshot のハッシュは package/contexts/ledger 全体の正規化 SHA-256、依存実体は package の指定ハッシュと入力全体のハッシュで固定します。

compare の `results` は query ID 順です。各行は view/query、before_context_ref/after_context_ref、before_status/after_status、status、lost/added/unchanged、lost_evidence/added_evidence、reason_codes を持ちます。左右が supported/opposed/undetermined のいずれかなら status=compared とし、binding の差・共通部分をソートして返します。喪失根拠は before、追加根拠は after から取り、それぞれ ledger_ref を付けてローカル ID の所属を明示します。否定支持や根拠だけの変化は支持 binding の追加・喪失とはしませんが、両側の状態・根拠は残します。

どちらかが conflict/unassessed なら status=incomparable とし、差分・共通部分・差分根拠の五項目は null、理由には側を付けます（after_conflict、after_unknown_capability、after_step_limit 等）。比較不能の query を incomplete に列挙します。上限到達で全体 status が resource_limit になっても、既に左右の計算を完了した query の比較は残します。根拠が異なるだけで同じ binding が支持され続ける場合は unchanged で、両側の evidence を参照します。

結果は `schema_version="p0-result-draft-1"`, `status`, `profile`, `input_sha256` と操作固有の値を持ちます。query の `results` は view ID・query ID 順、各 binding は変数名順に比較した組の順とし、根拠 ID の集合もソートします。result は `view, query, status, bindings, evidence, reason_codes` を持ちます。evidence は各成功 binding に対する `{binding, assertion_refs, review_refs, definition_refs}` の配列です。opposed/conflict の場合も、それを支持する同形式の根拠を残します。P0-c の conflict は `conflicts` 配列に、衝突した ground `atom` と `positive_evidence`、`negative_evidence` を atom 順で返します。既存の evidence に集約した両根拠も維持し、どの主張・定義がどちらの符号を支えるかを区別できます。

P0-b の定義根拠は `package_ref#/definitions/添字` または `package_ref#/inclusions/添字` です。query の `definition_sources` に参照・package_ref・package_sha256・入力内 pointer を返し、不変な入力の規則へ遡れます。配列順を変更したパッケージは別ハッシュ・別実体です。同じ直接 atom の主張・確認は集約し、導出では深さの小さい証明を優先、同じ深さなら assertion/review/definition のソート済み参照列を順に辞書比較して一つを選びます。事実ごとに証明を改善して固定点まで計算する方式で、全証明の列挙・全ての代替根拠・全体最小の証明は保証しません。問い合わせの結合で同じ binding に集まった根拠は従来どおり集合としてまとめます。

応答のトップレベル status は `ok / invalid_input / unsupported_profile / resource_limit`。意味上の衝突・未知能力等は `results[]` の status と理由にも残します。`ok` は医学的妥当性や全項目の評価完了を意味しません。入力の正規化 SHA-256・契約版を結果に固定し、実装コミット・実行日時・所要時間は再現比較から分けた実験票で記録します。操作が失敗した場合は reason_codes と未完了の範囲を必須にし、成功時だけの項目を偽装して埋めません。

## 6. JSON・資源・再現性

UTF-8 の単一 JSON object を受け取り、重複 object key、NaN/Infinity、浮動小数、未知の schema_version、役割数違い、未宣言述語、同じ主張 ID の異なる再定義を拒否します。整数・真偽値・null は schema で認める位置だけに限り、ID・日時・数量参照は文字列です。欠落を null や偽へ補完しません。

ハッシュ用の P0 正規化は、浮動小数を含まない object に対する `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)` の UTF-8 とします。Unicode・配列の順序・参照文字列は勝手に書き換えません。これは本プロジェクトのハッシュ規約で、標準の JSON 正規化方式への適合を主張しません。入力ファイルの生バイトのハッシュも実験票に別途残します。

| 上限 | 初期値 |
| --- | ---: |
| 入力ファイル | 1 MiB |
| パッケージ数／view 数／JSON の深さ | 各 64 |
| 文脈数 | 1,000 |
| 全パッケージの述語／定義 | 各 64 |
| 全パッケージの包含／一問の atom 数 | 各 64 |
| 台帳の主張／確認記録 | 各 1,000 |
| 関係のアリティ | 8 |
| 問い合わせ数／一問の変数数 | 64／4 |
| 一問の返却 binding 数 | 1,000 |
| `budget.max_steps` | 100,000（0 も指定可） |

steps は規則の ground 適用候補の検査一回、または問い合わせで一つの候補 atom と現在の binding の照合一回ごとに 1 とし、実行順序は参照・atom・規則の辞書順で固定します。上限を超える次の操作の前に止め、完了していない一問の途中 binding を完全回答として返しません。0 は計算開始前の打切りです。時間や CPU に依存する決定不能性の判定ではありません。

compare の max_steps は左右で共有し、before の query ID 順を計算してから after を計算します。片側ごとに予算をリセットしません。一般の集合差の計算は ground 規則・atom 照合とは別であり、このカウンターへ追加しません。入力サイズは request 全体、パッケージ数・述語・定義・包含は両側の到達閉包の和を対象とします。パッケージは参照で、述語は同じ不変な参照で重複を除き、定義・包含は別パッケージの項目数を合計します。文脈と台帳の各件数上限は snapshot ごとです。

P0-b の認定操作は開始に 1、追加包含の検査・新記号の定義有無の検査・未訪問の定義の訪問・定義依存辺の検査に各 1 step を使います。構文・依存ハッシュの検証には件数・サイズ上限を適用し、認定計算の途中打切りでは certificate を返しません。推論は body の辞書順先頭の述語にある各 atom を ground 候補として数え、残りの連言要素も同じ引数で検査します。証明改善後の再走査・固定点の確認にも候補ごとに課金します。

サイズ・件数上限も request の resource_limit とし、未完了の結果は unassessed、比較不能の理由を `resource_limit` にします。上限に合わせて黙って入力や候補を削除しません。Python の最小版 3.11 と実行確認済みの版は別記し、3.11 自体は現環境で未検証です。

## 7. 受入ケース P01〜P22

R4 の既存ケースを置き換える評価セットではありません。P0 の実装受入条件です。全件は作成者草案、P0-d で全 22 ケースを [37 の JSON 入出力例](../../examples/p0/README.md) に具体化しました。作成者草案の指定パス・再実行の照合を評価スクリプトで記録します。独立確認後の正解による評価・R4 全体の評価とは分けます。

| ID | 入力・操作 | 必須の期待結果 | 根拠・対応 |
| --- | --- | --- | --- |
| P01 | 旧 A,B に新 N を `N↔A∧B` で追加 | certified。旧語彙とデータ固定の条件を認定票へ記録。A(a),B(a) を別の query 入力にすると N(a) を支持し根拠を追跡 | S1 |
| P02 | 旧 `A⊑B` に新 `N⊑A` を追加。データは A(a) だけ | certified。旧 B(a) は支持、N(a) は未決。N の存在を捏造しない | S2／K02 |
| P03 | 新 N と、追加包含 `A⊑N,N⊑B` | not_certified。旧 B(a) が増え得る反例をケース根拠に残す。非保存の完全判定器とはしない | K03 |
| P04 | 同じ N を共有する二更新を併用 | 単独の確認票だけで certified にしない。共有記号と全体の追加包含を検査 | K04 |
| P05 | `N↔M`, `M↔N` の循環定義 | not_certified。条件外であって危険の証明とはしない | S1 の限界 |
| P06 | 依存版は固定だが指定 hash と実体が違う | invalid_input。最新版へ黙って置換せず、依存参照を返す | I1 |
| P07 | e1/s1/m1/陽性、e2/s2/m2/陰性の二観察 | e1,s1,m1 の結果だけ陽性。s2,m1 の組は未決。読み戻しで元の二組を復元 | G1／K09 |
| P08 | P07 を各値の集合へ射影し、同じ結合 Q を前後比較 | 元の binding を lost とする。値集合から誤った結合を作らない | G1／U1 |
| P09 | 人の確認がない AI 候補だけが p を主張 | p は未決、候補主張は保留・原情報は保持。確認済みへ昇格しない | D22 |
| P10 | t1 の疑い h1 を、同じ対象時点について t2 の確認済み否定 h2 が明示訂正 | t1 では疑いを保留し事実は未決。t2 では opposed、h1 は訂正済み。両主張を保持 | R1／K07 |
| P11 | 同じ X で家族の肯定と本人の否定 | 本人の肯定を返さず、対象者の違いを衝突としない | K08 |
| P12 | 同じ文脈・atom に確認済み肯定と否定、訂正関係なし | conflict と両根拠。最新・多数決で裁定しない | R1 |
| P13 | 観察対象時点は同じで、記録時点・確認時点が異なる | as_of より後の主張・確認を使わない。対象時点と記録時点を入れ替えない | I5 |
| P14 | 可視主張に未知の意味修飾の必要能力 | 該当文脈を unassessed。修飾を捨てた肯定を出さず、原情報を保持 | K13 |
| P15 | 方法が新たに必須。方法の query を required=true にする | 既存台帳から得られれば出典付き supported。なければ needs_information。AI で補完しない | K14 |
| P16 | 同じ版付き package 参照または主張 ID に異なる実体 | invalid_input。同じ参照の意味を上書きしない | I1・I2 |
| P17 | 新しい存在証人を要求する意味能力の package を、P0 以外の profile として指定 | unsupported_profile。未決や対応なしと混同しない。P0 の atom 書式を壊した式なら別に invalid_input とする | K05 の範囲外 |
| P18 | 有効な入力だが max_steps=0。別に binding 上限超過も用意 | resource_limit と未完了を返す。正常な空回答や部分的な全件回答にしない | D16 |
| P19 | S2 認定後に新しい N(a) という観察を加える | A(a) の支持が増え得る。旧データ固定の認定とデータ追加の差を区別する | S2 の前提 |
| P20 | 同じ新 N に S1 の `N↔A` と S2 の `N⊑B` を別々に付ける | 同じ N の二重導入を invalid_input として拒否。個別認定を足して A⊑B を保存扱いにしない | 合成の反例 |
| P21 | 定義 `N↔A`、確認済み negative N のみ | N の ground query は opposed、A は P0 では未決。古典論理の対偶未対応を明記し、一般の ¬A の非含意とは言わない | 支持と含意の分離 |
| P22 | 同じ架空入力の二回実行、入力配列を並べ替えた実行 | 意味結果・binding・根拠集合が一致。生入力・正規化 hash の違いは別記。原入力を変更しない | I2・I8 の一部 |

P22 の並べ替えは、同じパッケージ実体を固定したまま contexts/views/queries/assertions/reviews と、結合問い合わせの atoms の順を変更するものです。役割の順と atom の引数順は意味を持つため変えません。定義配列の並べ替えもパッケージのハッシュ・根拠 pointer を変えるので、同一実体の並べ替え試験には含めません。正規化入力ハッシュを除いた結果全体を比較し、ハッシュの違い自体は保持します。これは契約版・実装・上限を固定した再現性の検証で、異なる実装間の互換性の証明ではありません。

P01・P02・P07・P10・P15 の正例は必ず結果を返すことを求め、全棄権を通しません。全件の期待値からの逸脱 0、誤認定・裏付けのない確定 0 を最低条件にします。未対応の一件を結果表から削除して分母を縮めません。原理の証明、未見性能、臨床精度をこの 22 件だけで認定しません。

## 8. 実装と検証に使う既存機能

Python の [json](https://docs.python.org/3.11/library/json.html) の重複キー取得・非有限数の処理、[hashlib](https://docs.python.org/3.11/library/hashlib.html) の SHA-256、[unittest](https://docs.python.org/3.11/library/unittest.html) のテスト実行を使う方針です。2026-10-18 に公式の 3.11 系文書で確認しました。独自に作るのは、P0 の参照検証、意味の断片、選択方針、認定と比較です。

配置は `src/med_dsl/`、テストは `python3 -m unittest discover -s tests` です。model/validation/definitions/ledger/query/compare/cli と公開 evaluate を実装済みです。全 22 ケースの記録は `python3 scripts/research/evaluate-p0.py --cli` で再現できます。標準ライブラリの unittest を使い、新しいテスト framework、サーバー、アカウント、JavaScript 依存は追加していません。

各段階の開発テストは、事前草案とテスト内の明示的な派生入力で進めます。P01〜P22 の全受入評価の前には全件を JSON 化し、実装コミット、草案入力・期待値の hash、profile、上限を実験票へ固定します。これは作成者草案による工学的検証です。R4 の独立確認・裁定後の正解凍結は別途行い、現在の草案スナップショットを独立確認済みと呼びません。
