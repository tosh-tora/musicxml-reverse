# TODO

## Issue #92: CLAUDE.md を本プロジェクト向けに作り直す

- [x] 旧 CLAUDE.md の別プロジェクト由来の記述を洗い出す（`uv run abap-review`, `npm test`, `main` ブランチ等）
- [x] 公式ガイドライン（memory / best-practices）に沿って英語で書き直す（200行未満、コードから推測できない事実のみ）
- [x] 実コマンドの動作確認（`python -m pytest tests/`、単一テスト指定）

### レビュー

成果物の言語は日本語のまま、`tasks/` は運用継続・参照のみ（@import しない）、汎用ルールは削る方針をユーザーに確認して決定。
`lessons.md` のうち全作業に効く落とし穴（範囲/境界/前方向スパン、music21 往復の扱い）だけを Architecture に要約した。
引数なしの `pytest` はルート直下の旧スクリプト `test_viola_roundtrip.py` の収集エラーで止まるため、`tests/` 指定を明記した。

### 検証

- `python -m pytest tests/` → 162 passed, 19 skipped

## Issue #88: 終端が不明な指示（sostenuto・simile 等）の反転に←を付与する

- [x] 対象語彙の列挙（実コーパスで確認済み: sostenuto, simile, ad lib. + ユーザー判断で
      検証なし先行対応: dolce, cantabile, espressivo, marcato, legato, sempre,
      poco a poco, con moto, agitato, tranquillo, grazioso, leggiero）
- [x] `UNCLEAR_END_WORD_PATTERNS` / `_is_unclear_end_word()` を追加（layout_preservation.py）
- [x] 「その他 (テキスト等)」カテゴリの単純位置反転に←付与を追加（既存の経過的テンポと同じ規約）
- [x] テスト追加（単体7件 + ラウンドトリップ1件、威風堂々ラスト-Violin.mxl の
      sostenuto@m1 / simile@m3 で確認）
- [x] README 更新
- [x] 動作確認（pytest、実ファイルでの反転結果を目視確認）

### レビュー

`rit.` / `accel.` 等の経過的テンポで既に採用されている「有効範囲を計算せず単純位置反転 +
先頭に←」という規約を、テンポ語ではないため `_is_tempo_direction`（sound 要件）の対象に
ならなかった sostenuto / simile 等にも適用した。新しいパイプライン分岐は作らず、既存の
「6. その他」カテゴリ（[layout_preservation.py:2410](../layout_preservation.py:2410)）の
cresc./decresc. 特殊分岐の隣に同型の分岐を追加するだけで済んだ（位置計算ロジックの変更なし）。

対象語彙はユーザー判断で `dolce` 等の一般的な発想標語まで検証なしに先行して含めた
（オルガンのレジストレーション語彙を開いた集合として扱わなかった #73/#83 とは異なり、
今回は「未知の words を状態と誤認するリスク」ではなく「既に単純位置反転されている語に
警告マーカーを追加するだけ」なので誤反転のリスクが無い）。

### 検証

- `python -m pytest tests/` → 157 passed, 19 skipped（変更前と同数、リグレッションなし）
- `work/inbox/威風堂々ラスト-Violin.mxl` を実際に反転し、出力の words テキストを確認:
  `sostenuto`（m1→m53）は `←sostenuto`、`simile`（m3→m51 ×2）は `←simile` になった。
  既存の `rit.`（m34→m20）`←rit.`、`(allargando)`（m29→m25）`←(allargando)` は変化なし

### 対応外

- `simile` は「直前と同様に」という後方参照の指示のため、←は方向が反転したことを示す
  警告に過ぎず、内容の妥当性までは保証しない（反転後の手動確認が必要。D.C./D.S. と同じ扱い）
- オルガンのレジストレーション等、構造的な手がかりの無い状態指示は対象外のまま（#83で対応）
- `reverse_score.py` 側のテンポ収集ロジック（フォールバック時のみ使用）は、
  sostenuto/simile 等を主要テンポとして誤って有効範囲ベース反転してしまう既存の潜在バグを
  持つが、通常経路では `layout_preservation.py` が全 direction を上書きするため顕在化しない。
  今回は対象外（別問題）

