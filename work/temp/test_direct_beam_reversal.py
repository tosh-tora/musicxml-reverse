#!/usr/bin/env python3
"""
最小限の連桁反転テスト
"""
from music21 import note


def test_direct_beam_reversal():
    """reverse_beams()を直接テスト"""
    from reverse_score import reverse_beams

    print("=== reverse_beams() 直接テスト ===\n")

    # 単純なstart beamを持つ音符
    n = note.Note('C4', quarterLength=0.25)
    n.beams.fill('16th', type='start')

    print(f"変更前: {n.beams}")
    for beam_obj in n.beams.beamsList:
        print(f"  Beam {beam_obj.number}: type='{beam_obj.type}'")

    reverse_beams(n)

    print(f"\n変更後: {n.beams}")
    for beam_obj in n.beams.beamsList:
        print(f"  Beam {beam_obj.number}: type='{beam_obj.type}'")

    # 検証
    assert n.beams.beamsList[0].type == 'stop', "start が stop に変わっていません！"
    print("\n✓ start -> stop の反転が成功しました")


if __name__ == "__main__":
    test_direct_beam_reversal()
