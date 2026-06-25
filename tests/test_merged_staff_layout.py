#!/usr/bin/env python3
"""
複数譜パート結合時に失われるレイアウト要素の復元テスト

Issue #63: PartStaff を1つの<part staves="N">に結合する際、music21は
2番目以降のパートの<print>要素を常に捨てる（partStaffExporter.py の
既知の仕様）。これは反転処理の有無に関係なく発生する。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import stream, layout, note
from reverse_score import (
    find_joinable_staff_groups,
    collect_dropped_print_layouts,
    process_file,
    ErrorHandling,
)


def _make_part_staff(part_id: str, measure_numbers=(1,)) -> stream.PartStaff:
    ps = stream.PartStaff()
    ps.id = part_id
    for num in measure_numbers:
        m = stream.Measure(number=num)
        m.append(note.Note('C4', quarterLength=4))
        ps.append(m)
    return ps


class TestFindJoinableStaffGroups:
    """結合対象StaffGroupの抽出テスト"""

    def test_two_partstaffs_are_joinable(self):
        p1 = _make_part_staff('P1-Staff1')
        p2 = _make_part_staff('P1-Staff2')
        score = stream.Score()
        score.insert(0, p1)
        score.insert(0, p2)
        score.insert(0, layout.StaffGroup([p1, p2]))

        groups = find_joinable_staff_groups(score)
        assert len(groups) == 1
        assert list(groups[0]) == [p1, p2]

    def test_single_member_group_not_joinable(self):
        p1 = _make_part_staff('P1-Staff1')
        score = stream.Score()
        score.insert(0, p1)
        score.insert(0, layout.StaffGroup([p1]))

        assert find_joinable_staff_groups(score) == []

    def test_regular_parts_not_joinable(self):
        """PartStaffでない通常のPartは結合対象にならない"""
        p1 = stream.Part(id='P1')
        m1 = stream.Measure(number=1)
        m1.append(note.Note('C4', quarterLength=4))
        p1.append(m1)
        p2 = stream.Part(id='P2')
        m2 = stream.Measure(number=1)
        m2.append(note.Note('C4', quarterLength=4))
        p2.append(m2)
        score = stream.Score()
        score.insert(0, p1)
        score.insert(0, p2)
        score.insert(0, layout.StaffGroup([p1, p2]))

        assert find_joinable_staff_groups(score) == []


class TestCollectDroppedPrintLayouts:
    """結合で失われるレイアウト要素の収集テスト"""

    def test_staff_layout_on_second_member_is_collected(self):
        p1 = _make_part_staff('P1-Staff1')
        p2 = _make_part_staff('P1-Staff2')
        p2.measure(1).insert(0, layout.StaffLayout(distance=78.44, staffNumber=2))
        score = stream.Score()
        score.insert(0, p1)
        score.insert(0, p2)
        score.insert(0, layout.StaffGroup([p1, p2]))

        dropped = collect_dropped_print_layouts(score)
        assert len(dropped) == 1
        assert dropped[0]['anchor_part'] is p1
        assert dropped[0]['measure_num'] == 1
        assert dropped[0]['layout_obj'].distance == 78.44

    def test_layout_on_first_member_is_not_collected(self):
        """先頭パートの宣言はmusic21の通常の書き出しで残るので収集不要"""
        p1 = _make_part_staff('P1-Staff1')
        p1.measure(1).insert(0, layout.StaffLayout(distance=50.0, staffNumber=1))
        p2 = _make_part_staff('P1-Staff2')
        score = stream.Score()
        score.insert(0, p1)
        score.insert(0, p2)
        score.insert(0, layout.StaffGroup([p1, p2]))

        assert collect_dropped_print_layouts(score) == []


def _staff_layouts_in_mxl(mxl_path: Path) -> list[tuple[str, str, str]]:
    """MXLファイル内の (part_id, measure_number, staff_number) のリストを取得"""
    results = []
    with zipfile.ZipFile(mxl_path, 'r') as zf:
        container = ET.fromstring(zf.read('META-INF/container.xml'))
        rootfile = container.find('.//{*}rootfile')
        content = zf.read(rootfile.get('full-path'))
    root = ET.fromstring(content)
    for part in root.findall('.//{*}part'):
        pid = part.get('id')
        for measure in part.findall('{*}measure'):
            for sl in measure.findall('.//{*}staff-layout'):
                results.append((pid, measure.get('number'), sl.get('number')))
    return results


class TestRealDataMergedStaffLayout:
    """実データ(威風堂々ラスト_in-Violin.mxl)での回帰テスト"""

    def test_violin_staff_layout_survives_reversal(self, tmp_path):
        """2段譜のstaff-layout(number=2)が反転後も出力に残ることを確認

        修正前: music21が結合時に2番目の譜のstaff-layoutを常に捨てるため
        出力から完全に消えていた（反転の有無に関係なく発生）。
        """
        input_path = Path(__file__).parent.parent / 'work/inbox/test/威風堂々ラスト_in-Violin.mxl'
        if not input_path.exists():
            pytest.skip(f"Test file not found: {input_path}")

        output_path = tmp_path / 'violin_rev.mxl'
        process_file(input_path, output_path, ErrorHandling.SKIP_MEASURE_CONTENT)

        assert output_path.exists()
        staff_layouts = _staff_layouts_in_mxl(output_path)
        staff_numbers = {sl[2] for sl in staff_layouts}
        assert '2' in staff_numbers, (
            f"staff-layout number=2 が出力から失われている: {staff_layouts}"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