---

## Issue #74: 未対応の有効範囲・ペア構造（pedal/dashes/bracket, D.C.・D.S., 曲中の転調）

- [x] ベースライン: master で work/inbox 26ファイルを反転して保存（work/temp/baseline、26/26 成功、pytest 116 passed / 19 skipped）
- [x] ① スパナのペア処理を仕様表駆動に統合（wedge / octave-shift は spread の位置だけが変化）
- [x] ① pedal / dashes / bracket / principal-voice / staff-divide のペア反転、words 同居の対応
- [x] ② string-mute / harp-pedals / scordatura / accordion-registration / metronome の有効範囲反転
- [x] ③ sound ナビゲーションをテンポ判定から分離、ジャンプ属性を削除して警告
- [x] ④ 曲中の key/time の有効範囲反転、最終小節の余分な key/time を除去
- [x] ⑤ measure-repeat / beat-repeat / slash の再配置
- [x] テスト追加（33件、すべて修正前に失敗することを確認）
- [x] README 更新
- [x] 動作確認（pytest、26ファイル一括、master 出力との差分・要素数比較、最小スコアの end-to-end）

### レビュー

ユーザー判断により5項目すべてを対応。項目3（D.C. / D.S.）は保守的な扱いを選択。

- **①** wedge / octave-shift の2関数を `SpannerSpec` の表にまとめ、pedal / dashes / bracket /
  principal-voice / staff-divide に広げた。コーパスで出力が変わったのは hairpin の `spread` の位置だけ。
  入力は「cresc. の start と dim. の stop に spread」という書き方だが、従来は役割と一緒に動かしていたため
  反転後は dim. の start / cresc. の stop に付いていた。端点の位置に付く属性として残すことで
  入力と同じ規則になった（25ファイル。意味比較で他の内容・順序の差分 0）
- **②** string-mute は既存のミュートの状態グループに記号として追加し、打ち消しも同じ記号で合成する。
  harp-pedals 等は #73 の持ち替えラベルと同じ計算を流用。metronome 単独もテンポに含め、
  メトリック・モジュレーションは境界として分離した（テンポ判定を広げたことで新たに誤反転させないため）
- **③** To Coda がテンポの有効範囲を汚染する問題をテストで再現（Allegro が m5 ではなく m8 に来る）してから
  テンポ判定より前に分離した
- **④** issue 記載の `reverse_score.py:788-800` は現在 908-944 に移動していた。原因は小節コピーのループが
  Clef は除去するのに KeySignature / TimeSignature を除去していないこと。clef / layout と計算を共通化した
- **⑤** 仕様（stop は表示が終わった最初の小節・拍、繰り返される実音はファイルに書かれている）を確認し、
  音符の展開ではなく記号の付け直しだけで済むことを確かめてから実装した

テストの期待値を2か所書き誤った（Allegro を m4、segno を m9。正しくは m5 / m10）。
実装前に区間で検算して修正した（#70 の教訓どおり、小節番号の式ではなく区間で書き出す）。

### 検証

- `python -m pytest tests/` → **149 passed, 19 skipped**（master は 116 passed, 19 skipped）
- 26ファイル一括反転 → 各段階（①②④③⑤）で 26/26 成功
- master 出力との差分（ランダム id を除く意味比較）:

  | 変化 | 対象 |
  |---|---|
  | hairpin の `spread` が反対側の端点に移る | 25ファイル |
  | 余分な key / time が最終小節 m53 から消える | 49パート（全ファイル） |
  | key の再掲が m9 → m10 に移る（区間 m45–53 は反転後 m1–9） | 33パート（m45 に再掲がある17ファイル＋総譜） |
  | それ以外 | 差分なし（Viola の m9 は clef と key が別の attributes に分かれただけで、clef の位置は不変） |

- 要素数（入力 / master / 本ブランチ）: key / time は全26ファイルで入力と一致（master は各 +1）。
  その他の増減（括弧付き強弱の direction、tied、Organ の slur 等）は master と同数で本変更とは無関係
