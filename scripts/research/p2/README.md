# P2 の独立確認の資料（変異表・実行器・生成器・前後比較）

P2-a〜P2-c の作業で、宣言・例・検査の強さを確かめるために使った道具です。**作成者（AI-001）の草案・独立確認前**で、Git 管理外の作業場所（`data/research/review-001/scripts/`）にあったものを、確認者が再現できるようにリポジトリへ移しました。実行器の既定の作業場所は一時ディレクトリで、環境変数 `P2_REPO`（作業ツリー。既定はこのリポジトリ）と `P2_SCRATCH`（作業場所）で変えられます。すべて架空データだけを扱います。

| ファイル | 役割 |
| --- | --- |
| `mutants_extensions.py` | 契約の検査（`src/med_dsl/extensions.py`）の変異表 X01〜X54（53 件） |
| `mutrun_p2.py` | 上の変異を一つずつ別の木に当て、`tests/p2` が失敗するか（検出）を記録 |
| `mutrun_guards.py` | 防護例（`examples/p2/`）のゲートの変異 28 件（と対照 C0）。意図した例が失敗するか、既存のテストが見逃すかを記録 |
| `mutrun_split.py` | 概念の分割（`split.py`）の変異 35 件。手で指定した例・オラクルのテスト・契約の検査のそれぞれで検出するかを記録 |
| `mutrun_splits.py` | 分割の併用（`splits.py`）の変異 39 件。同上に、独立の検査を加えた |
| `gen_extension_manifests.py` | `extensions/*.json` と `index.json` の生成 |
| `gen_guard_fixtures.py`・`gen_split_fixtures.py`・`gen_splits_fixtures.py` | `examples/p2`・`examples/p2-split`・`examples/p2-splits` の生成。期待結果は設計の意味から手で指定し、処理系の出力から作らない（予算の境界の n だけ測る） |
| `repin_specs.py` | 仕様の改訂の後、依存の順に仕様の hash を再計算し、モジュールの定数と依存先の仕様へ反映する（P2-l。実行例と宣言は生成器で再生成する）。`--check` で再固定が要るかだけを確かめる |
| `mutrun_checkers.py` | 検査器自体（`p2_checks.py`・`evaluate-p2.py`・`compare-versions.py`）の変異の表と実行器。変異後の木で固定対象の台帳を作り直して判定する |
| `refactor_digest.py` | 固定済みの全例・改変入力（各 150）・予算の全値掃引の出力（22,052 件）の digest。挙動を変えない変更の前後比較に使う |
| `gen_temporal_fixtures.py`・`gen_temporal_manifest.py` | P2-eの61例・R5宣言。期待は文書32から手指定。宣言は既存の生成器から呼び出す |
| `gen_quantity_fixtures.py`・`gen_quantity_manifest.py` | P2-fの79例・R2宣言。期待は文書35から手指定。量固有の変異9件は `tests/p2/test_quantity.py` 内で実行 |
| `gen_measurement_fixtures.py`・`gen_measurement_manifest.py` | P2-gの137例・R5宣言。期待は文書38から手指定。10変異と共有予算の観測は `tests/p2/test_measurement.py` 内で実行 |
| `gen_display_fixtures.py`・`gen_display_manifest.py` | P2-hの145例・R4宣言。期待は文書41から手指定。表示固有の10変異と子予算の観測は `tests/p2/test_display.py` 内で実行 |
| `gen_temporal_measurement_fixtures.py`・`gen_temporal_measurement_manifest.py` | P2-iの151例・R5宣言。期待は文書44から手指定。区間差引きと12変異・子予算の観測は `tests/p2/test_temporal_measurement.py` 内で実行 |
| `gen_temporal_display_fixtures.py`・`gen_temporal_display_manifest.py` | P2-jの170例・R4宣言。期待は文書47から手指定 |
| `gen_refinement_fixtures.py`・`gen_refinement_manifest.py` | P2-kの66例・R5宣言。期待は文書51から手指定 |
| `gen_longitudinal_fixtures.py`・`gen_longitudinal_manifest.py` | P2-mの103例・R5宣言。期待は文書57から手指定。別計算の二つの経路・P2-gとの文脈の差分・27変異と子予算の観測は `tests/p2/test_longitudinal.py` 内で実行 |
| `gen_library_fixtures.py`・`gen_library_manifest.py` | P2-oの141例・R5宣言。期待は文書64から手指定（O08・O09は実装中に足した例）。別計算・要求の版の差・出力先の追加・26変異と子予算の観測は `tests/p2/test_library.py` 内で実行 |
| `gen_grounding_fixtures.py`・`gen_grounding_manifest.py` | P2-pの97例・R5宣言。期待は文書68から手指定（P2-oの生成器の部品を使う）。Decimalによる別計算・値の格子の全数・20変異と子予算の観測は `tests/p2/test_grounding.py` 内で実行 |
| `gen_observation_fixtures.py`・`gen_observation_manifest.py` | P2-qの75例・R5宣言。期待は文書71から手指定（P2-pの生成器の部品を使う）。宣言の全数・確認と出自・19変異と子予算の観測は `tests/p2/test_observation.py` 内で実行 |
| `make_observer_version_record.py` | P2-rの版の記録（P2-i の draft-2 → draft-3）を、旧版・新版のコミットの木の比較から作る。宣言と予測は文書73・74から手で書いた値、測定値は比較器の出力を固定する |
| `inheritance_suspects.py` | 継承の疑いの機械的な探索（P2-n。二つの拡張だけが共有する識別子らしい文字列定数）。登録の条件ではなく、測定のための道具 |

