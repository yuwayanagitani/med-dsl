# R4：一次資料と確認範囲

確認日：2026-10-18。R3 の利用条件を継承します。以下の既存仕様の事実と、[R4](04-evaluation.md) の独自の評価契約・合格条件は別です。40 ケースの数、分割、100%・0 件の工学的条件を各標準や臨床ガイドラインが要求しているわけではありません。

| ID | 一次資料・版 | 確認した箇所／R4 への用途 | 限界 |
| --- | --- | --- | --- |
| R4-S01 | [NLM RxNorm Technical Documentation](https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html)、確認時点の文書 | §12.4 RXNCONSO、§12.5 RXNREL、§12.7 RXNSAT の列。関係の向き、出典、名称と属性の投影を再確認 | 全医学的意味の定義を確認したわけではない。一般文書と固定した CPC の内容を区別 |
| R4-S02 | [NLM Appendix 1: RxNorm Relationships](https://www.nlm.nih.gov/research/umls/rxnorm/docs/appendix1.html)、確認時点 | RXCUI2→RELA→RXCUI1 の表、SCD の consists_of・has_dose_form。選定した実レコードの関係を追跡 | 関係グラフ全体の意味保存・臨床的代替性は未検証 |
| R4-S03 | [NLM CPC](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html) | 三ファイル、収載の範囲。固定版二つの実測結果は [追跡記録](04-material-probes.md) | 全体版・履歴ファイルを確保したとはしない。利用条件の根拠は [R3](03-sources.md) |
| R4-S04 | [HL7 FHIR R4 Procedure](https://hl7.org/fhir/R4/procedure.html)、[詳細](https://hl7.org/fhir/R4/procedure-definitions.html)、v4.0.1 | performed[x] の定義・選択型・多重度を保存 HTML と照合 | リソース全体の変換手順は未確認。外部用語の転用は含めない |
| R4-S05 | [HL7 FHIR R5 Procedure](https://hl7.org/fhir/R5/procedure.html)、[詳細](https://hl7.org/fhir/R5/procedure-definitions.html)、v5.0.0 | occurrence[x] の定義・Timing を含む選択型。狭い時点比較の根拠 | 同名型の存在だけで全意味の同等性は示さない |
| R4-S06 | [HL7 FHIR R5 ConceptMap](https://hl7.org/fhir/R5/conceptmap.html)、v5.0.0 | 対応の方向と用途、条件の存在を再確認。直接対応の比較条件に反映 | 今回の CPC 二版の公式対応表ではない。独自の状態・意味関係をそのまま FHIR の列挙値と称しない |
| R4-S07 | [HL7 FHIR R5 Extensibility](https://hl7.org/fhir/R5/extensibility.html)、v5.0.0 | modifier extension の未知処理に意味上の影響があること。K13・E10 の動機 | これらの架空例は FHIR 適合性試験ではない |

保守的拡張・問い合わせ範囲の理論上の区別は [R2b の出典と精読範囲](02b-sources.md) を引き継ぎます。R4 で原著の未読部分まで証明を確認したとはしません。K01〜K05 の小さな導出、K06 以降の期待判断、D/E の定義と正解草案は本プロジェクトによるものです。

実資料の集合比較はローカルの固定バイト列に対する計算、少数追跡はその投影と一次定義を照合した結果です。医学的な判断の独立レビューや人の作業時間の測定は未実施です。実行可能な変換器・体系の意味論・評価器は、この調査では追加していません。
