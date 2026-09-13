#!/usr/bin/env python3
"""
複数小節休符（multiple-rest）の再配置テスト

Issue #70: <multiple-rest>N</multiple-rest> は「この小節から N 小節」という
前方向スパンなので、時間反転するとブロックの開始小節が変わる。小節と一緒に
運ばれるとブロック末尾に付いたままになり、音符のある小節を休符として結合してしまう。
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from layout_preservation import (
    LayoutMap,
    MeasureStyleElement,
    extract_layout_from_xml,
    restore_measure_styles,
)
from reverse_score import process_file


def _write_score(path: Path, total_measures: int,
                 multiple_rests: dict[int, int]) -> None:
    """最小構成のMusicXMLを書き出す（divisions=1, 2/4, 各小節は全休符）

    Args:
        multiple_rests: {小節番号: 小節数}
    """
    measures = []
    for num in range(1, total_measures + 1):
        attributes = ''
        if num == 1:
            attributes = ('<attributes><divisions>1</divisions>'
                          '<key><fifths>0</fifths></key>'
                          '<time><beats>2</beats><beat-type>4</beat-type></time>'
                          '<clef><sign>G</sign><line>2</line></clef></attributes>')
        if num in multiple_rests:
            attributes += (f'<attributes><measure-style>'
                           f'<multiple-rest>{multiple_rests[num]}</multiple-rest>'
                           f'</measure-style></attributes>')
        measures.append(
            f'    <measure number="{num}">{attributes}'
            f'<note><rest/><duration>2</duration><voice>1</voice>'
            f'<type>half</type></note></measure>\n'
        )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        '  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>\n'
        '  <part id="P1">\n' + ''.join(measures) + '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _multiple_rests(path: Path) -> list[tuple[int, int]]:
    """(小節番号, 小節数) のリストを返す"""
    if path.suffix == '.mxl':
        with zipfile.ZipFile(path, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            root = ET.fromstring(z.read(name))
    else:
        root = ET.parse(path).getroot()

    result = []
    for part in root.findall('.//{*}part'):
        for measure in part.findall('{*}measure'):
            for mr in measure.findall('{*}attributes/{*}measure-style/{*}multiple-rest'):
                result.append((int(measure.get('number')), int(mr.text)))
    return sorted(result)


class TestMultipleRestExtraction:
    """multiple-rest の抽出"""

    def test_extracts_measure_num_and_count(self, tmp_path):
        score = tmp_path / 'score.xml'
        _write_score(score, 10, {4: 3})

        layout_map = extract_layout_from_xml(score)

        styles = layout_map.measure_styles['P1']
        assert len(styles) == 1
        assert (styles[0].measure_num, styles[0].count) == (4, 3)


class TestMultipleRestRelocation:
    """multiple-rest の反転後位置"""

    def test_marker_moves_to_block_start(self, tmp_path):
        """ブロック末尾ではなく先頭に置かれる

        全10小節で m4 から 3 小節（m4-m6）のブロックは、反転後 m5-m7 に移る。
        マーカーは m5（= 10 - 4 - 3 + 2）に置く。
        """
        score = tmp_path / 'score.xml'
        _write_score(score, 10, {4: 3})
        layout_map = extract_layout_from_xml(score)

        # 反転後の出力を模して、小節番号だけ鏡像化した状態を作る
        # （music21 は multiple-rest を小節と一緒に運ぶので m7 に付いている）
        _write_score(score, 10, {7: 3})
        restore_measure_styles(score, layout_map, total_measures=10)

        assert _multiple_rests(score) == [(5, 3)]

    def test_single_measure_rest_is_restored(self, tmp_path):
        """music21 が落とす N=1 の multiple-rest も復元される"""
        score = tmp_path / 'score.xml'
        _write_score(score, 10, {3: 1})
        layout_map = extract_layout_from_xml(score)

        # 出力側には multiple-rest が無い状態
        _write_score(score, 10, {})
        restore_measure_styles(score, layout_map, total_measures=10)

        # 10 - 3 - 1 + 2 = 8
        assert _multiple_rests(score) == [(8, 1)]

    def test_attributes_is_created_when_missing(self, tmp_path):
        """挿入先に <attributes> が無ければ小節先頭に作る"""
        score = tmp_path / 'score.xml'
        _write_score(score, 10, {4: 3})
        layout_map = extract_layout_from_xml(score)
        _write_score(score, 10, {})
        restore_measure_styles(score, layout_map, total_measures=10)

        root = ET.parse(score).getroot()
        target = next(m for m in root.findall('.//{*}measure') if m.get('number') == '5')
        tags = [child.tag.split('}')[-1] for child in target]
        assert tags[0] == 'attributes', tags
        assert tags.index('attributes') < tags.index('note'), tags

    def test_no_measure_styles_is_a_noop(self, tmp_path):
        """multiple-rest が無いスコアでは何もしない"""
        score = tmp_path / 'score.xml'
        _write_score(score, 10, {})
        before = score.read_text(encoding='utf-8')

        restore_measure_styles(score, LayoutMap(), total_measures=10)

        assert score.read_text(encoding='utf-8') == before

    def test_out_of_range_target_is_skipped(self, tmp_path):
        """反転先が曲の範囲外になる場合はスキップする（例外を出さない）"""
        score = tmp_path / 'score.xml'
        layout_map = LayoutMap()
        layout_map.measure_styles['P1'] = [
            MeasureStyleElement(measure_num=1, count=20,
                                measure_style_xml='<measure-style>'
                                                  '<multiple-rest>20</multiple-rest>'
                                                  '</measure-style>')
        ]
        _write_score(score, 10, {})

        restore_measure_styles(score, layout_map, total_measures=10)

        assert _multiple_rests(score) == []


class TestIssue70MultipleRestEndToEnd:
    """Issue #70: 実ファイルでの multiple-rest 再配置"""

    def _reverse(self, name: str, tmp_path: Path) -> Path:
        input_file = Path(__file__).parent.parent / 'work/inbox' / name
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")
        output_file = tmp_path / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success
        return output_file

    def _all_rests(self, output_file: Path, start: int, count: int) -> bool:
        """start から count 小節がすべて休符だけか"""
        with zipfile.ZipFile(output_file, 'r') as z:
            name = next(n for n in z.namelist()
                        if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF'))
            root = ET.fromstring(z.read(name))
        for part in root.findall('.//{*}part'):
            for measure in part.findall('{*}measure'):
                num = int(measure.get('number'))
                if not (start <= num < start + count):
                    continue
                for note in measure.findall('{*}note'):
                    if note.find('{*}rest') is None:
                        return False
        return True

    def test_triangle_blocks_are_at_block_start(self, tmp_path):
        """威風堂々Triangle: 元 m34(5小節) → m16、元 m50(2小節) → m3"""
        output_file = self._reverse('威風堂々ラスト-Triangle.mxl', tmp_path)

        assert _multiple_rests(output_file) == [(3, 2), (16, 5)]

    def test_triangle_blocks_cover_only_rests(self, tmp_path):
        """再配置したブロックが休符だけの小節に一致する"""
        output_file = self._reverse('威風堂々ラスト-Triangle.mxl', tmp_path)

        for start, count in _multiple_rests(output_file):
            assert self._all_rests(output_file, start, count), \
                f"m{start}〜m{start + count - 1} に音符が含まれている"

    def test_tambourine_blocks_are_at_block_start(self, tmp_path):
        """威風堂々Tambourine: 元 m37(2小節) → m16、元 m41(4小節) → m10"""
        output_file = self._reverse('威風堂々ラスト-Tambourine.mxl', tmp_path)

        assert _multiple_rests(output_file) == [(10, 4), (16, 2)]

    def test_unmei_single_measure_rest_is_not_lost(self, tmp_path):
        """運命_冒頭: music21 が落とす N=1 の multiple-rest が復元される

        元 m6(2小節) → m18、元 m11(1小節) → m14
        """
        output_file = self._reverse('運命_冒頭-Violins_I.mxl', tmp_path)

        assert _multiple_rests(output_file) == [(14, 1), (18, 2)]


def _write_style_score(path: Path, total_measures: int,
                       styles: dict[int, list[tuple[float, str]]]) -> None:
    """divisions=1, 2/4、各小節に四分音符2つ。styles の measure-style を指定オフセットに置く

    Args:
        styles: {小節番号: [(小節内オフセット, measure-style の子要素 XML)]}
    """
    measures = []
    for num in range(1, total_measures + 1):
        body = ''
        placed = styles.get(num, [])
        for beat in range(2):
            attrs = ''
            if num == 1 and beat == 0:
                attrs += ('<divisions>1</divisions><key><fifths>0</fifths></key>'
                          '<time><beats>2</beats><beat-type>4</beat-type></time>'
                          '<clef><sign>G</sign><line>2</line></clef>')
            attrs += ''.join(f'<measure-style>{xml}</measure-style>'
                             for offset, xml in placed if offset == beat)
            if attrs:
                body += f'<attributes>{attrs}</attributes>'
            body += ('<note><pitch><step>C</step><octave>5</octave></pitch>'
                     '<duration>1</duration><voice>1</voice><type>quarter</type></note>')
        measures.append(f'    <measure number="{num}">{body}</measure>\n')
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="4.0">\n'
        '  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>\n'
        '  <part id="P1">\n' + ''.join(measures) + '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _style_events(path: Path) -> list[tuple[int, float, str, str, str]]:
    """(小節, 小節内オフセット, 要素名, type, テキスト) のリストを出現順に返す"""
    root = ET.parse(path).getroot()
    events = []
    for measure in root.findall('.//{*}measure'):
        offset = 0.0
        for child in measure:
            tag = child.tag.split('}')[-1]
            if tag == 'note' and child.find('{*}chord') is None:
                offset += float(child.findtext('{*}duration'))
            elif tag == 'attributes':
                for style in child.findall('{*}measure-style'):
                    for elem in style:
                        name = elem.tag.split('}')[-1]
                        if name in ('measure-repeat', 'beat-repeat', 'slash'):
                            events.append((int(measure.get('number')), offset, name,
                                           elem.get('type'), (elem.text or '').strip()))
    return events


def _relocate(path: Path, total_measures: int, styles: dict, output_styles=None):
    """元譜から抽出し、出力（既定は measure-style 無し）に置き直した結果を返す"""
    from layout_preservation import restore_measure_styles

    _write_style_score(path, total_measures, styles)
    layout_map = extract_layout_from_xml(path)
    _write_style_score(path, total_measures, output_styles or {})
    restore_measure_styles(path, layout_map, total_measures)
    return _style_events(path)


MEASURE_REPEAT_START = '<measure-repeat type="start" slashes="1">{n}</measure-repeat>'
MEASURE_REPEAT_STOP = '<measure-repeat type="stop"/>'
SLASH_START = '<slash type="start"><slash-type>quarter</slash-type></slash>'
SLASH_STOP = '<slash type="stop"><slash-type>quarter</slash-type></slash>'
BEAT_REPEAT_START = '<beat-repeat type="start"><slash-type>quarter</slash-type></beat-repeat>'
BEAT_REPEAT_STOP = '<beat-repeat type="stop"><slash-type>quarter</slash-type></beat-repeat>'


class TestIssue74MeasureRepeat:
    """Issue #74: measure-repeat は反転後のブロックの先頭 N 小節を実音にして付け直す

    MusicXML では繰り返される実音も各小節に書かれているので、マーカーだけを動かせばよい。
    stop は「繰り返し表示が終わった最初の小節」に置かれる。
    """

    TOTAL = 10

    def test_single_measure_repeat(self, tmp_path):
        """元: m3 が実音、m4–6 が繰り返し（stop@m7）

        ブロック m3–6 は反転後 m5–8。先頭の m5 を実音にして m6–8 を繰り返し、stop@m9。
        """
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            4: [(0, MEASURE_REPEAT_START.format(n=1))],
            7: [(0, MEASURE_REPEAT_STOP)],
        })

        assert events == [(6, 0.0, 'measure-repeat', 'start', '1'),
                          (9, 0.0, 'measure-repeat', 'stop', '')]

    def test_two_measure_pattern(self, tmp_path):
        """元: m2–3 が実音、m4–7 が2小節単位の繰り返し（stop@m8）

        ブロック m2–7 は反転後 m4–9。m4–5 を実音にして m6–9 を繰り返し、stop@m10。
        """
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            4: [(0, MEASURE_REPEAT_START.format(n=2))],
            8: [(0, MEASURE_REPEAT_STOP)],
        })

        assert events == [(6, 0.0, 'measure-repeat', 'start', '2'),
                          (10, 0.0, 'measure-repeat', 'stop', '')]

    def test_repeat_through_end_of_part(self, tmp_path):
        """stop が無い（曲末まで繰り返し）: m7 実音 + m8–10 → 反転後 m1 実音 + m2–4、stop@m5"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            8: [(0, MEASURE_REPEAT_START.format(n=1))],
        })

        assert events == [(2, 0.0, 'measure-repeat', 'start', '1'),
                          (5, 0.0, 'measure-repeat', 'stop', '')]

    def test_stop_is_omitted_when_repeat_reaches_end(self, tmp_path):
        """m1 実音 + m2–3（stop@m4）→ 反転後 m8 実音 + m9–10 は曲末まで続くので stop を出さない"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            2: [(0, MEASURE_REPEAT_START.format(n=1))],
            4: [(0, MEASURE_REPEAT_STOP)],
        })

        assert events == [(9, 0.0, 'measure-repeat', 'start', '1')]

    def test_markers_carried_by_music21_are_replaced(self, tmp_path):
        """出力に小節と一緒に運ばれたマーカーが残っていても、取り除いてから置き直す"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            4: [(0, MEASURE_REPEAT_START.format(n=1))],
            7: [(0, MEASURE_REPEAT_STOP)],
        }, output_styles={
            7: [(0, MEASURE_REPEAT_START.format(n=1))],
            4: [(0, MEASURE_REPEAT_STOP)],
        })

        assert events == [(6, 0.0, 'measure-repeat', 'start', '1'),
                          (9, 0.0, 'measure-repeat', 'stop', '')]


class TestIssue74SlashAndBeatRepeat:
    """Issue #74: slash は表示区間、beat-repeat は拍単位の繰り返しとして付け直す"""

    TOTAL = 10

    def test_slash_region_is_reversed(self, tmp_path):
        """slash 区間 m3–5（stop@m6頭）→ 反転後 m6–8（stop@m9頭）"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            3: [(0, SLASH_START)],
            6: [(0, SLASH_STOP)],
        })

        assert events == [(6, 0.0, 'slash', 'start', ''), (9, 0.0, 'slash', 'stop', '')]

    def test_slash_mid_measure_boundaries(self, tmp_path):
        """小節の途中の境界は時間点として鏡像にする: m3 2拍目–m5 2拍目 → m6 2拍目–m8 2拍目"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            3: [(1, SLASH_START)],
            5: [(1, SLASH_STOP)],
        })

        assert events == [(6, 1.0, 'slash', 'start', ''), (8, 1.0, 'slash', 'stop', '')]

    def test_slash_through_end_of_part(self, tmp_path):
        """stop が無い slash 区間 m8–10 → 反転後 m1–3（stop@m4頭）"""
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            8: [(0, SLASH_START)],
        })

        assert events == [(1, 0.0, 'slash', 'start', ''), (4, 0.0, 'slash', 'stop', '')]

    def test_beat_repeat_keeps_source_beat_before_repeats(self, tmp_path):
        """元: m3 1拍目が実音、m3 2拍目–m4 1拍目が繰り返し（stop@m4 2拍目）

        ブロック m3 1拍目–m4 1拍目 は反転後 m7 2拍目–m8 2拍目。先頭の1拍（m7 2拍目）を
        実音にして、繰り返しは m8 頭から、stop は m9 頭。
        """
        events = _relocate(tmp_path / 'score.xml', self.TOTAL, {
            3: [(1, BEAT_REPEAT_START)],
            4: [(1, BEAT_REPEAT_STOP)],
        })

        assert events == [(8, 0.0, 'beat-repeat', 'start', ''),
                          (9, 0.0, 'beat-repeat', 'stop', '')]
