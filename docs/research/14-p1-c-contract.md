# P1-c：モデル被覆・合成・再実行の実行契約

作成日：2026-10-19。作成者草案。[P1研究契約](11-p1-contract.md) の H13〜H19 を具体化します。profile は `p1-handover-draft-1`、request/result は `p1-handover-request-draft-1` / `p1-handover-result-draft-1`。P0/P1-a/P1-b の仕様と実行例は変更しません。[native仕様](../../src/med_dsl/handover_spec.json) の生バイトハッシュを handler に固定します。

共通必須項目は schema_version/operation/consumer/budget。consumer は profile/profile_spec_sha256/operations。今回の操作を含む既知操作の非空部分集合のみ受理し、任意コード・自己申告した認定票は実行・採用しません。JSON全体1 MiB・深さ64、max_steps は厳密な整数0〜100000で、一つの要求内で共有します。構造とハッシュの検証後に課金し、資源不足では部分的な認定を返しません。

## 参考意味と有限反例

`check_reference_change` は signature/source/target/queries/models/finite_domain_sizes を取ります。signature は predicates の ref/arity と constants の参照一覧。source/target は theory/data。data は ground の肯定 atom、theory と query は閉じた式です。

式の kind は atom/not/and/or/implies/forall/exists/eq。atom は predicate/args、not は body、and/or は items、implies は left/right、量化は var/body、eq は left/right。項は `{var:…}` または `{const:…}`。自由変数、変数の隠蔽、未知の記号、項数不一致、空の連言・選言は拒否します。最大8述語・8定数・4項、16理論文・16データ・16問い合わせ、全式512 node・深さ16です。

models は id/model。model は非空 domain、全定数の割当、全述語の明示した組の集合で、宣言を省略して空集合を補いません。最大16モデル・各8要素・各関係64組。指定モデルでの真理、source/target のモデルであること、非含意・被覆失敗の反例を分けて返します。等しい旧語彙で identity の文対応・モデル読み戻しだけを扱います。

含意を返せるのは、文の明示、ground の単項 Horn 導出、`∀x(A(x)→∃y(r(x,y)∧B(y)))` と A(a) からの `∃z B(z)` という既知の構文条件です。最後の規則も個体名を生成しません。非含意は有効なモデルと反例がある場合だけ、それ以外は unassessed。一般の一階推論器ではありません。

全モデルの保存を認定する入口は、同じ signature・同じ文集合の identity template に限ります。旧モデルで新理論を満たさない例、新モデルの読み戻しが旧理論を満たさない例を返せれば not_certified。理論の包含で片方向のモデル条件を示せても、両条件が揃うまでは認定しません。1/2要素で一致したことから全モデルを認定しません。finite_domain_sizes は空 signature の純粋等号式だけに使う非空領域サイズの有限検査で、他の signature では空配列にします。

この層の真理・含意は P0 の支持状態と別です。評価は式 node と量化割当ごと、証明候補ごとに課金し、短絡評価します。モデル・query は id 順、式・domain は入力順で処理します。

## 欠落を否定にする意味変更

`check_absence_policy` は source/views/queries を取り、P0 の正の ground 一原子問い合わせを対象にします。未決を opposed とする閉世界方針を診断用に実行し、正の問いと否定リテラルの状態を区別します。新しい否定の根拠は closed_world_assumption として表示し、臨床 assertion は追加しません。未知能力・衝突・打切りを否定に変換しません。現記録の回答が偶然一致しても方針変更の保存認定はしません。

## 事象化と一対一改名の合成

`rename_events` は target/renames/target_ledger_ref を取り、新しい target を返します。renames は from_ref/to_ref の全域単射で、全ての原事象を一度ずつ覆います。新しい事象名の新鮮性を検査し、原と異なる台帳参照への更新を明示します。役割、原由来、確認・訂正、package・依存・文脈は変更できません。

`check_event_chain` は source/relation_ref/intermediate/target/renames/stages/views/queries。原・中間・最終の実体を読み、第一段が P1-b の四役割表現で原履歴を完全に復元し、第二段が上記の改名だけであることを検査します。

stages は2件で、kind/source/target/source_scope_sha256/target_scope_sha256。kind は event_reification/event_rename。端点は profile/profile_spec_sha256/snapshot_sha256/dependencies/policy_ref です。依存はルートを含む実際の閉包の ref/sha256、順序は ref 順。P0仕様のハッシュは固定した契約文書、P1-b は固定 native仕様。P0 の runtime も既知ソースのハッシュと照合します。

