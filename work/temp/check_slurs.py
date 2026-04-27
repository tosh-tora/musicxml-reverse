#!/usr/bin/env python3
"""反転前後でスラーがどう変化するか確認"""

from music21 import converter, spanner
from pathlib import Path

def check_slurs(filepath):
    """ファイル内のスラーを表示"""
    score = converter.parse(str(filepath))

    print(f"\n{'='*60}")
    print(f"ファイル: {filepath.name}")
    print(f"{'='*60}")

    for part_idx, part in enumerate(score.parts, 1):
        part_name = part.partName or f"Part {part_idx}"
        slurs = [sp for sp in part.spannerBundle if isinstance(sp, spanner.Slur)]

        print(f"\n{part_name}: {len(slurs)} スラー")

        if not slurs:
            print("  (スラーなし)")
            continue

        for i, sl in enumerate(slurs, 1):
            elements = list(sl.getSpannedElements())
            if len(elements) >= 2:
                start = elements[0]
                end = elements[-1]
                print(f"  Slur {i}:")
                print(f"    開始: {start.nameWithOctave} (offset={start.offset}, measure={start.measureNumber})")
                print(f"    終了: {end.nameWithOctave} (offset={end.offset}, measure={end.measureNumber})")
            else:
                print(f"  Slur {i}: 要素数不足 ({len(elements)})")

# 反転前
original = Path("work/inbox/test-slurs.xml")
if original.exists():
    check_slurs(original)

# 反転後
reversed_file = Path("work/outbox/test-slurs_rev.xml")
if reversed_file.exists():
    check_slurs(reversed_file)
else:
    print(f"\n反転後のファイルが見つかりません: {reversed_file}")
