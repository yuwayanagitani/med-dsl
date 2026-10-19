# 防護例（P2-a、拡張契約の宣言が引く拒否・境界の例）

[拡張の宣言](../../extensions/README.md) で「防護例のない義務」だった義務に、拒否・境界の例を追加したものです。状態：**作成者の草案・独立確認前・評価用正解の凍結なし**（`independent_review` / `evaluation_frozen` は false）。[追加作業の記録 22](../../docs/research/22-p2-a-hardening.md) と併読します。

この系列は共通の評価（P1 の20条件・80 JSON・417必須パス）にも、231開発テストにも、レビュー系列にも加えません。別の分母（35 例）として扱います。ただし宣言が根拠として引くので、共通 manifest（lock）には載せます。

```bash
python3 -m unittest tests.p2.test_guard_examples -v     # 例の期待・台帳・派生元・予算の境界を検査する
python3 scripts/research/check-extensions.py            # 宣言が引く防護例を評価する
```

## 作り方

- 各例は、固定済みの例（`derived_from`）の入力を最小限に書き換えたもので、どのゲートを壊すと検出できなくなるかを `gate` に記録しています。
- **期待結果は、ゲートの意味から手で指定しました**（処理系の出力から生成していません）。例外は予算の境界の n（完了に要る最小の steps）だけで、無制限の実行の `steps_used` を測りました（`measured_budgets`）。`budget-below-*` は n-1、`budget-exact-*` は n で、入力は派生元と予算以外が同一です。
- 鎖の入力（`chain-*`）は、変更した履歴から端点・範囲の宣言を作り直す必要があるため、実装の事象化・改名・端点の計算を**入力の構成にだけ**使いました。期待結果は使っていません。
- 生成した例がゲートを壊した実装を実際に検出するかは、変異検査で確かめました（[22 の §2](../../docs/research/22-p2-a-hardening.md)）。

## 例（35 件）