- 最小スコアの end-to-end（`work/temp/e2e74`、music21 を通す）: pedal / words 付き wedge / To Coda / 転調 /
  measure-repeat / string-mute / segno / slash / D.S. がすべて区間で計算した位置に出力され、警告は3件

### 対応外

- `<sound>` を持たない文字だけの D.C. / D.S.: テキストとして単純に位置反転される
- harp-pedals 等の最初の指示より前の区間: 設定が分からないので、反転後の末尾区間には何も出さない
- スパナ要素を2つ以上持つ1つの direction: 従来どおり単純鏡像
- 小節の途中にある key / time の変更: 反転後は小節の頭に置く

---

## Issue #84: 途中で移調が変わる打楽器パートで instrument 参照が復元されない（#78 の漏れ）

- [x] 原因特定（music21 が移調変更で Instrument を複製 → 全音符に自前 id の `<instrument>` を付ける）
- [x] 復元対象パートでは music21 の `<instrument>` を取り除いてから元の参照を書き込む
- [x] テスト追加（2件、修正なしで失敗することを確認）
- [x] 動作確認（work/inbox 26ファイル一括、master 出力との差分比較）

### レビュー

#73 の調査中に、Tambourine の反転出力で 123 音符すべてが music21 の生成した1つの id を
参照し、`<score-part>` に定義が無い無効な参照になっているのを発見。同内容の Schellen は正常。

最初は `<sound><instrument-change>` が原因と推測したが、**最小構成では再現しなかった**。
Tambourine と Schellen の入力差分から m45 の `<transpose>` を切り分け、music21 の
`xmlToM21` が途中の移調変更で Instrument を複製することを確認した（Issue 本文も訂正）。

修正は `_restore_instrument_refs()` で、元譜の参照を復元するパートに限り既存の `<instrument>` を
先に取り除くだけ。`_insert_instrument_element()` の「既にあれば何もしない」は重複防止として残す。

### 検証

- `python -m pytest tests/` → 101 passed, 19 skipped（skip は既存の入力ファイル欠如）
- 26ファイル一括反転 → 全件成功
- master 出力との比較: 楽器参照（と music21 のランダム id）以外の差分は全ファイルで無し
- 楽器参照を持つ全パート（Tambourine / Schellen / Percussion / Triangle / Concert_Snare_Drum / 総譜 P14–P17）で
  入力と id 分布が一致、未定義の参照 0 件（修正前は Tambourine と総譜 P17 が不一致）
- Tambourine の出力は同内容の Schellen と全53小節で音高↔楽器の対応が一致

---

## Issue #73: 任意テキストの状態指示が1区間ずれる（打楽器のみ対応）

- [x] 打楽器の持ち替えラベルを `<note><instrument id>` の切り替わりから検出
- [x] ラベルを「次のラベルまで」の区間ごと反転（区間の先頭に移す）
- [x] テスト追加（11件）
- [x] README 更新
- [x] 動作確認（work/inbox 26ファイル一括、master 出力との差分比較）
- [x] オルガンのレジストレーション・simile を別 Issue 化（#83、ユーザー判断で今回は対象外）

### レビュー

ユーザー判断により打楽器のみ対応。語彙ではなく構造で検出する:
「その位置で開始する音符の楽器 id が、直前の持ち替え以降まだ使われていない」words をラベルとする。
音高ごとに id が変わるグロッケン区間の途中の words を誤検出しないため
「直前の持ち替え以降」で窓を切る。位置は厳密一致のみ（後続の入りを巻き込まない）。

**issue 本文の期待値は1小節ずれていた。** 区間で検算すると
Glockensp. の区間 m45–m51 は反転後 m3–m9、Tambourine の区間 m17–m44 は m10–m37 なので、
正しい位置は m1 / **m3** / **m10**（issue は m1 / m2 / m9）。出力でもグロッケンの音符
（P1-I87/91/94/99）が m3–m9 にあることを確認した。

### 実測結果（master 出力との direction 差分）

