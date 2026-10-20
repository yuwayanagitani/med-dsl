# P2-j：表示接続の手指定期待・反例と設計式の有限点検

作成日：2026-10-20。状態：**実装前の設計期待**。[意味設計46](46-p2-j-design.md) のJ36/N12/B4、計52条件です。変種を含むためJSON件数・必須パス数とは異なります。runtime・実行用fixture・独立確認・評価用正解の凍結は未実施です。§5は式だけの点検で、実装評価へ数えません。

## 1. 共通設定

全て架空データです。dは `2026-10-ddT00:00:00Z`。標準のI計画は一slot S（主体u）、数量Q（k_a、point 121/100 u_base、不確かさ未評価）、記録A（period_quantity、[1,10)、rec=2、confirmed、revises=[]）、内容に一致する人の確認RA（3）、view v（k=8）、convert query q（S、t=5、target=u_base）です。property・既知の検体/方法はIの標準と同じ架空のものです。原記録/数量はobserved/literal由来で、Jに渡す計画にはbudgetを入れません。

標準表示dはv/q、p=1、既知のhalf-even方針・自profile能力だけ、questionはdisplay_text一件、retention=none、十分な予算です。標準C=16、J=28。artifactはcoefficient=12、text=`1.2`、セル[23/20,5/4]。rootはok、表示はcomputed、assessment_complete=trueで、表示の問いだけの認定です。

Bは別Qb=124/100 u_base、[4,6)、rec=6、確認RB=7、revises=[A]。CはQc=131/100、[5,6)、rec=8、確認RC=9、revises=[B]。Cを含む正例はk=9です。原内容を変える例はHq/Hr_iと人の確認を新しい内容に一致させます。古い確認を意図的に残すN条件とは区別します。

全例で両origin・原内容・子のnot_certifiedを保持し、臨床未評価・基底への変換なし・臨床主張追加なしを共通期待とします。認定はartifactだけの問いに限定します。artifact/hash/cell/両根拠がない意味上停止行と、六値欄全てnullの資源未完了行を分けます。

## 2. 意味条件J01〜J36

### 数値表示と型

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| J01 | 標準 | `1.2`、セル[23/20,5/4]、display_textはpreserved。新J profile/仕様と固定した量種・単位をartifactへ |
| J02 | x=5/4、27/20、-5/4、-27/20、p=1 | 順に`1.2`,`1.4`,`-1.2`,`-1.4`。等距離の偶数側へ直接丸める |
| J03 | x=9007199254740993、p=0 | その整数文字列。floatで9007199254740992へ潰さない |
| J04 | x=12501/10000、p=1 | 直接なら`1.3`。先に二桁の1.25へ丸めてから一桁へ丸めると`1.2`になる反例。原値から直接決める |
| J05 | x=1/20、-1/20、0、p=1 | 全て`0.0`、係数0。負の零を作らない |
| J06 | x=5/2、-5/2、7/2、-7/2、p=0 | `2`,`-2`,`4`,`-4`。小数点なし |
| J07 | 原数量1 u_third→u_base、p=2 | 厳密な1/3から`0.33`、係数33、セル(13/40,67/200)。Iで先に丸めない |
| J08 | 原数量未約分2/4 u_base、p=2、bundleあり、exact_valueも要求 | text=`0.50`、exact_valueのprojectionは範囲外、source_answer=1/2。原2/4と元の型を保持 |
| J09 | 原領域(1,2] | unsupported_display_domain、artifactなし。期間の代表時刻や数値の中点を作らない |
| J10 | 原領域が閉じた[1,1]、p=1 | `1.0`。bundleには元のinterval型を保持。幅のある領域を潰した例には数えない |
| J11 | 同じ数値やtextを比較するとき、量種、単位、p、方針/profileが異なる場合。量種の変更にはpropertyと確認も一致させる | artifact全体の同一とはしない。標準をp=6へ変えると`1.210000`。pによる末尾零等の相違と、未対応の別方針の拒否を分ける |
| J12 | G/HとI/Jで数式・換算値・pが一致する比較 | coefficient/textの手指定期待は一致してよい。H/Jのschema/profile/自己仕様hashは別で、artifact hashを同じものとして流用しない |

