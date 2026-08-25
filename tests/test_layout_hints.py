#!/usr/bin/env python3
"""
反転で無効になる水平位置情報の除去テスト

Issue #76: 音符の default-x は小節先頭からの絶対位置、<measure width> は段の幅に
合わせて justify された結果なので、時間反転すると整合しなくなる。横方向のレイアウトは
楽譜ソフトに任せる。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from layout_preservation import strip_horizontal_layout_hints
from reverse_score import process_file


SCORE_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1" width="187.33">
      <print new-system="yes"><system-layout><system-distance>124.42</system-distance></system-layout></print>
      <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
        <time><beats>2</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef></attributes>
      <direction placement="above">
        <direction-type><words default-x="12.5" default-y="20" relative-x="3">dolce</words></direction-type>
      </direction>
      <direction placement="below">
        <direction-type><dynamics default-x="8.5" default-y="-40"><p/></dynamics></direction-type>
      </direction>
      <note default-x="88.13" default-y="-15" relative-x="2">
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
        <notations><articulations><tenuto default-x="0.18" default-y="-54.3"/></articulations></notations>
      </note>
      <note default-x="132.33" default-y="-20">
        <pitch><step>D</step><octave>5</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
'''


def _write_score(path: Path) -> None:
    path.write_text(SCORE_TEMPLATE, encoding='utf-8')


def _attrs(root: ET.Element, tag: str, attr: str) -> list[str]:
    return [el.get(attr) for el in root.findall(f'.//{{*}}{tag}') if el.get(attr) is not None]


class TestStripHorizontalLayoutHints:
    """水平位置情報の除去"""

    def test_note_default_x_is_removed(self, tmp_path):
        """音符の default-x / relative-x は反転で無効になるので取り除く"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert _attrs(root, 'note', 'default-x') == []
        assert _attrs(root, 'note', 'relative-x') == []

    def test_measure_width_is_removed(self, tmp_path):
        """<measure width> は元の行組みの justify 結果なので取り除く"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert _attrs(root, 'measure', 'width') == []

    def test_direction_default_x_is_removed(self, tmp_path):
        """direction 配下（words, dynamics 等）も小節先頭基準なので取り除く"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert _attrs(root, 'words', 'default-x') == []
        assert _attrs(root, 'words', 'relative-x') == []
        assert _attrs(root, 'dynamics', 'default-x') == []

    def test_vertical_positions_are_kept(self, tmp_path):
        """縦方向（default-y）は反転で無効にならないので残す"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert _attrs(root, 'note', 'default-y') == ['-15', '-20']
        assert _attrs(root, 'words', 'default-y') == ['20']
        assert _attrs(root, 'dynamics', 'default-y') == ['-40']

    def test_notation_default_x_is_kept(self, tmp_path):
        """<notations> 配下は音符基準の微調整なので残す"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert _attrs(root, 'tenuto', 'default-x') == ['0.18']
        assert _attrs(root, 'tenuto', 'default-y') == ['-54.3']

    def test_print_layout_is_kept(self, tmp_path):
        """<print> の縦方向の間隔情報は残す（このパスでは触らない）"""
        score = tmp_path / 'score.xml'
        _write_score(score)

        strip_horizontal_layout_hints(score)

        root = ET.parse(score).getroot()
        assert root.find('.//{*}print/{*}system-layout/{*}system-distance').text == '124.42'


class TestIssue76LayoutEndToEnd:
    """Issue #76: 反転出力に横方向のレイアウト情報が残らない"""

    @pytest.fixture(scope='class')
    def reversed_root(self, tmp_path_factory):
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/威風堂々ラスト-Violin.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path_factory.mktemp('layout') / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success

        with zipfile.ZipFile(output_file, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            return ET.fromstring(z.read(name))

    def test_no_note_default_x(self, reversed_root):
        """音符の水平位置が残っていない（残ると右から左に並ぶ）"""
        assert _attrs(reversed_root, 'note', 'default-x') == []

    def test_no_measure_width(self, reversed_root):
        assert _attrs(reversed_root, 'measure', 'width') == []

    def test_no_forced_line_breaks(self, reversed_root):
        """改行・改ページを強制しない（楽譜ソフトの自動改行に任せる）"""
        breaks = [dict(pr.attrib) for pr in reversed_root.findall('.//{*}print')
                  if pr.get('new-system') == 'yes' or pr.get('new-page') == 'yes']
        assert breaks == [], breaks

    def test_vertical_positions_survive(self, reversed_root):
        """縦方向の情報は残っている"""
        assert len(_attrs(reversed_root, 'note', 'default-y')) > 0
        assert len(_attrs(reversed_root, 'accent', 'default-x')) > 0, \
            "<notations> 配下の音符基準の位置は残すべき"
