# 版の記録（P2-d、X11）

[p0-draft-1-to-draft-2.json](p0-draft-1-to-draft-2.json)（`p2-version-record-draft-1`）は、契約版 `p0-draft-1` から `p0-draft-2` への更新を、再実行できる形にした記録です。状態：**作成者（AI-001）の草案・独立確認前**。例（入力と期待結果の組）ではなく、P0/P1 の分母にも P2 の例の分母にも含みません。

| 項目 | 内容 |
| --- | --- |
| `from`・`to` | 旧版・新版のコミット（git の履歴）と、その版が自分の木で再現した評価（P1 20 条件・80 JSON・417 必須パス、P0 37 JSON・221 必須パス、束と台帳の hash） |
| `pins_changed` | 版の更新で再固定が要った pin（`HANDOVER_SPEC_SHA256`・`P0_SPEC_SHA256`・`P0_RUNTIME_SHA256`） |
| `declared_changes` | 作成者が宣言する変更：付加した項目（`added_field`）、値が変わる経路と入力（`changed_value`）、旧入力で観測されない変更と別の根拠（`not_observed`）。**ここにない差は、比較器が失敗にする** |
| `measured` | 比較器の測定値を固定したもの（旧入力 117 件の分類、再固定後の一致、付加した項目を持つ結果の数）。記録と測定が食い違えば失敗 |

```bash
python3 -B scripts/research/compare-versions.py          # git の履歴に旧版のコミットが要る（浅い clone では実行できない）
python3 -B -m unittest tests.p2.test_versions -v
```

手順（V1〜V6）と範囲は [設計 27 の §4](../../docs/research/27-p2-d-design.md)、結果は [28](../../docs/research/28-p2-d-results.md)。宣言は作成者の主張で、旧入力が行使しない新版の変更は旧入力の比較では見えません。有限の旧入力での一致を、版の手順の一般の保存の証明とは扱いません。
