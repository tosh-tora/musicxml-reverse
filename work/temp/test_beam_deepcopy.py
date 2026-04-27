#!/usr/bin/env python3
"""
deepcopy で beam が正しくコピーされるか確認
"""
from music21 import note
import copy


def test_beam_deepcopy():
    """deepcopy が beam を正しくコピーするかテスト"""
    print("=== Beam deepcopy テスト ===\n")

    # 元の音符を作成
    n1 = note.Note('C4', quarterLength=0.25)
    n1.beams.fill('16th', type='start')

    print(f"元の音符:")
    print(f"  id(n1): {id(n1)}")
    print(f"  id(n1.beams): {id(n1.beams)}")
    print(f"  id(n1.beams.beamsList[0]): {id(n1.beams.beamsList[0])}")
    print(f"  n1.beams.beamsList[0].type: {n1.beams.beamsList[0].type}")

    # deepcopy を作成
    n2 = copy.deepcopy(n1)

    print(f"\ndeepコピー後の音符:")
    print(f"  id(n2): {id(n2)}")
    print(f"  id(n2.beams): {id(n2.beams)}")
    print(f"  id(n2.beams.beamsList[0]): {id(n2.beams.beamsList[0])}")
    print(f"  n2.beams.beamsList[0].type: {n2.beams.beamsList[0].type}")

    # n2 の beam を変更
    print(f"\nn2 の beam タイプを 'stop' に変更...")
    n2.beams.beamsList[0].type = 'stop'

    print(f"\n変更後:")
    print(f"  n1.beams.beamsList[0].type: {n1.beams.beamsList[0].type}")
    print(f"  n2.beams.beamsList[0].type: {n2.beams.beamsList[0].type}")

    if n1.beams.beamsList[0].type == 'start' and n2.beams.beamsList[0].type == 'stop':
        print("\n結論: deepcopy は beam を正しく独立にコピーしています")
    else:
        print("\n問題: deepcopy が beam の参照を共有しています！")


if __name__ == "__main__":
    test_beam_deepcopy()
