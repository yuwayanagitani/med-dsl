# P2-d：評価の固定、版の手順、独立確認の準備（設計）

作成日：2026-10-19。契約版：`p0-draft-2`。状態：**作成者（AI-001）の単独・内部実施の設計。独立確認前**。[P2 の研究設計](19-p2-design.md) の §8 の P2-d（評価の固定、独立確認の準備 PO13〜PO18、版の手順の実演）を、実行できる形にします。結果は [28](28-p2-d-results.md)。対象は拡張契約（P2-a〜P2-c）の**検査の仕組み**であり、拡張の医学的な正しさ、体系の永続性、将来の全変化への耐性は対象にしません。例・識別子はすべて架空で、外部資料・患者情報・実データは含みません。

**2026-10-20 運用方針の更新**：以下はP2-d実施時点の設計です。現在のリポジトリは独立の確認者を置かずに進めます。§5の独立確認の準備は、将来、英語で記述する別リポジトリで、確認が必要な時点からG0を再開するための資料として保持します。[決定記録](29-review-repository-policy.md) を参照してください。

## 1. 何をするか、しないか

| する | しない |
| --- | --- |
| 統合評価 `evaluate-p2.py`：P0・P1 の固定対象の整合を確かめたうえで、拡張の登録・P2 の例・共通予算の不変条件・版の比較を、固定した分母と照合する | `evaluation_frozen` を true にすること（凍結は独立確認の後。この段階の「固定」は、分母と実体の hash を固定して変更を見落とさないこと） |
| X12：全要求に共通の予算の不変条件を課し、検査器自体の検出力を確かめる | 拡張ごとの意味の正しさの検査（これは各拡張の義務と手作業の導出に残る） |
| X11：`p0-draft-1` → `p0-draft-2` の版の手順を、git の履歴を使って再現する（版の記録、比較器、テスト） | 履歴にない版、将来の版の予測。有限の旧入力での成功を、版の一般の保存の証明とは扱わない |
| 独立確認の資料：PO13〜PO18 の命題・証拠・反例の探し方・覆り得る内部判断・再開点、変異表・生成器・前後比較の整備 | 独立の確認者の確保、独立確認済みの主張、評価の凍結 |

## 2. 評価の固定

### 2.1 統合評価

[evaluate-p2.py](../../scripts/research/evaluate-p2.py) は、次を順に行い、結果を `data/research/p2-d/`（Git 管理外）にだけ書きます。期待結果の自動更新はしません。

1. **P0・P1 の固定対象**：`evaluate-p1-d.py` の lock（`examples/p1-evaluation/manifest.json`）の整合（実体から再構成した台帳との完全一致）と、P1 20 条件・80 JSON・417 必須パス、P0 37 JSON・221 必須パスの期待。
2. **拡張の登録**：`extensions/*.json` 12 件を、依存の順に登録し、宣言した防護例を実際に評価する。
3. **P2 の例**：`examples/p2`（防護例）、`examples/p2-split`、`examples/p2-splits` を、手で指定した期待と照合する。
4. **共通予算の不変条件**（§3）：203 要求。
5. **版の比較**（§4）：git の履歴に旧版のコミットがあれば実行し、なければ「行わなかった」と記録する（合格にも不合格にも数えない）。
6. 評価の前後で lock が変わっていないこと（`snapshot_changed_during_evaluation`）。

### 2.2 固定する分母

分母は P0・P1 と別に数えます。値は宣言と例の台帳から数えて固定したもので、実装の出力から生成していません（`budget_evaluations` だけは、予算の掃引の評価回数を測って固定）。食い違えば `mismatches` に位置が出て失敗します。

| 項目 | 固定値 |
| --- | --- |
| 拡張 | 登録 12／拒否 0。義務 112、防護例 238、防護例のない義務 3（`R1-3`・`R3-3`・`COMP-3`） |
| 証拠の強さ（義務ごと） | `checked_native_template` 95、`finite_check` 9、`hand_derivation` 8、`self_declared` 0、`individual_io` 0 |
| 拡張の独立 | 基底を除く 11 件の 55 組のうち 42 組が独立 |
| P2 の例 | `p2` 35 例・128 必須パス、`p2-split` 34 例・224、`p2-splits` 38 例・221 |
| 予算 | 203 要求、掃引の評価 2,936、違反 0、予算に依る拒否の許容 1 件 |

### 2.3 固定対象への追加

