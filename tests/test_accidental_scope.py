#!/usr/bin/env python3
"""
臨時記号の有効範囲のテスト

Issue #68: 時間反転で小節内の音符順が変わると、<accidental>（表示する記号）の
必要・不要が変わる。recalculate_accidentals() が調号と小節内の有効範囲から
必要な記号だけを残すことを検証する。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from layout_preservation import recalculate_accidentals
from reverse_score import process_file


def _write_score(path: Path, measures_xml: str, fifths: int = 2) -> None:
    """最小構成のMusicXMLを書き出す（divisions=1, 2/4）"""
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        '  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>\n'
        '  <part id="P1">\n'
        f'    <measure number="1">\n'
        '      <attributes><divisions>1</divisions>'
        f'<key><fifths>{fifths}</fifths></key>'
        '<time><beats>2</beats><beat-type>4</beat-type></time>'
        '<clef><sign>G</sign><line>2</line></clef></attributes>\n'
        f'{measures_xml}'
        '    </measure>\n'
        '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _note(step: str, octave: int, alter=None, accidental: str = None,
          tie: str = None, duration: int = 1) -> str:
    """テスト用の<note>XMLを組み立てる"""
    alter_xml = f'<alter>{alter}</alter>' if alter is not None else ''
    tie_xml = f'<tie type="{tie}"/>' if tie else ''
    acc_xml = f'<accidental>{accidental}</accidental>' if accidental else ''
    return (f'      <note><pitch><step>{step}</step>{alter_xml}'
            f'<octave>{octave}</octave></pitch>'
            f'<duration>{duration}</duration>{tie_xml}<voice>1</voice>'
            f'<type>quarter</type>{acc_xml}<stem>up</stem></note>\n')


def _accidentals(path: Path) -> list[tuple[str, str]]:
    """(音名, accidentalテキスト or '') のリストを返す"""
    root = ET.parse(path).getroot()
    result = []
    for note in root.findall('.//{*}note'):
        pitch = note.find('{*}pitch')
        if pitch is None:
            continue
        alter = pitch.findtext('{*}alter') or '0'
        name = f"{pitch.findtext('{*}step')}{alter}{pitch.findtext('{*}octave')}"
        acc = note.find('{*}accidental')
        result.append((name, acc.text if acc is not None else ''))
    return result


class TestIssue68AccidentalScope:
    """Issue #68: 臨時記号を有効範囲から再計算する"""

    def test_redundant_accidental_is_removed(self, tmp_path):
        """調号で既に変化している音の臨時記号は削除される

        D major (fifths=2) では C は♯なので、C♯には臨時記号は不要。
        """
        score = tmp_path / 'score.xml'
        _write_score(score, _note('C', 5, alter=1) + _note('C', 5, alter=1, accidental='sharp'))

        recalculate_accidentals(score)

        assert _accidentals(score) == [('C15', ''), ('C15', '')]

    def test_missing_accidental_is_added(self, tmp_path):
        """小節内の臨時記号を打ち消す記号が追加される

        D major で C♮ → C♯ の順に並ぶと、C♮には♮が必要（調号を打ち消す）で、
        後続の C♯には♯が必要（小節内の♮を打ち消す）。
        """
        score = tmp_path / 'score.xml'
        _write_score(score, _note('C', 5, accidental='natural') + _note('C', 5, alter=1))

        recalculate_accidentals(score)

        assert _accidentals(score) == [('C05', 'natural'), ('C15', 'sharp')]

    def test_accidental_applies_only_to_same_octave(self, tmp_path):
        """臨時記号の有効範囲は同じオクターブに限られる"""
        score = tmp_path / 'score.xml'
        _write_score(score, _note('C', 5, accidental='natural') + _note('C', 6))

        recalculate_accidentals(score)

        # 別オクターブの C♮ は独立して♮が必要
        assert _accidentals(score) == [('C05', 'natural'), ('C06', 'natural')]

    def test_tied_note_does_not_repeat_accidental(self, tmp_path):
        """タイで繋がれた音は臨時記号を繰り返さないが有効範囲は更新する"""
        score = tmp_path / 'score.xml'
        _write_score(
            score,
            _note('C', 5, tie='stop') + _note('C', 5),
            fifths=2,
        )

        recalculate_accidentals(score)

        # タイの到着音は♮を出さない。後続の C も同じ状態なので記号不要
        assert _accidentals(score) == [('C05', ''), ('C05', '')]

    def test_accidental_is_inserted_in_valid_child_order(self, tmp_path):
        """<accidental>は<type>の後、<stem>の前に挿入される"""
        score = tmp_path / 'score.xml'
        _write_score(score, _note('C', 5))

        recalculate_accidentals(score)

        root = ET.parse(score).getroot()
        note = root.find('.//{*}note')
        tags = [child.tag.split('}')[-1] for child in note]
        assert tags.index('accidental') > tags.index('type')
        assert tags.index('accidental') < tags.index('stem')


class TestIssue68AccidentalScopeEndToEnd:
    """Issue #68: 反転出力の臨時記号（issue で指摘された3小節）"""

    @pytest.fixture(scope='class')
    def reversed_output(self, tmp_path_factory):
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/test/威風堂々ラスト_in-Violin.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path_factory.mktemp('accidental') / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success

        with zipfile.ZipFile(output_file, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            return ET.fromstring(z.read(name))

    def _measure_notes(self, root, measure_num: str, staff: str):
        """(音名, accidentalテキスト or '') を文書順で返す"""
        result = []
        for part in root.findall('.//{*}part'):
            for measure in part.findall('.//{*}measure'):
                if measure.get('number') != measure_num:
                    continue
                for note in measure.findall('{*}note'):
                    pitch = note.find('{*}pitch')
                    if pitch is None:
                        continue
                    note_staff = note.findtext('{*}staff') or '1'
                    if note_staff != staff:
                        continue
                    alter = pitch.findtext('{*}alter') or '0'
                    name = f"{pitch.findtext('{*}step')}{alter}{pitch.findtext('{*}octave')}"
                    acc = note.find('{*}accidental')
                    result.append((name, acc.text if acc is not None else ''))
        return result

    def test_m20_redundant_sharp_removed(self, reversed_output):
        """m20: 調号(C♯)と一致する C♯ の♯は不要"""
        notes = self._measure_notes(reversed_output, '20', '2')
        sharps = [(name, acc) for name, acc in notes if name.startswith('C1') and acc]
        assert sharps == [], f"m20 の C♯ に臨時記号は不要: {notes}"

    def test_m22_sharp_added_after_natural(self, reversed_output):
        """m22: C♮ の後の C♯ には♯が必要（♮は調号を打ち消すため必須で残る）"""
        notes = self._measure_notes(reversed_output, '22', '2')
        assert ('C05', 'natural') in notes, f"m22 1拍目の C♮ には♮が必要: {notes}"
        assert ('C15', 'sharp') in notes, f"m22 2拍目の C♯ には♯が必要: {notes}"

    def test_m25_redundant_natural_removed(self, reversed_output):
        """m25: 調号に G♯ は無いので最後の音の♮は不要"""
        for staff in ('1', '2'):
            notes = self._measure_notes(reversed_output, '25', staff)
            naturals = [(name, acc) for name, acc in notes if acc == 'natural']
            assert naturals == [], f"m25 staff{staff} の♮は不要: {notes}"
