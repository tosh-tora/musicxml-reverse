#!/usr/bin/env python3
"""music21でトリル重複がないことを検証"""

from music21 import converter, expressions
from pathlib import Path

# ファイルパス
project_root = Path(__file__).parent.parent.parent
output_file = project_root / "work/outbox/test/威風堂々ラスト_in-Concert_Snare_Drum_rev.mxl"

print(f"検証ファイル: {output_file}\n")

# スコア読み込み
score = converter.parse(output_file)
part = score.parts[0]

# M6取得
m6 = part.measure(6)
if not m6:
    print("[ERROR] M6が見つかりません")
    exit(1)

print("=== M6の解析 ===")
print(f"小節番号: {m6.number}")

# M6の音符とスパナーを確認
notes = list(m6.notesAndRests)
print(f"\n音符数: {len(notes)}")

if notes:
    first_note = notes[0]
    print(f"\n最初の音符: {first_note}")

    # Expression確認
    if hasattr(first_note, 'expressions'):
        trill_expressions = [e for e in first_note.expressions if isinstance(e, expressions.Trill)]
        print(f"  Trill expressions: {len(trill_expressions)}")
        if trill_expressions:
            print(f"    [WARNING] Trill expressionが残っています: {trill_expressions}")
        else:
            print(f"    [OK] Trill expressionなし（TrillExtensionスパナーから自動生成される想定）")

# パート全体のTrillExtensionスパナー確認
print(f"\n=== パート全体のスパナー確認 ===")
trill_extensions = [sp for sp in part.spannerBundle if isinstance(sp, expressions.TrillExtension)]
print(f"TrillExtension数: {len(trill_extensions)}")

for i, te in enumerate(trill_extensions, 1):
    spanned = list(te.getSpannedElements())
    if spanned:
        start_measure = spanned[0].measureNumber
        end_measure = spanned[-1].measureNumber
        print(f"  TrillExtension #{i}: M{start_measure} - M{end_measure} ({len(spanned)}要素)")

        # M6のTrillExtensionを詳細表示
        if start_measure == 6 or end_measure == 6:
            print(f"    開始音符: {spanned[0]}")
            if hasattr(spanned[0], 'expressions'):
                start_trill = [e for e in spanned[0].expressions if isinstance(e, expressions.Trill)]
                if start_trill:
                    print(f"    [ERROR] 開始音符にTrill expression残存: {start_trill}")
                else:
                    print(f"    [OK] 開始音符のTrill expressionはクリーンアップ済み")

print("\n=== 検証結果 ===")
if notes and hasattr(notes[0], 'expressions'):
    trill_count = len([e for e in notes[0].expressions if isinstance(e, expressions.Trill)])
    if trill_count == 0:
        print("[OK] M6の最初の音符にTrill expression重複なし")
        print("[OK] トリル重複修正が正常に機能しています")
    else:
        print(f"[ERROR] M6の最初の音符に{trill_count}個のTrill expression")
else:
    print("[OK] M6にTrill expressionなし")
