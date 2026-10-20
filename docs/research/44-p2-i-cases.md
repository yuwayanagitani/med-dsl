# P2-i：併用の手指定期待・反例と設計式の有限点検

作成日：2026-10-20。状態：**実装前の手指定期待**。[意味設計43](43-p2-i-design.md) のC32/N12/B4、計48条件です。将来のJSON件数・必須パス数とは異なります。runtime・登録・実行用fixture・独立確認・評価用正解の凍結は未実施です。§5の点検は選択式の比較だけで、runtime・数量adapter・内容確認の実証ではありません。

## 1. 共通の入力と記法

`d` は `2026-10-ddT00:00:00Z`、`d+½` は同日12時のUTC時刻です。秒精度の入力を受理する契約であり、日単位へ丸める仕様ではありません。kは参照時点、tは対象時点です。

標準は新profile/source/方針、slot S（主体u）、quantity Q（k_a、2 u_ten）、record A（period_quantity、validity=[1,10)、recorded_at=2、confirmed）、人の内容一致確認RA（3）、view k=8、convert query（S、t=5、target=u_base）です。property A@1、検体と方法はP2-gと同じ架空knownのref/版を明示します。原literalの不確かさは未評価、両originはobservedです。Aはrevises=[]。標準の期待はAを選び、閉じた一点領域20を返すことです。

Bを加える場合は別quantity Qb=3 u_ten、期間[4,6)、recorded_at=6、確認RB=7、revises=[A]、非空のchange_reason。CはQc=4 u_ten、[5,6)、recorded_at=8、確認RC=9、revises=[B]。Cを含む正例は原則k=9です。未来でも全sourceを検証するため、追加・変更した記録に対応するHq/Hr_i・確認も新しく構成します。hash自体の差替えを調べる負例だけは意図的に不一致にします。

全行でrootのnot_certified、臨床未評価、構造的な確認照合、原sourceと両出自の保持を要求します。unassessed行では数値・両完成根拠はnull。完成した診断と資源未完了を混同しません。表中の候補・除外は手指定した選択の期待で、未完成時にそれらを公開する指示ではありません。

## 2. 意味条件C01〜C32

### 両時点、半開境界、訂正

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| C01 | 標準入力 | A、20。根拠にk=8、t=5、[1,10)、RA、Hr_i/Hq/Hs_i、明示期間と部分訂正の前提 |
| C02 | Aをrec=8、RA=9へ変更。k=7、t=5 | no_adopted_measurement。原sourceには保持するが、A/RAを可視の阻害や計算根拠にしない |
| C03 | C02でk=8、k=9 | 8は確認前で候補なし、9はA/20。確認境界ちょうどを含む |
| C04 | 標準でt=1、10、11。別変種でAをsuspectedとし内容一致確認あり | 1はA/20、10と11は候補なし。suspectedは期間内でも候補なし |
| C05 | A/B、k=8、t=3 | A/20、除外なし。Bの全体訂正でAを消す実装への反例 |
| C06 | C05でt=4、5、6 | 4と5はB/30、除外A。6はA/20、除外なし。部分訂正の両境界 |
| C07 | A/B、Bを[1,10)へ変更 | 全期間でBがAを訂正。t=1、9はB/30、t=10は候補なし |
| C08 | A←B←C、k=9、t=5 | C/40、除外A/B。B→AとC→Bの両辺・各可視確認を根拠へ。t=4はB/30、t=6はA/20 |
| C09 | C08でRBなし、またはRB=11、k=9、t=5 | A/Cが残り競合。未確認Bを介してAを推移的に除かない。RB=11の変種をk=11で見るとCのみ |
| C10 | A/BでRAなし、RBあり。k=8、t=5。その後RA=9、k=9 | どちらもB/30、除外A。対象の確認が後から到着してもAは復活しない |
| C11 | A/BでB.revises=[] | 期間内ではA/Bの競合。最新のBを自動選択しない。BもQを参照する同値変種でも競合 |
| C12 | C11に、期間[5,6)・revises=[A,B]のCを追加 | t=5はC/40、除外A/B。t=4はA/Bの競合。各対象への包含と両辺を検査 |

