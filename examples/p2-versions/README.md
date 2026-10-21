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

## 数量の単位表の改訂（P2-l、`p2-version-record-draft-2`）

[p2-quantity-draft-1-to-draft-2.json](p2-quantity-draft-1-to-draft-2.json) は、数量（P2-f）の単位表の改訂（`u_third` の倍率の変更、`u_hundred` の追加）と、依存する4拡張の再固定の記録です。上の P0 の記録（`p2-version-record-draft-1`）と違い、再固定を文字列の置換ではなく、**再生成した入力の比較**で検査します（確認が拘束する内容の hash は、置換では再固定できないため）。

| 項目 | 内容 |
| --- | --- |
| `from`・`to` | 旧版 `906766d` と新版 `a7328b9` のコミットと、その木での統合評価の要約（分母・manifest・束の hash） |
| `pins`・`pin_refusals` | 再固定するモジュールの定数5つと、旧入力を新版へ渡したときの宣言した拒否（`unsupported_profile`／`profile_spec_mismatch`） |
| `declared_changes` | 手で書いた宣言：追加した単位（D-1）、換算係数の改訂と影響を受ける入力6件（D-2）、意味の変更のない再固定（D-3） |
| `predicted` | 手で書いた予測：`affected()` が列挙する拡張と再生成の範囲、列挙から漏れる実体 |
| `measured` | 比較器の測定値を固定したもの（分類の件数、入力の数、予測との差、変更ファイルの数） |

```bash
python3 -B scripts/research/compare-versions.py --record examples/p2-versions/p2-quantity-draft-1-to-draft-2.json   # git の履歴に旧版・新版のコミットが要る
python3 -B -m unittest tests.p2.test_quantity_version -v
```

手順（V1〜V8）と予測は [設計53](../../docs/research/53-p2-l-design.md)・[期待54](../../docs/research/54-p2-l-cases.md)、結果は [55](../../docs/research/55-p2-l-results.md)。宣言と予測は作成者の主張です。履歴がない環境では、記録に沿った比較は行われません。

## 記録に観察者を足す版の更新（P2-r、`p2-version-record-draft-2`）

[p2-temporal-measurement-draft-2-to-draft-3.json](p2-temporal-measurement-draft-2-to-draft-3.json) は、期間つき数量（P2-i）の記録に任意の項目 `observer` を足す版の更新（draft-2 → draft-3）と、依存する5拡張（P2-j・P2-m・P2-o・P2-p・P2-q）の再固定・採用の記録です。書式は P2-l と同じで、宣言の種類 `added_field` と `repinned` を使います。

| 項目 | 内容 |
| --- | --- |
| `from`・`to` | 旧版 `dc0aabe`（P2-q の追加後）と新版のコミットと、その木での統合評価の要約 |
| `pins`・`pin_refusals` | 再固定するモジュールの定数6つと、旧入力を新版へ渡したときの宣言した拒否（`unsupported_profile`／`profile_spec_mismatch`） |
| `declared_changes` | D-1〜D-3：観察者の追加（P2-i）、選択の根拠への `record_observer`（P2-o）、生成の Provenance と観察者の型（P2-q）。追加した入力25件。D-4：意味の変更のない再固定 |
| `predicted`・`measured` | 手で書いた予測（列挙される拡張と範囲、列挙から漏れる実体）と、比較器の測定値 |

```bash
python3 -B scripts/research/compare-versions.py --record examples/p2-versions/p2-temporal-measurement-draft-2-to-draft-3.json   # git の履歴に旧版・新版のコミットが要る
python3 -B -m unittest tests.p2.test_observer_version -v
```

手順（V1〜V8）と予測は [設計73](../../docs/research/73-p2-r-design.md)・[期待74](../../docs/research/74-p2-r-cases.md)。宣言と予測は作成者の主張です。履歴がない環境では、記録に沿った比較は行われません。
