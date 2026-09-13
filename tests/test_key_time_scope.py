#!/usr/bin/env python3
"""
曲中の調号・拍子記号の有効範囲反転のテスト

Issue #74: 曲中の <key> / <time> は小節と一緒に鏡像位置へ運ばれるだけで、音部記号のような
有効範囲の反転が無かった（元 m6 から曲末まで有効な転調が、反転後 m5 から曲末まで有効になる）。
また元 m1 の小節のコピーが新しい最終小節になるため、最終小節に余分な調号・拍子が出ていた。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reverse_score import process_file


def _write_score(path: Path, total_measures: int,
                 keys: dict[int, int], times: dict[int, int]) -> None:
    """divisions=1 の楽譜を書き出す。各小節は拍子の拍数ぶんの四分音符

    Args:
        keys: {小節番号: fifths}
        times: {小節番号: 拍数}（拍の単位は四分音符）
    """
    beats = 2
    measures = []
    for num in range(1, total_measures + 1):
        attrs = '<divisions>1</divisions>' if num == 1 else ''
        if num in keys:
            attrs += f'<key><fifths>{keys[num]}</fifths></key>'
        if num in times:
            beats = times[num]
            attrs += f'<time><beats>{beats}</beats><beat-type>4</beat-type></time>'
        if num == 1:
            attrs += '<clef><sign>G</sign><line>2</line></clef>'
        attributes = f'<attributes>{attrs}</attributes>' if attrs else ''
        notes = ''.join(
            '<note><pitch><step>D</step><octave>5</octave></pitch>'
            '<duration>1</duration><voice>1</voice><type>quarter</type></note>'
            for _ in range(beats)
        )
        measures.append(f'    <measure number="{num}">{attributes}{notes}</measure>\n')
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        '  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>\n'
        '  <part id="P1">\n' + ''.join(measures) + '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _load_root(path: Path) -> ET.Element:
    if path.suffix == '.mxl':
        with zipfile.ZipFile(path, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            return ET.fromstring(z.read(name))
    return ET.parse(path).getroot()


def _signatures(path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """最初のパートの (小節番号, fifths) と (小節番号, 'beats/beat-type') のリストを返す"""
    part = _load_root(path).find('.//{*}part')
    keys, times = [], []
    for measure in part.findall('{*}measure'):
        num = int(measure.get('number'))
        for key in measure.findall('{*}attributes/{*}key'):
            keys.append((num, key.findtext('{*}fifths')))
        for time in measure.findall('{*}attributes/{*}time'):
            times.append((num, f"{time.findtext('{*}beats')}/{time.findtext('{*}beat-type')}"))
    return keys, times


def _reverse(tmp_path: Path, total_measures: int,
             keys: dict[int, int], times: dict[int, int]):
    score = tmp_path / 'score.xml'
    _write_score(score, total_measures, keys, times)
    output = tmp_path / 'score_rev.xml'
    report = process_file(score, output)
    assert report.success
    return _signatures(output)


class TestIssue74KeyTimeScope:
    """Issue #74: 調号・拍子記号は「次の同種の指示まで有効」な範囲として反転する"""

    TOTAL = 10

    def test_key_change_region_is_reversed(self, tmp_path):
        """fifths=0@m1（区間 m1–5）/ fifths=2@m6（区間 m6–10）→ 反転後 2@m1 / 0@m6"""
        keys, _times = _reverse(tmp_path, self.TOTAL, keys={1: 0, 6: 2}, times={1: 2})

        assert keys == [(1, '2'), (6, '0')]

    def test_time_change_region_is_reversed(self, tmp_path):
        """2/4@m1（区間 m1–3）/ 3/4@m4（区間 m4–10）→ 反転後 3/4@m1 / 2/4@m8

        小節の内容は小節と一緒に運ばれるので、反転後 m8–10 は元の 2/4 の小節になる。
        """
        _keys, times = _reverse(tmp_path, self.TOTAL, keys={1: 0}, times={1: 2, 4: 3})

        assert times == [(1, '3/4'), (8, '2/4')]

    def test_last_measure_has_no_extra_signatures(self, tmp_path):
        """元 m1 のコピーである最終小節に調号・拍子記号を出さない"""
        keys, times = _reverse(tmp_path, self.TOTAL, keys={1: 0}, times={1: 2})

        assert keys == [(1, '0')]
        assert times == [(1, '2/4')]

    def test_restated_key_is_kept_at_region_start(self, tmp_path):
        """同じ調号の再掲も区間の先頭として残す（元譜の情報を削らない）"""
        keys, _times = _reverse(tmp_path, self.TOTAL, keys={1: 2, 6: 2}, times={1: 2})

        assert keys == [(1, '2'), (6, '2')]

    def test_viola_key_restatement_end_to_end(self, tmp_path):
        """威風堂々Viola: 調号 m1 / m45（再掲）の区間 m1–44 / m45–53 は反転後 m10–53 / m1–9

        従来は m1 / m9（m45 の鏡像）/ m53（元 m1 のコピー）に出ていた。
        """
        input_file = Path(__file__).parent.parent / 'work/inbox/威風堂々ラスト-Viola.mxl'
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'viola_rev.mxl'
        report = process_file(input_file, output_file)
        assert report.success

        keys, times = _signatures(output_file)
        assert keys == [(1, '2'), (10, '2')]
        assert times == [(1, '2/4')]
