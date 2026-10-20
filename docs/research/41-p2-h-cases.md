# P2-h：表示射影の手指定期待

作成日：2026-10-20。状態：**実装前の設計期待**。[設計40](40-p2-h-design.md) のP36（意味）・N12（入力境界）・B4（資源）、計52条件です。変種を含むためJSON件数・必須パス数ではありません。runtime・実行用fixture・独立確認・評価用正解の凍結は未実施です。

## 1. 共通設定と読む範囲

全て架空データです。標準計画はP2-gの一slot S、数量Qのpoint `121/100 u_base`（k_a）、記録A（t2、confirmed）、内容に一致する人の確認RA（t3）、view v（as_of=t5）、convert query q（S→u_base）。時刻t1〜t9は2026-10-20の01:00〜09:00 UTCです。子の全体料金C=16です。

標準表示dはv/qを参照し、p=1、policy=`fiction:decimal-half-even@1`、自profile能力だけを要求します。標準questionはdisplay_text一件、retention=none、有効な十分予算。特記がなければrootはok、表示はcomputed、assessment_complete=trueです。原値や記録を変える例は、**新しい内容に一致する数量hash・記録hash・確認を用意してから**処理します。N条件の古いhashを使う負例とは区別します。

artifact同一とは、型・単位・双方の仕様hash・p・丸め方針・係数k・textが全て同じことです。出所根拠・表示ID・原要求を含む応答全体の同一ではありません。rounding_cellの開閉は、測定誤差・真値・確率を意味しません。

## 2. 意味P01〜P36

