"""
Divisi等で複数Voiceがある小節において、反転処理でVoice先頭に移動した
不要な隠し休符をforward要素に変換するテスト

Issue #64: 元のファイルでは forward 要素（何の要素も生成しない無音の
カーソル移動）で表現されていたVoice末尾の余白が、反転処理でVoiceの
先頭に移動すると、music21の書き出し時に非表示(print-object="no")の
休符として復元されてしまい、MuseScore等の編集画面で灰色の休符として
表示されてしまう問題を修正する。
"""

import xml.etree.ElementTree as ET

from music21 import chord, note, stream

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reverse_score import reverse_part
from layout_preservation import convert_filler_rests_to_forward


def _measure_with_voices(number, voice_notes):
    """voice_notes: list[list[note.GeneralNote]] each inner list becomes one Voice"""
    m = stream.Measure(number=number)
    for i, notes in enumerate(voice_notes, start=1):
        v = stream.Voice(id=i)
        for n in notes:
            v.append(n)
        m.insert(0, v)
    return m


def _hidden_rests(elements):
    return [
        el for el in elements
        if el.tag.endswith('note')
        and el.find('{*}rest') is not None
        and el.get('print-object') == 'no'
    ]


def _forwards(elements):
    return [el for el in elements if el.tag.endswith('forward')]


class TestFillerRestCleanup:
    """Voice先頭の不要な隠し休符のクリーンアップテスト"""

    def test_leading_filler_rest_converted_to_forward(self, tmp_path):
        """反転によりVoice先頭に移動した隠し休符がforwardに変換されること"""
        # Voice1: 小節全体を満たす半音符
        top_note = note.Note('G5', quarterLength=2.0)
        # Voice2: 先頭の四分音符の和音のみ（末尾1拍は元々forwardで埋められる想定）
        divisi_chord = chord.Chord(['G3', 'D4', 'B4'], quarterLength=1.0)

        part = stream.Part()
        part.append(_measure_with_voices(1, [[top_note], [divisi_chord]]))

        reversed_part = reverse_part(part)
        score = stream.Score()
        score.append(reversed_part)

        out_path = tmp_path / "out.musicxml"
        score.write('musicxml', fp=str(out_path))

        root_before = ET.parse(out_path).getroot()
        measure_before = list(root_before.find('.//{*}measure'))
        hidden_before = _hidden_rests(measure_before)
        # music21が実際に隠し休符を生成していることを前提として確認する
        # （前提が崩れたら、このテスト自体の意味がなくなるため明示的に検証する）
        assert len(hidden_before) == 1
        rest_duration = hidden_before[0].find('{*}duration').text

        convert_filler_rests_to_forward(out_path)

        root_after = ET.parse(out_path).getroot()
        measure_after = list(root_after.find('.//{*}measure'))

        assert _hidden_rests(measure_after) == []

        forwards = _forwards(measure_after)
        assert len(forwards) == 1
        assert forwards[0].find('{*}duration').text == rest_duration

        # forwardはbackupの直後、和音の音符の直前に配置されること
        tags = [el.tag.rsplit('}', 1)[-1] for el in measure_after]
        backup_idx = tags.index('backup')
        assert tags[backup_idx + 1] == 'forward'
        assert tags[backup_idx + 2] == 'note'

    def test_fully_rested_hidden_voice_left_untouched(self, tmp_path):
        """Voice全体が隠し休符のみの場合は変換しないこと"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Test</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>2</duration>
        <voice>1</voice>
        <type>half</type>
      </note>
      <backup><duration>2</duration></backup>
      <note print-object="no" print-spacing="yes">
        <rest/>
        <duration>2</duration>
        <voice>2</voice>
        <type>half</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""
        out_path = tmp_path / "negative.musicxml"
        out_path.write_text(xml_content, encoding='utf-8')

        convert_filler_rests_to_forward(out_path)

        root = ET.parse(out_path).getroot()
        measure = list(root.find('.//{*}measure'))

        assert len(_hidden_rests(measure)) == 1
        assert _forwards(measure) == []
