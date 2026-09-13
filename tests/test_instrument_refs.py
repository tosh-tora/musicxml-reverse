#!/usr/bin/env python3
"""
打楽器パートのper-note<instrument>参照の復元テスト

Issue #78: 1つの<part>内で音符ごとに異なる<instrument id="...">を参照して
複数の音高/音色を表現する打楽器パート（例: グロッケンシュピールの音高を
打楽器譜内に記譜する構成）では、music21がこの参照を読み込まないため、
反転後に書き出すと全音符が同じ音（デフォルトの音色）になってしまう。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from layout_preservation import extract_layout_from_xml
from reverse_score import process_file


def _score_instrument_ids(path: Path) -> list[str]:
    """出力の<score-part>直下にある<score-instrument id>の一覧を返す"""
    if path.suffix == '.mxl':
        with zipfile.ZipFile(path, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            root = ET.fromstring(z.read(name))
    else:
        root = ET.parse(path).getroot()
    return [si.get('id') for si in root.findall('.//{*}score-part/{*}score-instrument')]


def _write_score(path: Path, body_xml: str, part_list_xml: str | None = None) -> None:
    """<part id="P1">の中身だけを差し替えた最小構成のMusicXMLを書き出す"""
    if part_list_xml is None:
        part_list_xml = '<score-part id="P1"><part-name>Test</part-name></score-part>'
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        f'  <part-list>{part_list_xml}</part-list>\n'
        '  <part id="P1">\n' + body_xml + '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


# 複数instrumentを持つ<score-part>（威風堂々ラスト-Schellenのpart-listを最小化したもの）
_MULTI_INSTRUMENT_PART_LIST = (
    '<score-part id="P1"><part-name>Test</part-name>'
    '<score-instrument id="P1-IA"><instrument-name>Sound A</instrument-name></score-instrument>'
    '<score-instrument id="P1-IB"><instrument-name>Sound B</instrument-name></score-instrument>'
    '<midi-instrument id="P1-IA"><midi-channel>10</midi-channel>'
    '<midi-unpitched>91</midi-unpitched></midi-instrument>'
    '<midi-instrument id="P1-IB"><midi-channel>10</midi-channel>'
    '<midi-unpitched>94</midi-unpitched></midi-instrument>'
    '</score-part>'
)


def _notes(path: Path):
    """(voice, display-step+octave または REST, instrument id) のリストを小節ごとに返す"""
    if path.suffix == '.mxl':
        with zipfile.ZipFile(path, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            root = ET.fromstring(z.read(name))
    else:
        root = ET.parse(path).getroot()

    result: dict[int, list[tuple[str, str, str | None]]] = {}
    for part in root.findall('.//{*}part'):
        for measure in part.findall('{*}measure'):
            num = int(measure.get('number'))
            entries = []
            for note in measure.findall('{*}note'):
                if note.find('{*}chord') is not None:
                    continue
                voice_elem = note.find('{*}voice')
                voice = voice_elem.text.strip() if voice_elem is not None and voice_elem.text else '1'
                rest = note.find('{*}rest')
                if rest is not None:
                    key = 'REST'
                else:
                    unpitched = note.find('{*}unpitched')
                    step = unpitched.find('{*}display-step').text
                    octave = unpitched.find('{*}display-octave').text
                    key = f'{step}{octave}'
                inst_elem = note.find('{*}instrument')
                inst_id = inst_elem.get('id') if inst_elem is not None else None
                entries.append((voice, key, inst_id))
            result[num] = entries
    return result


# 2/4拍子・2voice。voice1: F5(instA) → 休符、voice2: G4(instB) → 休符（真裏拍）。
# 威風堂々ラスト-Schellen.mxl の45小節目以降と同じ構造（打楽器譜内に音高を記譜し、
# backupを挟んだ2voice構成）を最小化したもの。
_TWO_VOICE_MEASURE = (
    '    <measure number="1">'
    '<attributes><divisions>1</divisions><key><fifths>0</fifths></key>'
    '<time><beats>2</beats><beat-type>4</beat-type></time>'
    '<clef><sign>G</sign><line>2</line></clef></attributes>'
    '<note><unpitched><display-step>F</display-step><display-octave>5</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IA"/><voice>1</voice><type>quarter</type></note>'
    '<note><rest/><duration>1</duration><voice>1</voice><type>quarter</type></note>'
    '<backup><duration>2</duration></backup>'
    '<note><unpitched><display-step>G</display-step><display-octave>4</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IB"/><voice>2</voice><type>quarter</type></note>'
    '<note><rest/><duration>1</duration><voice>2</voice><type>quarter</type></note>'
    '</measure>\n'
)


class TestInstrumentRefExtraction:
    """extract_layout_from_xml() によるinstrument参照の抽出"""

    def test_extracts_voice_and_note_index(self, tmp_path):
        score = tmp_path / 'score.xml'
        _write_score(score, _TWO_VOICE_MEASURE)

        layout_map = extract_layout_from_xml(score)
        refs = layout_map.instrument_refs['P1']

        assert {(r.voice, r.note_index, r.instrument_id) for r in refs} == {
            ('1', 0, 'P1-IA'),
            ('2', 0, 'P1-IB'),
        }

    def test_no_instrument_elements_is_empty(self, tmp_path):
        score = tmp_path / 'score.xml'
        _write_score(
            score,
            '    <measure number="1">'
            '<attributes><divisions>1</divisions>'
            '<time><beats>2</beats><beat-type>4</beat-type></time>'
            '<clef><sign>G</sign><line>2</line></clef></attributes>'
            '<note><pitch><step>C</step><octave>4</octave></pitch>'
            '<duration>2</duration><voice>1</voice><type>half</type></note>'
            '</measure>\n',
        )

        layout_map = extract_layout_from_xml(score)

        assert layout_map.instrument_refs['P1'] == []

    def test_multi_instrument_score_part_captures_defs(self, tmp_path):
        """Issue #78: 複数<score-instrument>を持つ<score-part>では定義一式を保存する"""
        score = tmp_path / 'score.xml'
        _write_score(score, _TWO_VOICE_MEASURE, part_list_xml=_MULTI_INSTRUMENT_PART_LIST)

        layout_map = extract_layout_from_xml(score)

        defs = layout_map.instrument_defs_xml['P1']
        assert sum('<score-instrument' in d for d in defs) == 2
        assert sum('<midi-instrument' in d for d in defs) == 2

    def test_single_instrument_score_part_is_not_captured(self, tmp_path):
        """instrumentが1つだけの<score-part>は復元対象にしない（music21の出力で十分）"""
        score = tmp_path / 'score.xml'
        _write_score(score, _TWO_VOICE_MEASURE)  # デフォルトのpart-list（instrumentなし）

        layout_map = extract_layout_from_xml(score)

        assert 'P1' not in layout_map.instrument_defs_xml


