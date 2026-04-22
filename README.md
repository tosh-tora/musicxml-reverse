# mrev - MusicXML Score Reverser

MusicXML (.mxl / .xml / .musicxml) ファイルを「逆から演奏できる」スコアに変換するツール。

## 機能

- 小節順序を反転
- 各小節内の音符オフセットを反転
- 強弱記号（f, p等）、テキスト表現、テンポ指示、リハーサルマークのオフセットを反転
- Crescendo ↔ Diminuendo を変換
- タイの start/stop を反転
- スラー、オクターブ記号（8va/8vb）などのSpanner要素を保持
- 音部記号、調号、拍子記号を反転後も保持

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
├── reverse_score.py    # メインスクリプト
├── requirements.txt    # 依存パッケージ
├── README.md
└── work/
    ├── inbox/          # 入力ファイル置き場
    └── outbox/         # 出力ファイル置き場
```

## 依存関係

- Python 3.10+
- music21

## ライセンス

MIT