| ファイル | master | 本ブランチ |
|---|---|---|
| Tambourine / Schellen / 総譜 P17 | Gl.+Schellen.@m2 / Glockensp.@m9 / Tambourine@m37 | @m1 / @m3 / @m10 |
| 上記以外 23ファイル | — | 差分なし（Organ 含む） |

### 検証

- `python -m pytest tests/` → 110 passed, 19 skipped（skip は既存の入力ファイル欠如）
- 26ファイル一括反転 → 全件成功。words direction の入出力個数に減少なし
- 検出はコーパス全体で 4/4（切り替わりの無い `cresc.` 等は 0 件）

### 対応外

- オルガンのレジストレーション（Sw. / G t / Full. / 16 & 32 ft.）: 構造的な手がかりが無い
- `simile`: 後方参照なので位置を動かしても意味が成立しない
- 別件: Tambourine の per-note instrument 参照が復元されない（#78 の漏れ）→ #84 で対応（原因は m45 の `<transpose>`）

---

## Issue #76: 1小節だけの行ができる

- [x] （第1案・不採用）改行・改ページを「小節境界」として反転する
- [x] 音符の `default-x` / `<measure width>` / direction の `default-x` を出力から除去する
- [x] 改行・改ページを出力せず、楽譜ソフトの自動改行に任せる
- [x] テスト差し替え・追加（14件）
- [x] README 更新
- [x] 動作確認（27ファイルで残存 0 件）

### レビュー

最初は「改行位置が1段ずれている」と判断し、`isNew` を境界として反転する修正を入れた
（段構成は入力の完全な鏡像になった）。**しかし症状は悪化した。**
ユーザーから「m24 だけでなく m8, m44 なども1小節で1行を占拠している」と報告を受け、
押し出されているのがいずれも**段の最終小節**である点から切り分け直した。

真の原因は横方向のレイアウト情報が反転に追従していないことだった。

1. **音符の `default-x` が反転していない** — music21 が元の値を持ち回るため、
   反転後は水平位置が右から左に並ぶ。実測: 入力は左→右に増加する小節が20・減少0、
   反転出力は増加0・**減少19**。
2. **`<measure width>` が元の行組みの justify 結果のまま** — 入力ではどの段も合計が
   ちょうど 1029（段の容量）で、**各段の先頭小節だけが広い**（行頭の音部記号・調号ぶん、
   160〜271）。反転すると段の先頭が狭い小節（80〜108）に変わり、広い元・行頭小節が
   段末に来るため容量超過 → 最終小節が押し出される。

第1案で段構成を鏡像に直した結果、**すべての段がちょうど容量ぴったり**になり、
どの段でも押し出しが起きるようになった。これが「悪化」の正体。

最終的な方針（ユーザー判断）: 横方向のレイアウトは情報ごと取り除いて楽譜ソフトに任せ、
改行も強制しない。これは元々このプロジェクトの方針（Issue #30 /
`transform_layout_for_reversal` の「X座標は変換しない、music21 に任せる」）だが、
**music21 が往復で持ち回る値には適用されていなかった**。

### 検証

- 27ファイルすべてで `<note default-x>` 0個 / `<measure width>` 0個 /
  強制改行 0個 を実測
- `<notations>` 配下の音符基準の位置（accent, tenuto 等）と全 `default-y` は保持
- `python -m pytest tests/` → 94 passed, 9 skipped
- `python reverse_score.py` → 27/27 成功、警告なし
- #68〜#70 の成果が無傷であることを再確認（pizz./arco・a 2./I. の配置、
  multiple-rest の位置、臨時記号の不整合 0 件）

---

## Issue #70: 状態を持つ指示の有効範囲反転の漏れ

#68 と同種の漏れをコード・実データ両面で棚卸しした結果への対応。
棚卸しで判明した事実: **状態＋有効範囲を正しく反転できているのは clef / dynamics /
words系テンポ / pizz.arco の 4 つだけ**だった。

- [x] ① 奏法状態を「語彙駆動の状態グループ」に一般化（奏法・分割・ミュート・弓の位置）
- [x] ② `<multiple-rest>` を反転後のブロック先頭に再配置
- [x] 状態を変えていない再掲は鏡像位置に残す（元譜の情報を失わない）
- [x] テスト追加（21件）
- [x] README 更新
- [x] 対応外項目を別 Issue 化（#71 #72 #73 #74）
- [x] 動作確認（個別5ファイル + work/inbox 27ファイル一括）

