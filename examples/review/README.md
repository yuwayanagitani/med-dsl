# レビュー負例系列（RV-01・RV-05、AI-001、`p0-draft-2`）

[レビュー記録 AI-001](../../docs/research/16-review-record-ai-001.md) の指摘 RV-01（認定・可用性・射影の主要ゲートに負例がない）への追加例と、RV-05 の裁定（確認は対象の主張以後に限る）を `p0-draft-2` で実装した境界の例です。状態：**AI レビュアーの草案・独立確認前・評価用正解の凍結なし**（`independent_review` / `evaluation_frozen` は false）。[追補記録](../../docs/research/16-review-followup-ai-001.md)、[内部実施の完了記録](../../docs/research/17-internal-run-ai-001.md) と併読します。

この系列は共通台帳の対象外で、**P1の20条件・80 JSON・417必須パスにも、231開発テストにも加えません**。別の分母（負例13・境界1・テスト52件）として扱います。負例12件（RN01〜RN12）は draft-1（e73d4ba）でも同じ期待で通り、draft-2 の hash に合わせて再生成した（期待は変えていない）。RN13・RN14 は draft-2 で初めて成り立つ。draft-1 時点の系列は `data/research/review-001/snapshots/pre-draft2/`（Git管理外）。期待結果は各ゲートの意味から手で指定し、処理系の出力から生成していません。

```bash
python3 -m unittest discover -s tests/review -v   # 52テスト、約30秒。tests/ 直下の discover には含まれない
```

## 負例13件（RV-01・RV-05）

各例は、固定済みの例を最小限に書き換えたもので、どのゲートを壊すと検出できなくなるかを `gate` に記録しています。

| ID | ファイル | 対象のゲート | 期待 |
| --- | --- | --- | --- |
| RN01 | chain-forged-start-endpoint | handover.py:176 始端の票 | 不認定 `chain_obligation_failed`、`stage_1.source` が不一致 |
| RN02 | chain-forged-end-endpoint | handover.py:176 終端の票 | 不認定、`stage_2.target` が不一致 |
| RN03 | chain-consistently-forged-policy | 同上・両段で一貫した偽の採用方針 | 不認定。段の接続検査は通るが、実体からの再計算で拒否 |
| RN04 | chain-consistently-forged-dependencies | 同上・偽の依存 | 同上 |
| RN05 | chain-consistently-forged-scope | 同上・偽の翻訳後Q範囲 | 同上 |
| RN06 | archive-runtime-wrong-hash | handover.py:320 runtime 要求の hash | `unavailable`／`unknown_runtime_handler` |
| RN07 | archive-dependency-hash-mismatch | handover.py:319 依存の hash 照合 | 依存だけ `unavailable`、runtime は利用可のまま |
| RN08 | archive-no-runtime-requirement | handover.py:282-283 | `invalid_input` `expected_one_runtime_requirement` |
| RN09 | archive-two-runtime-requirements | 同上 | 同上 |
| RN10 | projection-mixed-scope | projection.py:122 | 不認定 `query_out_of_scope`、保持列の Q だけ `preserved` |
| RN11 | projection-collision-evidence | projection.py:119 | `verified_collision` と反例（旧固定例が未検査だった項目） |
| RN12 | projection-sidecar-mismatch | projection.py:69-70 | `invalid_input` `sidecar_mismatch` |
| RN13 | review-precedes-assertion | validation.py 先行する確認（RV-05、draft-2） | `invalid_input` `review_precedes_assertion`、`error_path` は `review.recorded_at` |

## 受理される境界 RN14（RV-05）

| ID | ファイル | 内容 |
| --- | --- | --- |
| RN14 | review-at-the-same-time-is-accepted | 確認が主張と**同時刻**に記録された入力は許される（`supported`、`adopted=[h1]`）。厳密に前の RN13 との境界 |

## 予算掃引（`tests/review/test_budget_sweep.py`）

固定した全117例と上の13例について、予算を 0 から steps+3 まで変え、完了済みの行は無制限実行と同一、未完了は値なし、打切り時に認定・回答・生成物なし、必要十分な予算で正常終了・その1少ない予算で `resource_limit`、入力不正は予算に依らず不変、を確認します。

## 限界

AI レビュアーが作成した草案で、独立確認は済んでいません。RN01〜RN12 は RV-01 の7ゲートに対応しますが、RV-07 の境界値などは `tests/review/test_boundaries.py` が扱います（例ではなくテストで構成）。RN13・RN14 以外に新しい意味は追加していません。ほかに、P0 の compare 経路と事象の役割結合（`split_roles`）・鎖の認定を独立オラクルで照合するテスト（`test_compare_paths.py`、`test_event_paths.py`、補助 `reference_oracle.py`）が同じ系列にあります（[18](../../docs/research/18-additional-checks-ai-001.md)）。
