# P1-b：四項関係を事象へ引き継ぐ実行契約

作成日：2026-10-19。実装前に定めた契約を具体化した作成者草案です。[P1研究契約](11-p1-contract.md) の H07〜H12 を具体化します。全モデルの保存認定・合成は P1-c 以降に残し、今回は可逆な履歴の符号化と有限の支持回答を照合します。

## 版と操作

native profile は `p1-events-draft-1`、request/result は `p1-events-request-draft-1` / `p1-events-result-draft-1`。P0 と P1-a の既存形式・固定仕様は変更しません。[機械可読仕様](../../src/med_dsl/events_spec.json) の生バイトハッシュを handler に固定します。共通必須項目は schema_version/operation/consumer/budget。consumer は profile/profile_spec_sha256/operations で、operations は既知操作の非空部分集合、今回の操作を含むものに限ります。自己申告した任意能力や実行コードを受け付けません。

| 操作 | 追加必須入力 | 出力 |
| --- | --- | --- |
| reify_events | source/relation_ref/target_ledger_ref | 完成した target と source の読み戻し一致・ハッシュ |
| restore_events | target | 完全に読み戻した source と原・先ハッシュ |
| query_events | target/views/queries | 役割付き事象を実際に評価した旧 Q の支持回答 |
| compare_event_handover | source/relation_ref/target/views/queries/translation | 原履歴・採用・有限回答の一致、不一致・対象外・未評価と根拠 |

source は package/dependency_packages/contexts/ledger。P0 と同じ厳格な検証を適用し、relation_ref は依存閉包内の一つの四項述語でなければなりません。元の役割名を勝手に変えず、四つの位置を新しい key/specimen/method/value へ対応させます。その他の述語と単項定義規則は保存します。

## 事象と原履歴

target は schema_version/profile/profile_spec_sha256/source_sha256/source_ledger_ref/relation_ref/package/dependency_packages/contexts/ledger。ledger は新しい ref と元の全 assertion/review を持ちます。assertion の atom を statement に置き換え、それ以外の id/文脈/極性/確実性/時刻/由来/supersedes/必要能力/change_reason をそのまま保持します。review も省略しません。

対象四項述語は `statement={kind:event_tuple,event_ref,source_assertion,roles}`。source_assertion は原 ledger_ref/id。roles は key/specimen/method/value の四つの非空文字列だけです。欠落、配列による複数値、余分な役割を拒否します。他の述語は `statement={kind:unchanged_atom,atom}` のままです。

生成する event_ref は原台帳と assertion id の canonical digest による `urn:med-dsl:event:…`。同じ key や四つ組でも原主張ごとに別IDです。生成・受入の両方で原 snapshot に現れる既存の文字列との衝突と、事象ID間の衝突を検査します。受入時は別の新鮮なIDも認め、特定の命名規則自体を意味の条件にしません。原・先台帳参照は異なる必要があります。複数リクエスト全体の名前の所有権管理は実装しません。

statement から元の atom を復元し、source_sha256 と照合します。全履歴の配列順、由来、訂正関係、確認者を復元し、原情報の別添えだけで元の関係の問い合わせを代行しません。入力は変更しません。変更した target を比較する場合も、まず target 自身の読み戻しハッシュを正しく与える必要があり、不正なハッシュを不一致の代わりに受け入れません。

## 問い合わせと採用

views は P0 の id/as_of/policy_ref。queries は id/context_ref/kind/required と、kind=legacy_positive の場合に atoms が必須です。原 Q は P0 と同じ正の結合・公開変数最大4。その他の kind は atoms を持たず、out_of_scope/unassessed とし、件数・新事象の同一性を推定しません。

各四項 atom を Active(z) と四役割へ展開し、同じ一つの新鮮な z を使います。ユーザー変数と衝突しない内部変数を選び、結合完了後に元の変数だけへ射影します。同じ旧 binding の重複を除き、複数の主張・確認の根拠は統合します。問い合わせは実際の採用済み事象の役割表から評価し、P0 の再実行結果を新側の回答に流用しません。

P0 の採用関数を、復元した assertion envelope と同じ view・方針に適用します。採用済み肯定の event_tuple だけが Active と役割表を作ります。negative は完全な四つ組の否定索引へ入り、個別役割を否定しません。疑い・未確認・訂正済みも target に保持します。元の未知 required_capabilities を取り除いたり、表現を理解できることだけで新たに容認したりしません。未知能力と文脈全体の衝突は P0 と同じ停止規則です。本人・家族・時点・用途が異なる文脈を統合しません。

## 比較と証拠の強さ

translation.kind=shared_event は上記の正しい展開です。split_roles は各役割を別の Active 事象で満たせる既知の誤翻訳で、反例の診断専用に受け付けます。任意の翻訳コードは実行しません。誤翻訳を指定した比較では正しい展開も別に評価し、共通予算へ課金します。

比較は原履歴の読み戻し、採用 metadata、完了した旧 Q の状態・binding・元の assertion/review/definition 根拠を照合します。台帳は原・先を区別して出力に固定します。conflict・unknown capability・計算打切りは比較不能で、差分は null。対象外 Q は別に返します。未決同士の完了一致は支持計算上の一致で、一般の古典論理での非含意の証明ではありません。

誤翻訳で余分な binding が出た場合は not_certified と反例を返します。H10 の source_truth/correct_target_truth/incorrect_target_truth は、原履歴が同じで衝突・未評価がないときの、採用済み肯定関係を完全な有限関係とした**列挙モデル内の真理**です。臨床情報の欠落を偽としたものではありません。

有限照合が全て一致しても certificate は not_certified、evidence_level=finite_execution_check です。C1 の全モデルの被覆等の十分条件を実行認定したとはしません。原理の手作業の構成、実行の支持、有限モデル反例は別の証拠です。

## 上限と停止

request と単独 target は1 MiB・JSON深さ64。P0 の各1000 context/assertion/review、64 view/query/atom、公開変数4を継承します。正しい展開は最大320 atom・内部込み68変数、誤翻訳診断は512 atom・260変数。新側の中間 binding は4096、公開 binding は1000まで。原側の再実行は P0 の従来の上限・課金を維持します。

max_steps は厳密な整数0〜100000で、比較の原・正しい新側・誤翻訳で共有します。構造・参照・ハッシュの検査は課金前ですが入力上限で制限します。課金点は機械可読仕様の steps と同じです。request 開始1、生成・読み戻しは assertion/review 各1と完成時1。新側は view ごと assertion/review 各1を前払いし、各 query の開始・完成各1、単項閉包の候補・結合候補・内部 binding の射影各1。比較は履歴照合1、P0再実行の既存課金、新側の課金、完了して比較可能な各行の照合1です。

途中まで作った artifact・一問の binding・差分・認定を返しません。完了済みの別の問い合わせは保持します。資源不足を入力不正や意味の喪失に読み替えず、resource_limit/unassessed として対象を残します。永続保存・臨床評価・独立レビューは未実施です。