### レビュー

**①** `a 2.` / `I.` / `div.` は `other_directions` として単純位置鏡像されており、
pizz./arco と全く同じ形で状態が入れ替わっていた。#68 の
`_calculate_reversed_play_state_markers()` を `StateMarkingGroup` 駆動に一般化し、
グループと staff の組ごとに独立した区間として反転する形に変更。新機構は作っていない。

実装中に判明した副作用への対処: 状態が変化する境界だけにマーカーを出すと、
`div.` を持たないパート（Flute, Oboe, A_Clarinet 等 8ファイル）の `a 2.` が
**丸ごと消える**という情報の後退が起きた。元譜で冗長だった再掲は鏡像位置に残す規則を
追加して解消。元 m1 頭の指示は鏡像が曲末を越えるため、練習番号の復元と同じく
最終小節にクランプする。

**②** `measure-style` を扱うコードはリポジトリに存在しなかった（grep 0件）。
`<multiple-rest>N</multiple-rest>` は前方向スパンなので、反転後もブロック末尾に
付いたままで**音符のある小節を休符として結合**していた。
`restore_direction_elements` と同じ「Phase 1 で保存 → Phase 3 で削除・再挿入」方式にし、
`target = total - M - N + 2` に置き直す。再挿入方式にしたため music21 が落とす
N=1 の multiple-rest（運命_冒頭）も同時に回復した。

### 実測結果

| ファイル | 修正前 | 修正後 |
|---|---|---|
| F_Trumpet | `I.`@m6 / `a 2.`@m33,m53（状態が入れ替わり） | `I.`@m1 / `a 2.`@m7,m34,m53 |
| Viola / Violoncello | `div.`@m13 のみ（div. 区間が無印） | `div.`@m1 / `unis.`@m14（合成） |
| Triangle | multiple-rest 5 が m20（音符のある m20-24 を結合） | m16（m16-20 が全休符と一致） |
| Tambourine | m13(4小節) / m17(2小節) | m10 / m16 |
| 運命_冒頭-Violins_I | N=1 が消失 | m14(1小節) / m18(2小節) |

プランに書いた期待値 m6 / m13 は小節頭の正規化（offset 0 の鏡像は次小節頭）を
反映していない誤りで、正しくは m7 / m14（`div.` 区間は反転後 m1-m13 なので解除は m14）。

### 検証

- `python -m pytest tests/` → **80 passed, 9 skipped**（#68 時点は 59 passed）
- `python reverse_score.py` → 27/27 成功、警告なし
- 状態指示テキストの入出力個数: 減少なし（増加分は必要な打ち消しマーカーのみ）
- `<multiple-rest>` の個数変化: 0ファイル（修正前は 1ファイルで消失）
- 全27ファイルの臨時記号の不整合: 0件（#68 の結果を維持）
- 再配置した全ブロックが休符だけの小節に一致することを実測

### 対応外（別 Issue）

- #71 スパナ消失（slur 13/27ファイル・最大18本、wavy-line は Percussion で全滅、tied 増加）
- #72 小節境界（終止線が m1 に出る、複縦線が1小節ずれる、repeat・ending 未対応）
- #73 任意テキストの状態指示（打楽器の持ち替え・オルガンのレジストレーション）
- #74 ペア構造（pedal / dashes / bracket）・`<sound>` ナビゲーション属性・曲中の転調

---

## Issue #68: Pizzや臨時記号の有効範囲

- [x] 問題1: pizz./arco を有効範囲ベースで反転し、区間終端に打ち消しマーカーを生成する
  - [x] `DirectionElement` に `staff` / `sound_pizzicato` を追加
  - [x] `_get_play_state` / `_separate_play_state_directions` を追加
  - [x] `_calculate_reversed_play_state_markers` で区間反転を算出
  - [x] `restore_direction_elements` でテンポ判定より前に分離して挿入
