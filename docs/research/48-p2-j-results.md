# P2-j：期間つき数量の表示接続の最小実装と内部評価

作成日：2026-10-20。状態：**限定した断片を実装し、両Python版の全体回帰・版比較つき統合評価を通過**。[設計46](46-p2-j-design.md)・[手指定期待47](47-p2-j-cases.md) の専用R4を追加しました。両文書の未実装という記載は設計時点の記録として保持します。独立確認・評価用正解の凍結は未実施です。

## 1. 実装した範囲

| 実体 | 内容 |
| --- | --- |
| [temporal_display.py](../../src/med_dsl/temporal_display.py) | Iの全計画の検証・予約・再実行、直接の丸め、七種類の問い、根拠・追加情報・認定の分離 |
| [native仕様](../../src/med_dsl/temporal_display_spec.json) | 新しい型、I/量の依存版、丸め・逆像セル、認定範囲、課金・上限 |
| [専用宣言](../../extensions/p2-temporal-display.json) | 共通4＋R4必須3＋設計46のTD-1〜12、19義務・19防護例参照 |
| [実行例](../../examples/p2-temporal-display/README.md) | 170 JSON・2670必須パス。文書47の手指定期待を展開 |
| [別計算](../../tests/p2/temporal_display_oracle.py) | Iの区間差引き・整数対換算、近隣整数への距離と偶奇、セル内の証人点 |
| [専用検査](../../tests/p2/test_temporal_display.py) | API/CLI、有限照合、seed、衝突、原入力・hash・出自、資源、型破損、旧経路の19テスト |

新profileは `p2-temporal-display-draft-1`、operationは `project_temporal_measurement_displays` です。Iの元要求からbudgetだけを除いた計画を受け取り、I・量の固定版と全内容を検証してから、一度だけ再実行します。計算済み結果を利用者から受け取る経路、Gへのinstant・確認の合成、Hのprivate関数やprofileの流用はありません。

Iの換算領域が閉じた単一点の場合に限り、元の厳密有理数から整数の商・剰余で最近接偶数丸めします。符号、零、末尾零、0〜6桁、2**53超、1/3、二重丸めの反例を点検します。幅のある領域には中点や代表値を作りません。

artifactは新schema/profile/自己仕様hash、数量profile/仕様hash、量種・単位・丸め方針・桁数・係数・textだけです。原値・記録ID・両時点・validity・出自・source hashは入れません。実際のcanonical bytesを符号化・復号して、全欄のhashと一致を検査します。同じtextでもH/Jや型・精度の違いはartifact全体の同一性と区別します。 追加の読み取り専用点検では、targetをu_base/u_tenに分けた同じtext=`1.2`も、単位を含む完全なartifactとして異なることを確認しました。補足記録は `data/research/p2-j/supplemental-boundaries.json` です。

## 2. 問い・原回答・根拠

| 問い | artifactだけの回答 | source_bundleがある完成行の追加回答 |
| --- | --- | --- |
| display_text | text / preserved | なし |
| threshold | 全実数の丸めセル上で一定ならbool / preserved。そうでなければnull / out_of_scope | 換算後の厳密値との比較bool |
| exact_value | null / out_of_scope | 約分した換算値 |
| selected_record | null / out_of_scope | 元のrecord_refとrecord_sha256 |
| target_at / as_of | null / out_of_scope | 対象時点 / 参照時点 |
| validity | null / out_of_scope | 元のbounded validity object |

後五種類は初回テンプレートの保守的な範囲指定です。out_of_scopeだけを普遍的な喪失証明と扱いません。丸めセル全体の判定も保存の十分条件であり、有限入力上限を使った完全な判定器ではありません。

J25/J26では、同じ「1.2」の完全なartifactに、閾値ge 61/50のfalse/trueや、121/100と31/25の原回答が対応します。J27/J29ではk/tも固定して、別の記録・内容hashや元の期間に同じartifactが対応する、実際に受理された二入力を検査します。J28の時点の反例はk/tが変わる入力族のもので、固定時点族へ一般化しません。