### 上流の時間・確認・未知情報

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| J13 | A/B、k=8、t=3と6 | どちらもAの1.21→`1.2`。除外なし。Bの全体訂正でAを消さない |
| J14 | A/B、k=8、t=4と5 | Bの1.24→`1.2`。Aを除外。数値表示がJ13と同じでもrecord/Hr_i/validity/訂正根拠は別 |
| J15 | A←B←C、k=9、t=5 | Cの1.31→`1.3`、除外A/B。Bが除かれてもB→Aとその確認を根拠へ残す |
| J16 | A/B、t=5、k=6と7を二viewで問う | 前者はA/1.21、後者はB/1.24、両表示`1.2`。RB=7ちょうどを含む。全計画C=37、二表示各一質問でJ=59 |
| J17 | J15でRBなし、または同値の適格記録二つが訂正なしで残る | unresolved_measurement_conflict。未確認Bを介してAを推移的に除かず、同じtextで競合を解消しない |
| J18 | Aの確認なし、suspected、または旧GのHrで確認を流用する各変種 | 前二者はno_adopted_measurement、後者は入力不正。新しい人の確認・instantをJが合成しない |
| J19 | 原recordとquantityがAI由来、確認なし/内容一致の確認あり | 前者は保留、後者は表示可能。両AI originと子のnot_certifiedを保持し、医学的な確認済みへ昇格しない |
| J20 | 適格なunknown/unspecified期間の記録あり。未確認またはsuspectedの変種も用意 | 適格ならvalidity_unknown/validity_unspecified。保留/suspectedの未知期間だけなら既知Aを表示可能。期間を全体へ補完しない |
| J21 | 可視slotの保留/訂正済み/期間外の記録または参照数量に未知能力。表示自身の未知能力も別変種 | 当該行unknown_capability、artifactなし。未来・未参照slotはJ23と区別する |
| J22 | 選ばれた記録のmethod/specimenがunknown/unspecified | Iの理由を保持し、表示だけを成功させない。Bの未知methodがt=3では選ばれない変種ならAを表示可能 |
| J23 | S表示に加え、slot Tの適格記録・確認とTのconvertを計画に入れる。Tも既知のQを参照し訂正辺なし（二slot一数量二記録二確認）。Tの記録自体の未知method/能力で意味上停止 | Sは表示可能、scopeはSの表示質問だけ。C=30、J=42。表示が参照しないTの行も実行・課金し、結果全体をSの根拠へコピーしない。未来の妥当な追加も同様に選択の非干渉とHs_i/料金の変化を区別 |

### 問いの因子化と衝突

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| J24 | 標準セルでge 11/10、le 13/10、eq 13/10 | true,true,false、全てpreserved。falseをnullへ変えない。偶数セル端23/20・5/4と奇数セル端も各operatorで点検 |
| J25 | A/B、t=3/5を二query、p=1、threshold ge 61/50、bundleの有無 | 両artifact同一。projectionは両方null/out_of_scope。bundleならsource_answer=false/true、なければnull。全体not_certified |
| J26 | J25でexact_value | 両projectionはout_of_scope。bundleの原回答は121/100と31/25。原値を表示だけから復元したと扱わない |
| J27 | k=8,t=5を固定し、単独のAと、同じ数値の単独の別記録A2を持つ二入力。selected_recordを問う | artifact同一、原record_ref/Hr_iは相違。bundleなら両原回答、noneならsource_answer=null。projectionは初回テンプレート外、scope拡大なし |
| J28 | 同じAだけのsourceでt=3/6、k=8/9の各変種。target_at/as_ofを問う | 数値表示は同じでも、各原回答は指定時点に一致。projectionは範囲外。k/tが変わる入力族の反例で、固定時点族にまで一般化しない |
| J29 | 同じk=8,t=5・値で、Aの期間[1,10)と[1,9)の二入力。各内容に新しい確認。validityを問う | artifact同一、原validity/Hr_iは相違。bundleの回答は各元のbounded object。期間不変を認定せず、医学的な期間の妥当性も認定しない |

