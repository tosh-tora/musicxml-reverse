#!/usr/bin/env python3
"""
和音(Chord)のタイ・連符が反転処理で二重反転され、
結果的に反転されないまま残ってしまう問題の回帰テスト

Chordの.tieプロパティのセッターは各構成音符(chord.notes)に対して
新しいTie/Tupletオブジェクトを個別に割り当てる。そのため、Chord本体に
reverse_ties()/reverse_tuplets()を適用した後、さらに各構成音符に対しても
同じ関数を適用すると、構成音符ごとに独立してもう一度反転されてしまい、
（構成音符数が偶数個の場合など）正味の反転が打ち消されて元のstart/stopの
まま残ってしまう。これにより、小節をまたぐタイの反転後の向きが元と同じに
なり、実際には逆側の小節にタイがかかっているように見える不具合が生じていた。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import stream, chord, tie

from reverse_score import reverse_part


def _measure_with_chord(number, pitches, quarter_length, tie_type):
    m = stream.Measure(number=number)
    c = chord.Chord(pitches, quarterLength=quarter_length)
    c.tie = tie.Tie(tie_type)
    m.append(c)
    return m, c


class TestChordTieReversal:
    """複数音からなるChordのタイ反転テスト"""

    def test_two_note_chord_tie_direction_is_flipped(self):
        """2音のChordでタイのstart/stopが正しく反転されること"""
        m1, c1 = _measure_with_chord(1, ['F4', 'F5'], 2.0, 'start')
        m2, c2 = _measure_with_chord(2, ['F4', 'F5'], 2.0, 'stop')

        part = stream.Part()
        part.append(m1)
        part.append(m2)

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))
        # 小節順序が反転: 元m2が新m1、元m1が新m2になる
        new_m1_chord = measures[0].notesAndRests[0]
        new_m2_chord = measures[1].notesAndRests[0]

        assert new_m1_chord.tie.type == 'start'
        assert new_m2_chord.tie.type == 'stop'

    def test_three_note_chord_tie_direction_is_flipped(self):
        """3音のChordでもタイのstart/stopが正しく反転されること"""
        m1, c1 = _measure_with_chord(1, ['C4', 'E4', 'G4'], 2.0, 'start')
        m2, c2 = _measure_with_chord(2, ['C4', 'E4', 'G4'], 2.0, 'stop')

        part = stream.Part()
        part.append(m1)
        part.append(m2)

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))
        new_m1_chord = measures[0].notesAndRests[0]
        new_m2_chord = measures[1].notesAndRests[0]

        assert new_m1_chord.tie.type == 'start'
        assert new_m2_chord.tie.type == 'stop'