class TestInstrumentRefRestoration:
    """反転後の出力へのinstrument参照の復元（voice単位で独立して反転される）"""

    def test_two_voice_measure_instruments_are_not_swapped(self, tmp_path):
        """Issue #78: 同一小節内で複数voiceがある場合、instrument参照が
        voiceをまたいで入れ替わってはいけない（各voiceは独立に反転される）"""
        score = tmp_path / 'score.xml'
        _write_score(score, _TWO_VOICE_MEASURE)
        output = tmp_path / 'output.xml'

        report = process_file(score, output)
        assert report.success

        notes = _notes(output)[1]
        by_voice = {(v, k): inst for v, k, inst in notes}

        # voice1: F5→休符 だったのが 休符→F5 に反転。instrumentはF5に付いたまま。
        assert by_voice[('1', 'F5')] == 'P1-IA'
        # voice2: G4→休符 だったのが 休符→G4 に反転。instrumentはG4に付いたまま。
        assert by_voice[('2', 'G4')] == 'P1-IB'

    def test_score_instrument_definitions_are_preserved(self, tmp_path):
        """Issue #78: music21が1つに統合してしまう<score-instrument>定義を復元する

        per-note<instrument id>を復元しても、参照先の<score-instrument>が
        <part-list>から消えていれば無効な参照になり、実際には効果がない。
        """
        score = tmp_path / 'score.xml'
        _write_score(score, _TWO_VOICE_MEASURE, part_list_xml=_MULTI_INSTRUMENT_PART_LIST)
        output = tmp_path / 'output.xml'

        report = process_file(score, output)
        assert report.success

        # music21が1つに統合していれば P1-IA/P1-IB は消えている
        assert set(_score_instrument_ids(output)) == {'P1-IA', 'P1-IB'}


