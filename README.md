# mrev - MusicXML Score Reverser

MusicXML (.mxl / .xml / .musicxml) ファイルを「逆から演奏できる」スコアに変換するツール。

## 機能

### 音楽的反転
- 小節順序を反転
- 各小節内の音符オフセットを反転
- 強弱記号（f, p等）、テキスト表現、テンポ指示、リハーサルマークのオフセットを反転
- Crescendo ↔ Diminuendo を変換
- タイの start/stop を反転
- start/stop の2点で線を描く記号（hairpin・8va・ペダル・`dashes`・`bracket`・`principal-voice`）は
  始点と終点の役割を入れ替える。hairpin の開き（`spread`）や bracket の鉤（`line-end`）のように
  端点の位置に付く属性は元の位置に残す。ペダルの `discontinue` ↔ `resume`、
  `staff-divide` の分割 ↔ 合流（`down` ↔ `up`）も入れ替える

### 有効範囲を持つ指示の反転
「その位置から次の指示まで有効」な指示は、位置だけでなく有効範囲ごと反転する。

- **音部記号・調号・拍子記号**: 次の同種の記号までを有効範囲として反転する。曲中の転調・拍子変更も
  適用区間が保たれ、同じ記号の再掲も区間の先頭に残す
- **強弱記号・テンポ指示**: 次の同種指示までを有効範囲として反転し、元の開始位置には
  括弧付きマーカー（例: `(ff)`）を残す。words を持たない `<metronome>` もテンポとして扱う。
  メトリック・モジュレーション（♩ = ♪. 等）は範囲ではなく前後のテンポを結ぶ境界なので、
  鏡像位置に置いて左右の音価を入れ替える
- **経過的テンポ・終端不明の状態語**（`rit.` / `accel.` / `sostenuto` / `simile` /
  `ad lib.` / `dolce` / `cantabile` / `marcato` 等）: 「次の指示まで有効」だが元譜に
  終端の手がかりが無く有効範囲を計算できないため、単純な位置反転のまま先頭に `←` を
  付けて「ここまで有効」と示す。`simile`（直前と同様に演奏、という後方参照の指示）は
  `←` を付けても内容の妥当性までは保証されないため、反転後は手動確認が必要
- **状態指示**: 譜（staff）ごと・グループごとに独立した状態として扱い、区間を反転する。
  反転により区間の終端になった位置には、元譜に無い打ち消しマーカーを新たに生成する
  （例: `div.` → `unis.`、`pizz.` → `arco`）。状態を変えていない再掲は鏡像位置に残す。
  対応する語彙:

  | グループ | 語彙 | 既定状態 |
  |---|---|---|
  | 奏法 | `pizz.` / `pizzicato` / `arco` | arco |
  | 分割・人数 | `div.` / `divisi` / `unis.` / `unison` / `a 2.` / `a due` / `I.` / `II.` | a 2. |
  | ミュート | `con sord.` / `con sordino` / `senza sord.` / `via sord.` / `<string-mute type="on/off">` | senza sord. |
  | 弓の位置 | `sul pont.` / `sul tasto` / `col legno` / `ord.` / `naturale` | ord. |

- **打楽器の持ち替えラベル**（`Tambourine` / `Glockensp.` 等）: 語彙を列挙できないため、
  音符の `<instrument id>` が新しい楽器に切り替わる位置にある words をラベルとみなし、
  「次のラベルまで」の区間ごと反転する（ラベルは反転後の区間の先頭に移る）。
  最初のラベルより前の区間は表記が分からないため、反転後その先頭には何も出さない。
  構造的な手がかりの無い状態指示（オルガンのレジストレーション等）は誤検出を避けるため対象外
- **設定（`<harp-pedals>` / `<scordatura>` / `<accordion-registration>`）**: 次の同種の指示まで有効だが
  既定状態が無いので、持ち替えラベルと同じく区間の先頭に移す（種類・譜ごとに独立）。
  最初の指示より前の区間は設定が分からないため、反転後その先頭には何も出さない
- **複数小節休符（multiple-rest）**: 「この小節から N 小節」という前方向スパンなので、
  反転後のブロック先頭に置き直す（末尾に残ると音符のある小節を休符として結合してしまう）
- **繰り返し記号（`<measure-repeat>` / `<beat-repeat>` / `<slash>`）**: MusicXML では繰り返される実音も
  書かれているので、記号だけを付け直す。`measure-repeat` は反転後のブロックの先頭 N 小節、
  `beat-repeat` は先頭の1単位（`slash-type` の音価）を実音として表示し、残りを繰り返しにする。
  `slash` は表示区間として反転する
- **臨時記号（♯/♭/♮）**: 有効範囲は調号と「同一小節・同一 staff・同一オクターブ」で決まるため、
  反転で小節内の音順が変わった後に必要な記号だけを再計算する。冗長な記号は削除し、
  打ち消しに必要な記号は追加する（タイで繋がれた音には記号を繰り返さない）

### 演奏順序（D.C. / D.S. / Coda）は変換しない