[evaluate-p1-d.py](../../scripts/research/evaluate-p1-d.py) の固定対象（`EXTENSION_PATTERNS`）に、P2-d の実体を加えます：共通部品 `scripts/research/p2_checks.py`、版の比較 `scripts/research/compare-versions.py`、独立確認の資料 `scripts/research/p2/*.py`、版の記録 `examples/p2-versions/*.json`。`evaluate-p2.py` は既存の `evaluate-*.py` の規則で入ります。変更すると、明示的な `--create-snapshot` と、`audit-preservation.py` の定数の更新が要ります（この定数を持つ `audit-preservation.py` は循環のため固定対象に入れない）。固定対象は同じリポジトリのファイルなので、**改ざんの防止ではなく、変更を見落とさないための関門**です。

## 3. X12：共通予算の不変条件

[p2_checks.py](../../scripts/research/p2_checks.py) の `budget_violations` は、一つの要求の予算を 0 から完了に要る値の少し先まで掃引し、型によらない次の不変条件を確かめます（C-stop・I5）。

| 番号 | 不変条件 | 違反の名前 |
| --- | --- | --- |
| B1 | 一度完了した予算より大きい予算でも完了し、結果は同じ（入力 hash を除く） | `completed_then_stopped`・`completed_result_changed` |
| B2 | 止まった結果は、状態が `resource_limit` で、認定票（`certified`）を含まない | `unexpected_status:…`・`certificate_on_stop` |
| B3 | 止まった結果の完了した行は、無制限の結果の同じ行と同一 | `completed_row_changed` |
| B4 | 打切りの行（`step_limit` を理由に持つ行）は値（束縛・根拠・回答・分割・候補・情報要求）を持たない | `value_on_stopped_row` |
| B5 | 入力不正・未対応の結果は、予算に依らず同じ | `refusal_depends_on_budget` |
| B6 | 無制限でも資源の上限で止まる要求は、小さい予算でも `resource_limit` のままで、認定票を出さない | `resource_stop_not_honest` |

- **掃引の範囲**：結果が `steps_used` を持つ要求は `steps_used + 2` まで。持たない要求（P0 の結果など）は、予算を倍々にして完了する上限を求めてからその先まで。初版では持たない 35 要求が予算 0〜2 しか掃引されておらず、範囲を直した（[28](28-p2-d-results.md)）。
- **許容する例外は 1 件**：`p1-a/unnormalized.json`。重みの総和が 1 かの確認は重みの加算を課金しながら行う（`forecast_spec.json` の steps に「正規化の比較」が含まれる）ので、予算が足りないと入力不正と判定する前に `step_limit` で止まる。この一件を `BUDGET_DEPENDENT_REFUSALS` に根拠つきで載せ、ほかの入力不正に例外を広げないことをテストが確かめる。この検査で、forecast の宣言の `stops.invalid_input` の文言が仕様と食い違っていた（「予算に依らず入力不正」）ので、宣言の文言を直した（挙動は仕様どおりで変更なし）。
- **検査器の検出力**：検査器に、壊した評価（打切りに認定票を足す、打切りの行に値を足す、完了した行を変える、予算で結果が変わる、完了後にまた止まる、拒否が予算で別の状態になる、例外が他の差を許してしまう）を渡し、期待した種類の違反が報告されることを確かめる。実装の変異（予算の課金を外す、など）は P2-a〜P2-c の変異検査が受け持つ。
- **空振りの防止**：予算の掃引を宣言した拡張（12 件）はすべて、無制限では完了し予算 0 では止まる要求を持つ（共有の前段 `p1-handover-host` は操作を所有しないので、引き継ぎの要求を通して数える）。

## 4. X11：版の手順（p0-draft-1 → p0-draft-2）

draft-2 への更新（[17](17-internal-run-ai-001.md)）で実際に行った手順を、再実行できる形にします。旧版は消さず、git の履歴のコミットとして残します。