class TestIssue78InstrumentRefEndToEnd:
    """Issue #78: 実ファイルでのinstrument参照復元"""

    def _reverse(self, name: str, tmp_path: Path) -> Path:
        input_file = Path(__file__).parent.parent / 'work/inbox' / name
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        output_file = tmp_path / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success
        return output_file

    def test_glockenspiel_section_pitches_are_preserved(self, tmp_path):
        """威風堂々Schellen: 元 m45-53 (Glockensp. ad lib.) は反転後 m1-9 になり、
        各音符が元と同じpitch<->instrument対応を保つ（全てFの音になる回帰を防ぐ）"""
        output_file = self._reverse('威風堂々ラスト-Schellen._(Jingles.).mxl', tmp_path)
        notes = _notes(output_file)

        # 元m50: A4(P1-I94) D4(P1-I87) F4(P1-I91) A4(P1-I94) → 反転後m4は逆順
        assert [(k, i) for _, k, i in notes[4]] == [
            ('A4', 'P1-I94'), ('F4', 'P1-I91'), ('D4', 'P1-I87'), ('A4', 'P1-I94'),
        ]

        # 元m52は2voice（F5とG4がbackupで並列）。反転後m2でvoiceをまたいで
        # instrumentが入れ替わっていないことを確認する。
        by_voice = {(v, k): inst for v, k, inst in notes[2]}
        assert by_voice[('1', 'F5')] == 'P1-I103'
        assert by_voice[('2', 'G4')] == 'P1-I92'

    def test_glockenspiel_score_instrument_definitions_are_preserved(self, tmp_path):
        """Issue #78: 元譜が持つ8つのscore-instrument定義が反転後も維持される

        （music21が1つに統合してしまうと、復元したper-note参照が無効になる）
        """
        output_file = self._reverse('威風堂々ラスト-Schellen._(Jingles.).mxl', tmp_path)

        assert set(_score_instrument_ids(output_file)) == {
            'P1-I55', 'P1-I56', 'P1-I87', 'P1-I91', 'P1-I92', 'P1-I94', 'P1-I99', 'P1-I103',
        }

    def test_all_unpitched_notes_have_instrument_restored(self, tmp_path):
        """反転後、元がinstrument参照を持っていた音符は全てinstrumentを持つ"""
        output_file = self._reverse('威風堂々ラスト-Schellen._(Jingles.).mxl', tmp_path)
        notes = _notes(output_file)

        total_notes = sum(len(entries) for entries in notes.values())
        notes_with_instrument = sum(
            1 for entries in notes.values() for _, k, inst in entries
            if k != 'REST' and inst is not None
        )
        notes_without_instrument = sum(
            1 for entries in notes.values() for _, k, inst in entries
            if k != 'REST' and inst is None
        )

        assert total_notes == 146
        assert notes_without_instrument == 0
        assert notes_with_instrument > 0


# 2小節目の頭で <transpose> が変わる（威風堂々ラスト-Tambourine の m45、グロッケンへの持ち替えと同じ構造）。
# music21 は途中の移調変更で Instrument を複製するため Instrument が2つになり、
# 書き出し時に全音符へ自前の id で <instrument> を付けてしまう。
_MID_PART_TRANSPOSE_MEASURES = (
    '    <measure number="1">'
    '<attributes><divisions>1</divisions><key><fifths>0</fifths></key>'
    '<time><beats>2</beats><beat-type>4</beat-type></time>'
    '<clef><sign>percussion</sign></clef></attributes>'
    '<note><unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IA"/><voice>1</voice><type>quarter</type></note>'
    '<note><unpitched><display-step>E</display-step><display-octave>5</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IA"/><voice>1</voice><type>quarter</type></note>'
    '</measure>\n'
    '    <measure number="2">'
    '<attributes><transpose><diatonic>0</diatonic><chromatic>0</chromatic>'
    '<octave-change>2</octave-change></transpose></attributes>'
    '<note><unpitched><display-step>F</display-step><display-octave>5</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IB"/><voice>1</voice><type>quarter</type></note>'
    '<note><unpitched><display-step>G</display-step><display-octave>4</display-octave></unpitched>'
    '<duration>1</duration><instrument id="P1-IB"/><voice>1</voice><type>quarter</type></note>'
    '</measure>\n'
)


def _dangling_instrument_refs(path: Path) -> set[str]:
    """<score-instrument> に定義されていない <note><instrument id> を返す"""
    notes = _notes(path)
    used = {inst for entries in notes.values() for _, _, inst in entries if inst is not None}
    return used - set(_score_instrument_ids(path))


class TestIssue84InstrumentChangeRefs:
    """Issue #84: 途中で移調が変わるパートで music21 が付けた <instrument> に
    元の参照が上書きされず、未定義の id を参照してしまう"""

    def test_mid_part_instrument_change_restores_original_refs(self, tmp_path):
        score = tmp_path / 'score.xml'
        _write_score(score, _MID_PART_TRANSPOSE_MEASURES,
                     part_list_xml=_MULTI_INSTRUMENT_PART_LIST)
        output = tmp_path / 'output.xml'

        report = process_file(score, output)
        assert report.success

        notes = _notes(output)
        # 小節順が反転: 反転後 m1 = 元 m2（P1-IB）、反転後 m2 = 元 m1（P1-IA）
        assert [(k, i) for _, k, i in notes[1]] == [('G4', 'P1-IB'), ('F5', 'P1-IB')]
        assert [(k, i) for _, k, i in notes[2]] == [('E5', 'P1-IA'), ('C5', 'P1-IA')]
        assert _dangling_instrument_refs(output) == set()

    def test_tambourine_refs_are_restored(self, tmp_path):
        """威風堂々Tambourine: 元の8種の id 分布が反転後も保たれ、未定義の参照が無い"""
        input_file = Path(__file__).parent.parent / 'work/inbox/威風堂々ラスト-Tambourine.mxl'
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        output_file = tmp_path / 'test_output.mxl'
        assert process_file(input_file, output_file).success

        def id_counts(path):
            counts: dict[str, int] = {}
            for entries in _notes(path).values():
                for _, _, inst in entries:
                    if inst is not None:
                        counts[inst] = counts.get(inst, 0) + 1
            return counts

        assert id_counts(output_file) == id_counts(input_file)
        assert _dangling_instrument_refs(output_file) == set()
