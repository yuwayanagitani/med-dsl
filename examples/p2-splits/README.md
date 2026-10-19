# 概念の分割の併用の例（P2-c、K04 型・鎖・独立）

[P2-c の設計 25](../../docs/research/25-p2-c-design.md) の、複数の分割の併用（記号を共有し得る）の例です。個別には保存的な二つの分割が、併用すると旧語彙に新しい含意を作る（K04 型）場合と、部分を共有しても保存的な場合、入れ子の鎖、互いに素な併用を含みます。状態：**作成者の草案・独立確認前・評価用正解の凍結なし**（`independent_review` / `evaluation_frozen` は false）。結果の記録は [26](../../docs/research/26-p2-c-results.md)。述語名・主体・文脈はすべて架空です。

この系列は共通の評価（P1 の20条件・80 JSON・417必須パス）にも、231開発テスト、レビュー系列、防護例（[p2](../p2/README.md)）、概念の分割（[p2-split](../p2-split/README.md)）にも加えません。別の分母（37 例）として扱います。ただし宣言が根拠として引くので、共通 manifest（lock）には載せます。

```bash
python3 -m unittest tests.p2.test_split_combination tests.p2.test_combinations -v   # 例・独立オラクル・全数・差分・独立の検査
python3 scripts/research/check-extensions.py                                         # 宣言が引く防護例を評価する
```

## 作り方

- **期待結果は、設計 25 の意味から手で導きました**（処理系の出力から生成していません）。例外は予算の境界の n（完了に要る最小の steps。判定 8、問い合わせ 10）だけで、測りました。
- 例は `check_split_combination`（併用の保存性の判定）と `query_split_combination`（併用での候補集合）の要求と、同じ台帳を併用を知らない消費側（基底の `query`）として読む要求です。後者は、併用の結論が基底の状態に変換されないこと（X05）と、併用の能力を理解しない消費側の停止（X04 に当たる）のために置いています。
- K04 型の例（`check-k04-shared-parts`、`query-k04-old-data`）は、同じ併用の静的な判定とデータでの結果です。判定が不認定なら旧データだけの状態で併用が矛盾し、保存的なら矛盾しません（設計 25 の J5）。
- 実装のゲートを壊した変異を、これらの例が検出するかは [26 の §4](../../docs/research/26-p2-c-results.md) に記録しました。

## 例（37 件）

