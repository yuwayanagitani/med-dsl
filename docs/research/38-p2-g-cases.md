# P2-g：接続契約の手指定期待・反例・受入条件

作成日：2026-10-20。状態：**実装前の設計期待**。[意味設計37](37-p2-g-design.md) のM36（意味）・N12（入力境界）・B4（資源）、計52条件です。複数の変種を含む条件があるため、将来のJSON件数・必須パス数とは異なります。runtime・実行用fixture・独立確認・評価用正解の凍結は未実施です。

## 1. 共通の記法と前提

`t1`〜`t9` は2026-10-20の01:00〜09:00のUTC時刻を表します。標準入力はsource `fiction:measurement:source@1`、slot S（主体u）、数量Q（`2 u_ten`、k_a、未評価の不確かさ、literal由来）、記録A（recorded_at=t2、certainty=confirmed）、人の内容一致確認RA（t3）、view k=t5、Sをu_baseへconvertするqueryです。

標準の文脈はproperty A@1、検体 `{known, ref: fiction:specimen:s, version: 1}`、方法 `{known, ref: fiction:method:m, version: 1}`、対象時点 `{instant, at: t1}`。ref/versionの値は文字列で、以下の表の短記は実際のJSON型ではありません。標準例はAを選び、数値領域 `[20,20]` を返します。単一点の両端は閉じています。Bは特記しない限り記録t4・確認t5、Cは記録t6・確認t7とし、Cを含む正例のviewはk=t8です。

Q'、B、RB等を追加する場合は別IDを使い、quantity_refには当該wrapperのHq、確認には当該記録のHrを指定します。Hq/Hrは設計37の方式で入力から構成する値で、期待する選択や数値結果から生成しません。M24〜M31は原則としてM24と同じ二slotのcompareを使い、M26だけは一slotの自己compareです。表で指定しない前提は標準と同じです。方針・schema・profile・依存hashは設計37の固定値です。

computed以外では数値三欄と完成根拠二欄は全てnull。全例で新たな臨床主張・基底への変換・認定なし、出自と原情報を保持することを共通期待とします。

## 2. 意味条件M01〜M36