| ID | 設定 | 手指定の期待 |
| --- | --- | --- |
| P01 | 標準 | k=12、text=`1.2`、セル[23/20,5/4]。display_textはpreserved/`1.2`、表示の問いだけに限定した認定 |
| P02 | x=124/100 | P01とartifact同一。原値の121/100と124/100を統合したことにはしない |
| P03 | x=5/4、p=1 | 半整数の偶数側へk=12、`1.2`。セル上端を含む |
| P04 | x=27/20、p=1 | k=14、`1.4`。奇数側の1.3ではない |
| P05 | x=-5/4、p=1 | k=-12、`-1.2`。符号を無視した切上げにしない |
| P06 | x=-27/20、p=1 | k=-14、`-1.4` |
| P07 | x=1/20、-1/20、0、p=1の各変種 | 全てk=0、`0.0`、セル[-1/20,1/20]。`-0.0`を出さない |
| P08 | x=1/3、p=2 | k=33、`0.33`、セル(13/40,67/200)。両端は開 |
| P09 | x=1/2、p=2 | k=50、`0.50`、セル[99/200,101/200]。末尾零を削らない |
| P10 | p=0、x=5/2,-5/2,7/2,-7/2 | textは順に`2`,`-2`,`4`,`-4`。小数点なし |
| P11 | x=9007199254740993、p=0 | 同じ整数文字列を表示。float化して9007199254740992へ潰さない |
| P12 | 原数量1 u_thirdをu_baseへconvert、p=2 | 正確な1/3を得てから`0.33`。原数量を先に小数へ丸めない |
| P13 | 四表・view/query・displays/questionsの入力順を反転 | 出力はID順、artifact・意味回答・根拠は同じ。入力hashとsource_bundle.request_planの原順序の違いは許す |
| P14 | 原数量は未約分2/4 u_base、p=2、bundleあり | text=`0.50`。source_answerのexact_valueは1/2、request_planには2/4が残る。元の小数字句を復元したとはしない |
| P15 | 原数量は非単一点(1,2] u_base | unassessed / unsupported_display_domain。artifact・セル・数値根拠はnull、questionはunassessedで回答null。中点・端点だけを表示しない |
| P16 | 原数量は閉じた単一点区間[1,1]、p=1 | text=`1.0`。bundleにはintervalの元の型・開閉を保持。幅のある区間を潰した例に数えない |
| P17 | 方法unknown / unspecifiedの各変種 | P2-gのmethod_unknown / method_unspecifiedを保持。表示の整形だけを成功させない |
| P18 | 人の確認なし、または確定性suspected | no_adopted_measurement。artifact・数値回答なし |
| P19 | 記録と数量をAI由来にし、確認なし/内容一致の人の確認あり | 前者は保留。後者は数値表示可能だが両originを根拠へ保持。clinical_confirmation=not_evaluated、臨床主張なし |
| P20 | 同じslotに同じ数値・表示の二つの適格記録、訂正辺なし | unresolved_measurement_conflict。等しい表示で採用の競合を消さない |
| P21 | 可視の保留/訂正済み記録・数量に未知能力、または表示自身に未知能力 | 子の範囲内の未知能力を無視せずunknown_capability。表示能力だけの未知も当該行をunassessedにする。全例でartifactなし |
| P22 | 標準セルでthreshold：ge 11/10、le 13/10、eq 13/10 | projection_answerは順にtrue,true,false、全てpreserved。falseをnullや未評価へ変えない |
| P23 | 標準の偶数k=12、閾値がセルの端点 | 下表の閉端の期待。原値xだけを検査してpreservedとしない |
| P24 | x=13/10、p=1の奇数k=13、閾値がセルの端点 | セル(5/4,27/20)。下表の開端の期待。開端を含めない |
| P25 | 標準にexact_valueを問う、bundleなし/あり | 両方projection_answer=null/out_of_scope。なしはsource_answer=null、ありはsource_replayで121/100。認定はどちらもnot_certified |
| P26 | ge 61/50、bundleなし/あり | 標準の原回答はfalseだがセル上では一定でない。両方out_of_scope/null。bundleありだけ別経路のsource_answer=false |
| P27 | display_textだけを問いbundleあり | preserved。source_answer=null、additional_source_used=false。別添えの利用可能性だけで使用済みにしない |
| P28 | 二slot・二convertで121/100と124/100、同じ型・p=1。ge 61/50、bundleあり | 二artifact同一、source_answer=false/true。両projection_answer=null/out_of_scope、全体not_certified。受理できる原要求の喪失の反例 |
| P29 | P28でexact_valueを問う | 二artifact同一、二source_answerは121/100と31/25。原値の一般復元ができない。別添えを含む応答の相違をartifactの区別と呼ばない |
| P30 | P28の二artifactをそれぞれcanonical JSONへ符号化・復号 | 復号は元artifactと一致し、符号化bytes/hashも同じ。それでも元のgeの区別は戻らずnot_certified |
| P31 | 二slotの同じ数値で、記録ID・方法の版・originを変える。display_textだけを問う | artifactは同一でもprojection_evidenceの出所は異なる。認定するのは表示の問いだけで、文脈・記録の同一性はscope外 |
| P32 | x=1251/1000からp=2とp=1を直接作る | 順に`1.25`,`1.3`。p=2の表示をもう一度p=1に丸めた`1.2`を採らない。各表示は厳密値から独立に作る |
| P33 | x=1/2でp=1/2、または別の数量を1 u_base / 1 u_tenへ表示、またはk_a/k_bの同じ数値 | 末尾零・型・単位の相違をartifactに保持。同じtextだけで同一としない。p/目標単位の変更でも元の記録・確認hashは不変 |
| P34 | Aの後に確認済み訂正Bを追加、過去/現在view、原計画の保存 | P2-gどおり過去はA、現在はBの厳密値から表示。旧snapshotを再実行すれば旧表示。最新の数量参照で置換しない |
| P35 | 計画に未来の未知能力記録、未参照slotの未知能力、または未参照convertを追加 | P2-gの範囲に従い、無関係な未知能力で当該表示を止めない。未参照convertも子の料金Cへ数える。Hs・根拠・料金の同一までは要求しない |
| P36 | p=6、AI確認済み入力・未評価の不確かさ、標準の別添え | 表示の桁数から測定精度・真値・確率を作らない。rounding_cellは数値丸めの逆像。uncertainty_propagated=false、converted_to_base=false、clinical_assertions_added=[] |

P13では入力hashの差を無条件に捨てず、各原入力から再計算して照合します。Hs・記録/数量の内容hash・artifact hash・数量計算の根拠は保持して比べます。

P35の「未参照」は表示が参照しない子のqueryと、子のqueryが参照しないslotを区別します。未来の記録でも構造やhashが不正なら、N条件として要求全体を拒否します。

### P23/P24：端点とfalse/null

各表のT/Fはpreservedかつboolのtrue/false、Oはout_of_scopeかつprojection_answer=nullです。xの実際の値によるsource_answerとは別です。