### 保持・資源・認定の範囲

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| J30 | source四表の外側とview/query/displays/questionsの順序を反転。bundleあり | ID順の意味結果・Hs_i・Hr_i・Hq・artifact hashは保持。root/I入力hashとraw request_planの順序は区別し、各hashをその原入力から検査 |
| J31 | 同じ元snapshot/k/t/方針/処理系で再実行。別変種で未来の妥当な記録を追加、またはpだけ変更 | 再実行は選択・意味・根拠を再現。未来追加は過去の選択/値を変えなくてもHs_i・料金を変え得る。p変更はartifactを変え得るが原確認を変更しない |
| J32 | artifactの実際の符号化・復号、retention二種、display_textだけ/追加の原情報の問いあり | 符号化一致で喪失は回復しない。bundleだけならadditional_source_used=false、source_answerを出せばtrue。noneでも両時点の根拠は残るが、artifact自身の保存とは別 |
| J33 | 表示が参照しないview/query、適格だが対象tの期間外の訂正辺を追加 | Cは全計画と全Eの辺で増える。子へCを一度渡す。必要な行だけへ計画を縮約せず、表示ごとの予算リセット・キャッシュ割引なし |
| J34 | 一slot一数量、20記録20確認（全て可視・適格・訂正辺なし）、64view×64queryの妥当な計画 | C=125443。親上限100000でCを予約できず、Iを呼ばずresource_limit、全表示未完了。競合を含む計画でも料金を省略しない |
| J35 | 一表示に七kindを全部要求。bundle二種。別変種はdisplay_textだけ | 七kindではmetadata/exact_valueがout_of_scopeなのでnot_certified。bundleでも変わらない。textだけは全条件完了後にtemporal_display_questions_only。子Iは常にnot_certified |
| J36 | 新しいJ要求と、旧H/G/I/時間/量/旧基底の要求をそれぞれ処理 | 旧観測はcertifier以外不変。Hへ新I計画を渡すと従来どおり拒否し、新JへG計画を偽装して通さない。新しい臨床主張・基底変換なし |

J27/J29の二入力は互いに独立した要求の証人案です。同一IDを永続ストアで書き換えるAPIではなく、各snapshotの内容と確認を固定します。実装時には実際のHq/Hr_iと原要求を使って両方が受理されることを確認します。まだ新runtimeへの入力検証を通した証人ではありません。

## 3. 入力境界N01〜N12

| ID | 入力の変種 | 手指定の期待 |
| --- | --- | --- |
| N01 | 必須欄の欠落/null、余剰欄、既知の型不正、重複ID、空表示/質問 | invalid_input。入力を修復・変更しない |
| N02 | 表示の未解決view/query、I計画の未解決slot/quantity/record | invalid_input。未参照の不正も拒否 |
| N03 | 元quantity内容・期間・方法・訂正辺を変え、古いHq/Hr_i/確認を残す | Iのhash不一致としてinvalid_input。元の確認をJが書き換えない |
| N04 | 未来の不正記録、確認の時刻違反、自己/別slot/未来の訂正、空/逆転/はみ出す区間 | Iの静的検証でinvalid_input。表示の参照時点より後でも不正を隠さない |
| N05 | pが負数/bool/文字列、6超の整数、別のrounding_policy | 前三者はinvalid_input。範囲外の精度・方針はunsupported_profile。検証前に指数を計算しない |
| N06 | thresholdの分母0/負値・bool・生小数、63bit超、既知の型/次元の矛盾 | 型・分母・既知矛盾はinvalid_input。整数上限は量と同じresource_limit。数値の自動変換なし |
| N07 | 自己/I/量のconsumer profile・仕様hashやnative実体不一致 | 依存/consumer不一致はunsupported_profile、hash形式不正はinvalid_input、native実体不一致は明示拒否 |
| N08 | G/H計画、旧I方針、compare/集計/instant/不明期間の訂正を含む別の意味 | unsupported_profile。旧欄を新型の別名にしない。新型に旧欄を混ぜた余剰欄はinvalid_input |
| N09 | 外部からIの結果・完成根拠・certificate・artifactを注入、子budget欄を同梱 | invalid_input。計算済みの自己申告を入口にしない |
| N10 | 未知question kind/operator、metadata問いに回答や期間欄を注入 | 未知の問い/操作はunsupported_profile。既知問いの余剰欄はinvalid_input |
| N11 | 65表示、17質問、1 MiB/深さ64/予算100000の超過、負/bool予算 | 静的上限超はresource_limit、予算の型/負値はinvalid_input。派生I要求にもサイズ/深さ上限を適用 |
| N12 | 旧経路、原入力、並べ替え、全ノードの型破損、未知能力、十分予算の大小 | 旧観測・入力不変、例外を漏らさず、完成した意味を予算で変えない。静的拒否は予算0/1/7でも同じ |

不正な予算欄そのものを修復した別要求との拒否一致は要求しません。256bit/text64文字の上限は防護分岐として検査しますが、固定した63bit入力・換算倍率・pの範囲から自然に全境界へ到達するとは主張しません。

## 4. 資源条件B01〜B04

