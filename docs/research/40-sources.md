# P2-h：丸め・表示・精度の一次資料確認

確認日：2026-10-20。状態：**公開HTMLの対象箇所を閲覧**。[D03](03-data-access.md) に従い、仕様の閲覧と外部マスター・例・実装コードの取込を分けます。設計40と期待41のschema、逆像による判定、課金、認定範囲は本プロジェクトの作業定義です。

## 1. 確認した範囲

| ID | 主体・資料・参照版 | 読んだ箇所と確認できたこと | 今回の判断 |
| --- | --- | --- | --- |
| DS1 | W3C、[XPath and XQuery Functions and Operators 3.1 §4.4.5](https://www.w3.org/TR/xpath-functions-31/#func-round-half-to-even)、Recommendation 2017-03-21 | 最近接の桁への丸めで、等距離の場合は末尾が偶数となる側を選ぶ規則。float/doubleからの変換には期待と異なる結果があり得るとの注記 | 原有理数から整数商・剰余で直接決める。丸めを繰り返した表示を次の原値にしない。XPathの型・全数値・負のprecisionまでの実装とはしない |
| DS2 | Python Software Foundation、[Python 3.14 decimal：Rounding modes](https://docs.python.org/3.14/library/decimal.html#rounding-modes)、参照時の3.14系列HTML | ROUND_HALF_EVENと、零から離すROUND_HALF_UP等を区別。冒頭のモデル説明では精度・丸め規則がcontextの要素である | half-evenという名前だけでなく、方針・p・型をartifactに含める。小さい有限の式点検ではDecimalを別計算に使うが、本処理で有限精度の割算を先行させない |
| DS3 | HL7、[FHIR R5 v5.0.0 Datatypes：decimal](https://hl7.org/fhir/R5/datatypes.html#decimal)・[Quantity](https://hl7.org/fhir/R5/datatypes.html#Quantity) | primitive decimalとQuantity.valueの定義、Quantity.valueが暗黙の精度を伴い、comparatorを無視できない旨の説明 | 今回指定する表示桁数を、外部記録の精度や測定の不確かさに対応付けない。小数字句・比較子の取込、FHIR出力は別契約 |

W3Cの丸め規則は数学的な表示方針を選ぶ材料であり、医療用途にこの方針を推奨する根拠とはしません。FHIRの型・意味を本artifactが実装したとも扱いません。Pythonのページは更新されるため、今回の式の点検環境（3.14.4/3.11.17）と、閲覧した3.14系列の文書を区別します。

## 2. 独自に定めたこと

単一点だけを表示する初回の断片、0〜6桁、負の零の統合、ASCII表記、型付きartifactの射影範囲、丸めセル全体で一定の問いだけを認定する十分条件、原要求の別添えとsource_replay、P2-gを一度実行する共有予算は、作成者側の設計です。上記仕様がこの組合せを保証・要求しているという推論はしません。

セルの閉開と閾値の判定は設計40で手作業の導出を示し、期待41の単独コードで有限点検します。有限入力上限も含めた全ての問いの因子化を判定したとは扱いません。実世界の測定不確かさについては [P2-fの資料確認](34-sources.md) の未評価という境界を維持します。

## 3. 利用と残る調査

今回は発行主体のHTMLの閲覧に留め、外部マスター、仕様全文、コード実装、FHIRパッケージ、実測定データを取得・同梱していません。記録は独自の日本語要約とリンクです。丸める数量・検体・方法・単位は架空で、実検査の表示桁数や臨床閾値を選定したものではありません。

外部の精度・有効数字の取込、片側値・区間を誤解なく示す表示、実画面と確認負担、各国システムへの適合は今後の調査です。公開・ライセンス・独立確認の運用方針は変更しません。
