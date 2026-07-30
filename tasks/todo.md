# TODO

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