| ID | 計画・予算 | 手指定の期待 |
| --- | --- | --- |
| B01 | 標準C=16、一表示一質問、予算0〜29 | 16以下は子未呼出。17以上で子へ16を一度。26以下は全表示未完成、27は表示行完成でもroot resource_limit・認定なし・incompleteにcompletion、28以上で完成/認定 |
| B02 | 標準の同じ子から二表示、合計38。特に27/36/37/38 | 27/36は先の行だけ、37は両行完成でも最終1不足、38で認定可能。未完成のartifact/hash/cell/questions/両根拠はnull。表示ごとにIを呼ばない |
| B03 | A/B二query二表示C=34、J=56。二viewのJ16はC=37、J=59。七質問の標準J=40 | 最初の計画は44以下で表示なし、45〜54は一行、55は両行だが最終不足、56で完成。二viewは58で最終不足、59で完成。七質問は39で最終不足、40でokだがmetadata範囲外のためnot_certified |
| B04 | Iが途中の完成行を含んで資源停止。別変種で二表示目の算術・根拠生成に資源停止を注入 | 前者は表示を一つも完成させず親もresource_limit。後者は先の完成表示を保持し、後は六値欄null。いずれも認定なし。raw request_planの保持と計算値の公開は別 |

手計算は標準 `1+16+10+1=28`、二表示 `1+16+20+1=38`、A/B二query `1+34+20+1=56`、二view `1+37+20+1=59`、七質問 `1+16+22+1=40`。最後の1の前には全体の完成と認定を返しません。

## 5. 設計式だけの有限点検

下記は抽象的な日座標の期間、整数参照時点、厳密有理数を使う単独コードです。med_dslをimportせず、実際のschema・hash・確認レコードを構成しません。点選択と区間差引きで選ばれた値から、商/剰余と距離による丸め、セル上の閾値判定と証人点の回答集合を比較します。原記録・時点の問いの因子化判定器は実装しません。

