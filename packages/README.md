# 試作の配置方針

まだコア実装はありません。最終目標は [変化に原理的に耐えるコード体系の確立](../docs/vision.md) です。[R6](../docs/research/06-prototype-brief.md) で、最初の P0 は Python 3.11 以降・標準ライブラリを使う単一ライブラリとして選定しました。以下の配置は実装予定で、まだディレクトリを作成していません。

| 配置予定 | 責務 |
| --- | --- |
| `src/med_dsl/model.py` | 定義参照、役割付き atom、主張・確認・文脈の型 |
| `src/med_dsl/validation.py` | 入力構造、参照・依存版・ハッシュ、資源上限の検査 |
| `src/med_dsl/definitions.py` | S1/S2 の認定、対応断片の定義・包含 |
| `src/med_dsl/ledger.py` | 参照時点、確認、明示的な訂正から主張を選択 |
| `src/med_dsl/query.py` | 文脈内の正の計算、結合、明示否定の検索、根拠追跡 |
| `src/med_dsl/compare.py` | 指定問い合わせの前後差と比較不能 |
| `src/med_dsl/cli.py`・`__main__.py` | 同じライブラリ関数を呼ぶ薄い JSON 入出力 |
| `tests/` | [P01〜P22](../docs/research/06-p0-contract.md) の意味契約の検証 |

外部アダプター、DSL の parser、臨床 SDK、独立した ontology や compiler の package は、試作で責務が確認できてから分けます。将来の臨床ライブラリの公開言語を Python に固定する決定でもありません。移行用の接続先や P0 の制約を、体系全体の表現能力に固定しません。