原側の範囲は views/queries の canonical hash。中間・最終は P1-b が生成する役割式と旧変数への project を含む翻訳済み範囲の hash です。第一段の出力と第二段の入力を実体・仕様・依存・方針・翻訳後 Q まで照合します。票に並べた参照が同じという理由だけで認定しません。

全条件が成立し実行照合も完了した場合、checked_native_template として **原履歴と、両計算が完了した P0 の正の結合・ground明示否定の支持契約**を certified にできます。証拠は固定した四役割の構成と可逆な改名の条件検査で、有限例の一致だけではありません。一般の一階論理全体、事象の件数・同一性、新所属データ、方針変更、将来の任意言語はこの保証に含めません。対象外 Q と未評価を明示し、全体の認定に混ぜません。

## 射影と、その後の無損失符号化

`check_projection_chain` は source_a/source_b/projection/queries/source_sidecar。二つの旧関係は最大64の四つ組集合。projection は kind=value_set、または kind=columns/positions。queries は id/where/select、where は position/value、select は position/var。各位置0〜3、重複禁止。返す変数は元の位置だけです。

射影した実体を canonical JSON に符号化し、実際に復号して同じ中間値になることを確認します。第二段の認定はこの中間値に限ります。列射影では残った位置だけを使う Q を引き継ぎ、他の Q は対象外。値集合だけへの射影では四つ組の区別を保証しません。同じ中間値で旧回答が違う例を、全体の復元不能の証拠として返します。

source_sidecar は null または relation/sha256 を持つ実データで、source_a と照合します。原記録を別添えで読む回答は sidecar_replay とし、射影だけから復元した認定にはしません。対象外・比較不能の回答は null で、空集合にしません。

## 原保存と旧処理系の可用性

`audit_replay` は archive/available_resources/semantic_chain。archive は bytes_base64/sha256/profile/profile_spec_sha256/requirements、resource は kind/ref/sha256/bytes_base64。kind は runtime/runtime_dependency/semantic_dependency。原バイトと提供された各実体のハッシュを検証します。最大16 resource/requirement、runtime 要件はちょうど一つ。未知 runtime の原バイトを持っていても自動実行しません。可用性の判定範囲は提供 inventory と既知 native registry で、世界中の所在を検索した結果ではありません。

復号した JSON にも通常入力と同じ1 MiB・深さ64・文字と数値の検証を適用します。原バイトが既知の P0 source snapshot として検証できなければ、必要な実行実体が揃っていても ready_to_replay にしません。semantic_chain は null または独立に検査する事象合成要求です。原バイトを JSON として読め、その source が合成要求の source と一致する場合だけ結び付けます。旧 runtime の不足を新意味の成功・失敗に流用せず、新側の認定は別途検査します。ここでは旧バイナリ自体を実行せず、再実行可能性と保存を分けます。

## 共通の停止・証拠

課金は native仕様の steps に固定します。生成・改名は各主張/確認と完成時、新側・旧側の問い合わせは既存の課金、合成は端点・範囲・履歴・改名の各義務と最終票、射影は各組の射影・検索と符号化検証、inventory は各要件と最終報告に課金します。予算0・中間上限超過は resource_limit。未完成の認定・回答・差分は返しません。

反例、既知 template の十分条件、実行済みの照合、inventory の可用性、自己申告を区別します。全て架空データで、医学的な妥当性・独立レビュー・永続性全体の証明は含みません。

## p0-draft-2 での追補（レビュー AI-001）

- すべての `certificate`（`second_step_certificate` を含む）は `certifier`（`kind=native_python_modules`、`files`、`bundle_sha256`）を持つ。束は `src/med_dsl/` の `*.py` と `*.json` の生バイトから作り、共通 manifest の該当行から再計算できる。`profile_spec_sha256` は**仕様JSONの**hashで、実装の同一性は `certifier` が担う。
- 参考意味の不認定の理由は、未証明の側を指す。反例があれば `old_model_not_liftable`／`new_model_reduct_invalid`、反例がなく被覆だけ未証明なら `model_coverage_not_established`、還元だけ未証明なら `model_reduct_not_established`（両方なら両方）。
- 鎖の不認定の理由に、実行照合で回答が食い違う場合の `answers_mismatch` を加える（`incomparable_execution` は未評価・比較不能に限る）。
- P0 の入力検査が変わったため、`P0_SPEC_SHA256`・`P0_RUNTIME_SHA256`・`HANDOVER_SPEC_SHA256` を再固定した（draft-1 の値は e73d4ba の記録を参照）。
