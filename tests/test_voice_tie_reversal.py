"""
複数Voice（Divisi）を持つ小節でのタイ・連桁・オフセット反転テスト

Issue #58: 管楽器パート等でDivisiによりVoiceが分かれている小節では、
Voice内の音符が measure.notesAndRests に現れないため、タイの反転や
小節内オフセットの反転が一切適用されず、タイが消えたように見えていた。
"""

from music21 import stream, note, tie, beam

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reverse_score import reverse_part


def _measure_with_voices(number, voice_notes):
    """voice_notes: list[list[note.GeneralNote]] each inner list becomes one Voice"""
    m = stream.Measure(number=number)
    for i, notes in enumerate(voice_notes, start=1):
        v = stream.Voice(id=i)
        for n in notes:
            v.append(n)
        m.insert(0, v)
    return m


class TestVoiceTieReversal:
    """Voice内の音符のタイ反転テスト"""

    def test_tie_across_measures_inside_voice_is_flipped(self):
        """Voice内でmeasureをまたぐタイのstart/stopが反転されること"""
        n1 = note.Note('F4', quarterLength=2.0)
        n1.tie = tie.Tie('start')
        n2 = note.Note('F4', quarterLength=2.0)
        n2.tie = tie.Tie('stop')

        part = stream.Part()
        part.append(_measure_with_voices(1, [[n1]]))
        part.append(_measure_with_voices(2, [[n2]]))

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))
        assert len(measures) == 2

        def voice_notes(m):
            return [el for v in m.getElementsByClass('Voice') for el in v.notesAndRests]

        # 小節順序が反転: 元m2が新m1、元m1が新m2になる
        new_m1_notes = voice_notes(measures[0])
        new_m2_notes = voice_notes(measures[1])
        assert len(new_m1_notes) == 1
        assert len(new_m2_notes) == 1
        assert new_m1_notes[0].tie.type == 'start'
        assert new_m2_notes[0].tie.type == 'stop'

    def test_multiple_voices_both_get_tie_flipped(self):
        """Divisiで複数Voiceがある場合、すべてのVoiceでタイが反転されること"""
        def make_pair():
            a = note.Note('A-4', quarterLength=2.0)
            a.tie = tie.Tie('start')
            b = note.Note('A-4', quarterLength=2.0)
            b.tie = tie.Tie('stop')
            return a, b

        v1_n1, v1_n2 = make_pair()
        v2_n1, v2_n2 = make_pair()

        part = stream.Part()
        part.append(_measure_with_voices(1, [[v1_n1], [v2_n1]]))
        part.append(_measure_with_voices(2, [[v1_n2], [v2_n2]]))

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))

        for voice in measures[0].getElementsByClass('Voice'):
            notes = list(voice.notesAndRests)
            assert len(notes) == 1
            assert notes[0].tie.type == 'start'
        for voice in measures[1].getElementsByClass('Voice'):
            notes = list(voice.notesAndRests)
            assert len(notes) == 1
            assert notes[0].tie.type == 'stop'

    def test_offsets_inside_voice_are_time_reversed(self):
        """Voice内の音符のオフセットも小節内で時間反転されること"""
        r = note.Rest(quarterLength=0.5)
        n1 = note.Note('A-4', quarterLength=0.5)
        n2 = note.Note('A-4', quarterLength=0.5)
        n3 = note.Note('A-4', quarterLength=0.5)

        part = stream.Part()
        part.append(_measure_with_voices(1, [[r, n1, n2, n3]]))

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))
        voice = next(iter(measures[0].getElementsByClass('Voice')))
        result = list(voice.notesAndRests)

        # 休符が末尾に移動し、音符が先頭から詰まる（時間反転）
        assert [el.isRest for el in result] == [False, False, False, True]
        assert [el.offset for el in result] == [0.0, 0.5, 1.0, 1.5]

    def test_beams_inside_voice_are_flipped(self):
        """Voice内の連桁start/stopも反転されること"""
        r = note.Rest(quarterLength=0.5)
        n1 = note.Note('A-4', quarterLength=0.5)
        n1.beams.fill('eighth', type='start')
        n2 = note.Note('A-4', quarterLength=0.5)
        n2.beams.fill('eighth', type='continue')
        n3 = note.Note('A-4', quarterLength=0.5)
        n3.beams.fill('eighth', type='stop')

        part = stream.Part()
        part.append(_measure_with_voices(1, [[r, n1, n2, n3]]))

        reversed_part = reverse_part(part)
        measures = list(reversed_part.getElementsByClass(stream.Measure))
        voice = next(iter(measures[0].getElementsByClass('Voice')))
        result = [el for el in voice.notesAndRests if not el.isRest]

        assert result[0].beams.beamsList[0].type == 'start'
        assert result[1].beams.beamsList[0].type == 'continue'
        assert result[2].beams.beamsList[0].type == 'stop'
