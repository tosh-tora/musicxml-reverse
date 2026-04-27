#!/usr/bin/env python3
"""
オクターブシフト問題の詳細調査
"""
from music21 import converter
from pathlib import Path

def investigate_octave_shift():
    """オクターブシフトの原因を調査"""
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    restored = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    orig_score = converter.parse(str(original))
    rest_score = converter.parse(str(restored))

    # パート1の小節2-4を詳細調査
    orig_part = orig_score.parts[0]
    rest_part = rest_score.parts[0]

    orig_measures = list(orig_part.getElementsByClass('Measure'))
    rest_measures = list(rest_part.getElementsByClass('Measure'))

    print("=== オクターブシフト問題の詳細調査 ===\n")

    for m_idx in [1, 2, 3]:  # 小節2-4（0-indexed: 1-3）
        print(f"小節 {m_idx + 1}:")
        orig_m = orig_measures[m_idx]
        rest_m = rest_measures[m_idx]

        print(f"  元の小節:")
        print(f"    timeSignature: {orig_m.timeSignature}")
        print(f"    keySignature: {orig_m.keySignature}")
        print(f"    duration: {orig_m.duration.quarterLength}")

        # オクターブシフト要素の確認
        for element in orig_m.flatten():
            if hasattr(element, 'octaveChange') or 'Ottava' in element.classes:
                print(f"    [検出] Ottava要素: {element}")

        print(f"  再反転後の小節:")
        print(f"    timeSignature: {rest_m.timeSignature}")
        print(f"    keySignature: {rest_m.keySignature}")
        print(f"    duration: {rest_m.duration.quarterLength}")

        for element in rest_m.flatten():
            if hasattr(element, 'octaveChange') or 'Ottava' in element.classes:
                print(f"    [検出] Ottava要素: {element}")

        # 音符を比較
        orig_notes = list(orig_m.flatten().notesAndRests)
        rest_notes = list(rest_m.flatten().notesAndRests)

        print(f"  音符比較:")
        for i, (on, rn) in enumerate(zip(orig_notes, rest_notes)):
            if not on.isRest:
                on_pitch = on.pitch.nameWithOctave if hasattr(on, 'pitch') else str([p.nameWithOctave for p in on.pitches])
                rn_pitch = rn.pitch.nameWithOctave if hasattr(rn, 'pitch') else str([p.nameWithOctave for p in rn.pitches])

                if on_pitch != rn_pitch:
                    print(f"    音符{i+1}: {on_pitch} -> {rn_pitch}")

        print()

if __name__ == "__main__":
    investigate_octave_shift()