| ID | 入力の差・問い | 手指定の期待 |
| --- | --- | --- |
| M01 | 標準例 | selected=A、computed、換算値20。A/Hr、Q/Hq、RA、両仕様hashへ辿れる |
| M02 | RAを削除 | unassessed / no_adopted_measurement。confirmedの自己申告だけでは選ばない |
| M03 | Sは宣言するがrecords/reviews/quantitiesは空 | unassessed / no_adopted_measurement。値0や否定にしない |
| M04 | Aをt6、RAをt7に記録し、k=t5 | unassessed / no_adopted_measurement。対象時点がt1でも後の記録は利用しない |
| M05 | Aはt2、RAはt6。k=t5とt6 | t5ではno_adopted_measurement、t6ではAを選び20。確認時刻ちょうどを含む |
| M06 | Aのcertainty=suspectedで、その内容に一致するRAあり | no_adopted_measurement。確認だけでcertaintyを書き換えない |
| M07 | AとQがai_candidate由来、RAなし | no_adopted_measurement。P2-f単体で計算できることを採用根拠にしない |
| M08 | M07に内容全体を指定する人のRAを追加 | Aを選び20。両方のAI由来を残し、clinical_confirmation=not_evaluated、臨床主張追加なし |
| M09 | A/RAに、B（Q'=3 u_ten、t4、supersedes=[A]）を追加。RBなし | Aを選び20。Bを保留として残し、未確認の訂正でAを消さない |
| M10 | M09のRBをt5に追加。k=t4とt5 | t4はA/20、t5はB/30。Aは履歴に残るが候補から除く |
| M11 | A←B←C、三記録とも適格。Cは4 u_ten | Cを選び40。A/Bを除く。Bが候補に残らなくてもB→Aの辺を使う |
| M12 | A←B←CでAとCだけ適格、Bは未確認 | AとCが残りunresolved_measurement_conflict。未確認Bの辺を推移的に使ってAを除かない。RBをt9に記録しk=t9で見るとCのみ |
| M13 | 同じSにB/30を追加し確認するがsupersedes=[] | A/Bの競合。最新のBを自動選択しない |
| M14 | M13でBもAと同じQを参照し、値は20で等しい | A/Bの競合。数値や内容hashの一致で記録を統合しない |
| M15 | 競合するA/BをCが明示的に両方supersedeし、人の確認あり | Cのみを選ぶ。訂正先を一つしか見ない実装は失敗する |
| M16 | Aのmethod={unknown}、その内容へのRAあり | unassessed / method_unknown。SをSと比較してもequalを返さない |
| M17 | Aのmethod={unspecified} | unassessed / method_unspecified。M16と理由を分ける |
| M18 | Aのspecimen={unknown} | unassessed / specimen_unknown |
| M19 | Aのspecimen={unspecified} | unassessed / specimen_unspecified |
| M20 | Aのeffective_at={unknown} | unassessed / effective_time_unknown。recorded_atを代入しない |
| M21 | Aのeffective_at={unspecified} | unassessed / effective_time_unspecified |
| M22 | S内の可視の保留記録、または訂正済みの可視記録に未知能力。各変種でその数量側の未知能力も試す | 全てunknown_capabilityを優先。Aの値だけを拾って成功にしない。阻害記録/数量を診断に残す |
| M23 | 未参照slot Tの記録またはkより後の記録に未知能力 | Sの完成値は20。全体の構造検証・保持・課金は省略しない |
| M24 | S/Tに別の適格記録を一つずつ置く。同じ既知文脈、1 u_tenと10 u_baseを比較 | relation_set=[equal]、certain_relation=equal。数値関係だけを返し医学的同等性は認定しない |
| M25 | S/Tの別記録が、同じID・同じHqの区間Q=[1,2] u_baseを参照 | relation_set=[less,equal,greater]、certain_relation=null。作業用数量IDは二つ |
| M26 | M25からT側のslot・記録・確認を除き、Sを自己比較 | relation_set=[equal]。同じ選択記録版へ対応する作業用数量IDは一つ |
| M27 | 両記録は適格で各slotの主体と一致するが、主体u/vが異なる | not_comparable / different_subject。異なる主体を一slotに入れる不正例N06とは分ける |
| M28 | Sはproperty A@1、TはA-other@1。同じk_a、他の文脈は同じ | not_comparable / different_property。同じ量種・次元だけでは比較しない |
| M29 | 検体refのみ異なる。別変種では同じrefの版だけ異なる | not_comparable / different_specimen |
| M30 | 方法refのみ異なる。別変種では同じrefの版だけ異なる | not_comparable / different_method |
| M31 | 対象時点がt1/t2で異なり、他の文脈は同じ | not_comparable / different_effective_time。縦断比較一般への否定ではない |
| M32 | 適格な選択記録に未知property、未知quantity kind、未知input unit、未知target unitをそれぞれ配置 | unknown_property / unknown_quantity_kind / unknown_unit。同時にある場合は全て併記。自己比較でも未知unitをequalにしない |
| M33 | SのAは方法不明。Bが同じSで方法を明示してAを訂正 | Bの確認前はAのmethod_unknownのまま。Bの内容一致確認後にBを選び20。不明からの精密化は新記録・新確認を通す |
| M34 | 同じSのBが値・property・検体・方法・対象時点のいずれかを明示訂正。RAはAのまま保持 | Bの新しいHrを指すRBの確認前後で選択を分ける。property変更の変種はA→A-other、時点変更はt1→t2。古いas_ofではAの文脈と値を再現。RBをRAのhashで代用すればN04 |
| M35 | 選択した数量を負の分数、未約分数、開閉区間に変える | -3 u_half→-3/2 u_base、2/4 u_ten→5 u_base、(1,2] u_ten→(10,20] u_base。原値・境界・出自・未評価の不確かさを保持 |
| M36 | snapshot S0を保存後、別IDの数量Q'=3 u_tenとB（t6）・RB（t7）を追加したS1でk=t8の訂正を採用 | S0とその仕様・処理系による再実行はA/20。S1の過去as_ofもA/20、現在はB/30。Hs・保持一覧・所要予算の違いは許す。latest参照だけのreceiptを認めない |

