# P1-c の実行例

全て架空データ・作成者草案。H13〜H19 の7条件を27 JSON・126必須パスに具体化しました。独立確認・評価用正解の凍結は未完了です。元の [8設計例](../p1/README.md) は変更していません。

```bash
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-c/coverage-countermodel.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-c/existential-without-named-witness.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-c/event-renaming-chain.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-c/lossy-composition.json
PYTHONPATH=src python3 -m med_dsl --fixture examples/p1-c/new-guarantee-independent-of-old-binary.json
python3 scripts/research/evaluate-p1-c.py --cli
```

[実行契約](../../docs/research/14-p1-c-contract.md) と [結果・制限](../../docs/research/14-p1-c-results.md) を参照してください。CLI は request だけを評価し、expected は計算へ渡しません。期待条件は runtime の出力から作っていません。

| 条件 | JSON数 | 主な期待 |
| --- | --- | --- |
| H13 | 3 | A⊑B の追加で旧モデルを失う。対照の恒等 template は認定。証拠不足は未評価 |
| H14 | 1 | 存在を含意しても B(a) を生成しない。有限モデルと既知導出を区別 |
| H15 | 3 | 未記載を否定にする変更を明示。未知能力を否定にしない |
| H16 | 7 | 事象化と一対一改名の合成。中間実体・方針・依存・翻訳後 Q の不一致を拒否 |
| H17 | 5 | 後段の無損失符号化で前段の喪失を埋めない。別添えの原情報と保証範囲を明示 |
| H18 | 2 | 1/2要素の一致と全モデルの被覆を区別し、3要素の反例を検証 |
| H19 | 6 | 原保存・既知 handler・依存の可用性・独立した新側の保証を別に検査 |

モデルは与えられた候補を検証し、任意理論の反例を自動探索しません。certified の正例も既知 template の限定した十分条件です。P1-b の有限照合票をそのまま認定票へ昇格させません。

manifest の全ファイルの生バイトハッシュ・サイズを先に照合し、API/CLI 各2回、必須パス、入力保持、再実行を検証します。結果は Git 管理外の `data/research/p1-c/`。全将来の意味・永続性・臨床性能を保証する評価ではありません。