| 番号 | 手順 | 検査 |
| --- | --- | --- |
| V1 | 旧版を保持する：旧版のコミットと、その版が固定した実体の hash（lock）を版の記録に書く | 記録のコミットが履歴にあり、新版のコミットの祖先で、現在の履歴の祖先 |
| V2 | 旧版は旧版の契約で再現できる：コミットを取り出し、その木で `evaluate-p1-d.py` を実行する | 評価が通り、束の hash と台帳の hash が記録と一致（旧版・新版の両方） |
| V3 | 版の記録に、変更を宣言する：付加した項目、値が変わる経路と入力、旧入力で観測されない変更とその別の根拠 | 記録の構造、宣言した入力・根拠の実在 |
| V4 | 旧入力は新版で黙って再解釈されない：旧入力を新版で実行した結果を、同一／固定した hash の変更による拒否／それ以外、に分類する | それ以外が、宣言した入力に限る。拒否は、入力が旧い hash を実際に埋め込んでいる場合に限る |
| V5 | hash だけを再固定した旧入力は、旧版の手で指定した期待を満たす：差は宣言した変更の経路だけ | 期待を満たさない入力 0。差の経路が宣言と一致 |
| V6 | 再検証の範囲：基底の変更から列挙した範囲が、実際に再固定が要った範囲と一致する | X13（`tests/p2/test_extension_contract.py::ReverificationTests.test_the_kernel_change_of_draft_2_is_enumerated_and_covers_the_forced_repin`） |

版の記録は [p0-draft-1-to-draft-2.json](../../examples/p2-versions/p0-draft-1-to-draft-2.json)（`p2-version-record-draft-1`）。宣言した変更は 5 件：V-1 `certifier` の付加（RV-04）、V-2 forecast の `incomplete` が未知の能力の行も列挙する（RV-03、旧入力 2 件で観測）、V-3〜V-5 は旧入力で観測されない変更（確認の時刻順 RV-05、不認定の理由コード RV-02）で、別の根拠（`examples/review/…`、`tests/review/…`）を挙げる。`measured` は比較器の測定値を固定したもので、記録と測定が食い違えば失敗します。

比較は [compare-versions.py](../../scripts/research/compare-versions.py) が行います。取り出した木は別のプロセスで評価し、旧版と新版の `med_dsl` を混ぜません。再固定は、旧版と新版のソースから 3 つの pin（`HANDOVER_SPEC_SHA256`・`P0_SPEC_SHA256`・`P0_RUNTIME_SHA256`）の値を読み、旧い値を新しい値に置き換えるだけです。

**範囲**：旧入力は P0・P1 の 117 入力（有限）。再固定は pin 3 つの機械的な置換。宣言した変更は作成者の主張で、**宣言にない差は検出するが、旧入力が行使しない新版の変更（V-3〜V-5）は、旧入力の比較では見えない**。版の手順が将来の版でも成り立つことは示さない。

## 5. 独立確認の準備

独立確認は**未実施**で、確認者もまだいません。この節は、確認者が得られたときに、作成者の判断を見ずに反例を先に探せるようにするための計画です。確認者が見る資料は、宣言・防護例・期待結果・欠落の理由・内部判断のすべてが**作成者の主張**であることを前提にします。

### 5.1 資料と再現

| 区分 | 内容 |
| --- | --- |
| 基準 | P2-a：`25f6cf3`・`5c8efd4`・`44ced2b`、P2-b：`6d9a5c9`、P2-c：`edb4953`、P2-d：この文書を含むコミット。P0/P1 の基準は [17 の §6](17-internal-run-ai-001.md)（`e73d4ba`／`2b501c1`）。確認者が基準コミットと hash を G0 で記録する |
| 宣言と実体 | `extensions/`（12 宣言と索引）、`src/med_dsl/extensions.py`、固定対象 `examples/p1-evaluation/manifest.json` |
| 検査 | `tests/p2/`、独立オラクル `tests/p2/split_oracle.py`・`tests/p2/splits_oracle.py` |
| 変異表と生成器 | `scripts/research/p2/`（変異表 `mutants_extensions.py` と各実行器、生成器、前後比較 `refactor_digest.py`、`README.md`） |
| 版の手順 | `examples/p2-versions/`、`scripts/research/compare-versions.py` |

```bash
git worktree add --detach ../med-dsl-review-p2 <基準コミット>
cd ../med-dsl-review-p2
python3 -B -m unittest discover -s tests -v            # 開発テスト
python3 -B -m unittest discover -s tests/review        # レビュー系列
python3 -B -m unittest discover -s tests/audits        # 追加監査
python3 -B -m unittest discover -s tests/p2 -v         # P2 系列
python3 -B scripts/research/check-extensions.py --strict   # 登録と防護例。防護例のない義務 3 件が出て失敗するのが想定
python3 -B scripts/research/evaluate-p1-d.py --cli --output data/research/p1-d/review-p2
python3 -B scripts/research/evaluate-p2.py --output data/research/p2-d/review-p2
python3 -B scripts/research/compare-versions.py        # 履歴に旧版が必要（浅い clone では行われない）
```

