#!/usr/bin/env python3
"""M4とM6のTrill expressionを詳細検証"""

from music21 import converter, expressions
from pathlib import Path

# ファイルパス
project_root = Path(__file__).parent.parent.parent
output_file = project_root / "work/outbox/test/威風堂々ラスト_in-Concert_Snare_Drum_rev.mxl"

print(f"検証ファイル: {output_file}\n")

# スコア読み込み
score = converter.parse(output_file)
part = score.parts[0]

# M4とM6を取得
m4 = part.measure(4)
m6 = part.measure(6)

print("=== TrillExtension #1 (M4-M6) の詳細 ===")
trill_extensions = [sp for sp in part.spannerBundle if isinstance(sp, expressions.TrillExtension)]
te1 = trill_extensions[0] if trill_extensions else None

if te1:
    spanned = list(te1.getSpannedElements())
    print(f"スパンされた音符数: {len(spanned)}")

    for i, note in enumerate(spanned):
        measure_num = note.measureNumber
        trill_exps = [e for e in note.expressions if isinstance(e, expressions.Trill)] if hasattr(note, 'expressions') else []
        print(f"\n  音符 #{i+1} (M{measure_num}):")
        print(f"    {note}")
        print(f"    Trill expressions: {len(trill_exps)}")
        if trill_exps:
            print(f"      -> {trill_exps}")
        else:
            print(f"      -> なし")

print("\n" + "="*60)
print("期待される結果:")
print("  - M4 (開始音符): Trill expression 1個 (保持)")
print("  - M6 (終了音符): Trill expression 0個 (削除)")
print("="*60)
