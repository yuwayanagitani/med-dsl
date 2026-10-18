# 試作の配置方針

最終目標は [変化に原理的に耐えるコード体系の確立](../docs/vision.md) です。[R6](../docs/research/06-prototype-brief.md) に基づき、Python の単一ライブラリとして [P0-d](../docs/research/10-p0-d-results.md) まで実装し、作成者草案の全22ケースを照合しました。外部依存はありません。

| 配置 | 責務・状態 |
| --- | --- |
| `src/med_dsl/model.py` | 役割付き atom、根拠、エラー、照合ステップの上限 |
| `src/med_dsl/validation.py` | 入力構造、参照・依存版・ハッシュ、資源上限の検査 |
| `src/med_dsl/definitions.py` | S1/S2 の認定、対応断片の定義・包含 |
| `src/med_dsl/ledger.py` | 参照時点、確認、明示的な訂正から主張を選択。未知能力が必要な主張を追跡 |
| `src/med_dsl/query.py` | 文脈ごとの正の閉包、事実の結合・明示否定の検索、衝突 atom ごとの両根拠と停止元の提示 |
| `src/med_dsl/compare.py` | 指定問い合わせの前後差と比較不能 |
| `src/med_dsl/cli.py`・`__main__.py` | 同じライブラリ関数を呼ぶ薄い JSON 入出力 |
| `tests/` | 116 件の開発テスト。ケース数・指定パス数・独立評価と区別 |
| `scripts/research/evaluate-p0.py` | 全22ケースのファイルハッシュ・指定パス・再実行・API/CLI を照合し、結果を Git 管理外へ記録 |

[P1](../docs/research/11-p1-design.md) は意味能力・コア改訂の研究設計のみです。有限予測、事象への引き継ぎ、認定と合成の責務を定めましたが、新しい runtime/module はまだ追加していません。次は P1-a の実行入出力と能力照合・有限予測を、既存の単一ライブラリ内で実装します。

外部アダプター、DSL の parser、臨床 SDK、独立した ontology や compiler の package は、試作で責務が確認できてから分けます。将来の臨床ライブラリの公開言語を Python に固定する決定でもありません。移行用の接続先や P0 の制約を、体系全体の表現能力に固定しません。