### 未知、保留、slot範囲

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| C13 | A.validity=unknown、別変種でunspecified。訂正なし、内容一致確認あり | validity_unknown / validity_unspecified。全てのtで保留。欠落・全期間へ補わない |
| C14 | 標準Aに、同じSの期間unknownのUを追加し確認。Uは訂正しない | 既知のAがtを覆ってもvalidity_unknown。Uがsuspectedまたは未確認の変種ならA/20 |
| C15 | A/BでBまたはBのQbに未知能力。Bは期間外、未確認、Cで訂正済み（k=9）の各変種 | 見えるS内なら全変種unknown_capability。数値処理や期間で絞る前に止める |
| C16 | C15のBをrec=9、確認=10としk=8。別変種で未参照のslot Tへ訂正辺なしで置く | Sの結果はA/20。未来・未参照slotの未知能力は阻害しない。構造不正なら別途拒否 |
| C17 | 唯一のAのmethod=unknown、unspecified。検体についても同様の変種 | method_unknown / method_unspecified、specimen_unknown / specimen_unspecified。情報源から補完しない |
| C18 | A/BのB.method=unknown、k=8、t=3と5 | 3はA/20、5はmethod_unknown。未知能力の全可視走査と、選択後の文脈不足を区別 |
| C19 | Aをunknown property、量種、単位の各変種へ変更。全既知の矛盾は作らない | 該当するunknown_property / unknown_quantity_kind / unknown_unit。known値を推測して補完しない |

### 内容、数値、再現、他能力との境界

| ID | 入力・問い | 手指定の期待 |
| --- | --- | --- |
| C20 | Bが期間内だけmethod/specimen/property/値を明示訂正。各変更に新Hq/Hr_i・確認 | t=5はBの文脈と値。t=3/6はAの文脈と値。変更をslot全体へ広げない |
| C21 | AとQがai_candidate、確認なし／内容一致のRAあり | なしは候補なし、ありはA/20。両AI originを残し、新規臨床主張は空、clinical_confirmation=not_evaluated |
| C22 | Q=1 u_third、target=u_base。別変種でQ=-3/2 u_ten | 正確に1/3、-15。floatへの変換・丸めはしない。literal原表記と原出自を保持 |
| C23 | A/Bを含む同じsnapshotでk=6と7、t=5。さらに妥当な未来の記録を追加 | k=6はA/20、7はB/30。未来追加前後で各kの選択・数値・使った確認は不変。Hs_i・料金・原sourceの一致は要求しない |
| C24 | Qの領域を[1,2] u_tenとし期間[1,10)を明示 | 各tで[10,20]。単一点・中点へ変えない。各時点で同じ実値であるとの時間相関は追加しない |
| C25 | C24でtを二つ問う | 二つのconvertは可能。両時点の差が零か、同一変数か、医学的に一定かという問いは初回範囲外。compareは拒否 |
| C26 | source四表の外側、views/queriesの順序だけを変更 | ID順の意味結果とHs_iは同じ。原順序と要求hashは別に照合。record内部配列の変更に旧確認は流用しない |
| C27 | 同じsource/両時点/方針/依存/処理系を保持し再実行 | 意味・根拠・source内容hashを再現。最新sourceへの参照だけを再現の根拠にしない。保存サービスの可用性は未保証 |
| C28 | 旧P2-gのinstantを新period_quantityに自動変換する案 | 自動補完を採らない。instant入力は新要求でunsupported_profile。旧G要求は従来どおり。旧Gの成功を新しい期間の根拠にしない |
| C29 | 旧P2-eの確認ID、または旧P2-gのHrを新記録へ流用 | 不正な確認として拒否。adapterが新しい人の確認を発行したことにしない。新Hr_iへの明示確認が必要 |
| C30 | A=121/100 u_base、B=124/100 u_baseの部分訂正。t=3/5を一桁表示へ写す後続案 | 両textは1.2でも、原値が61/50以上かはfalse/true。表示だけの回答は範囲外。この新経路の表示・source_replayは未実装 |
| C31 | A/Bが同じ値で、t=3はA、t=5はB | 同じ型付き表示へ写ってもrecord・target_atの問いは戻らない。型付きartifactに期間を暗黙に符号化したと主張しない |
| C32 | C30の原sourceを保持する案と、既存P2-hへ新sourceを渡す案 | 別添えは表示の保存範囲を広げない。現P2-hは新計画を受理せず、旧R4認定を流用しない。新R5 rootも常にnot_certified |

C30〜C32は表示への接続を実装する指示ではなく、誤った接続を防ぐ境界条件です。初回のruntimeでは換算と停止・旧経路を検査し、表示の数値反例は別の式点検として記録します。全48条件を実行用JSONへ一対一に機械生成できるという主張ではありません。