- [x] 問題2: 臨時記号を有効範囲から再計算する `recalculate_accidentals` を追加し Phase 3 で実行
- [x] 問題3: アップ/ダウン弓 → issue に「対応は不要」と明記のため対象外
- [x] テスト追加（17件）
- [x] README 更新
- [x] 動作確認（威風堂々Violin 単体 + work/inbox 27ファイル一括）

## レビュー

### 変更内容

**問題1** — `pizz.`/`arco` は `words` + `sound` を持つため `_is_tempo_direction()`
（`has_sound and has_words`）が真になり、テンポ指示として誤分類されていた。結果として
(a) 区間の終端で状態を打ち消すマーカーが出力されない、(b) staff1 では pizz. と arco が
入れ替わる、(c) 本物のテンポ指示の有効範囲境界を汚染する、の3つの不具合が出ていた。

奏法状態を staff ごとの区間として扱い、曲頭の暗黙状態を arco として区間列を時間反転し、
状態が変化する境界だけにマーカーを出す方式に変更。区間終端には元譜に無い打ち消しマーカーを
生成する。テンポ判定より前に分離することで (c) も解消。

**問題2** — `<accidental>` は「表示する記号」であり、必要かどうかは調号と
「同一小節・同一 staff・同一オクターブ」の有効範囲で決まる。反転で小節内の音順が変わるのに
記号が音符に付いたまま移動するため、冗長な記号が残り必要な記号が欠けていた。
出力XMLを走査して必要な記号だけを残す後処理 `recalculate_accidentals` を追加。

### 実測結果（威風堂々ラスト_in-Violin.mxl / 53小節・2/4）

pizz./arco の配置:

| staff | 修正前 | 修正後 |
|---|---|---|
| 2 | m1 `arco` / m7頭 `pizz.` / (打ち消し無し) | m7頭 `pizz.` / **m8 2拍目 `arco`** |
| 1 | m1 `pizz.` / m4 0.75拍 `arco` | **m4 2拍目 `pizz.`** / **m7頭 `arco`** |

臨時記号: 追加 11 / 削除 6。issue 指摘の m20 2拍目 ♯ と m25 最後の音 ♮ は削除、
m22 は 1拍目の ♮ を残して 2拍目の C♯ に ♯ を追加。

副次的な改善: `Più mosso.`（原譜 m45、最後の主要テンポ）の反転位置が m9 → m1 に修正された。
従来は m46 の `pizz.` がテンポ境界として扱われ有効範囲が m45 で打ち切られていた。

### 検証

- `python -m pytest tests/` → 59 passed, 9 skipped（変更前は 42 passed, 9 skipped。skip は
  既存テストの cwd 相対パス依存によるもので今回は未変更）
- `python reverse_score.py` → 27/27 ファイル成功、警告なし
- 生成した27ファイル全小節を独立の検証関数で走査 → 臨時記号の不整合 0 件
  （Harp/Organ の複数譜、Percussion の unpitched を含む）

## Issue #94: 実行ログを簡素化し、処理ステップを README に記載する

- [x] `process_file()` の Phase 開始/完了行・パート数の出力を削除
- [x] 音符数を `音符数: 入力 → 出力` の 1 行に集約（不一致時の警告は維持）
- [x] Phase 3 の例外メッセージを「XML後処理に失敗しました」に修正
- [x] README に「処理の流れ」「実行時の出力」を追加し、古い「3段階処理」の記述を削除

### レビュー

ユーザーに必要なのは成否・出力先・警告のみで、各ステップの内容は README で読めれば十分という方針。
`layout_preservation.py` 側の詳細出力は既に `verbose=False` で抑制されているため変更していない。

### 検証

- `python -m pytest tests/` → 162 passed, 19 skipped
- `python reverse_score.py` → 26/26 ファイル成功、警告なし。ログは 506 行 → 107 行（うち 9 行は music21 自身の midi channel 警告で変更前から出ている）
- 変更前（master）と変更後の outbox 26 ファイルを展開後 XML で比較 → 差分 0 件
  （`encoding-date` と、music21 が実行ごとにランダム生成する `score-instrument` / `midi-instrument` の id は除外）