変異検査は時間がかかるので、テストには含めていません（`scripts/research/p2/README.md` の手順）。Python 3.11 と 3.14 の両方での実行を勧めます。

### 5.2 PO13〜PO18

[12 の証明義務](16-proof-obligations.md) に PO13〜PO18 を加えます。各項は、命題、証拠、確認者が**作成者の期待を見る前に**探す反例、作成者の内部判断のうち覆り得るもの、を分けて書きます。以下の「証拠」は作成者の用意したもので、独立確認ではありません。

#### PO13 宣言の完全性と識別

- **命題**：登録を通った宣言は、必須項目がそろい、実体（仕様の hash・実装・防護例・検査）と食い違わず、クラスの必須の義務を欠かさず、証拠の強さを偽らない。拒否された登録は何も変えない（全か無か）。
- **証拠**：`src/med_dsl/extensions.py`、`tests/p2/test_extension_contract.py::RefusalTests.test_every_missing_top_level_field_is_refused`、`tests/p2/test_extension_contract.py::RefusalTests.test_removing_any_class_required_obligation_is_refused`、`tests/p2/test_extension_contract.py::RefusalTests.test_guard_rules`、`tests/p2/test_extension_contract.py::RefusalTests.test_refusal_is_atomic_for_a_whole_batch`、変異 X01〜X18・X44〜X46・X52〜X53（`scripts/research/p2/mutants_extensions.py`）、[契約 20](20-p2-a-contract.md)。
- **先に探す反例**：(1) 必須の項目や義務を欠いたまま登録できる経路。(2) 防護例を評価せずに通る宣言（例が実在しても結果を見ない）。(3) 宣言した証拠の強さを、実際の検査より強く申告できる経路。(4) 登録の失敗後に、部分的な状態が残る経路。
- **覆り得る内部判断**：J01（X07 の置換）、J02（クラス R6・JOINT の追加）。

#### PO14 所有と名前空間の分離

- **命題**：基底または他の拡張と所有する名前（操作・schema_version・profile・回答型・述語・能力）が重なる拡張は登録されない。末尾が `:` の名前は名前空間として、その下のすべての名前を所有する。
- **証拠**：`src/med_dsl/extensions.py`、`tests/p2/test_extension_contract.py::OverlapTests.test_a_trailing_colon_makes_a_namespace_that_owns_everything_below_it`、`tests/p2/test_extension_contract.py::RefusalTests.test_owner_conflicts_for_every_kind_including_namespaces`、`tests/p2/test_extension_contract.py::ShippedDeclarationTests.test_owned_names_are_disjoint_and_namespaces_do_not_overlap_names`、変異 X19〜X27。
- **先に探す反例**：(1) 名前を実行時に組み立てる拡張が、宣言せずに他の拡張の名前を使う。(2) 名前空間の境界（`:` の位置、接頭辞の一致）で衝突を見逃す。(3) 種別をまたいだ同名の扱い。
- **覆り得る内部判断**：J03（名前の存在確認が文字列の出現に限られる）。

#### PO15 非干渉（基底の要求の観測不変）

- **命題**：拡張を登録しても、その拡張に属さない要求の結果は変わらない（`certifier` を除く）。独立と判定された拡張の併用は、単独で載せたときと結果が同じ。
- **証拠**：`tests/p2/test_extension_contract.py::NonInterferenceTests.test_disabling_each_extension_changes_nothing_outside_it_and_its_dependents`、`tests/p2/test_extension_contract.py::NonInterferenceTests.test_an_undeclared_read_is_exposed_by_disabling_the_extension_that_is_read`、`tests/p2/test_combinations.py::IndependenceTests.test_every_independent_subset_gives_the_same_results_as_each_extension_alone`、`tests/p2/test_p2_tools.py::BehaviourDigestTests.test_the_outcomes_of_the_pinned_suites_are_identical_to_the_baseline_taken_before_p2`、補助 `tests/p2/support.py`（拡張を不活性にする）。
- **先に探す反例**：(1) 不活性化が効かず、非干渉が空振りになる経路（他のモジュールが import 済みの束縛）。(2) `certifier` 以外の観測の差。(3) 振り分けの順序への依存。
- **覆り得る内部判断**：J04（不活性化の方法と `certifier` の除外）。

#### PO16 不変条件 I1〜I7 の保存（新しい出力に対して）

