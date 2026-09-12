#!/usr/bin/env python3
"""
Spanner（Slur, TrillExtension等）が反転処理で消失する問題の回帰テスト

Issue #71: 打楽器・弦楽器パート等で、以下の3つの原因によりSlur/wavy-line
（TrillExtension）が反転出力から失われていた。

1. Voice（Divisi）内の音符に付いたSpannerが measure.notesAndRests に
   現れないため、位置照合に失敗して消失する。
2. 1音のみにまたがるTrillExtension（持続音上のwavy-line）が、
   Slur等と同じ「2要素以上」の足切りで無条件にスキップされていた。
3. Grand staff（Organ/Harp等のPartStaff）楽器では、music21がSpannerを
   実際の所属Staffとは異なるPartStaffのspannerBundleにまとめて格納する
   ことがあり、そのままでは所属Staffのspanner収集で取りこぼす。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import stream, note, spanner, expressions, layout

from reverse_score import reverse_part


def _measure_with_voices(number, voice_notes):
    m = stream.Measure(number=number)
    for i, notes in enumerate(voice_notes, start=1):
        v = stream.Voice(id=i)
        for n in notes:
            v.append(n)
        m.insert(0, v)
    return m


class TestSlurInsideVoice:
    """Voice内の音符にまたがるSlurの反転テスト"""

    def test_slur_between_notes_in_same_voice_is_preserved(self):
        n1 = note.Note('C4', quarterLength=1.0)
        n2 = note.Note('D4', quarterLength=1.0)
        sl = spanner.Slur(n1, n2)

        m = _measure_with_voices(1, [[n1, n2]])
        part = stream.Part()
        part.append(m)
        part.insert(0, sl)

        reversed_part = reverse_part(part)
        slurs = [sp for sp in reversed_part.spannerBundle if isinstance(sp, spanner.Slur)]
        assert len(slurs) == 1


class TestSingleNoteTrillExtension:
    """1音のみにまたがるTrillExtension（持続音上のwavy-line）の反転テスト"""

    def test_single_note_trill_extension_is_preserved(self):
        n1 = note.Note('C4', quarterLength=4.0)
        trill_ext = expressions.TrillExtension(n1)

        m = stream.Measure(number=1)
        m.append(n1)
        part = stream.Part()
        part.append(m)
        part.insert(0, trill_ext)

        reversed_part = reverse_part(part)
        trills = [sp for sp in reversed_part.spannerBundle
                  if isinstance(sp, expressions.TrillExtension)]
        assert len(trills) == 1


class TestPartStaffSiblingSpanner:
    """Grand staff（PartStaff）で他Staffのspannerbundleに誤って
    格納されたSlurが、正しい所属Staffの反転結果に復元されることのテスト"""

    def test_slur_misattributed_to_sibling_staff_is_recovered(self):
        n1 = note.Note('C4', quarterLength=1.0)
        n2 = note.Note('D4', quarterLength=1.0)
        sl = spanner.Slur(n1, n2)

        staff1 = stream.PartStaff()
        staff1.id = 'P1-Staff1'
        m1 = stream.Measure(number=1)
        m1.append(note.Note('G4', quarterLength=4.0))
        staff1.append(m1)

        staff2 = stream.PartStaff()
        staff2.id = 'P1-Staff2'
        m2 = stream.Measure(number=1)
        m2.append(n1)
        m2.append(n2)
        m2.append(note.Note('E3', quarterLength=2.0))
        staff2.append(m2)

        # music21が実際のStaffとは異なる方にSpannerをまとめて格納する
        # 事例を再現するため、意図的にstaff1側にSlurを格納する
        staff1.insert(0, sl)

        score = stream.Score()
        score.insert(0, staff1)
        score.insert(0, staff2)
        score.insert(0, layout.StaffGroup([staff1, staff2]))

        reversed_staff2 = reverse_part(staff2)
        slurs = [sp for sp in reversed_staff2.spannerBundle if isinstance(sp, spanner.Slur)]
        assert len(slurs) == 1


class TestGraceNoteAnchoredSlur:
    """Grace noteを端点とするSlurの反転テスト"""

    def test_slur_from_grace_note_to_main_note_is_preserved(self):
        grace = note.Note('C4').getGrace()
        main_note = note.Note('D4', quarterLength=2.0)
        sl = spanner.Slur(grace, main_note)

        m = stream.Measure(number=1)
        m.append(grace)
        m.append(main_note)
        part = stream.Part()
        part.append(m)
        part.insert(0, sl)

        reversed_part = reverse_part(part)
        slurs = [sp for sp in reversed_part.spannerBundle if isinstance(sp, spanner.Slur)]
        assert len(slurs) == 1
