# mrev - MusicXML Score Reverser

MusicXML (.mxl / .xml / .musicxml) ファイルを「逆から演奏できる」スコアに変換するツール。

## 機能

### 音楽的反転
- 小節順序を反転
- 各小節内の音符オフセットを反転
- 強弱記号（f, p等）、テキスト表現、テンポ指示、リハーサルマークのオフセットを反転
- Crescendo ↔ Diminuendo を変換
- タイの start/stop を反転

### 有効範囲を持つ指示の反転
「その位置から次の指示まで有効」な指示は、位置だけでなく有効範囲ごと反転する。

- **強弱記号・テンポ指示**: 次の同種指示までを有効範囲として反転し、元の開始位置には
  括弧付きマーカー（例: `(ff)`）を残す
- **奏法状態（pizz. / arco）**: 譜（staff）ごとに独立した状態として扱い、区間を反転する。
  反転により区間の終端になった位置には、元譜に無い打ち消しマーカー（pizz. → arco）を
  新たに生成する
- **臨時記号（♯/♭/♮）**: 有効範囲は調号と「同一小節・同一 staff・同一オクターブ」で決まるため、
  反転で小節内の音順が変わった後に必要な記号だけを再計算する。冗長な記号は削除し、
  打ち消しに必要な記号は追加する（タイで繋がれた音には記号を繰り返さない）

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
│   ├── test_direction_preservation.py  # direction（強弱・テンポ・奏法状態）の復元
│   ├── test_accidental_scope.py        # 臨時記号の有効範囲
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