- **命題**：拡張の新しい出力が、核の不変条件 I1〜I7（[19 の §2](19-p2-design.md)）を破らない。特に、拡張の回答型が基底の状態へ暗黙に変換されず（I1・I2）、AI の候補は人の確認まで採用されず（I3）、未知の能力は解釈されず（I4）、打切りで部分回答も認定票も出ず（I5）、入力は変更されず（I6）、結果は決定的（I7）。
- **証拠**：I1・I2・L5：`examples/p2-split/old-record-only.json`、`examples/p2-splits/query-base-unchanged-by-the-combination.json`。I3：`examples/p2-split/ai-candidate-pending.json`。I4：`examples/p2-split/unknown-capability-blocks.json`。I5：`tests/p2/test_budget_contract.py::BudgetContractTests.test_every_request_satisfies_the_budget_contract`（X12）。I6・I7：`scripts/research/evaluate-p1-d.py`（入力の保持と再実行の同一性）、`tests/p2/test_concept_split.py`。
- **先に探す反例**：(1) 新しい回答型の値が `supported`・`opposed` などの基底の状態として現れる経路。(2) 保留・訂正済みの主張が未知の能力を要求するとき、拡張が落とす経路。(3) 打切りの行が候補や情報要求を持つ経路。(4) 入力の並べ替えで結果が変わる経路。
- **覆り得る内部判断**：J05（I1〜I7 が不変条件の完全な列挙でないこと）、J06（X12 の例外 1 件）。

#### PO17 併用（独立・共有・鎖）

- **命題**：(a) 独立と判定された拡張は互いに干渉しない。(b) 記号を共有し得る拡張の併用は、個別の認定ではなく併用全体で再判定する。保存性の判定は、単項述語の分割に対して、併用全体の公理の下で全数に正確である。(c) 鎖の範囲は交差に狭まり、情報を失う段は後段で回復しない。
- **証拠**：`src/med_dsl/splits.py`、`src/med_dsl/splits_spec.json`、独立オラクル `tests/p2/splits_oracle.py`、`tests/p2/test_split_combination.py`、`tests/p2/test_combinations.py::IndependenceTests.test_no_pair_that_depends_or_reads_is_called_independent`、変異 39 件（`scripts/research/p2/mutrun_splits.py`）と X47〜X54、[設計 25](25-p2-c-design.md)・[結果 26](26-p2-c-results.md)。
- **先に探す反例**：(1) 独立と判定された組で、片方を不活性にするともう片方の結果が変わる。(2) 個別に保存的でも併用では保存的でない分割（K04 型）を認定する。(3) 反例として返す旧記号の割り当てが、実際には拡張できる。(4) 入れ子の鎖で、前段の除外や後段の情報が流れない。
- **覆り得る内部判断**：J07（独立の判定の保守性）、J08（保存性の判定を単項述語に限った）、J09（情報を失う段を含む鎖を範囲外にした）。

#### PO18 基底変更の波及と再検証範囲

- **命題**：基底の検証規則や固定した実体を変えたとき、宣言から機械的に列挙した再検証範囲は、実際に再固定が要った範囲を含む。版を上げた拡張の旧版の入力は、旧版の契約で再現でき、新版で黙って再解釈されない。
- **証拠**：`src/med_dsl/extensions.py`（`affected`）、`tests/p2/test_extension_contract.py::ReverificationTests.test_the_kernel_change_of_draft_2_is_enumerated_and_covers_the_forced_repin`、`tests/p2/test_extension_contract.py::AffectedLogicTests.test_a_registration_import_is_not_followed_but_an_ordinary_one_is`、`tests/p2/test_versions.py::VersionProcedureTests.test_old_inputs_are_never_silently_reinterpreted`、`tests/p2/test_versions.py::VersionProcedureTests.test_repinned_old_inputs_satisfy_their_old_expectations`、`scripts/research/compare-versions.py`、`examples/p2-versions/p0-draft-1-to-draft-2.json`。
- **先に探す反例**：(1) 実際に再固定が要ったのに列挙から漏れる実体。(2) 登録の辺の規則（ホストの import を辿らない）のため、過小になる列挙。(3) 旧入力が新版で、同一でも拒否でもない形に変わるのに、宣言にない。(4) 版の記録の宣言が、実際の変更を過少に申告する。
- **覆り得る内部判断**：J10（登録の辺の規則）、J11（版の手順の範囲）。

### 5.3 覆り得る内部判断

作成者（AI）が単独で行った判断のうち、独立の確認で覆り得るものです（P2-a〜P2-c の各段で利用者に了承を得た範囲の中の判断を含みます）。覆った場合に戻す・やり直す箇所を添えます。