| ID | ファイル | 拡張・義務 | 種類 | 対象のゲート |
| --- | --- | --- | --- | --- |
| GD01 | budget-below-definitions | p0-definitions K-RES | boundary | 課金の境界：steps が 4（完了に要る 5 より 1 少ない）で止まる |
| GD02 | budget-exact-definitions | p0-definitions K-RES | boundary | 課金の境界：steps がちょうど 5 で完了する（上限を厳しくしすぎない） |
| GD03 | budget-below-absence | p1-absence K-RES | boundary | 課金の境界：steps が 4（完了に要る 5 より 1 少ない）で止まる |
| GD04 | budget-exact-absence | p1-absence K-RES | boundary | 課金の境界：steps がちょうど 5 で完了する（上限を厳しくしすぎない） |
| GD05 | budget-below-event-chain | p1-event-chain K-RES | boundary | 課金の境界：steps が 96（完了に要る 97 より 1 少ない）で止まる |
| GD06 | budget-exact-event-chain | p1-event-chain K-RES | boundary | 課金の境界：steps がちょうど 97 で完了する（上限を厳しくしすぎない） |
| GD07 | budget-below-events | p1-events K-RES | boundary | 課金の境界：steps が 33（完了に要る 34 より 1 少ない）で止まる |
| GD08 | budget-exact-events | p1-events K-RES | boundary | 課金の境界：steps がちょうど 34 で完了する（上限を厳しくしすぎない） |
| GD09 | budget-below-rename-events | p1-handover-host K-RES | boundary | 課金の境界：steps が 5（完了に要る 6 より 1 少ない）で止まる |
| GD10 | budget-exact-rename-events | p1-handover-host K-RES | boundary | 課金の境界：steps がちょうど 6 で完了する（上限を厳しくしすぎない） |
| GD11 | budget-below-projection | p1-projection K-RES | boundary | 課金の境界：steps が 14（完了に要る 15 より 1 少ない）で止まる |
| GD12 | budget-exact-projection | p1-projection K-RES | boundary | 課金の境界：steps がちょうど 15 で完了する（上限を厳しくしすぎない） |
| GD13 | budget-below-reference | p1-reference K-RES | boundary | 課金の境界：steps が 8（完了に要る 9 より 1 少ない）で止まる |
| GD14 | budget-exact-reference | p1-reference K-RES | boundary | 課金の境界：steps がちょうど 9 で完了する（上限を厳しくしすぎない） |
| GD15 | budget-below-replay | p1-replay K-RES | boundary | 課金の境界：steps が 99（完了に要る 100 より 1 少ない）で止まる |
| GD16 | budget-exact-replay | p1-replay K-RES | boundary | 課金の境界：steps がちょうど 100 で完了する（上限を厳しくしすぎない） |
| GD17 | definitions-zero-budget | p0-definitions K-STOP | refusal | 予算 0 では認定票を出さない |
| GD18 | definitions-empty-extension-zero-budget | p0-definitions K-STOP | refusal | 追加が空でも、予算 0 は未評価（認定票を出さない） |
| GD19 | definitions-empty-extension-one-step | p0-definitions K-STOP | boundary | 追加が空なら 1 step で認定する（予算 0 との境界） |
| GD20 | chain-unknown-capability | p1-event-chain K-STOP | refusal | 未知の能力を含む履歴の鎖は、未評価を残して認定しない |
| GD21 | host-unsupported-operation | p1-handover-host K-STOP | refusal | 未登録の操作は、別の操作で代用せず unsupported_profile |
| GD22 | host-consumer-operation-unsupported | p1-handover-host K-STOP | refusal | consumer が未登録の操作を宣言していれば止まる |
| GD23 | host-consumer-profile | p1-handover-host K-STOP | refusal | consumer の profile が違えば unsupported_profile |
| GD24 | reference-finite-probe-unsupported | p1-reference K-STOP | refusal | 語彙を持つ入力への有限領域の探査は未対応として止まる（非含意にしない） |
| GD25 | reference-formula-depth-limit | p1-reference K-STOP | boundary | 式の深さが上限（16）を超えれば resource_limit（非含意に見せない） |
| GD26 | reference-formula-depth-exact | p1-reference K-RES | boundary | 式の深さがちょうど上限（16）なら評価する（上限を厳しくしすぎない） |
| GD27 | definitions-ledger-field-refused | p0-definitions K-INV | refusal | 認定は定義パッケージだけを読む：台帳（採用・確認）を受け付けない |
| GD28 | chain-ai-candidate-not-adopted | p1-event-chain K-INV | non_conversion | 確認のない AI 候補は、鎖を通っても支持にならない（未決のまま両計算が一致） |
| GD29 | chain-zero-budget | p1-handover-host K-INV | non_conversion | 打切り（予算 0）で認定票・部分の報告を出さない |
| GD30 | chain-out-of-scope-query | p1-event-chain COMP-2 | non_conversion | 鎖の範囲外の問い（事象の同一性）を、旧の問いの認定に含めない |
| GD31 | forecast-arbitrary-package-refused | p1-finite-forecast R2-2 | refusal | 任意の package を受け付けない（報告専用の固定 package だけ） |
| GD32 | forecast-nonreport-predicate-refused | p1-finite-forecast R2-2 | refusal | 報告専用の述語以外（基底の語彙の述語）を台帳に持ち込めない |
| GD33 | reference-stronger-target | p1-reference R3-4 | non_conversion | 新理論が文を一つ追加するとき、保存を認定せず、被覆を真にも偽にもしない |
| GD34 | reference-ledger-field-refused | p1-reference R3-5 | refusal | 参考意味は履歴・採用を持たない：台帳を受け付けない |
| GD35 | reference-new-name-refused | p1-reference R3-6 | refusal | 翻訳は新しい名前を導入しない：宣言した語彙にない述語を目標に持ち込めない |