## 3. 入力境界N01〜N12

| ID | 入力の変種 | 手指定の期待 |
| --- | --- | --- |
| N01 | 必須欄の欠落/null、型違い、余剰欄、同一collection内の重複ID | invalid_input。各欄の変種を持ち、入力を修復・破壊しない |
| N02 | 未解決slot/quantity/record、slot主体との不一致、確認時刻がrecordより前 | invalid_input。未来・期間外の記録も全て検査 |
| N03 | quantity内容だけを差替え、validity/方法/revisesだけを変更し旧確認を残す | HqまたはHr_i不一致でinvalid_input。過去の記録への古い確認と、新しい別記録の確認は併存可能 |
| N04 | 自己・別slot・未来の訂正、同時刻訂正、循環、理由欠落 | invalid_input。最新順に並べ替えて受理しない |
| N05 | boundedの逆転/空/片端欠落、対象をはみ出す訂正 | invalid_input。target_atがたまたま重なっていても拒否 |
| N06 | unknown/unspecified期間から・へのrevises | unsupported_profile。期間を全体へ読み替えて解消しない |
| N07 | open_end、日付だけ、時差つき、秒未満、未知の期間kind | open_end等の意味拡張はunsupported_profile、厳密UTC時刻の型不正はinvalid_input。欄名だけで推定しない |
| N08 | instant/集計期間、旧supersedes/effective_at、compare/表示操作、旧方針・旧source schema | 認識した別操作・意味型・方針・schemaはunsupported_profile。新recordに旧欄を混ぜる場合は余剰欄としてinvalid_input |
| N09 | 自己/量のprofile・仕様hashの不一致、native実体の差替え | 依存/consumer不一致はunsupported_profile。不正なhash形式はinvalid_input。native実体不一致は既存と同様に明示拒否 |
| N10 | property/量種・量種/単位の既知の矛盾、非有限・生小数、分母0、bool/63bit超入力 | 既知の矛盾・数値型不正はinvalid_input。数量の既存静的上限はP2-fの拒否を保持。換算を先に試して隠さない |
| N11 | collection/1 MiB/深さ64/予算100000の上限超、負またはbool予算 | 静的上限超はresource_limit、予算の型/負値はinvalid_input。数量子の上限も適用 |
| N12 | 既存schema群、原入力、並べ替え、全ノードの型破損、未知能力 | 旧経路の観測はcertifier以外不変。新要求で例外を漏らさず入力不変。未知能力は意味上の停止と構造不正を混同しない |

静的な拒否は予算0・1・7・十分な予算で同じです。不正な予算欄を修復した別要求との一致は求めません。N07のうち時刻書式の拒否と、型として認識する期間拡張を分けた実行例を作ります。

## 4. 資源条件B01〜B04

| ID | 計画・予算 | 手指定の期待 |
| --- | --- | --- |
| B01 | 標準計画の予算0〜17。必要料金16 | 15以下はresource_limit、行の値・両根拠・diagnosticsはnull、assessment_complete=false。子convertは行全体の予約が終わるまで呼ばない。16以上でA/20と同じ完成行 |
| B02 | 標準に同じslotの二queryをID順で追加。合計27。0〜28を掃引 | 16〜26では先の行だけ完成、後はnull。27以上で両行完成。各完成行につき子をbudget=8で一度。別の子へ100000を渡さない |
| B03 | A/B・別数量二つ・一view一query=21。二query=34 | 20以下は一行目未完了。二queryでは21〜33が一行目のみ、34で両行完成。Bがtを覆わなくてもEのB→Aの辺料金を含める |
| B04 | 先の行を完成させ、後の子にサイズ/算術の資源停止、または数量の部分結果を注入 | rootもresource_limit。後の行の値・完成根拠・diagnosticsはnull、先の行は不変。not_certified。構造検証時の静的停止と区別 |

料金の手計算は標準 `1+1+1+(1+1)+(2+1+0+8)=16`、二queryは `3+2+2*11=27`、A/B一queryは `1+1+2+(2+2)+(2+2+1+8)=21`、二queryは `4+4+2*13=34`。同じ完成行・同じ意味上停止行の予算単調性を照合し、早期の空配列・false回答・根拠漏出も検出します。rootの認定は予算にかかわらずnot_certifiedです。

## 5. 設計式だけの再現可能な有限点検