| ID | ファイル | 義務 | 種類 | 内容 |
| --- | --- | --- | --- | --- |
| SC01 | check-k04-shared-parts | JOINT-3, JOINT-1, JOINT-6 | refusal | K04 型：部分を共有する二つの分割は、単独ではどちらも保存的だが、併用は旧語彙に P = R を強制するので不認定（反例つき） |
| SC02 | check-shared-one-part-conservative | JOINT-3 | non_conversion | 部分を一つ共有しても、各親に固有の部分があれば保存的（森の十分条件の外でも、全数の判定は認定する） |
| SC03 | check-chain | JOINT-4, JOINT-1 | non_conversion | 入れ子の鎖（親が別の分割の部分）は森で、保存的 |
| SC04 | check-disjoint | JOINT-2, JOINT-1 | non_conversion | 語彙が互いに素な併用は、成分が分かれ、保存的 |
| SC05 | check-same-parent-twice | JOINT-1, JOINT-3 | non_conversion | 同じ親の二つの細分は森（部分は重ならない）で、保存的 |
| SC06 | check-cyclic | JOINT-1 | non_conversion | 「部分→親」に閉路がある併用は cyclic と分類する（旧記号がなければ保存性は自明） |
| SC07 | check-individual-certificates-refused | JOINT-1, JOINT-3 | refusal | 個別の認定票を併用の根拠として受け付けない（未知の項目として拒否） |
| SC08 | check-claimed-structure-refused | JOINT-1 | refusal | 要求の構造の自己申告（disjoint など）を受け付けない：構造は分割から再計算する |
| SC09 | check-duplicate-split | JOINT-5 | refusal | 同じ分割を二度宣言できない |
| SC10 | check-too-many-splits | JOINT-5 | refusal | 分割は 4 個まで |
| SC11 | check-vocabulary-limit | JOINT-5 | refusal | 語彙は 10 記号まで |
| SC12 | check-symbol-has-rules | JOINT-5, R6-1 | refusal | 規則に現れる述語の分割は範囲外 |
| SC13 | check-extra-axiom-refused | R6-1 | refusal | 併用でも公理を追加・変更できない |
| SC14 | check-consumer-profile | K-ID, K-STOP | refusal | consumer の profile が違えば unsupported_profile |
| SC15 | check-consumer-spec-hash | K-ID | refusal | consumer が違う仕様の hash を持てば拒否 |
| SC16 | check-consumer-operations | K-STOP | refusal | consumer が未登録の操作を宣言していれば止まる |
| SC17 | check-unsupported-operation | K-STOP | refusal | 未登録の操作は unsupported_profile |
| SC18 | check-budget-zero | K-STOP, K-INV, K-RES | refusal | 予算 0 では認定票を出さない |
| SC19 | check-budget-below | K-RES | boundary | 課金の境界：steps が 7（完了に要る 8 より 1 少ない）で止まる |
| SC20 | check-budget-exact | K-RES | boundary | 課金の境界：steps がちょうど 8 で完了する |
| SC21 | query-k04-old-data | JOINT-3, JOINT-6, R6-2 | refusal | K04 型：旧記号だけの採用された状態（P 肯定・R 否定）で、併用は矛盾する（単独では open と parent_opposed）。旧データで矛盾する＝併用は保存的でない |
| SC22 | query-base-unchanged-by-the-combination | R2-4, JOINT-6 | non_conversion | 併用が矛盾する状態でも、基底の問い（P の支持・R の否定）は変わらない：併用の結論は基底の状態に変換されない |
| SC23 | query-shared-part-narrows | JOINT-3, JOINT-6 | non_conversion | 部分を共有する併用：R の否定が共有する部分 A を除き、P の候補が単独の open から single [B] に狭まる（単独の結果では分からない） |
| SC24 | query-chain-exclusion-flows | JOINT-4, JOINT-6 | non_conversion | 鎖：前段の除外（P かつ B でない → A）が後段に流れ、後段は単独では no_parent だが、併用では open [C, D] |
| SC25 | query-chain-loss-not-recovered | JOINT-4 | non_conversion | 鎖：前段が A と B を区別していない個体（P だけが採用）は、後段の分割だけでは葉まで確定しない（後段は no_parent、葉の候補は B・C・D） |
| SC26 | query-chain-later-info-flows-back | JOINT-4, JOINT-6 | non_conversion | 鎖：後段の情報（C の肯定）が前段へ流れ、A が定まる（前段を単独で見ると no_parent） |
| SC27 | query-disjoint-factors | JOINT-2, JOINT-6 | non_conversion | 互いに素な併用：各分割の併用での結果は単独の結果と同じ（differs が偽） |
| SC28 | query-disjoint-violation-does-not-leak | JOINT-2, JOINT-6 | non_conversion | 互いに素な併用：一方の分割が矛盾しても、他方の結果は矛盾の影響を受けない（成分ごとの分解） |
| SC29 | query-ai-candidate-pending | K-INV, R2-3 | non_conversion | 確認のない AI 候補は併用でも候補を狭めず、保留として残す |
| SC30 | query-unknown-capability-blocks | K-STOP, K-INV | refusal | 未知の能力を要求する保留中の主張があれば、その文脈の行を解釈しない |
| SC31 | query-conflict-blocks | K-STOP | refusal | 同じ原子の肯定と否定がともに採用されていれば、解決せずに止める |
| SC32 | query-combination-capability-understood | R2-5 | non_conversion | 併用と分割の能力を要求する主張は、併用を理解する消費側が解釈する |
| SC33 | base-unaware-consumer-stops-on-combination-capability | R2-5, K-INV | refusal | 併用の能力を要求する主張は、併用を理解しない消費側（基底）には文脈ごと解釈されない |
| SC34 | query-budget-zero | K-STOP, K-INV, K-RES | refusal | 予算 0 では、候補集合も部分の値も返さない |
| SC35 | query-budget-below | K-RES | boundary | 課金の境界：steps が 9（完了に要る 10 より 1 少ない）で止まる |
| SC36 | query-budget-exact | K-RES | boundary | 課金の境界：steps がちょうど 10 で完了する |
| SC37 | query-self-claim-refused | R2-5 | refusal | 要求の自己申告（read_only など）を根拠にしない |
