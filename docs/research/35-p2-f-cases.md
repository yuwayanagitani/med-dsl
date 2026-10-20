# P2-f：実装前の数量の正例・反例と手指定期待

作成日：2026-10-20。状態：**設計用の期待。runtime・実行用JSON・機能の実測結果はまだない**。[意味設計34](34-p2-f-design.md) を基準に、Q24/N12/B4条件と、別枠の射影の反例D2件を用意します。全て架空で、臨床の閾値・実測定の精度・実単位の対応を表しません。

## 1. 表記

`x unit` は点リテラル、`[a,b)` 等は端点の開閉を持つ数値領域です。分数は正確な有理数。明記しない種類は `k_a`、uncertaintyは明示的な `not_evaluated`、originはliteral、必須能力は既知の数量profileです。比較の左右は、同一IDと明記した例以外は異なるIDです。

換算は入力数値×入力単位の倍率÷目標単位の倍率です。基準への倍率は、u_base=1、u_ten=10、u_third=1/3、u_half=1/2、v_base=1、w_base=1、w_hundredth=1/100。種類・次元の定義は設計34の局所表に従います。

## 2. Q：数量の意味24条件

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| Q01 | 2 u_ten → u_base | `computed`、閉じた単一点[20,20] |
| Q02 | 20 u_base → u_ten | `computed`、[2,2]。Q01の逆換算 |
| Q03 | 1 u_third → u_base | `computed`、[1/3,1/3]。丸めた小数にしない |
| Q04 | 1 u_base → u_third | `computed`、[3,3]。倍率の方向を逆にしない |
| Q05 | 未約分の2/4 u_ten → u_base | `computed`、[5,5]。原入力の2/4は保持し、出力の分母は正・既約 |
| Q06 | -3 u_half → u_base | `computed`、[-3/2,-3/2]。値を非負の確率として検証しない |
| Q07 | (1,2] u_ten → u_base | `computed`、(10,20]。端点の開閉を維持 |
| Q08 | 区間形式の[3,3] u_third → u_base | `computed`、[1,1]。空集合と区別し、原入力の形式も保持 |
| Q09 | 1 u_ten と10 u_baseを比較 | `{equal}`、certain_relation=equal |
| Q10 | 2 u_base と3 u_baseを比較 | `{less}`、certain_relation=less |
| Q11 | 3 u_base と2 u_baseを比較 | `{greater}`、certain_relation=greater |
| Q12 | [1,2) u_base と[2,3] u_base | `{less}`。接しても左の終端を含まない |
| Q13 | [1,2] u_base と[2,3] u_base | `{less,equal}`、certain_relation=null |
| Q14 | (1,3) u_base と[2,4] u_base | `{less,equal,greater}`、certain_relation=null |
| Q15 | 異なるIDの[1,2] u_base と[1,2] u_base | 三関係全て。区間が同じでも値が等しいと断定しない |
| Q16 | 同じIDの[1,2] u_base を自身と比較 | `{equal}`。同一変数に対するx=xとして区別する |
| Q17 | 種類k_ratio_a、25 w_hundredth → w_base | `computed`、[1/4,1/4]。種類はk_ratio_aのまま |
| Q18 | k_aの1 u_base とk_bの1 u_base | `not_comparable / incompatible_quantity_kind`、値と関係集合はnull |
| Q19 | k_aの1 u_base とk_cの1 v_base | `not_comparable / incompatible_dimension`。種類不一致より先に次元不一致を示す |
| Q20 | k_ratio_aの1 w_base とk_ratio_bの1 w_base | `not_comparable / incompatible_quantity_kind`。無次元を全て同じ量にしない |
| Q21 | 未知の入力単位u_base_futureを持つ一点を、同じ数量IDで自身と比較 | `unassessed / unknown_unit`、関係集合null。同一参照でも解釈前に等号を返さない |
| Q22 | 未知の種類k_future、既知のu_baseから換算を要求 | `unassessed / unknown_quantity_kind`。単位から種類を補完しない |
| Q23 | Q21に未知の必須能力も付す | `unassessed / unknown_capability`。未知単位の判定より能力の停止を優先 |
| Q24 | origin=ai_candidateの2 u_ten → u_base | 数学的な結果は[20,20]。由来を保持し、clinical_confirmation=not_evaluated、主張追加なし・基底変換なし |