source_bundle.request_planは元のJ要求からbudgetだけを除いて保持し、内部配列の順序、未約分の2/4、元の記録・確認を変えません。source_answerはsource_replayとして分離し、実際に回答を一つでも返した場合だけadditional_source_used=trueです。bundleを持つだけではfalseで、追加回答があってもprojectionの認定範囲は広がりません。

noneでもprojection_evidenceには二時点、Hs_i、selectedのrecord/Hr_i・quantity/Hq・validity・可視確認・両origin、全effective revision_evidence・前提、子Iのnot_certified、子の実入力hash・予約料金・実費を残します。原値・差分・Iの結果全体はこの欄へ入れません。bundle時のsource_evidenceも支払い済みの当該I行だけで、他の行を含む結果全体をコピーしません。

認定対象はartifactだけです。応答の根拠や呼出側の要求から時点を読めることは、artifact自体が時点を符号化することを意味しません。上流が停止した行は、入力にtarget_at等があっても、その回答だけを別経路で完成させません。

全表示・全質問と最後の料金が完了した場合だけ、temporal_display_questions_only / checked_native_templateで認定します。原値一般・記録・文脈・履歴・as_of/target_at/validity・temporal_selection・臨床の真実・測定の不確かさを除外し、Iのnot_certifiedを変更しません。clinical_confirmation=not_evaluated、review_verification=structural_only、uncertainty_propagated=false、converted_to_base=false、clinical_assertions_added=[]です。

## 3. 手指定期待と別計算

| 系列 | 分母 | 内容 |
| --- | --- | --- |
| J | 36条件・101 JSON・2228必須パス | 数値・型、時間選択と訂正、未知・確認、原回答の衝突、保持・認定 |
| N | 12条件・48 JSON・96必須パスと専用検査 | 型・参照・内容hash・依存・精度・問い・上限・旧経路 |
| B | 4条件・21 JSON・346必須パスと注入検査 | 子・表示・最後の料金と未完成値 |
| 有限丸め | 201分子×10分母×7精度＝14070行 | 分子-100〜100、分母1〜10、精度0〜6。近隣整数への最小距離と偶奇で比較 |
| 有限閾値 | 84係数/精度組・252表示行・2940問 | 係数-10〜10、精度0〜3、セル内外と端点7点×5演算子。証人点で比較 |
| 確認・訂正・時点 | 64履歴・2688表示行 | 三記録の未確認・通常確認・遅延確認・suspected、七view×六query。七種類の回答も照合 |
| seed付き数量・停止 | 200要求・200行 | seed 20261020、負数・分数、四単位、未知能力・文脈、精度・retention |
| seed付き全計画料金 | 100要求 | seed 470033、確認遅延、四view×四query。表示未参照の行と対象期間外の適格訂正辺も課金 |

主要四系列の意味比較は17210表示行です。閾値2940問はその一部で、表示行と足しません。停止の完成行も含み、異なるartifactの個数ではありません。設計47の式だけの有限点検は、このruntime比較へ加算しません。

期待をruntime出力から生成・更新していません。展開時に、閉セル下端のltと上端のgtは常にfalseとなる手指定表の誤りを修正しました。AIの由来と重複ID・数値上限等の拒否理由名は既存の契約へ合わせ、runtimeはそのために変更していません。生小数は共通fixtureローダー自身が拒否するため、fixtureの負例を文字列へ替え、APIのfloat拒否とCLIのJSON小数拒否を専用検査に分けました。

別計算はnativeの丸め・閾値・期間選択・換算関数を呼びません。ただし同じ作業定義を扱う作成者側の検査で、独立確認済みの正解ではありません。Iの静的負例も新しい入口に包んで、未来・未参照の不正や旧Gの確認hashが修復されず、計算前に拒否されることを点検します。全ノードの型破損、サイズ・深さ・依存native実体の破損も検査します。

