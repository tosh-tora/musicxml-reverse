#!/usr/bin/env python3
"""
バーライン（bar-style）の反転位置テスト

Issue #72: 終止線（light-heavy）が小節と一緒に運ばれて新m1に出現する。
複縦線（light-light）は小節境界に紐づくため、反転後は「境界のミラー」の
位置（total_measures - N）に来るべきだが、現状は1小節ずれる。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import stream, note, bar

from reverse_score import (
    reverse_part,
    collect_barline_positions,
    calculate_reversed_barline_positions,
    process_file,
)


def _build_part(total_measures: int, barlines: dict[int, str]) -> stream.Part:
    """各小節が全音符1個の単純なパートを組み立てる

    Args:
        barlines: {小節番号: music21のbarline type ('double'/'final'など)}
    """
    part = stream.Part()
    for num in range(1, total_measures + 1):
        m = stream.Measure(number=num)
        m.append(note.Note('C4', quarterLength=4))
        if num in barlines:
            m.rightBarline = bar.Barline(type=barlines[num])
        part.append(m)
    return part


class TestBarlinePositionCalculation:
    """calculate_reversed_barline_positions() の位置計算"""

    def test_final_barline_goes_to_new_last_measure(self):
        """終止線は常に反転後の実際の最終小節に付け直される"""
        part = _build_part(5, {5: 'final'})
        measures = list(part.getElementsByClass(stream.Measure))

        positions = collect_barline_positions(measures)
        reversed_positions = calculate_reversed_barline_positions(positions, total_measures=5)

        assert [(p['reversed_measure_num'], p['barline'].type) for p in reversed_positions] == [
            (5, 'final'),
        ]

    def test_mid_piece_double_bar_shifts_by_boundary(self):
        """複縦線は境界のミラーリング（total - N）で位置が計算される"""
        part = _build_part(53, {40: 'double', 53: 'final'})
        measures = list(part.getElementsByClass(stream.Measure))

        positions = collect_barline_positions(measures)
        reversed_positions = calculate_reversed_barline_positions(positions, total_measures=53)

        result = {p['reversed_measure_num']: p['barline'].type for p in reversed_positions}
        assert result == {13: 'double', 53: 'final'}


class TestReversePartBarlines:
    """reverse_part() を通した反映結果"""

    def test_barlines_land_on_correct_measures(self):
        part = _build_part(5, {3: 'double', 5: 'final'})

        new_part = reverse_part(part)

        by_number = {m.number: m for m in new_part.getElementsByClass(stream.Measure)}
        assert by_number[2].rightBarline.type == 'double'
        assert by_number[5].rightBarline.type == 'final'
        for num in (1, 3, 4):
            assert by_number[num].rightBarline is None


class TestIssue72BarlineEndToEnd:
    """Issue #72: 実ファイルでのバーライン再配置"""

    def _reverse(self, name: str, tmp_path: Path) -> Path:
        input_file = Path(__file__).parent.parent / 'work/inbox' / name
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        output_file = tmp_path / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success
        return output_file

    def _bar_styles(self, output_file: Path) -> dict[int, str]:
        with zipfile.ZipFile(output_file, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            root = ET.fromstring(z.read(name))
        result = {}
        for part in root.findall('.//{*}part'):
            for measure in part.findall('{*}measure'):
                bar_style = measure.find('{*}barline/{*}bar-style')
                if bar_style is not None:
                    result[int(measure.get('number'))] = bar_style.text
            break  # 1パート分で十分
        return result

    def test_violin_final_and_double_bar_are_relocated(self, tmp_path):
        """威風堂々ラスト-Violin: 入力 m40=light-light/m53=light-heavy(全53小節)
        反転後は m13=light-light、実際の最終小節(m53)=light-heavy になるべき"""
        output_file = self._reverse('威風堂々ラスト-Violin.mxl', tmp_path)

        assert self._bar_styles(output_file) == {13: 'light-light', 53: 'light-heavy'}