全てのQ条件で、原入力・origin・uncertaintyを変更しません。計算が完成しても測定の不確かさの伝播や臨床的妥当性は未評価です。停止・比較不能の行に、途中の正規化値や完成根拠を出しません。実行例へ展開した後のJSON数・必須パス数は未確定です。

## 3. N：入力・契約境界12条件

一条件を複数の拒否例へ展開します。各例は原則一つの違反を持たせます。具体的な細分化エラーcodeと検証順は実装前のnative仕様で固定し、以下の状態の区別を守ります。

| ID | 反例・境界 | 手指定の期待 |
| --- | --- | --- |
| N01 | 分母0/負、整数でない分子/分母、boolの分子/分母、有理数の欄欠落 | `invalid_input`。値を修復せず、boolを0/1にしない |
| N02 | 分子/分母のbit_lengthが63ちょうど・64 | 63までは構造上の範囲内。64では予算に依らず `resource_limit / rational_integer_limit`。丸めない |
| N03 | 逆転区間、片端欠落、等しい端点で片方が開く区間、boolでない開閉 | `invalid_input`。空集合をneitherや0へ変換しない |
| N04 | 既知の種類k_aで既知の単位v_baseを入力 | `invalid_input`。妥当な別種類どうしを比較するQ19とは区別 |
| N05 | uncertaintyの欠落、必須能力の欄/数量profileの欠落 | `invalid_input`。不確かさ0や既知の意味を既定値にしない |
| N06 | JSON小数や数値文字列を有理数として渡す。NaN/Infinity等のJSON外の値も別に試す | `invalid_input`。自動parse・浮動小数点化しない |
| N07 | 要求に単位表や倍率の上書きを加える、単位に任意の説明を足して意味を変える | `invalid_input`。nativeの局所表は要求が変えられない |
| N08 | magnitudeに片側打切り・無限区間・統計的な包含区間の専用形式を使う | 認識した範囲外の形式は `unsupported_profile`。有限区間や点に縮めない |
| N09 | 統計的uncertaintyの専用形式、外部形式の自動parse、丸め表示、種類間変換の操作を要求 | `unsupported_profile`。単なる倍率で代用しない。未知の余分な欄だけの入力は構造不正として別例にする |
| N10 | consumerのprofile/仕様hash/操作が違う、未知のquery種別 | `unsupported_profile`。旧handlerや近い単位名へ代用しない |
| N11 | 存在しない数量への参照、重複ID、空のqueries/quantities、不正なbudget | `invalid_input`。入力上限の超過は明示したresource_limitとして別例にする |
| N12 | 旧要求、全配列の順序入替え、新結果を基底のsupportedへ変換する退行 | 旧意味と入力を維持し、ID順の完成結果・根拠・課金が一致。基底への変換・臨床主張の追加を検出 |

最上位ホストの未登録schemaの既存拒否を、新機能のために読み替えません。N01〜N11の構造・型・上限・未対応の検査は、予算0と十分な予算で同じ結論にします。

## 4. B：資源4条件

課金式は `1 + 数量数 + convert行数×6 + compare行数×9`。未知・比較不能にも同じ行コストを予約します。以下は設計式の手計算で、runtimeの実測値ではありません。

| ID | 入力・予算 | 手指定の期待 |
| --- | --- | --- |
| B01 | 妥当な要求、予算0 | `resource_limit`、steps_used=0、未完了の値・関係集合・根拠はnull |
| B02 | 一数量・一convert行 | 完了に8必要。7で完成値なし、8で完成、9以上で同じ値・steps_used=8 |
| B03 | 二数量・一compare行。同一IDの比較も別に試す | 二数量なら12、同一IDの一数量なら11必要。直前で完成値なし、境界で完成。同一参照でも二オペランド分を払う |
| B04 | 一数量・ID順で二つのconvert行 | 全体に14必要。予算8では先行行だけ完成。0〜15を掃引し、完成済みの意味は不変・上限超過なし |

## 5. D：初回に実装しない射影の反例2件

| ID | 比較するもの | 設計上の期待 |
| --- | --- | --- |
| D01 | 1241/1000と1249/1000を、小数第1位への最近接丸めで表示 | 表示はどちらも1.2でも、正確な値の比較はless。表示だけを使う問いはこの区別を失う。原値を別添えしても表示自体の無損失を主張しない |
| D02 | 外部の数値文字列「2.3」と「2.30」 | 数値だけなら同じ有理数へ写せても、元の表記・精度の情報を保持したとは限らない。初回の入力型はこれを取り込まず、精度を0と補完しない |