```python
from fractions import Fraction as F
from itertools import product
import json
import operator

spans = ((1, 10), (4, 6), (5, 6))
recorded, reviewed = (2, 6, 8), (3, 7, 9)
edges = ((1, 0), (2, 1))
ops = {'lt': operator.lt, 'le': operator.le, 'eq': operator.eq,
       'ge': operator.ge, 'gt': operator.gt}

def subtract(parts, cut):
    result = []
    for lo, hi in parts:
        a, b = max(lo, cut[0]), min(hi, cut[1])
        if a >= b:
            result.append((lo, hi))
        else:
            if lo < a:
                result.append((lo, a))
            if b < hi:
                result.append((b, hi))
    return result

def rounded(x, p):
    scaled = x * 10**p
    a, remainder = divmod(scaled.numerator, scaled.denominator)
    k = a + int(2*remainder > scaled.denominator or
                (2*remainder == scaled.denominator and a % 2 != 0))
    digits = str(abs(k)).zfill(p+1)
    text = digits if p == 0 else digits[:-p] + '.' + digits[-p:]
    return k, ('-' if k < 0 else '') + text

def nearest(x, p):
    scaled = x * 10**p
    floor = scaled.numerator // scaled.denominator
    k = min(range(floor-1, floor+3), key=lambda n: (abs(scaled-n), n % 2))
    whole, fraction = divmod(abs(k), 10**p)
    text = str(whole) if p == 0 else f'{whole}.{fraction:0{p}d}'
    return k, ('-' if k < 0 else '') + text

def constant(op, z, lo, hi, closed):
    inside = lo < z < hi or closed and z in (lo, hi)
    yes = {'lt': hi < z or hi == z and not closed, 'le': hi <= z,
           'eq': False, 'ge': lo >= z, 'gt': lo > z or lo == z and not closed}[op]
    no = {'lt': lo >= z, 'le': lo > z or lo == z and not closed,
          'eq': not inside, 'ge': hi < z or hi == z and not closed, 'gt': hi <= z}[op]
    return True if yes else False if no else None

histories = contexts = projections = questions = 0
for states in product(range(4), repeat=3):
    # 0:確認なし、1:通常の確認、2:11で遅延確認、3:suspectedで確認あり
    for bits in product((0, 1), repeat=3):
        values = [F(121 if b == 0 else 124, 100) for b in bits]
        histories += 1
        for k, t in product((2, 3, 6, 7, 8, 9, 11), (1, 3, 4, 5, 6, 10)):
            eligible = {a for a in range(3) if states[a] in (1, 2)
                        and recorded[a] <= k
                        and (reviewed[a] if states[a] == 1 else 11) <= k}
            covering = {a for a in eligible if spans[a][0] <= t < spans[a][1]}
            direct = covering - {b for a, b in edges if a in covering}
            remaining = {a: [spans[a]] for a in eligible}
            for a, b in edges:
                if a in eligible and b in remaining:
                    remaining[b] = subtract(remaining[b], spans[a])
            other = {a for a, parts in remaining.items()
                     if any(lo <= t < hi for lo, hi in parts)}
            assert direct == other
            contexts += 1
            if len(direct) != 1:
                continue
            x = values[next(iter(direct))]
            for p in (0, 1, 2):
                coefficient, text = rounded(x, p)
                assert (coefficient, text) == nearest(x, p)
                lo, hi = F(2*coefficient-1, 2*10**p), F(2*coefficient+1, 2*10**p)
                closed, width = coefficient % 2 == 0, hi-lo
                for z in (lo-width, lo, lo+width/4, (lo+hi)/2, hi-width/4, hi, hi+width):
                    cuts = sorted({lo, hi} | ({z} if lo < z < hi else set()))
                    witnesses = [(a+b)/2 for a, b in zip(cuts, cuts[1:])]
                    witnesses += [z] if lo < z < hi else []
                    if closed:
                        witnesses += [lo, hi]
                    for op, compare in ops.items():
                        answers = {compare(y, z) for y in witnesses}
                        expected = next(iter(answers)) if len(answers) == 1 else None
                        assert constant(op, z, lo, hi, closed) == expected
                        questions += 1
                projections += 1

# 数値の衝突と二重丸め。メタデータの衝突案は表J27〜J29と別に扱う。
for x, p, expected in ((F(5, 4), 1, '1.2'), (F(27, 20), 1, '1.4'),
                       (F(-5, 4), 1, '-1.2'), (F(-27, 20), 1, '-1.4'),
                       (F(1, 20), 1, '0.0'), (F(-1, 20), 1, '0.0'),
                       (F(1, 2), 2, '0.50'), (F(1, 3), 2, '0.33'),
                       (F(121, 100), 6, '1.210000'),
                       (F(2**53+1), 0, '9007199254740993')):
    assert rounded(x, p) == nearest(x, p)
    assert rounded(x, p)[1] == expected
assert rounded(F(121, 100), 1) == rounded(F(124, 100), 1) == (12, '1.2')
assert (F(121, 100) >= F(61, 50)) is False
assert (F(124, 100) >= F(61, 50)) is True
x = F(12501, 10000)
assert rounded(x, 1)[1] == '1.3'
assert rounded(F(rounded(x, 2)[0], 100), 1)[1] == '1.2'
assert 1+16+10+1 == 28 and 1+16+20+1 == 38 and 1+34+20+1 == 56
assert 1+37+20+1 == 59 and 1+16+22+1 == 40
assert 1+1+1+64*(20+20+64*(2+20+8)) == 125443
print(json.dumps({'histories': histories, 'contexts': contexts,
                  'numeric_projections': projections, 'threshold_checks': questions,
                  'differences': 0}))
```

Python 3.14.4と3.11.17で上のコードを実行し、両版とも **512履歴・21,504対象文脈・16,080数値式比較・562,800閾値式比較、相違0** でした。数値式比較の主系列はp=0/1/2、値は121/100と124/100です。別のassertで負数・半整数・零・末尾零・1/3・2**53超・p=6・二重丸め・料金例を点検し、主系列の分母へ足していません。同じ選択や数値セルになる重複も含み、異なるartifactや意味モデルの個数ではありません。

コードはこの文書の唯一のpython fenceから抽出して再実行できます。抽出コードと実行環境・件数は `data/research/p2-j/`（Git管理外）にも記録します。係数・textとセルの数学を比較しており、まだ新しい型付きartifactの構築・hash・実際の符号化や、新要求の受理を実証していません。unknown/unspecified、複数slot、認証・内容hash、Iへの委譲、上限・共有予算のruntime、原情報の回答・認定は将来の検査です。有限点検を上流Iや旧Hの実装結果へ足しません。

今回の変更は文書だけです。52条件の連番、変更したMarkdownのローカルリンク・fence、`git diff --check`、保存監査8件を確認しました。統合台帳のpreflightでも979ファイルとmanifest/束hashがP2-iの基準と同一でした。runtime・固定対象・評価分母は変更していないため、Iで通過した全557テストと版比較つき統合評価は再実行していません。新しい接続の実装時に、設計46の受入条件に従って別途回帰します。