M22と同時に競合・文脈不明がある場合は未知能力が優先です。M16〜M21とM32の情報不足が複数なら理由を併記します。既知の複数の文脈が違えばM27〜M31の相違理由を併記します。選択できた片側だけの数値を完成値として漏らしません。

## 3. 入力境界N01〜N12

| ID | 入力・破壊する点 | 手指定の期待 |
| --- | --- | --- |
| N01 | 必須欄・hash・型の欠落、不正な文字列、未知欄、bool等の誤型 | invalid_input。nullをunknownやunspecifiedへ自動変換しない |
| N02 | 四表/view/queryの重複ID、未解決のslot/record/quantity参照、literal.idとwrapper.refの不一致 | invalid_input。曖昧なIDを一つにしない |
| N03 | 数量の同次元の単位・原値・出自・能力を型として妥当に変更し、記録のquantity_ref.sha256は古いまま | invalid_input / quantity_reference_hash_mismatch。未参照や未来の記録でも全体の参照hash検証を行う |
| N04 | 記録の文脈・数量参照hash・出自・確定性・時刻・訂正辺を型と参照が妥当な範囲で変更し、reviewのrecord_sha256は古いまま | invalid_input / review_record_hash_mismatch。主体変更の変種はslotの主体も併せて変更する。同じID・同じ値だけでは古い確認を使えない |
| N05 | reviewer_kindがhuman以外、outcome不正、確認が記録より早い、certainty不正 | invalid_input。確認をAIが代行したことにしない |
| N06 | supersedesが自己・未解決・同時刻以後・別slot。slotとrecordの主体不一致 | invalid_input。訂正DAGの条件とslotの主体を予算前に検査 |
| N07 | P2-fの分母・整数型・区間の不正、64bit入力、統計的不確かさや未対応の量表現、依存profile/hashの相違 | 不正はinvalid_input、63bit超過はresource_limit、未対応の表現・依存版はunsupported_profile。値を修復しない |
| N08 | knownのref/version欠落、unknown/unspecifiedに境界やref混在、不正UTC。期間やnot_applicableを代用 | 型の不正はinvalid_input、期間/not_applicableはunsupported_profile。不明を「該当なし」と同一視しない |
| N09 | 既知property A@1と既知k_b、またはk_aとv_base | invalid_input / property_quantity_kind_mismatch または input_dimension_mismatch。後段の比較不能へ隠さない |
| N10 | consumer・方針・native実体のhash/操作/source schema、別comparison_scope。retraction/absence等のrecord kind | 未対応はunsupported_profile。実体のhash不整合はinvalid_input / native_spec_mismatch。新経路から旧意味へ黙って代用しない。最上位の未知schemaの既存の振り分け・拒否はN12で維持 |
| N11 | 不正な予算、件数超過、1 MiB/深さ64超過。子の作業用入力の複製による上限超過も別変種で試す | 予算の負数・bool等はinvalid_input、静的上限はresource_limit。元sourceの静的な拒否は予算0でも同じ。子の入力構築上限は計算時の資源停止として扱う。不正予算を修復した入力との同一拒否は要求しない |
| N12 | 旧P0/P1/P2要求、並べ替え、キャッシュを跨ぐ別snapshot、臨床昇格・量ID統合の変異 | 旧意味はcertifier以外同じ。四表/view/queryの順序に依らず同じ意味・Hs・完成根拠。原要求hashは変わり得る。記録やquantity literal内部の配列順はhash内容として扱う。変異は対応するM条件で失敗する |