D01の表示操作とD02の外部parseは、今回のruntime受入条件Q/N/Bの分母へ混ぜません。これらは後続の表示・取込の契約で先に探す反例です。[一次資料と作業定義の区別](34-sources.md) を参照してください。

## 6. 実装前の有限監査の再現

以下は設計の区間比較式を点の証人と照合する**単独の有限監査**です。MedDSLのruntimeを呼びません。端点{-1,0,1}から作る非空領域15個に、四つの正倍率を組み合わせ、異なる参照の3,600組と同一参照の60組を調べます。

隣接端点の間に一点だけを置くと、同じ開区間どうしのless/greaterを見逃すため、各領域に二つの内点を置きます。これは有限の設計式の照合であり、任意の実数・実単位への機械的な証明や、未実装のhandlerの試験ではありません。

```python
from fractions import Fraction as F
from itertools import combinations_with_replacement, product

def inside(x, d):
    a, b, ac, bc = d
    return (a < x or (ac and a == x)) and (x < b or (bc and x == b))

def formula(l, r, same=False):
    if same:
        return {"equal"}
    result = set()
    if l[0] < r[1]:
        result.add("less")
    if l[1] > r[0]:
        result.add("greater")
    a, b = max(l[0], r[0]), min(l[1], r[1])
    if a < b or (a == b and inside(a, l) and inside(a, r)):
        result.add("equal")
    return result

def witnessed(l, r, same=False):
    bounds = sorted({l[0], l[1], r[0], r[1]})
    points = set(bounds)
    for a, b in zip(bounds, bounds[1:]):
        points.update((a + (b-a)/3, a + 2*(b-a)/3))
    left = [x for x in points if inside(x, l)]
    right = [y for y in points if inside(y, r)]
    pairs = ((x, x) for x in left) if same else product(left, right)
    return {"less" if x < y else "greater" if x > y else "equal"
            for x, y in pairs}

domains = []
for a, b in combinations_with_replacement(map(F, (-1, 0, 1)), 2):
    for ac, bc in product((False, True), repeat=2):
        if a < b or (ac and bc):
            domains.append((a, b, ac, bc))
assert len(domains) == 15
scales = (F(1), F(10), F(1, 3), F(1, 2))
scaled = lambda d, s: (d[0]*s, d[1]*s, d[2], d[3])
count = 0
for l, r, s, t in product(domains, domains, scales, scales):
    l, r = scaled(l, s), scaled(r, t)
    assert formula(l, r) == witnessed(l, r), (l, r)
    count += 1
for d, s in product(domains, scales):
    d = scaled(d, s)
    assert formula(d, d, same=True) == witnessed(d, d, same=True)
    count += 1
assert count == 3660
print("quantity design comparisons:", count)
```

この有限監査と、Q/N/Bのruntime照合は別に記録します。実装後は種類・未知・確認の境界、換算、予算、CLI、旧経路、変異、原入力の保存も検査し、今回の数値領域の照合だけでパイロット全体が完了したとしません。

## 7. この設計を追加した時点の確認

2026-10-20、上記のコードをそのまま取り出してPython 3.14.4と3.11.17で実行し、両方で3,660組が一致しました。コード部分のSHA-256は `12184b31c450d117b1e29fdedfb644ed7316c2ee9fa02a27dc02639a2310cb4f`。実行記録は `data/research/p2-f-design/formula-check.json` に保存しています（Git管理外）。型・未知・臨床境界や新しいhandlerの評価は含みません。

変更した文書のローカルリンク・fence・Q/N/B/DのIDと件数・予算式の算術を検査し、既存の資料整合テスト8件も通過しました。この8件は旧P2-d資料に対する検査で、数量の正しさの検査ではありません。既存評価器の `preflight()` で427ファイルのsnapshotが変更されていないことも確認しました。manifest hashは `96ae56c57ec5c85ef8122a5daac1712aa10b4dd5668a88491cab504dc18a1a79` のままです。

今回は文書だけの追加・更新で、既存runtimeの全回帰・数量用の実行例の照合・新native仕様の固定は行っていません。独立確認・評価用正解の凍結も未実施です。
