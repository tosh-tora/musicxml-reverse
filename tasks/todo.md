# TODO

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
