#!/usr/bin/env python3
"""
全小節の音符を詳細比較
"""
from music21 import converter
from pathlib import Path

def compare_all_measures():
    """全小節の音符を比較"""
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    restored = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    orig_score = converter.parse(str(original))
    rest_score = converter.parse(str(restored))

    print("=== 全小節の音符詳細比較 ===\n")

    total_diff_count = 0

    for part_idx, (orig_part, rest_part) in enumerate(zip(orig_score.parts, rest_score.parts)):
        print(f"パート {part_idx + 1}: {orig_part.partName}")

        orig_measures = list(orig_part.getElementsByClass('Measure'))
        rest_measures = list(rest_part.getElementsByClass('Measure'))

        for m_idx in range(min(len(orig_measures), len(rest_measures))):
            orig_m = orig_measures[m_idx]
            rest_m = rest_measures[m_idx]

            orig_notes = list(orig_m.flatten().notesAndRests)
            rest_notes = list(rest_m.flatten().notesAndRests)

            def get_pitches(n):
                if n.isRest:
                    return []
                elif n.isChord:
                    return [p.nameWithOctave for p in n.pitches]
                else:
                    return [n.pitch.nameWithOctave]

            if len(orig_notes) != len(rest_notes):
                print(f"  小節{m_idx+1}: 音符数不一致 ({len(orig_notes)} vs {len(rest_notes)})")
                total_diff_count += 1
                continue

            has_diff = False
            for j, (on, rn) in enumerate(zip(orig_notes, rest_notes)):
                if get_pitches(on) != get_pitches(rn):
                    if not has_diff:
                        print(f"  小節{m_idx+1}: ピッチ差異")
                        has_diff = True
                    print(f"    音符{j+1}: {get_pitches(on)} -> {get_pitches(rn)}")
                    total_diff_count += 1
                elif abs(on.duration.quarterLength - rn.duration.quarterLength) > 0.001:
                    if not has_diff:
                        print(f"  小節{m_idx+1}: 音価差異")
                        has_diff = True
                    print(f"    音符{j+1}: {on.duration.quarterLength} -> {rn.duration.quarterLength}")
                    total_diff_count += 1
                elif abs(on.offset - rn.offset) > 0.001:
                    if not has_diff:
                        print(f"  小節{m_idx+1}: オフセット差異")
                        has_diff = True
                    print(f"    音符{j+1}: offset {on.offset} -> {rn.offset}")
                    total_diff_count += 1

    if total_diff_count == 0:
        print("\n[OK] 全小節で音符が完全一致しています！")
    else:
        print(f"\n[差異] 合計 {total_diff_count} 箇所で差異が検出されました")

if __name__ == "__main__":
    compare_all_measures()