選定した丸め・閾値・metadata昇格の3変異を関数差替えで与え、別計算との不一致を検出しました。共通予算検査への六値欄・空object・空配列・falseを含む漏出と早期認定の注入も検出します。これらは選定した退行に対する検査であり、変異の網羅ではありません。

## 4. 共有予算と停止

全計画のI料金Cを、view/queryの全組合せ、全可視記録、全適格訂正辺を含めて算定します。開始1、Cを先払いしてbudget=CでIを一度実行、各表示8＋2×質問数、最後1です。子の実費=Cを照合し、表示ごとの計画縮約・再実行・予算リセット・割引・二重計上はしません。

| 計画 | C | Jの完成料金 | 最後の1不足 |
| --- | --- | --- | --- |
| 標準一表示一質問 | 16 | 28 | 27 |
| 同じ子から二表示 | 16 | 38 | 37 |
| A/B部分訂正、二query二表示 | 34 | 56 | 55 |
| 確認前後の二view二表示 | 37 | 59 | 58 |
| 標準一表示七質問 | 16 | 40 | 39 |
| 未参照slot Tの意味停止を含むSの表示 | 30 | 42 | 41 |

標準の16以下ではI未呼出、17以上で16を一度渡します。27では表示行が完成しても認定なしです。七質問の40でもmetadata/exact_valueが範囲外なので認定しません。参照しないTの行の意味停止はSの表示だけの認定を妨げませんが、全計画の構造不正とroot資源停止は別です。

20記録・20確認・64view×64queryの妥当な計画はC=125443です。親上限100000では予約できず、Iを呼ばず全表示を未完了にします。Iが完成済みの一部の値を含んで資源停止しても、Jの表示へ拾いません。後の表示行での資源停止は先の完成行を保持し、未完成のartifact/hash/cell/questions/両根拠は空容器やfalseでもなくnullです。最後の料金だけ不足したときはincompleteにcompletionを残します。

子の途中資源停止・表示途中停止と中間256bit/text64文字は防護分岐への注入・直接呼出による検査を含みます。固定した通常入力で全防護上限へ自然に到達することを実証したとは扱いません。

共通予算は942要求・16502掃引評価、違反0です。追加前773要求・11895評価から、新系列169要求・4607評価が増えました。全946要求のうちbudget欄欠落の4負例は元の拒否として照合し、予算を置換する掃引へ含めません。既存の予算依存拒否の例外1件は維持しています。

## 5. 全体回帰と固定した実体

Python 3.14.4と3.11.17で、全576テストが通過しました。版比較つき統合評価も両版で通過しました。ログと終了コードは `data/research/p2-j/py314/`・`py311/`、統合結果は `data/research/p2-d/p2-j-py314/`・`p2-j-py311/`（全てGit管理外）へ記録します。

| 系列 | 件数 | Python 3.14.4 | Python 3.11.17 |
| --- | --- | --- | --- |
| 開発 | 231 | 通過 | 通過 |
| 追加レビュー系列 | 52 | 通過 | 通過 |
| 保存監査 | 8 | 通過 | 通過 |
| P2 | 285（既存266＋新19） | 通過 | 通過 |
| 統合評価 | P1/P0・拡張・全P2・予算・版比較 | 通過 | 通過 |

両版ともpassed=true、mismatches=[]で、保存したP0 draft-1→draft-2の版記録もstatus=passedでした。版比較の省略を通過としていません。Markdownのローカルリンク・fence、旧モジュールのバイト不変と旧fixture不変、`git diff --check`も確認しました。

既存の22052出力の挙動digestと、生成器による全例・宣言のバイト一致も両版で通過しました。挙動digestは `d0a2233574ab350e65217ef6da8ed037fe34020e8ee79eee2506bd9ce4320236` のままです。