hash不一致の負例は元のhashを保って内容を変更します。正例の訂正・精密化では、別IDの内容を新しくhashし、その版に対する新しい確認を明示します。hashの更新だけで人の確認を生成する実装は認めません。

## 4. 資源条件B01〜B04

| ID | 入力・予算 | 手指定の期待 |
| --- | --- | --- |
| B01 | 標準例、予算0 | resource_limit、steps_used=0、未完了行の数値・完成根拠・diagnostics=null、assessment_complete=false、認定なし |
| B02 | 標準例、予算15/16/17 | 15では未完了。16でcomputed=20、17でも同じ完成結果・steps_used=16。子のconvert料金8は親が支払い済み |
| B03 | M24の二slot比較、予算24/25。M26の自己比較、予算19/20 | 前者は25で完成、後者は20で完成。自己比較でも比較の予約12を払い、子の実費11との差を返却しない |
| B04 | 標準例に二つのconvert（query a/b）を置き、予算0〜28 | 16でaだけ完成、17〜26でもbは未完了、27以後は両方完成しsteps_used=27。配列順に依らずaが先。先の完成行を保持し、子ごとの予算リセットや予約前の完成根拠公開を検出 |

入力条件を固定した全予算掃引に加え、未参照slotの追加、未来の記録の追加でも意味の完成結果だけを比較します。source全体のhash、保持一覧、予約料金まで同じになるとは要求しません。構造的に不正な未来記録を無視する変異もN条件で検出します。

## 5. 選択式の有限照合（設計だけ）

次のコードは、三記録までの全訂正辺、confirmed/suspected、確認なし/即時/遅延、9参照時点について、集合式と**確認が利用可能になった順の状態更新**を比較します。親の確認が子より遅れて届く場合も、既に除かれた記録を復活させません。quantity計算・hash検証・文脈ゲート・共有予算・接続adapterはまだ検査しません。

```python
from itertools import combinations, product

count = 0
for n in range(4):
    edges = list(combinations(range(n), 2))
    for mask in range(1 << len(edges)):
        parents = [set() for _ in range(n)]
        for bit, (old, new) in enumerate(edges):
            if mask & (1 << bit):
                parents[new].add(old)
        for confirmed in product((False, True), repeat=n):
            for review_mode in product((0, 1, 2), repeat=n):
                # 記録時刻2,4,6。確認はなし、同時、2時間後。
                rec = [2 * (i + 1) for i in range(n)]
                review = [None if mode == 0 else rec[i] + (2 if mode == 2 else 0)
                          for i, mode in enumerate(review_mode)]
                for k in range(1, 10):
                    eligible = {i for i in range(n) if confirmed[i]
                                and rec[i] <= k and review[i] is not None and review[i] <= k}
                    removed = {target for i in eligible for target in parents[i]}
                    want = eligible - removed
                    events = sorted((review[i], i) for i in range(n)
                                    if confirmed[i] and review[i] is not None and review[i] <= k)
                    active, masked = set(), set()
                    for _, i in events:
                        masked.update(parents[i])
                        active.difference_update(parents[i])
                        if i not in masked:
                            active.add(i)
                    assert active == want, (n, mask, confirmed, review_mode, k)
                    count += 1
assert count == 16263
print(count)
```

Python 3.14.4と3.11.17で **16,263条件が全て一致**しました。コードブロックの末尾改行を含むSHA-256は `7a1fdf131b058b196c027a385aa5840b3f0979b4bcb21fba3c0dd6c9f57d9793`。実行記録は `data/research/p2-g-design/py314.json`・`py311.json`（Git管理外）です。二つの計算法の一致は、実装前の作業定義の有限照合です。52受入条件のruntime通過や、一般の確認・訂正の正しさの証明として数えません。
