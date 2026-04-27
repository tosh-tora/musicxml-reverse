#!/usr/bin/env python3
"""元ファイルのM48-M50のTrillとTrillExtensionを解析"""

from music21 import converter, expressions
from pathlib import Path

# 元ファイルパス
project_root = Path(__file__).parent.parent.parent
input_file = project_root / "work/inbox/威風堂々ラスト_in-Concert_Snare_Drum.mxl"

print(f"元ファイル: {input_file}\n")

# スコア読み込み
score = converter.parse(input_file)
part = score.parts[0]

# M48-M50を取得
m48 = part.measure(48)
m49 = part.measure(49)
m50 = part.measure(50)

print("=== M48 (トリル開始) ===")
if m48 and m48.notesAndRests:
    note48 = m48.notesAndRests[0]
    print(f"音符: {note48}")
    if hasattr(note48, 'expressions'):
        trill_exps = [e for e in note48.expressions if isinstance(e, expressions.Trill)]
        print(f"Trill expressions: {len(trill_exps)}")
        if trill_exps:
            print(f"  -> {trill_exps}")

print("\n=== M49 (中間・タイ) ===")
if m49 and m49.notesAndRests:
    note49 = m49.notesAndRests[0]
    print(f"音符: {note49}")
    if hasattr(note49, 'expressions'):
        trill_exps = [e for e in note49.expressions if isinstance(e, expressions.Trill)]
        print(f"Trill expressions: {len(trill_exps)}")

print("\n=== M50 (トリル終了) ===")
if m50 and m50.notesAndRests:
    note50 = m50.notesAndRests[0]
    print(f"音符: {note50}")
    if hasattr(note50, 'expressions'):
        trill_exps = [e for e in note50.expressions if isinstance(e, expressions.Trill)]
        print(f"Trill expressions: {len(trill_exps)}")

print("\n=== TrillExtensionスパナー ===")
trill_extensions = [sp for sp in part.spannerBundle if isinstance(sp, expressions.TrillExtension)]
for i, te in enumerate(trill_extensions, 1):
    spanned = list(te.getSpannedElements())
    if spanned:
        start_m = spanned[0].measureNumber
        end_m = spanned[-1].measureNumber
        if 48 <= start_m <= 50 or 48 <= end_m <= 50:
            print(f"TrillExtension #{i}: M{start_m} - M{end_m} ({len(spanned)}要素)")
            for j, note in enumerate(spanned):
                print(f"  音符 #{j+1} (M{note.measureNumber}): {note}")