正本は、宣言・例については `extensions/`・`examples/p2*/` の JSON です。生成器はそれを再現できることを `tests/p2/test_p2_tools.py` が確かめます（コピーした木で生成し、バイト単位で比較）。

P2-eの意味変異5件は `tests/p2/test_temporal.py` 内で対象関数を一時的に差し替えて実行します。元のソースファイルは書き換えません。区間差分の参照計算・有限列挙・CLI照合も同じテスト系列にあり、[結果33](../../../docs/research/33-p2-e-results.md) に分母を記録します。

## 使い方

```bash
# 変異検査（変異ごとに木を複製して tests を動かすので時間がかかる。ID を渡すと一部だけ実行）
python3 -B scripts/research/p2/mutrun_p2.py [X01 ...]       # 契約の検査
python3 -B scripts/research/p2/mutrun_guards.py [--no-tests] [K1 ...]
python3 -B scripts/research/p2/mutrun_split.py [S01 ...]
python3 -B scripts/research/p2/mutrun_splits.py [J01 ...]   # ID は表を見る

# 生成器（P2_REPO を別の作業ツリーにすると、そこへ書く）
python3 -B scripts/research/p2/gen_extension_manifests.py

# 挙動の前後比較
python3 -B scripts/research/p2/refactor_digest.py . before.json
# …変更…
python3 -B scripts/research/p2/refactor_digest.py . after.json && cmp before.json after.json
```

実行器は作業ツリーを複製し、複製の側だけを変異させます。元のファイルは変更しません。結果は作業場所の `logs/` に JSON で書きます。テストが `git` の履歴を読むので、複製には `GIT_DIR` を元の `.git` に向けて実行します（実行器が設定する）。

## テストが確かめること（`tests/p2/test_p2_tools.py`）

- 変異表の置換元が、現在の実装の対象ファイルに**ちょうど一つ**現れる（実装が変わって表が古くなっていない）。変異後の構文が壊れていない。意図した例が実在する。
- 生成器が、固定した例と宣言を再現する。
- `refactor_digest.py` の出力が、P2-a の前に取った基準（22,052 件）と一致する。以後の P2-a〜P2-d の変更で、固定済みの例の挙動は変わっていない。意図して挙動を変える場合は、定数 `BEHAVIOUR_DIGEST` を更新する（変更の理由を記録すること）。

変異の**実行**（各変異後の木でテストを動かす）はテストに含めません。結果は [P2-a の追加作業 22](../../../docs/research/22-p2-a-hardening.md)、[P2-b の結果 24](../../../docs/research/24-p2-b-results.md)、[P2-c の結果 26](../../../docs/research/26-p2-c-results.md)、[P2-d の結果 28](../../../docs/research/28-p2-d-results.md) にあります。

## 限界

- 変異は作成者が選んだ集合で、変異演算子による網羅ではない。検出されたことは、その変異の種類の退行が検出できることを示すだけで、他の退行がないことは示さない。
- 等価と判断した変異の理由（`mutrun_split.py` の S36、鎖の `and not outside`）は作成者の判断で、独立の確認で覆り得る（[27 の §5.3](../../../docs/research/27-p2-d-design.md)）。
- 実行器は Linux の `cp`/`shutil` による複製を前提とする。Windows では未確認。