| operator | 閉セルのL=23/20 | 閉セルのU=5/4 | 開セルのL=5/4 | 開セルのU=27/20 |
| --- | --- | --- | --- | --- |
| lt | F | O | F | T |
| le | O | T | F | T |
| eq | O | O | F | F |
| ge | T | O | T | F |
| gt | O | F | T | F |

## 3. 入力境界N01〜N12

| ID | 不正・未対応の入力 | 期待 |
| --- | --- | --- |
| N01 | 必須欄の欠落、余分な欄、null、型違い | invalid_input。measurement_planの中にbudgetを持ち込む場合もunknown_field |
| N02 | display/question IDの重複、未解決view/query | invalid_input。question IDの同一は別表示間では許す |
| N03 | 未来・未参照を含む計画の参照hash、review内容hash、時刻・訂正の不正 | P2-gのinvalid_inputを保持。予算を先に消費して隠さない |
| N04 | decimal_placesがbool/負数/文字列、7以上の整数 | 前三者invalid_input。7以上はunsupported_profile。巨大整数でも10の累乗を計算してから拒否しない |
| N05 | 閾値が分母0/負、bool、小数・NaN等、63bit超過 | 不正はinvalid_input、63bit超過はresource_limit。未約分は妥当なら原入力に保持し、計算値だけ約分 |
| N06 | 計画の不正な数量、空区間、既知property/種類/次元の矛盾 | P2-g/P2-fの静的拒否を維持。区間が妥当だが非単一点の場合のP15と区別 |
| N07 | consumer/native実体/依存profile/hash不一致 | 未対応指定はunsupported_profile、nativeファイル自体の不整合はinvalid_input。旧版へ黙って代用しない |
| N08 | 未対応丸めpolicy、retention、question kind/operator、子のcompare | unsupported_profile。未知operatorに正答を推測しない |
| N09 | child_result・certificate・artifactを入力へ足す、またはそれを計画の代わりに送る | invalid_input。自己申告の完成結果を信用して進めない |
| N10 | 空displays/questions、件数超過、1 MiB・深さ64超過 | 空はinvalid_input、静的上限はresource_limit。予算0でも同じ拒否 |
| N11 | 不正予算、C>100,000となる妥当な大計画、子の資源停止の注入 | 不正予算はinvalid_input/静的上限。大計画はCを払えずresource_limit、子を呼ばない。注入された子の部分結果も表示に拾わない |
| N12 | 旧要求、並べ替え、別snapshot、臨床昇格・出所の除去・別添え認定・途中漏出の変異 | 旧観測はcertifier以外不変。原値・元の確認・旧handlerを変更しない。変異は対応するP/B条件で検出 |

## 4. 資源B01〜B04

標準は一表示・display_text一質問、子C=16、表示料金10、最後の確定1です。数値は手指定の課金式から算出し、将来の実行出力から正解を作りません。

| ID | 条件 | 期待 |
| --- | --- | --- |
| B01 | 予算0、16、17 | 0は処理開始前。16は子料金が未払いで子を呼ばない。17はbudget=16の子を一度だけ呼べるが、表示は未完成。いずれもartifact・セル・質問結果・両根拠はnull、認定なし |
| B02 | 予算26、27、28、29 | 26は表示途中で全てnull。27は表示行が完成するが最後の1不足でroot=resource_limit、certificate=not_certified、completionをincompleteへ。28で全体完了・表示の問いに限った認定。29でもsteps_used=28 |
| B03 | 同じ子の行からID a/bの二表示、一質問ずつ。予算27、36、37、38 | 27と36はaだけ完成。37は両行完成だが全体確定は未完了。38で全体完了。子budget=16、呼出一回。別添えの有無で料金は変えない |
| B04 | 静的不正と有効な全予算、未知/範囲外/区間の意味停止、子資源停止、セルや根拠の早期漏出 | 静的不正は予算非依存。意味停止でも同じ行料金を払い、未完成に値・根拠なし。子資源停止では全表示未完成、最終料金不足でも認定なし。漏出変異を共通検査器が検出 |

P28の二slot二convert計画では子C=31、一質問の二表示ならH=53です。子の全体料金を標準の16と誤認する変異も検査します。問いを一つ増やすたびに表示料金を2増やします。

## 5. 設計式の有限点検

以下はMedDSLを呼ばない単独コードです。丸め式・セルの開閉・閾値の十分条件だけを点検します。文字列整形・版の照合・子計算・確認・予算・認定の実装は検査しません。将来のruntimeのテスト件数へ加算しません。

