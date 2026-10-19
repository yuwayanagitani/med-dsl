# レビュー負例系列（RV-01・RV-05、AI-001）

[レビュー記録 AI-001](../../docs/research/16-review-record-ai-001.md) の指摘 RV-01（認定・可用性・射影の主要ゲートに負例がない）への追加例と、RV-05 の裁定で生じた既知の逸脱の記録です。状態：**AI レビュアーの草案・独立確認前・評価用正解の凍結なし**（`independent_review` / `evaluation_frozen` は false）。[追補記録](../../docs/research/16-review-followup-ai-001.md) と併読します。

固定済みの168ファイル（P0/P1-a/b/c の例、runtime、テスト、評価スクリプト、契約）は変更していません。この系列は共通台帳の対象外で、**P1の20条件・80 JSON・417必須パスにも、231開発テストにも加えません**。別の分母（負例12・既知の逸脱1・予算掃引2テスト）として扱います。期待結果は各ゲートの意味から手で指定し、処理系の出力から生成していません。

```bash
python3 -m unittest discover -s tests/review -v   # 約13秒。tests/ 直下の discover には含まれない
```

## 負例12件（RV-01）

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

## 既知の逸脱 KD01（RV-05）

| ID | ファイル | 内容 |
| --- | --- | --- |
| KD01 | known-deviation-review-precedes-assertion | 確認が主張より前に記録された入力。**現行版（p0-draft-1）の挙動を固定**：`supported`、`adopted=[h1]`。裁定では次の契約版で `invalid_input` `review_precedes_assertion`（`error_path` は `review.recorded_at`）とする。契約版を上げたら、期待を `known_deviation.after_adoption` へ反転させる |

## 予算掃引（`tests/review/test_budget_sweep.py`）

固定した全117例と上の12例について、予算を 0 から steps+3 まで変え、完了済みの行は無制限実行と同一、未完了は値なし、打切り時に認定・回答・生成物なし、必要十分な予算で正常終了・その1少ない予算で `resource_limit`、入力不正は予算に依らず不変、を確認します。

## 限界

AI レビュアーが作成した草案で、独立確認は済んでいません。12件は RV-01 の7ゲートに対応しますが、RV-07 の小さな網羅性の欠落（境界値、拡張認定の予算0、証明選択など）は含みません。新しい意味は追加していません。
