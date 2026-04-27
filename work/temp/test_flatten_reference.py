#!/usr/bin/env python3
"""
flatten() が参照を返すか、新しいオブジェクトを返すかテスト
"""
from music21 import stream, note


def test_flatten_reference():
    """flatten() の挙動をテスト"""
    print("=== flatten() テスト ===\n")

    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()

    n1 = note.Note('C4', quarterLength=0.25)
    n1.beams.fill('16th', type='start')

    m.append(n1)
    p.append(m)
    s.append(p)

    print(f"元の音符 n1:")
    print(f"  id(n1): {id(n1)}")
    print(f"  beams: {n1.beams.beamsList[0].type}")
    print(f"  id(beams[0]): {id(n1.beams.beamsList[0])}")

    # flatten で取得
    notes_flat = list(s.flatten().notes)
    n1_flat = notes_flat[0]

    print(f"\nflatten() で取得した音符:")
    print(f"  id(n1_flat): {id(n1_flat)}")
    print(f"  beams: {n1_flat.beams.beamsList[0].type}")
    print(f"  id(beams[0]): {id(n1_flat.beams.beamsList[0])}")

    # beamを変更
    print(f"\nn1_flat の beam を 'stop' に変更...")
    n1_flat.beams.beamsList[0].type = 'stop'

    print(f"\n変更後:")
    print(f"  n1.beams: {n1.beams.beamsList[0].type}")
    print(f"  n1_flat.beams: {n1_flat.beams.beamsList[0].type}")

    if id(n1) == id(n1_flat):
        print("\n結論: flatten() は同じオブジェクトへの参照を返します（コピーなし）")
    else:
        print("\n結論: flatten() は新しいオブジェクトを返します")


if __name__ == "__main__":
    test_flatten_reference()