| 統合評価の対象 | P2-j追加後の分母 |
| --- | --- |
| 登録・義務・防護例 | 18宣言・220義務・386防護例参照 |
| 証拠の強さ | checked_native_template 151、finite_check 61、hand_derivation 8 |
| 防護例のない義務 | 既存の3件。新19義務には全て防護例あり |
| 振り分け・依存の独立 | 136組中117組。任意の能力間の意味的な併用保証とは別 |
| 新系列 | 170 JSON・2670必須パス。旧系列の分母も保持 |
| 旧基底 | P1全20条件・80 JSON・417必須パス、別枠P0の37 JSON・221必須パス |

P2_I_EXPECTEDへ追加前の分母を残しました。過去のEXPECTED履歴や挙動digestを変更していません。

追加前のクリーンなa7d7a87で保存した旧共通要求とH/Iの予算変種、6095出力を、追加後とcertifierだけを再帰的に除いて比較し、相違0でした。他のhashや意味欄は除いていません。`data/research/p2-j/old-requests.json`・`old-results.json`・`old-behavior-comparison.json` に記録します。これは既存の22052出力の挙動digestとは別の比較で、合算しません。

固定対象は979→1159ファイル、180追加・削除なしです。新仕様・実装・宣言・実行例・生成器・別計算・検査と契約46/47を加えました。旧fixtureと旧核、quantity/temporal/measurement/display/temporal_measurementの実装・仕様、projection.pyは変更していません。共有入口、登録生成器、評価、依存・生成器検査に新経路を加えています。

- 新native仕様hash：`8b401795d6687df75ddaf7962f02b49d558a306fff98af9d311a7bbd2a83ba0e`
- Iの依存仕様hash：`80785e67b978fe9801d36c653a003d8954cba517b4a16500a2bc648931d80705`
- 数量の依存仕様hash：`84af2e771d1868471d0a8441021fde2a7253b1fc17f8ff9b807461e3df7f1f43`
- manifest hash：`0768eed5e60f620cc3b5234236b9634a7686ac8e06eb6a124844dd9aa927294a`
- 束hash：`5d0791a346c0815cc8d8bbe705c36d30f46a0da792132ff11c8326ddcbcf622d`
- 追加前manifest：`4c68018054499ebf6ba3a34a8efa59fcb61e7438c47f890f644aa73dc58d1968`
- 追加前の束：`9d28e76aeeddfd4eeb72768589365c6d650f8c736d128be690e50706e2331835`

作成者snapshotで、independent_review / evaluation_frozenはfalseです。コミット前の実行はgit_dirty=trueで、コミット後の同じhash・新例・旧挙動・旧核の読み取り専用確認を `data/research/p2-j/postcommit-check.json` へ記録します。

## 6. 再現と次の判断

```bash
PYTHONPATH=src python3 -B -m med_dsl --fixture examples/p2-temporal-display/j01.json
python3 -B -m unittest discover -s tests/p2 -p test_temporal_display.py -v
python3 -B scripts/research/check-extensions.py --json
python3 -B scripts/research/evaluate-p2.py --output data/research/p2-d/p2-j-reproduce
```

次は各接続の前提・確認対象・選択・問い・資源・観測を、反例・制限・再検証範囲を伴う原理の草案へ整理します。専用モジュールの成功を任意の将来能力の合成保証へ一般化せず、原理の候補と有限の実証を対応付けます。その後にR4の実資料評価・薄い臨床ライブラリの試作範囲を選定します。

未知期間の精密化、瞬間/集計からの意味引き継ぎ、縦断比較・相関、一般の合成保証、認証・永続台帳、実コード・会計システムへの接続と標準化は未完了です。独立確認は [運用方針29](29-review-repository-policy.md) に従う将来の英語の別リポジトリへの引継ぎ対象です。有限の表示接続を、変化に耐える医療コード体系そのものの完成とは扱いません。