時間反転後の演奏順序は「曲頭以外から始まる」「先に前方へ飛んでから戻る」形になることが多く、
標準記譜では表せない。`segno` / `coda` の記号と `D.C.` / `To Coda` 等の文字は境界として
鏡像位置に置き、再生用の `<sound>` のジャンプ指定（`dacapo` / `dalsegno` / `tocoda` / `fine` /
`segno` / `coda` / `forward-repeat`）は削除して処理レポートに警告を出す。
反転後の演奏順序は手動で確認すること。`<sound>` を持たない文字だけの `D.C.` 等は対象外
（テキストとして単純に位置反転される）。

### 横方向のレイアウトは楽譜ソフトに任せる

元のMusicXMLが持つ水平位置は「元の音符順・元の行組み」を前提にした値なので、
時間反転すると整合しない。次の情報は出力から取り除き、横方向の配置は楽譜ソフトに任せる。

- **音符の `default-x` / `relative-x`**: 小節先頭からの絶対位置。反転で音符順が変わるため、
  残すと水平位置が右から左に並ぶ
- **`<measure width>`**: 段の幅に合わせて justify された結果。反転で段の構成が変わると
  行頭に必要な音部記号・調号のぶんが入らず、はみ出した小節が単独で1行を占めてしまう
- **`<direction>` 配下の `default-x` / `relative-x`**: 同じく小節先頭基準
- **改行・改ページ（`new-system` / `new-page`）**: 強制せず、楽譜ソフトの自動改行に任せる

縦方向（`default-y` / `relative-y` / `placement`、段や譜の間隔）と、`<notations>` 配下の
音符基準の微調整（accent, tenuto 等）はそのまま保持する。

### レイアウト保存
- **視覚的配置の保存**: 反転後もスコアの視覚的品質を維持
  - ダイナミクス（f, p等）の座標変換（X座標を小節内で鏡像反転）
  - Y座標、配置属性（above/below）の保持
  - 元の小節幅に基づく正確な座標変換
- **3段階処理**:
  1. 元のXMLからレイアウト情報を抽出（music21処理前）
  2. 音楽的反転処理（既存ロジック）
  3. 変換されたレイアウトを出力XMLに適用（music21処理後）
- **graceful degradation**: レイアウト処理が失敗しても反転は完了

## インストール

```bash
pip install -r requirements.txt
```

## 使い方

### 対応形式

- `.mxl` (圧縮MusicXML)
- `.xml` (非圧縮MusicXML)
- `.musicxml` (非圧縮MusicXML)

入力ファイルの形式はそのまま出力にも保持されます（.mxl → .mxl、.xml → .xml）。

### 基本的な使い方

1. `work/inbox/` に MusicXML ファイル (.mxl / .xml / .musicxml) を配置
2. スクリプトを実行
3. `work/outbox/` に反転されたファイルが出力される

```bash
python reverse_score.py
```

例:
- `work/inbox/score.mxl` → `work/outbox/score_rev.mxl`
- `work/inbox/score.xml` → `work/outbox/score_rev.xml`
- `work/inbox/score.musicxml` → `work/outbox/score_rev.musicxml`

反転版であることが分かるように、スコアのタイトル（work-title / movement-title およびタイトルのcredit）には ` 反転` が追記されます（例: `Pomp and Circumstance March No. 1 反転`）。

### オプション

| オプション | 説明 |
|------------|------|
| `-s`, `--skip-measure-content` | 問題のある小節の音符反転のみスキップ（小節順序・タイ・ダイナミクスは反転） |

```bash
# 問題のある小節があっても可能な限り処理を続行
python reverse_score.py -s
```

## エラーハンドリング

### デフォルトモード

問題のあるパート全体をスキップして処理を続行。

### `-s` モード（推奨）

1. 小節内の音符反転を試行
2. 書き出しエラー発生 → 元の小節（反転前）を使用
3. 元の小節も問題がある場合 → 音価を量子化（最も近い標準音価に丸める）
4. それでもダメな場合 → 休符に置き換え
5. 最後に問題箇所をレポート出力

### レポート例

```
============================================================
問題レポート: example.mxl
============================================================
スキップした小節数: 2

詳細:

  [Harp 2]
    小節 9: スキップ - 書き出しエラー（音符反転スキップ）: Cannot convert inexpressible durations
    小節 267: スキップ - 書き出しエラー（音符反転スキップ）: Cannot convert inexpressible durations
```

## ディレクトリ構成

```
mrev/
├── reverse_score.py          # メインスクリプト
├── layout_preservation.py    # レイアウト保存モジュール
├── tests/                    # pytest テストスイート
│   ├── test_direction_preservation.py  # direction（強弱・テンポ・状態指示・ペア構造・演奏順序）の復元
│   ├── test_accidental_scope.py        # 臨時記号の有効範囲
│   ├── test_key_time_scope.py          # 調号・拍子記号の有効範囲
│   ├── test_measure_style.py           # 複数小節休符・繰り返し記号の再配置
│   ├── test_layout_hints.py            # 水平位置情報の除去
│   ├── test_position_adjustment.py     # 音部記号・レイアウトの位置計算
│   ├── test_voice_tie_reversal.py      # voice内のタイ・連桁の反転
│   └── test_merged_staff_layout.py     # 複数譜パート結合時のレイアウト
├── requirements.txt          # 依存パッケージ
├── README.md
└── work/
    ├── inbox/                # 入力ファイル置き場
    └── outbox/               # 出力ファイル置き場
```

## 依存関係

- Python 3.10+
- music21

## ライセンス

MIT