次のコードはmed_dslをimportしません。三つの既知区間、包含を満たす全訂正DAG、四種の確認/確定性、八つの参照時点で、点選択のAと、各記録の区間から適格な直接訂正の区間を差し引いた結果を比べます。境界0/1/2/3と間・外側の半整数を対象にします。差引きは最終採用元だけでなく全適格元を使い、中間が未確認ならその辺を使いません。

```python
from fractions import Fraction
from itertools import combinations, product
import json

intervals = list(combinations(range(4), 2))
recorded = (10, 20, 30)
views = (0, 10, 11, 20, 21, 30, 31, 40)
targets = tuple(Fraction(i, 2) for i in range(-1, 8))

def subtract(parts, cut):
    result = []
    for lo, hi in parts:
        left, right = max(lo, cut[0]), min(hi, cut[1])
        if left >= right:
            result.append((lo, hi))
        else:
            if lo < left:
                result.append((lo, left))
            if right < hi:
                result.append((right, hi))
    return result

histories = snapshots = comparisons = 0
for spans in product(intervals, repeat=3):
    possible = [(a, b) for a in range(3) for b in range(a)
                if spans[b][0] <= spans[a][0]
                and spans[a][1] <= spans[b][1]]
    for bits in product((False, True), repeat=len(possible)):
        edges = [edge for edge, enabled in zip(possible, bits) if enabled]
        # 0:確認なし、1:記録+1で確認、2:記録+10で確認、3:suspectedで確認あり
        for states in product(range(4), repeat=3):
            histories += 1
            for k in views:
                eligible = {a for a in range(3)
                            if states[a] in (1, 2)
                            and recorded[a] <= k
                            and recorded[a] + (1 if states[a] == 1 else 10) <= k}
                remaining = {a: [spans[a]] for a in eligible}
                for a, b in edges:
                    if a in eligible and b in remaining:
                        remaining[b] = subtract(remaining[b], spans[a])
                snapshots += 1
                for t in targets:
                    covering = {a for a in eligible
                                if spans[a][0] <= t < spans[a][1]}
                    masked = {b for a, b in edges if a in covering}
                    direct = covering - masked
                    reference = {a for a, parts in remaining.items()
                                 if any(lo <= t < hi for lo, hi in parts)}
                    assert direct == reference, (spans, edges, states, k, t)
                    comparisons += 1

# 表の料金と、表示の衝突は選択の列挙と別に点検する。
assert 1 + 1 + 1 + 2 + 11 == 16
assert 1 + 1 + 1 + 2 + 2 * 11 == 27
assert 1 + 1 + 2 + 4 + 13 == 21
assert 1 + 1 + 2 + 4 + 2 * 13 == 34
left, right, threshold = Fraction(121, 100), Fraction(124, 100), Fraction(61, 50)
assert round(left * 10) == round(right * 10) == 12
assert (left >= threshold) is False and (right >= threshold) is True
print(json.dumps({'histories': histories, 'snapshots': snapshots,
                  'target_comparisons': comparisons, 'differences': 0}))
```

Python 3.14.4と3.11.17で上のコードを実行し、両版とも **41,088履歴・328,704参照時点評価・2,958,336対象時点比較、相違0** でした。履歴は区間・辺・確認状態の組合せで、参照時点評価には同じ適格集合になる場合も含まれます。異なる意味モデルの個数とは扱いません。料金四例・表示衝突のassertも通過しましたが、選択の分母へ足していません。

コードはこの文書の唯一のpython fenceから抽出して再実行できます。抽出したコードと実行環境・件数は `data/research/p2-i/`（Git管理外）にも記録します。この比較は既知区間の選択部分だけです。unknown/unspecified、複数slot、内容hash、文脈の相違、数量adapter、入出力schema、予算のruntime実装は検証していません。両式は同じ作業定義から作成者が書いたもので、独立確認済みの正解ではありません。将来のruntimeがこの式と異なる不具合を持たない保証にもなりません。

今回の変更は文書だけです。48条件の連番、変更したMarkdownのローカルリンク・fence、`git diff --check`、保存監査8件を確認しました。統合台帳のpreflightで818ファイルとmanifest/束hashがP2-hの基準と同一であることも確認しています。runtime・固定対象・評価分母を変更していないため、P2-hで通過した全542テストと版比較つき統合評価の再実行は行っていません。将来の最小実装は設計43の受入条件に従い、別途回帰します。