| ID | 内部判断 | 覆った場合 |
| --- | --- | --- |
| J01 | 設計 X07「各クラスの各ゲートに負例」を、「防護例または理由つきの欠落」に置き換えた。欠落 3 件（`R1-3`・`R3-3`・`COMP-3`）の理由は「拒否する入力を構成できない」 | 3 件に負例を作る。構成できないと示せなければ、その義務の証拠を弱める |
| J02 | クラス R6・JOINT を作成者が追加した（義務表が完全である保証はない） | クラス表を書き直し、12 宣言の義務を再検査する |
| J03 | 宣言した名前の存在確認は、実装・仕様の本文に文字列として現れることに限る | 実行時に名前を組み立てる拡張に、別の検査を足す |
| J04 | 非干渉の観測は、`certifier`（実装の束の hash）を除く。不活性化は関数の差し替え | 差し替えが及ばない経路があれば、非干渉の主張の範囲を狭める |
| J05 | I1〜I7 は、散在していた性質を整理したもので、完全性は主張しない | 不変条件を足し、各拡張の `K-INV` を再検査する |
| J06 | X12 の例外 1 件（`p1-a/unnormalized.json`）。宣言の文言を仕様に合わせて直した | 仕様を直して重みの確認を課金しないようにするか、例外を撤回して宣言を戻す |
| J07 | 拡張の独立の判定は、依存・読み取り・順序・実装の import 閉包による保守的な十分条件。基底の核のモジュールの共有は干渉とみなさない | 核の共有を干渉とみなす場合、独立な組は 42 組より少なくなる |
| J08 | 併用の保存性の判定を、単項述語の分割に限った（正確な判定の範囲） | 多項述語に広げるときは、判定を作り直す |
| J09 | 情報を失う段（射影）を含む鎖を範囲外にした（X10 は一部達成） | 範囲に入れるなら、段の損失と分割の併用の関係を設計し直す |
| J10 | 再検証範囲の列挙で、自分に依存する拡張のモジュールへの import（登録のため）は辿らない | 辿ると、再検証範囲が広がる（過大側）。draft-2 の実測は現在の規則と一致 |
| J11 | 版の手順の「旧入力」は P0・P1 の 117 入力。再固定は pin 3 つの置換。旧入力で観測されない変更（V-3〜V-5）は別の根拠で補った | 旧入力を増やす、または未観測の変更を版の手順の外に置く |
| J12 | 等価な変異は 2 件：鎖の `and not outside`（[22](22-p2-a-hardening.md)）と分割の二重の除外（S36、[24](24-p2-b-results.md)）。理由を記録した | 等価でないと判断されたら、検出する検査を足す |

### 5.4 再開点

**再開地点は G0（資料固定）**です（[17 の §6](17-internal-run-ai-001.md)）。独立の確認者が得られた場合の手順：

1. G0：基準コミットと hash を記録する。P0/P1 の資料（draft-1 の `e73d4ba`、draft-2 の `2b501c1`）に加えて、P2 の基準コミットを記録する。
2. G1／G2：12 の証明義務（PO01〜PO12）の独立なやり直しに続けて、PO13〜PO18 を、§5.2 の「先に探す反例」を作成者の証拠を見る前に試す形で行う。
3. §5.3 の内部判断を一つずつ裁定する。覆る判断は、戻す箇所に従って修正し、旧版の記録を消さずに版を上げる（§4 の手順）。
4. `independent_review` と `evaluation_frozen` の変更は、独立確認の記録ができた後にだけ行う。それまでは false のまま、登録時に true の主張は拒否される。

## 6. 範囲外と未解決

- 独立の確認者、Python 3.11 以外の実行環境（他 OS）、人手による期待の再導出は未実施。
- 変異は作成者が選んだ集合で、変異演算子による網羅的な検査は未実施。
- 宣言の誤りを、実装に対する正しさと独立に見つける手段は、防護例・変異・オラクルの三つの範囲に限る。
- 任意の意味能力に対する共存の自動判定、拡張が拡張を読む併用、循環する依存、無限の更新列の極限、動的な意味、性能は、[19 の §10](19-p2-design.md) のとおり範囲外。
- 医学的な妥当性は対象外。契約は意味の共存を検査するもので、拡張の医学的な正しさを検査しない。
- この段階の達成は、体系の永続性や将来の全変化への耐性の証明ではない。