Decimalとの比較はこの小さい有限入力で精度80を使う点検で、任意の有理数を有限精度で先に割ってよいという実装方法の採用ではありません。

```python
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction as F


def coefficient(x, p):
    z = x * 10**p
    a, rem = divmod(z.numerator, z.denominator)
    twice = 2 * rem
    return a + int(twice > z.denominator or
                   (twice == z.denominator and a % 2 != 0))


def cell(k, p):
    s = 10**p
    return F(2*k-1, 2*s), F(2*k+1, 2*s), k % 2 == 0


def inside(x, lo, hi, closed):
    return (x > lo or (closed and x == lo)) and (x < hi or (closed and x == hi))


def decide(op, t, lo, hi, closed):
    all_true = {'lt': hi < t or (hi == t and not closed),
                'le': hi <= t, 'eq': False, 'ge': lo >= t,
                'gt': lo > t or (lo == t and not closed)}[op]
    all_false = {'lt': lo >= t, 'le': lo > t or (lo == t and not closed),
                 'eq': not inside(t, lo, hi, closed),
                 'ge': hi < t or (hi == t and not closed), 'gt': hi <= t}[op]
    return True if all_true else False if all_false else None


def test_value(op, x, t):
    return {'lt': x < t, 'le': x <= t, 'eq': x == t,
            'ge': x >= t, 'gt': x > t}[op]

rounds = cells = questions = 0
with localcontext() as ctx:
    ctx.prec = 80
    for n in range(-200, 201):
        for d in range(1, 21):
            for p in range(4):
                exact = coefficient(F(n, d), p)
                dec = (Decimal(n)/Decimal(d)).quantize(Decimal(1).scaleb(-p), rounding=ROUND_HALF_EVEN)
                assert exact == int(dec * 10**p)
                rounds += 1
for k in range(-20, 21):
    for p in range(4):
        lo, hi, closed = cell(k, p)
        width = hi-lo
        for x in (lo-width/4, lo, lo+width/4, (lo+hi)/2, hi-width/4, hi, hi+width/4):
            # 距離と偶奇の順で近隣整数を選ぶ別計算。
            z = x*10**p
            base = z.numerator//z.denominator
            nearest = min(range(base-1, base+3), key=lambda j: (abs(z-j), j % 2))
            assert (nearest == k) == inside(x, lo, hi, closed)
            cells += 1
        for t in (lo-width, lo, lo+width/4, (lo+hi)/2, hi-width/4, hi, hi+width):
            cuts = sorted({lo, hi, *([t] if lo < t < hi else [])})
            witnesses = [x for x in cuts if inside(x, lo, hi, closed)]
            witnesses += [(a+b)/2 for a,b in zip(cuts, cuts[1:])]
            for op in ('lt','le','eq','ge','gt'):
                answers = {test_value(op, x, t) for x in witnesses}
                expected = next(iter(answers)) if len(answers) == 1 else None
                assert decide(op,t,lo,hi,closed) is expected
                questions += 1
assert (rounds, cells, questions) == (32080, 1148, 5740)
print({'rounds': rounds, 'cells': cells, 'questions': questions})
```

今回の点検は丸め32,080組・セル1,148組・閾値5,740組です。これは有限の式の照合で、外部標準への適合、臨床的正しさ、任意の問いの保存性の証明ではありません。次はこの期待を実行例へ固定し、設計40に沿って最小実装を作ります。

## 6. 今回の確認と固定対象

上記の単独コードをPython 3.14.4/3.11.17で点検し、全assertが通過しました。手指定の丸め値・二重丸めの反例・端点表も別に照合しました。結果は `data/research/p2-h/design-audit.json` に記録しています（Git管理外）。既存の統合評価は版比較を省いて `data/research/p2-d/p2-h-design/` で通過しました。新しいruntimeの試験や、既存全テストの再実行を行ったという意味ではありません。

P2-g時点の固定対象は663ファイルのままです。manifest hashは `ef7cf5fe4a3c304765f38b5576db61629d7f4f9696318322bcce205708883e4b`、束hashは `23c9c49095316533213edb38fd6ff11310fb98b756e891cbe60c071c76e49bdb`。今回は設計文書だけを追加し、実装時に明示的に固定対象へ加える方針です。独立確認・評価の凍結はfalseを維持します。
