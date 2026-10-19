# 概念の分割の例（P2-b、K06）

[P2-b の設計 23](../../docs/research/23-p2-b-design.md) の「概念の分割」（旧い概念 P が部分 P1・P2 に分かれる）の例です。旧い記録 `P(a)` には、どちらの部分かを区別する情報がない。状態：**作成者の草案・独立確認前・評価用正解の凍結なし**（`independent_review` / `evaluation_frozen` は false）。結果の記録は [24](../../docs/research/24-p2-b-results.md)。述語名・主体・文脈はすべて架空です。

この系列は共通の評価（P1 の20条件・80 JSON・417必須パス）にも、231開発テスト、レビュー系列、防護例（[p2](../p2/README.md)）にも加えません。別の分母（34 例）として扱います。ただし宣言が根拠として引くので、共通 manifest（lock）には載せます。

```bash
python3 -m unittest tests.p2.test_concept_split -v      # 例・独立オラクル・全数列挙・予算の掃引・X04/X05/X14
python3 scripts/research/check-extensions.py            # 宣言が引く防護例を評価する
```

## 作り方

- **期待結果は、設計 23 の意味から手で指定しました**（処理系の出力から生成していません）。例外は予算の境界の n（完了に要る最小の steps = 8）だけで、測りました。
- 例は `query_split`（分割の候補集合）の要求と、同じ台帳を**分割を知らない消費側**として読む基底（P0）の `query` の要求の二種類です。後者は、X04（理解しない消費側の停止）、X05（変換の経路がない）、X14（旧い問いの回答の再現）のために置いています。
- 実装のゲートを壊した変異を、これらの例が検出するかは [24 の §4](../../docs/research/24-p2-b-results.md) に記録しました。

## 例（34 件）

| ID | ファイル | 義務 | 種類 | 内容 |
| --- | --- | --- | --- | --- |
| SP01 | old-record-only | R6-2, R6-6, R2-1, K-INV | non_conversion | K06：旧い記録だけでは、どの部分かを確定しない（候補集合と情報要求） |
| SP02 | part-asserted | R6-3, R2-3, K-INV | non_conversion | 部分が直接採用されていれば、他の部分は排他で除かれる（基底では他の部分は未決のまま） |
| SP03 | part-only-parent-derived | R6-4, R6-3 | non_conversion | 部分だけが採用されたとき、親は包含から導かれる（基底の親は未決のまま。基底へ変換しない） |
| SP04 | single-by-exclusion | K-INV, R2-2, R2-4, R6-4 | non_conversion | 他の候補がすべて除かれて一つに定まっても、採用された主張にはならず、基底の状態へ変換しない |
| SP05 | narrowed-three-parts | R6-3 | non_conversion | 三つの部分で一つが否定されたら、残り二つを候補にする |
| SP06 | parent-opposed | R6-2, R6-3 | non_conversion | 親が否定されたら、どの部分も成り立たない（候補なし。基底の部分は未決のまま） |
| SP07 | all-parts-opposed | R6-3 | non_conversion | すべての部分が否定されたら、被覆から親は成り立たない（基底の親は未決のまま） |
| SP08 | inconsistent-all-parts-opposed | R6-3, R6-6 | refusal | 親が採用され、すべての部分が否定されたら、公理に反する（解消を求める） |
| SP09 | inconsistent-two-parts-asserted | R6-3 | refusal | 二つの部分がともに採用されたら、排他に反する |
| SP10 | no-parent | K-INV, R6-2 | non_conversion | 親も部分も採用されていなければ、候補を作らず、未決を偽にしない |
| SP11 | ai-candidate-pending | K-INV, R2-3, R6-6 | non_conversion | 確認のない AI 候補は、候補集合を狭めず、保留として残す |
| SP12 | corrected-assertion | R2-3 | non_conversion | 訂正された部分の主張は採用に残らず、訂正後の主張だけが候補を決める |
| SP13 | views-over-time | R2-3, R6-5 | non_conversion | 参照時点ごとに別の結果を返す（時点の履歴を消さない） |
| SP14 | contexts-do-not-leak | R6-5 | non_conversion | 別の文脈の部分の主張は、旧い文脈の候補集合に入らない（文脈をまたぐ推論をしない） |
| SP15 | unknown-capability-blocks | K-STOP, K-INV | refusal | 未知の能力を要求する保留中の主張があれば、その文脈の行を解釈しない |
| SP16 | conflict-blocks | K-STOP | refusal | 同じ原子の肯定と否定がともに採用されていれば、解決せずに止める |
| SP17 | base-unaware-consumer-stops | R2-5, K-INV | refusal | 分割を理解しない消費側は、分割の能力を要求する文脈を解釈せず、保留・訂正済みの主張も落とさない |
| SP18 | aware-consumer-reads-the-same-ledger | R2-5 | non_conversion | 同じ台帳を分割を理解する消費側が読めば、保留・訂正済みを除いて解釈する |
| SP19 | old-queries-unchanged | R2-4, R6-2 | non_conversion | K06：旧い問い（基底）は分割の有無によらず、旧回答を再現する（部分の問いは未決のまま） |
| SP20 | single-is-not-base-support | R2-4, R6-4 | non_conversion | 分割の結論（残りの一つ）は、基底の問い合わせでは支持されない（変換の経路がない） |
| SP21 | symbol-has-rules | R6-1, R6-5 | refusal | 部分が包含の規則に現れる述語の分割は範囲外として拒否する |
| SP22 | duplicate-parts | R6-1 | refusal | 同じ部分を二度宣言できない |
| SP23 | parent-among-parts | R6-1 | refusal | 親を部分に含められない |
| SP24 | one-part | R6-1 | refusal | 部分が一つでは分割にならない |
| SP25 | undeclared-part | R6-1 | refusal | package に宣言のない述語を部分にできない |
| SP26 | non-unary-part | R6-1, R6-5 | refusal | 単項でない述語の分割は範囲外として拒否する |
| SP27 | extra-axiom-refused | R6-1 | refusal | 要求は公理を追加・変更できない（公理は仕様に固定されている） |
| SP28 | self-claim-refused | R2-5 | refusal | 要求の自己申告（read_only など）を根拠にしない：未知の項目として拒否する |
| SP29 | consumer-profile | K-ID, K-STOP | refusal | consumer の profile が違えば unsupported_profile |
| SP30 | consumer-spec-hash | K-ID | refusal | consumer が違う仕様の hash を持てば拒否する |
| SP31 | consumer-operations | K-STOP | refusal | consumer が未登録の操作を宣言していれば止まる |
| SP32 | budget-zero | K-STOP, K-INV, K-RES | refusal | 予算 0 では、候補集合も部分の値も返さない |
| SP33 | budget-below | K-RES | boundary | 課金の境界：steps が 7（完了に要る 8 より 1 少ない）で止まる |
| SP34 | budget-exact | K-RES | boundary | 課金の境界：steps がちょうど 8 で完了する |
