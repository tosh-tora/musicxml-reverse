#!/usr/bin/env python3
"""
reverse_measure_contents() の前後で連桁を確認
"""
from music21 import stream, note
import copy


def test_reverse_measure_contents_effect():
    """reverse_measure_contents() が連桁に影響するか確認"""
    from reverse_score import reverse_measure_contents

    print("=== reverse_measure_contents() の連桁への影響テスト ===\n")

    # テスト小節を作成
    m = stream.Measure()

    n1 = note.Note('C4', quarterLength=0.25)
    n2 = note.Note('D4', quarterLength=0.25)
    n3 = note.Note('E4', quarterLength=0.25)
    n4 = note.Note('F4', quarterLength=0.25)

    # 連桁を設定
    n1.beams.fill('16th', type='start')
    n2.beams.fill('16th', type='continue')
    n3.beams.fill('16th', type='continue')
    n4.beams.fill('16th', type='stop')

    for n in [n1, n2, n3, n4]:
        m.append(n)

    print("処理前の連桁:")
    for i, n in enumerate(list(m.notesAndRests), 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type}, id={id(n.beams.beamsList[0])}")

    # deepcopy を作成
    m_copy = copy.deepcopy(m)

    print("\ndeepコピー直後:")
    for i, n in enumerate(list(m_copy.notesAndRests), 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type}, id={id(n.beams.beamsList[0])}")

    # reverse_measure_contents を実行
    print("\nreverse_measure_contents() 実行...")
    processed_m, error = reverse_measure_contents(m_copy)

    print("\n処理後の連桁:")
    for i, n in enumerate(list(processed_m.notesAndRests), 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type}, id={id(n.beams.beamsList[0])}")

    print("\n結論:")
    print("reverse_measure_contents() がbeamのオブジェクトIDを変更している場合、")
    print("music21が自動的に連桁を再生成している可能性があります")


if __name__ == "__main__":
    test_reverse_measure_contents_effect()
