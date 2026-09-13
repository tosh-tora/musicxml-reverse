#!/usr/bin/env python3
"""
direction要素の保存と復元のテスト

Issue #27: Tempo primo. や rit. などの指示が増殖する問題のリグレッションテスト
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import converter, stream, expressions, tempo
from layout_preservation import (
    extract_layout_from_xml,
    restore_direction_elements,
    DirectionElement,
    InstrumentRef,
    LayoutMap,
    _is_transitional_tempo_text,
    _build_state_marking_direction,
    _calculate_reversed_instrument_change_labels,
    _calculate_reversed_state_markers,
    _separate_instrument_change_labels,
    _get_state_marking,
    _is_tempo_direction,
    _separate_state_marking_directions,
)
from reverse_score import process_file, reverse_score


def count_directions_in_mxl(mxl_path: Path) -> int:
    """MXLファイル内のdirection要素数をカウント"""
    with zipfile.ZipFile(mxl_path, 'r') as z:
        for name in z.namelist():
            if (name.endswith('.xml') or name.endswith('.musicxml')) and not name.startswith('META-INF'):
                content = z.read(name)
                root = ET.fromstring(content)
                return len(root.findall('.//direction'))
    return 0


def get_words_texts_from_mxl(mxl_path: Path) -> list[tuple[str, str]]:
    """MXLファイルから(小節番号, wordsテキスト)のリストを取得"""
    result = []
    with zipfile.ZipFile(mxl_path, 'r') as z:
        for name in z.namelist():
            if (name.endswith('.xml') or name.endswith('.musicxml')) and not name.startswith('META-INF'):
                content = z.read(name)
                root = ET.fromstring(content)
                for part in root.findall('.//{*}part'):
                    for measure in part.findall('.//{*}measure'):
                        measure_num = measure.get('number', '?')
                        for d in measure.findall('{*}direction'):
                            words = d.find('.//{*}direction-type/{*}words')
                            if words is not None and words.text:
                                text = words.text.strip()
                                if text:
                                    result.append((measure_num, text))
                break
    return result


class TestTransitionalTempoDetection:
    """経過的テンポ検出のテスト"""

    def test_rit_is_transitional(self):
        assert _is_transitional_tempo_text('rit.') is True
        assert _is_transitional_tempo_text('ritardando') is True
        assert _is_transitional_tempo_text('Rit.') is True

    def test_accel_is_transitional(self):
        assert _is_transitional_tempo_text('accel.') is True
        assert _is_transitional_tempo_text('accelerando') is True

    def test_allargando_is_transitional(self):
        assert _is_transitional_tempo_text('allargando') is True
        assert _is_transitional_tempo_text('(allargando)') is True

    def test_main_tempo_is_not_transitional(self):
        assert _is_transitional_tempo_text('Tempo primo.') is False
        assert _is_transitional_tempo_text('Allegro') is False
        assert _is_transitional_tempo_text('Molto Maestoso.') is False

    def test_empty_text_is_not_transitional(self):
        assert _is_transitional_tempo_text('') is False
        assert _is_transitional_tempo_text(None) is False


class TestDirectionExtraction:
    """direction要素抽出のテスト"""

    def test_extract_directions_from_viola_file(self):
        """威風堂々Violaファイルからdirection要素を抽出できる"""
        test_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        layout_map = extract_layout_from_xml(test_file)

        # direction要素が抽出されていることを確認
        total_directions = sum(len(dirs) for dirs in layout_map.directions.values())
        assert total_directions == 24, f"Expected 24 directions, got {total_directions}"

    def test_direction_element_attributes(self):
        """DirectionElementの属性が正しく設定される"""
        test_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        layout_map = extract_layout_from_xml(test_file)

        # 最初のパートのdirection要素を確認
        part_id = list(layout_map.directions.keys())[0]
        directions = layout_map.directions[part_id]

        # 小節1にはwordsとsoundを持つdirection要素がある
        measure_1_dirs = [d for d in directions if d.measure_num == 1]
        assert len(measure_1_dirs) >= 3, "Measure 1 should have at least 3 direction elements"

        # words+soundの組み合わせがあることを確認
        has_words_and_sound = any(d.has_words and d.has_sound for d in measure_1_dirs)
        assert has_words_and_sound, "Measure 1 should have direction with both words and sound"


class TestDirectionRestoration:
    """direction要素復元のテスト"""

    def test_roundtrip_preserves_direction_count(self, tmp_path):
        """反転処理後もdirection要素数が保持される"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'

        # Phase 1: レイアウト抽出
        layout_map = extract_layout_from_xml(input_file)

        # Phase 2: 反転処理
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))

        # Phase 3: direction要素復元
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        # 検証
        input_count = count_directions_in_mxl(input_file)
        output_count = count_directions_in_mxl(output_file)

        # Issue #56: 非臨時ダイナミクスに括弧付きマーカーが追加されるため
        # 出力のdirection数は入力以上になることがある
        assert output_count >= input_count, f"Direction count should not decrease: input={input_count}, output={output_count}"

    def test_transitional_tempo_gets_arrow(self, tmp_path):
        """経過的テンポには←記号が付与される"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'

        # Phase 1: レイアウト抽出
        layout_map = extract_layout_from_xml(input_file)

        # Phase 2: 反転処理
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))

        # Phase 3: direction要素復元
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        # 検証
        words_list = get_words_texts_from_mxl(output_file)

        # rit. には←が付与されている
        rit_texts = [text for measure, text in words_list if 'rit' in text.lower()]
        assert all(text.startswith('←') for text in rit_texts), "rit. should have ← prefix"

        # allargando には←が付与されている
        allarg_texts = [text for measure, text in words_list if 'allargando' in text.lower()]
        assert all(text.startswith('←') for text in allarg_texts), "(allargando) should have ← prefix"

        # Tempo primo. には←が付与されていない
        tempo_primo_texts = [text for measure, text in words_list if 'Tempo primo' in text]
        assert all(not text.startswith('←') for text in tempo_primo_texts), "Tempo primo should NOT have ← prefix"


class TestIssue27Regression:
    """Issue #27のリグレッションテスト"""

    def test_no_direction_multiplication(self, tmp_path):
        """direction要素が増殖しない"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'

        # Phase 1: レイアウト抽出
        layout_map = extract_layout_from_xml(input_file)

        # Phase 2: 反転処理
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))

        # Phase 3: direction要素復元
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        # 検証
        input_count = count_directions_in_mxl(input_file)
        output_count = count_directions_in_mxl(output_file)

        # Issue #56: 括弧付きダイナミクスマーカーによる意図的な増加を許容
        # 大幅な増殖（2倍以上）は起きていないことを確認
        assert output_count <= input_count * 2, f"Direction elements multiplied excessively: {input_count} -> {output_count}"
        # 減少は起きていないこと
        assert output_count >= input_count, f"Direction elements lost: {input_count} -> {output_count}"


def get_rehearsal_marks_from_mxl(mxl_path: Path) -> list[tuple[str, str]]:
    """MXLファイルから(小節番号, 練習番号テキスト)のリストを取得"""
    result = []
    with zipfile.ZipFile(mxl_path, 'r') as z:
        for name in z.namelist():
            if (name.endswith('.xml') or name.endswith('.musicxml')) and not name.startswith('META-INF'):
                content = z.read(name)
                root = ET.fromstring(content)
                for part in root.findall('.//{*}part'):
                    for measure in part.findall('.//{*}measure'):
                        measure_num = measure.get('number', '?')
                        for d in measure.findall('{*}direction'):
                            r = d.find('.//{*}direction-type/{*}rehearsal')
                            if r is not None and r.text:
                                result.append((measure_num, r.text.strip()))
                break
    return result


class TestIssue47RehearsalMarkPosition:
    """Issue #47: 練習番号の反転位置が小節境界に正しく対応する"""

    def test_rehearsal_marks_shifted_by_one_measure(self, tmp_path):
        """練習番号は反転後 total - N + 2 に配置される（境界貼付）"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'

        layout_map = extract_layout_from_xml(input_file)
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        marks = get_rehearsal_marks_from_mxl(output_file)
        # 元: S at m17, T at m41, total=53 → 反転後: S at m38, T at m14
        mark_measures = {text: measure for measure, text in marks}
        assert mark_measures.get('T') == '14', \
            f"T should be at measure 14 (between m13 and m14), got {mark_measures.get('T')}"
        assert mark_measures.get('S') == '38', \
            f"S should be at measure 38, got {mark_measures.get('S')}"

        # 旧バグ位置 (m13, m37) には練習番号が無いこと
        old_bug_measures = {measure for measure, _ in marks}
        assert '13' not in old_bug_measures or all(
            text not in ('S', 'T') for measure, text in marks if measure == '13'
        ), "Rehearsal mark wrongly at measure 13 (off-by-one regression)"


def get_dynamics_positions_from_mxl(mxl_path: Path) -> list[tuple[str, float, str]]:
    """MXLファイルから(小節番号, 小節内オフセット_quarters, ダイナミクス種別)を取得"""
    result = []
    with zipfile.ZipFile(mxl_path, 'r') as z:
        for name in z.namelist():
            if (name.endswith('.xml') or name.endswith('.musicxml')) and not name.startswith('META-INF'):
                content = z.read(name)
                root = ET.fromstring(content)
                for part in root.findall('.//{*}part'):
                    divs = 1.0
                    for measure in part.findall('.//{*}measure'):
                        measure_num = measure.get('number', '?')
                        current_offset = 0.0
                        for elem in measure:
                            tag = elem.tag.split('}')[-1]
                            if tag == 'attributes':
                                d = elem.find('.//{*}divisions')
                                if d is not None and d.text:
                                    divs = float(d.text)
                            elif tag == 'direction':
                                dyn = elem.find('.//{*}dynamics')
                                if dyn is not None:
                                    for ch in dyn:
                                        dyn_tag = ch.tag.split('}')[-1]
                                        if dyn_tag == 'other-dynamics' and ch.text:
                                            dyn_type = ch.text.strip()
                                        else:
                                            dyn_type = dyn_tag
                                        result.append((measure_num, current_offset / divs, dyn_type))
                            elif tag == 'note':
                                chord = elem.find('.//{*}chord')
                                dur_e = elem.find('.//{*}duration')
                                if chord is None and dur_e is not None and dur_e.text:
                                    current_offset += float(dur_e.text)
                break
    return result


class TestIssue56DynamicsRangeReversal:
    """Issue #56: 強弱記号の有効範囲ベース反転"""

    def _run_reversal(self, input_file, output_file):
        """反転処理を実行してダイナミクス位置を返すヘルパー"""
        layout_map = extract_layout_from_xml(input_file)
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)
        return get_dynamics_positions_from_mxl(output_file), total_measures

    def test_viola_ff_at_beginning_after_reversal(self, tmp_path):
        """威風堂々Viola: ffは反転後もm1に来る（有効範囲が全曲のため）"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        positions, total_measures = self._run_reversal(input_file, output_file)

        # ff は m1 に来るべき（有効範囲 m1-m53 → reversed_start = 1）
        ff_positions = [(m, offset, dyn) for m, offset, dyn in positions if dyn == 'ff']
        assert any(m == '1' for m, _, _ in ff_positions), \
            f"ff should appear at measure 1 after reversal, got: {ff_positions}"

    def test_viola_parenthesized_ff_at_last_measure(self, tmp_path):
        """威風堂々Viola: (ff)が最終小節に残る"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        positions, total_measures = self._run_reversal(input_file, output_file)

        # (ff) が最終小節に残るべき
        last_measure_str = str(total_measures)
        paren_ff_positions = [
            (m, offset, dyn) for m, offset, dyn in positions
            if dyn == '(ff)' and m == last_measure_str
        ]
        assert len(paren_ff_positions) >= 1, \
            f"(ff) should appear in measure {last_measure_str}, positions: {positions}"

    def test_viola_accidental_dynamics_simple_reversal(self, tmp_path):
        """威風堂々Viola: 臨時ダイナミクス(rf, sf)は単純反転のまま"""
        input_file = Path('work/inbox/威風堂々ラスト_in-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        positions, total_measures = self._run_reversal(input_file, output_file)

        # rf (m17) → 単純反転: 53 - 17 + 1 = 37
        rf_positions = [(m, offset, dyn) for m, offset, dyn in positions if dyn == 'rf']
        assert any(m == '37' for m, _, _ in rf_positions), \
            f"rf should be at measure 37 (simple reversal), got: {rf_positions}"

        # sf (m52) → 単純反転: 53 - 52 + 1 = 2
        sf_positions = [(m, offset, dyn) for m, offset, dyn in positions if dyn == 'sf']
        assert any(m == '2' for m, _, _ in sf_positions), \
            f"sf should be at measure 2 (simple reversal), got: {sf_positions}"

    def test_unmei_dynamics_effective_range(self, tmp_path):
        """運命Violins_I: 複数ダイナミクスの有効範囲ベース反転"""
        input_file = Path('work/inbox/運命_冒頭-Violins_I.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        positions, total_measures = self._run_reversal(input_file, output_file)

        # m1:ff → 有効範囲 m1-m7 → reversed m18, (ff) at m24
        ff_at_18 = any(m == '18' and dyn == 'ff' for m, _, dyn in positions)
        assert ff_at_18, f"ff should be at measure 18, positions: {positions}"

        paren_ff_at_24 = any(m == '24' and dyn == '(ff)' for m, _, dyn in positions)
        assert paren_ff_at_24, f"(ff) should be at measure 24, positions: {positions}"

        # m8:p → 有効範囲 m8-m17 (m18にcresc.があるため手前で切る) → reversed m8, (p) at m17
        p_at_8 = any(m == '8' and dyn == 'p' for m, _, dyn in positions)
        assert p_at_8, f"p should be at measure 8, positions: {positions}"

        paren_p_at_17 = any(m == '17' and dyn == '(p)' for m, _, dyn in positions)
        assert paren_p_at_17, f"(p) should be at measure 17, positions: {positions}"


def get_words_positions_from_mxl(mxl_path: Path) -> list[tuple[str, float, str, str]]:
    """MXLファイルから(小節番号, 小節内オフセット_quarters, staff, wordsテキスト)を取得"""
    result = []
    with zipfile.ZipFile(mxl_path, 'r') as z:
        for name in z.namelist():
            if (name.endswith('.xml') or name.endswith('.musicxml')) and not name.startswith('META-INF'):
                root = ET.fromstring(z.read(name))
                for part in root.findall('.//{*}part'):
                    divs = 1.0
                    for measure in part.findall('.//{*}measure'):
                        measure_num = measure.get('number', '?')
                        current_offset = 0.0
                        for elem in measure:
                            tag = elem.tag.split('}')[-1]
                            if tag == 'attributes':
                                d = elem.find('.//{*}divisions')
                                if d is not None and d.text:
                                    divs = float(d.text)
                            elif tag == 'direction':
                                words = elem.find('.//{*}direction-type/{*}words')
                                if words is not None and words.text and words.text.strip():
                                    staff_elem = elem.find('{*}staff')
                                    staff = (staff_elem.text if staff_elem is not None
                                             and staff_elem.text else '1')
                                    result.append((measure_num, current_offset / divs,
                                                   staff, words.text.strip()))
                            elif tag == 'note':
                                dur_e = elem.find('.//{*}duration')
                                if (elem.find('.//{*}chord') is None
                                        and dur_e is not None and dur_e.text):
                                    current_offset += float(dur_e.text)
                            elif tag == 'backup':
                                dur_e = elem.find('.//{*}duration')
                                if dur_e is not None and dur_e.text:
                                    current_offset = max(0.0, current_offset - float(dur_e.text))
                            elif tag == 'forward':
                                dur_e = elem.find('.//{*}duration')
                                if dur_e is not None and dur_e.text:
                                    current_offset += float(dur_e.text)
                break
    return result


def _play_state_direction(measure_num: int, offset_q: float, staff: str,
                          words_text: str, pizzicato: Optional[str],
                          measure_duration_q: float = 2.0) -> DirectionElement:
    """pizz./arco の DirectionElement を組み立てるテスト用ヘルパー"""
    sound = f'<sound pizzicato="{pizzicato}"/>' if pizzicato is not None else ''
    xml = (f'<direction placement="above"><direction-type>'
           f'<words>{words_text}</words></direction-type>'
           f'<staff>{staff}</staff>{sound}</direction>')
    return DirectionElement(
        measure_num=measure_num,
        element_index=0,
        direction_xml=xml,
        placement='above',
        has_sound=pizzicato is not None,
        has_words=True,
        words_text=words_text,
        offset_quarters=offset_q,
        measure_duration_quarters=measure_duration_q,
        staff=staff,
        sound_pizzicato=pizzicato,
    )


class TestIssue68PlayStateDetection:
    """Issue #68: pizz./arco の判定と分類"""

    def test_sound_pizzicato_attribute_detects_state(self):
        """sound の pizzicato 属性から奏法状態を判定する"""
        pizz = _play_state_direction(46, 1.0, '2', 'pizz.', 'yes')
        arco = _play_state_direction(48, 0.0, '2', 'arco', 'no')
        assert _get_state_marking(pizz)[1] == 'pizz'
        assert _get_state_marking(arco)[1] == 'arco'

    def test_words_text_detects_state_without_sound(self):
        """sound属性を持たない arco もテキストで判定できる"""
        arco = _play_state_direction(50, 1.0, '1', 'arco', None)
        assert _get_state_marking(arco)[1] == 'arco'

    def test_tempo_direction_is_not_play_state(self):
        """テンポ指示は奏法状態として判定されない"""
        tempo_dir = DirectionElement(
            measure_num=45, element_index=0,
            direction_xml='<direction><direction-type><words>Piu mosso.</words>'
                          '</direction-type><sound tempo="126"/></direction>',
            has_sound=True, has_words=True, words_text='Piu mosso.',
        )
        assert _get_state_marking(tempo_dir) is None

    def test_play_state_separated_before_tempo_classification(self):
        """pizz./arco は _is_tempo_direction が真になるため事前に分離される必要がある"""
        pizz = _play_state_direction(46, 1.0, '2', 'pizz.', 'yes')
        assert _is_tempo_direction(pizz) is True

        state_dirs, others = _separate_state_marking_directions([pizz])
        assert state_dirs == [pizz]
        assert others == []


class TestIssue68PizzArcoRangeReversal:
    """Issue #68: pizz./arco の有効範囲ベース反転"""

    TOTAL_MEASURES = 53

    def _markers(self, dirs):
        """(状態, staff, 小節, オフセット) の集合を返す"""
        return {
            (m.state, m.staff, m.measure_num, m.offset_quarters)
            for m in _calculate_reversed_state_markers(dirs, self.TOTAL_MEASURES)
        }

    def test_cancel_marker_is_generated_at_range_end(self):
        """区間終端に打ち消しマーカー(arco)が生成される

        原譜 staff2: pizz.@m46 2拍目 → arco@m48 頭
        反転後: m7頭から pizz.、m8 2拍目から arco（元の pizz. 開始位置）
        """
        dirs = [
            _play_state_direction(46, 1.0, '2', 'pizz.', 'yes'),
            _play_state_direction(48, 0.0, '2', 'arco', 'no'),
        ]
        markers = self._markers(dirs)

        assert ('pizz', '2', 7, 0.0) in markers, f"pizz. should start at m7 head: {markers}"
        assert ('arco', '2', 8, 1.0) in markers, \
            f"arco cancel marker should be at m8 beat 2: {markers}"

    def test_no_marker_at_score_start_when_state_is_default(self):
        """反転後の曲頭が既定状態(arco)ならマーカーを出さない"""
        dirs = [
            _play_state_direction(46, 1.0, '2', 'pizz.', 'yes'),
            _play_state_direction(48, 0.0, '2', 'arco', 'no'),
        ]
        markers = self._markers(dirs)

        assert not [m for m in markers if m[2] == 1], \
            f"no play-state marker should be emitted at measure 1: {markers}"

    def test_states_are_not_swapped(self):
        """staff1: pizz.@m48頭 → arco@m50 2拍目 が入れ替わらない

        反転後は m4 2拍目から pizz.、m7 頭から arco になる。
        """
        dirs = [
            _play_state_direction(48, 0.0, '1', 'pizz.', 'yes'),
            _play_state_direction(50, 1.0, '1', 'arco', None),
        ]
        markers = self._markers(dirs)

        assert ('pizz', '1', 4, 1.0) in markers, f"pizz. should be at m4 beat 2: {markers}"
        assert ('arco', '1', 7, 0.0) in markers, f"arco should be at m7 head: {markers}"

    def test_staves_are_handled_independently(self):
        """複数譜パートでは staff ごとに独立した状態として扱う"""
        dirs = [
            _play_state_direction(46, 1.0, '2', 'pizz.', 'yes'),
            _play_state_direction(48, 0.0, '2', 'arco', 'no'),
            _play_state_direction(48, 0.0, '1', 'pizz.', 'yes'),
            _play_state_direction(50, 1.0, '1', 'arco', None),
        ]
        markers = self._markers(dirs)

        assert {m for m in markers if m[1] == '2'} == {
            ('pizz', '2', 7, 0.0), ('arco', '2', 8, 1.0)}
        assert {m for m in markers if m[1] == '1'} == {
            ('pizz', '1', 4, 1.0), ('arco', '1', 7, 0.0)}

    def test_violin_pizz_arco_positions_end_to_end(self, tmp_path):
        """威風堂々Violin(2段譜): 反転出力の pizz./arco 配置を実測で検証"""
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/test/威風堂々ラスト_in-Violin.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        layout_map = extract_layout_from_xml(input_file)
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        positions = [
            (m, offset, staff, text) for m, offset, staff, text
            in get_words_positions_from_mxl(output_file)
            if text.lower() in ('pizz.', 'arco')
        ]

        assert ('7', 0.0, '2', 'pizz.') in positions, positions
        assert ('8', 1.0, '2', 'arco') in positions, positions
        assert ('4', 1.0, '1', 'pizz.') in positions, positions
        assert ('7', 0.0, '1', 'arco') in positions, positions
        assert not [p for p in positions if p[0] == '1'], \
            f"measure 1 should have no pizz./arco marker: {positions}"


class TestIssue70StateMarkingGroups:
    """Issue #70: 語彙で定義できる状態指示の有効範囲反転"""

    TOTAL_MEASURES = 53

    def _markers(self, dirs):
        """(状態, staff, 小節, オフセット) の集合を返す"""
        return {
            (m.state, m.staff, m.measure_num, m.offset_quarters)
            for m in _calculate_reversed_state_markers(dirs, self.TOTAL_MEASURES)
        }

    def _words(self, dirs):
        """(表示テキスト, 小節) の集合を返す（合成される打ち消し表記の検証用）"""
        result = set()
        for marker in _calculate_reversed_state_markers(dirs, self.TOTAL_MEASURES):
            direction = _build_state_marking_direction(marker)
            words = direction.find('.//{*}direction-type/{*}words')
            result.add((words.text, marker.measure_num))
        return result

    def test_divisi_vocabulary_is_detected(self):
        """a 2. / I. / II. / div. / unis. が divisi グループとして判定される"""
        cases = [('a 2.', 'tutti'), ('unis.', 'tutti'), ('div.', 'div'),
                 ('I.', 'first'), ('II.', 'second')]
        for text, expected_state in cases:
            d = _play_state_direction(1, 0.0, None, text, None)
            marking = _get_state_marking(d)
            assert marking is not None, f"{text} should be a state marking"
            group, state = marking
            assert group.name == 'divisi', f"{text} → {group.name}"
            assert state == expected_state, f"{text} → {state}"

    def test_mute_and_bowing_vocabulary_is_detected(self):
        """con sord. / sul pont. 等が判定される"""
        cases = [('con sord.', 'mute', 'muted'), ('senza sord.', 'mute', 'open'),
                 ('sul pont.', 'bowing', 'pont'), ('sul tasto', 'bowing', 'tasto'),
                 ('col legno', 'bowing', 'legno'), ('ord.', 'bowing', 'ord')]
        for text, expected_group, expected_state in cases:
            group, state = _get_state_marking(_play_state_direction(1, 0.0, None, text, None))
            assert (group.name, state) == (expected_group, expected_state), \
                f"{text} → ({group.name}, {state})"

    def test_words_split_across_siblings_is_detected(self):
        """<words>con</words><words>sord.</words> のように分割されていても判定できる"""
        d = DirectionElement(
            measure_num=1, element_index=0,
            direction_xml='<direction><direction-type><words>con</words>'
                          '<words>sord.</words></direction-type></direction>',
            has_words=True, words_text='con',
        )
        group, state = _get_state_marking(d)
        assert (group.name, state) == ('mute', 'muted')

    def test_non_vocabulary_words_are_not_state_markings(self):
        """語彙外のテキストは状態指示として扱わない（誤検出の防止）"""
        for text in ('sostenuto', 'simile', 'ad lib.', 'glissando',
                     'Tambourine', 'Sw.', 'Full.'):
            d = _play_state_direction(1, 0.0, None, text, None)
            assert _get_state_marking(d) is None, f"{text} should not be a state marking"

    def test_a2_to_first_is_not_swapped(self):
        """F_Trumpet: a 2.@m1 → I.@m48 の状態が入れ替わらない

        I. の有効範囲は m48〜曲末なので、反転後は曲頭〜m6 が I.、m7 から a 2. に戻る。
        """
        dirs = [
            _play_state_direction(1, 0.0, None, 'a 2.', None),
            _play_state_direction(48, 0.0, None, 'I.', None),
        ]
        markers = self._markers(dirs)

        assert ('first', None, 1, 0.0) in markers, f"I. should be at m1: {markers}"
        assert ('tutti', None, 7, 0.0) in markers, f"a 2. should be at m7: {markers}"

    def test_div_cancel_marker_is_synthesized_as_unis(self):
        """Viola: div.@m41 に解除記号が無い場合、unis. を合成して区間終端に置く

        div. の有効範囲は m41〜曲末なので、反転後は m1〜m13 が div.、m14 で解除。
        """
        dirs = [_play_state_direction(41, 0.0, None, 'div.', None)]

        assert ('div.', 1) in self._words(dirs), self._words(dirs)
        assert ('unis.', 14) in self._words(dirs), self._words(dirs)

    def test_first_cancel_marker_is_synthesized_as_a2(self):
        """I. の解除は unis. ではなく a 2. を合成する"""
        dirs = [_play_state_direction(41, 0.0, None, 'I.', None)]

        assert ('I.', 1) in self._words(dirs), self._words(dirs)
        assert ('a 2.', 14) in self._words(dirs), self._words(dirs)

    def test_redundant_restatement_is_kept_at_mirrored_position(self):
        """状態を変えていない再掲は鏡像位置に残す（元譜の情報を失わない）

        Flute: a 2.@m1 と a 2.@m45 はどちらも既定状態の再掲。
        m45 の鏡像は m10、m1 の鏡像は曲末を越えるため最終小節にクランプする。
        """
        dirs = [
            _play_state_direction(1, 0.0, None, 'a 2.', None),
            _play_state_direction(45, 0.0, None, 'a 2.', None),
        ]
        markers = self._markers(dirs)

        assert ('tutti', None, 10, 0.0) in markers, f"a 2. should be at m10: {markers}"
        assert ('tutti', None, 53, 0.0) in markers, \
            f"a 2. at m1 should be clamped to the last measure: {markers}"

    def test_groups_are_independent(self):
        """奏法と分割は互いに独立した状態として扱う"""
        dirs = [
            _play_state_direction(46, 1.0, '1', 'pizz.', 'yes'),
            _play_state_direction(41, 0.0, '1', 'div.', None),
        ]
        markers = self._markers(dirs)

        # pizz. の区間は m46〜曲末 → 反転後 m1〜m8 2拍目
        assert ('pizz', '1', 1, 0.0) in markers, markers
        assert ('arco', '1', 8, 1.0) in markers, markers
        # div. の区間は m41〜曲末 → 反転後 m1〜m13
        assert ('div', '1', 1, 0.0) in markers, markers
        assert ('tutti', '1', 14, 0.0) in markers, markers

    def test_f_trumpet_positions_end_to_end(self, tmp_path):
        """威風堂々F_Trumpet: 反転出力の a 2. / I. 配置を実測で検証"""
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/威風堂々ラスト-F_Trumpet.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        layout_map = extract_layout_from_xml(input_file)
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        positions = [(m, text) for m, _offset, _staff, text
                     in get_words_positions_from_mxl(output_file)
                     if text in ('a 2.', 'I.')]

        assert ('1', 'I.') in positions, positions
        assert ('7', 'a 2.') in positions, positions
        assert not [p for p in positions if p == ('1', 'a 2.')], \
            f"measure 1 should be I., not a 2.: {positions}"

    def test_viola_div_unis_end_to_end(self, tmp_path):
        """威風堂々Viola: div. が m1、合成した unis. が m14 に来る"""
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/威風堂々ラスト-Viola.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        layout_map = extract_layout_from_xml(input_file)
        score = converter.parse(str(input_file))
        reversed_score = reverse_score(score, None)
        reversed_score.write('mxl', fp=str(output_file))
        total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
        restore_direction_elements(output_file, layout_map, total_measures)

        positions = [(m, text) for m, _offset, _staff, text
                     in get_words_positions_from_mxl(output_file)
                     if text in ('div.', 'unis.')]

        assert ('1', 'div.') in positions, positions
        assert ('14', 'unis.') in positions, positions


def _instrument_ref(measure_num: int, offset_q: float, instrument_id: str,
                    voice: str = '1') -> InstrumentRef:
    """per-note instrument 参照のテスト用ヘルパー"""
    return InstrumentRef(measure_num=measure_num, voice=voice, note_index=0,
                         instrument_id=instrument_id, offset_quarters=offset_q)


class TestIssue73InstrumentChangeLabels:
    """Issue #73: 打楽器の持ち替えラベルを楽器参照の切り替わりから検出し区間ごと反転する"""

    TOTAL_MEASURES = 53

    def _label_texts(self, dirs, refs):
        labels, _others = _separate_instrument_change_labels(dirs, refs)
        return [d.words_text for d in labels]

    def test_label_at_instrument_change_is_detected(self):
        """楽器参照が新しい楽器に切り替わる位置の words はラベル"""
        refs = [_instrument_ref(1, 0.0, 'TAMB'), _instrument_ref(2, 0.0, 'TAMB'),
                _instrument_ref(3, 0.0, 'GLOCK')]
        dirs = [_play_state_direction(3, 0.0, None, 'Glockensp.', None)]

        assert self._label_texts(dirs, refs) == ['Glockensp.']

    def test_words_without_instrument_change_are_not_labels(self):
        """楽器が変わらない位置の words（ad lib. / simile 等）はラベルにしない"""
        refs = [_instrument_ref(1, 0.0, 'TAMB'), _instrument_ref(2, 0.0, 'TAMB')]
        dirs = [_play_state_direction(2, 0.0, None, 'ad lib.', None)]

        assert self._label_texts(dirs, refs) == []

    def test_words_inside_per_pitch_section_are_not_labels(self):
        """音高ごとに楽器 id が変わる区間の途中にある words はラベルにしない

        グロッケン区間では音符ごとに id が切り替わるが、直前の持ち替え以降に
        既に使われた id なので持ち替えではない。
        """
        refs = [_instrument_ref(1, 0.0, 'TAMB'),
                _instrument_ref(2, 0.0, 'GL-A'), _instrument_ref(2, 1.0, 'GL-C'),
                _instrument_ref(3, 0.0, 'GL-A'), _instrument_ref(3, 1.0, 'GL-C')]
        dirs = [_play_state_direction(2, 0.0, None, 'Glockensp.', None),
                _play_state_direction(3, 1.0, None, 'simile', None)]

        assert self._label_texts(dirs, refs) == ['Glockensp.']

    def test_first_note_of_part_is_not_a_label(self):
        """パート最初の音符上の words は切り替え元が無いのでラベルにしない（単一楽器パート）"""
        refs = [_instrument_ref(1, 0.0, 'TRI'), _instrument_ref(2, 0.0, 'TRI')]
        dirs = [_play_state_direction(1, 0.0, None, 'ad lib.', None)]

        assert self._label_texts(dirs, refs) == []

    def test_words_before_entrance_are_not_labels(self):
        """後続の入りまで離れた words（休符上）は巻き込まない"""
        refs = [_instrument_ref(1, 0.0, 'TAMB'), _instrument_ref(5, 0.0, 'GLOCK')]
        dirs = [_play_state_direction(4, 0.0, None, 'cresc. molto', None)]

        assert self._label_texts(dirs, refs) == []

    def test_return_to_previous_instrument_is_detected(self):
        """Tambourine → Glockensp. → Tambourine の戻りもラベルとして検出する"""
        refs = [_instrument_ref(1, 0.0, 'TAMB'), _instrument_ref(5, 0.0, 'GLOCK'),
                _instrument_ref(9, 0.0, 'TAMB')]
        dirs = [_play_state_direction(5, 0.0, None, 'Glockensp.', None),
                _play_state_direction(9, 0.0, None, 'Tambourine', None)]

        assert self._label_texts(dirs, refs) == ['Glockensp.', 'Tambourine']

    def test_same_position_labels_are_all_detected(self):
        """同じ位置に分けて置かれた Gl. と Schellen. はどちらもラベル"""
        refs = [_instrument_ref(1, 0.0, 'GLOCK'),
                _instrument_ref(2, 0.0, 'GL-HI', voice='1'),
                _instrument_ref(2, 0.0, 'JINGLE', voice='2')]
        dirs = [_play_state_direction(2, 0.0, None, 'Gl.', None),
                _play_state_direction(2, 0.0, None, 'Schellen.', None)]

        assert self._label_texts(dirs, refs) == ['Gl.', 'Schellen.']

    def test_labels_move_to_start_of_reversed_region(self):
        """威風堂々Tambourine: Tambourine@m17 → Glockensp.@m45 → Gl.+Schellen.@m52

        区間 m52-53 / m45-51 / m17-44 は反転後 m1-2 / m3-9 / m10-37。
        ラベルの無い初期区間 m1-16（反転後 m38-53）には何も出さない。
        """
        dirs = [
            _play_state_direction(17, 0.0, None, 'Tambourine', None),
            _play_state_direction(45, 0.0, None, 'Glockensp.', None),
            _play_state_direction(52, 0.0, None, 'Gl.', None),
            _play_state_direction(52, 0.0, None, 'Schellen.', None),
        ]
        positions = {
            (d.words_text, m, offset)
            for d, m, offset in _calculate_reversed_instrument_change_labels(
                dirs, self.TOTAL_MEASURES)
        }

        assert positions == {
            ('Gl.', 1, 0.0), ('Schellen.', 1, 0.0),
            ('Glockensp.', 3, 0.0), ('Tambourine', 10, 0.0),
        }

    def test_mid_measure_label_uses_mirrored_offset(self):
        """小節途中の境界は小節内オフセットも鏡像にする"""
        dirs = [
            _play_state_direction(10, 0.0, None, 'Tambourine', None, measure_duration_q=2.0),
            _play_state_direction(20, 0.5, None, 'Glockensp.', None, measure_duration_q=2.0),
        ]
        positions = {
            (d.words_text, m, offset)
            for d, m, offset in _calculate_reversed_instrument_change_labels(
                dirs, self.TOTAL_MEASURES)
        }

        # 元 m20 の 0.5 拍 → 反転後 m34 の 1.5 拍
        assert positions == {('Glockensp.', 1, 0.0), ('Tambourine', 34, 1.5)}

    def test_tambourine_positions_end_to_end(self, tmp_path):
        """威風堂々Tambourine: 反転出力のラベル配置を実測で検証"""
        input_file = (Path(__file__).parent.parent
                      / 'work/inbox/威風堂々ラスト-Tambourine.mxl')
        if not input_file.exists():
            pytest.skip(f"Test file not found: {input_file}")

        output_file = tmp_path / 'test_output.mxl'
        report = process_file(input_file, output_file)
        assert report.success

        labels = ('Tambourine', 'Glockensp.', 'Gl.', 'Schellen.')
        positions = sorted((int(m), offset, text) for m, offset, _staff, text
                           in get_words_positions_from_mxl(output_file)
                           if text in labels)

        assert positions == [
            (1, 0.0, 'Gl.'), (1, 0.0, 'Schellen.'),
            (3, 0.0, 'Glockensp.'), (10, 0.0, 'Tambourine'),
        ], positions

    def test_parts_without_instrument_refs_are_unchanged(self):
        """楽器参照を持たないパートでは何も分離しない"""
        dirs = [_play_state_direction(15, 0.0, '3', 'Sw.', None)]
        labels, others = _separate_instrument_change_labels(dirs, [])

        assert labels == []
        assert others == dirs


# ---------------------------------------------------------------------------
# Issue #74: 最小構成の楽譜で direction の反転を検証するヘルパー
# ---------------------------------------------------------------------------

def _dt(inner: str) -> str:
    return f'<direction-type>{inner}</direction-type>'


def _dir(direction_types: str, staff: Optional[str] = None, sound: str = '') -> str:
    staff_xml = f'<staff>{staff}</staff>' if staff else ''
    return f'<direction placement="below">{direction_types}{staff_xml}{sound}</direction>'


def _write_direction_score(path: Path, total_measures: int,
                           directions: dict[int, list[tuple[float, str]]],
                           beats: int = 2) -> None:
    """divisions=1、各小節に四分音符を beats 個並べた楽譜を書き出す

    Args:
        directions: {小節番号: [(小節内オフセット, direction XML)]}。
            オフセットが beats 以上なら小節末（音符の後）に置く
    """
    measures = []
    for num in range(1, total_measures + 1):
        body = ''
        if num == 1:
            body += ('<attributes><divisions>1</divisions><key><fifths>0</fifths></key>'
                     f'<time><beats>{beats}</beats><beat-type>4</beat-type></time>'
                     '<clef><sign>G</sign><line>2</line></clef></attributes>')
        placed = directions.get(num, [])
        for beat in range(beats):
            body += ''.join(xml for offset, xml in placed if offset == beat)
            body += ('<note><pitch><step>C</step><octave>5</octave></pitch>'
                     '<duration>1</duration><voice>1</voice><type>quarter</type></note>')
        body += ''.join(xml for offset, xml in placed if offset >= beats)
        measures.append(f'    <measure number="{num}">{body}</measure>\n')
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="4.0">\n'
        '  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>\n'
        '  <part id="P1">\n' + ''.join(measures) + '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _direction_events(path: Path) -> list[tuple[int, float, ET.Element]]:
    """(小節番号, 小節内オフセット, direction 要素) を出現順に返す"""
    root = ET.parse(path).getroot()
    events = []
    for measure in root.findall('.//{*}measure'):
        offset = 0.0
        for child in measure:
            tag = child.tag.split('}')[-1]
            if tag == 'note' and child.find('{*}chord') is None:
                offset += float(child.findtext('{*}duration'))
            elif tag == 'backup':
                offset -= float(child.findtext('{*}duration'))
            elif tag == 'forward':
                offset += float(child.findtext('{*}duration'))
            elif tag == 'direction':
                events.append((int(measure.get('number')), offset, child))
    return events


def _elements(events, tag: str) -> list[tuple[int, float, ET.Element, ET.Element]]:
    """events から tag 要素を (小節, オフセット, 要素, direction) で抜き出す"""
    return [(m, offset, elem, direction)
            for m, offset, direction in events
            for elem in direction.iter() if elem.tag.split('}')[-1] == tag]


def _reverse_directions(path: Path, total_measures: int) -> list[tuple[int, float, ET.Element]]:
    """direction の抽出と復元だけを通す（音符は反転しない）"""
    layout_map = extract_layout_from_xml(path)
    restore_direction_elements(path, layout_map, total_measures)
    return _direction_events(path)


class TestIssue74SpannerPairs:
    """Issue #74: start/stop で線を描く direction は役割を入れ替えて反転する"""

    TOTAL = 10

    def test_pedal_start_precedes_stop(self, tmp_path):
        """pedal: 元 m2 頭の start → m4 2拍目の stop は、反転後 m7 2拍目の start → m9 末の stop"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<pedal type="start" line="yes" sign="yes"/>')))],
            4: [(1, _dir(_dt('<pedal type="stop" line="yes" sign="no"/>')))],
        })

        pedals = [(m, offset, e.get('type'), e.get('sign'))
                  for m, offset, e, _d in _elements(_reverse_directions(score, self.TOTAL), 'pedal')]

        assert pedals == [(7, 1.0, 'start', 'yes'), (9, 2.0, 'stop', 'no')]

    def test_pedal_discontinue_and_resume_are_swapped(self, tmp_path):
        """線だけの終了（discontinue）と再開（resume）は、反転後も同じ位置で入れ替わる

        元: start@m2頭 → discontinue@m3 2拍目 → resume@m5頭 → stop@m6 2拍目
        反転後: start@m5 2拍目 → discontinue@m6末 → resume@m8 2拍目 → stop@m9末
        """
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<pedal type="start" line="yes"/>')))],
            3: [(1, _dir(_dt('<pedal type="discontinue" line="yes"/>')))],
            5: [(0, _dir(_dt('<pedal type="resume" line="yes"/>')))],
            6: [(1, _dir(_dt('<pedal type="stop" line="yes"/>')))],
        })

        pedals = [(m, offset, e.get('type'))
                  for m, offset, e, _d in _elements(_reverse_directions(score, self.TOTAL), 'pedal')]

        assert pedals == [(5, 1.0, 'start'), (6, 2.0, 'discontinue'),
                          (8, 1.0, 'resume'), (9, 2.0, 'stop')]

    def test_bracket_line_end_stays_at_its_position(self, tmp_path):
        """bracket の鉤（line-end / end-length）は役割ではなく位置に付いたまま残る"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<bracket type="start" line-end="none" number="1"/>')))],
            4: [(1, _dir(_dt('<bracket type="stop" line-end="down" end-length="15" number="1"/>')))],
        })

        brackets = [(m, offset, e.get('type'), e.get('line-end'), e.get('end-length'))
                    for m, offset, e, _d in _elements(_reverse_directions(score, self.TOTAL), 'bracket')]

        assert brackets == [(7, 1.0, 'start', 'down', '15'), (9, 2.0, 'stop', 'none', None)]

    def test_dashes_with_cresc_words(self, tmp_path):
        """cresc. - - - は、文字を新しい start に付けたまま decresc. に反転する"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<words>cresc.</words>') + _dt('<dashes type="start"/>')))],
            5: [(0, _dir(_dt('<dashes type="stop"/>')))],
        })

        dashes = _elements(_reverse_directions(score, self.TOTAL), 'dashes')

        assert [(m, offset, e.get('type')) for m, offset, e, _d in dashes] == [
            (6, 2.0, 'start'), (9, 2.0, 'stop')]
        start_direction = dashes[0][3]
        assert start_direction.findtext('.//{*}words') == 'decresc.'

    def test_principal_voice_symbol_moves_with_start(self, tmp_path):
        """principal-voice の記号（Hauptstimme）は新しい start に付く"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<principal-voice type="start" symbol="Hauptstimme"/>')))],
            4: [(1, _dir(_dt('<principal-voice type="stop" symbol="plain"/>')))],
        })

        voices = [(m, offset, e.get('type'), e.get('symbol')) for m, offset, e, _d
                  in _elements(_reverse_directions(score, self.TOTAL), 'principal-voice')]

        assert voices == [(7, 1.0, 'start', 'Hauptstimme'), (9, 2.0, 'stop', 'plain')]

    def test_wedge_with_words_is_paired(self, tmp_path):
        """words と同居する wedge もペアとして反転する（spread は位置に残る）"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<words>poco</words>') + _dt('<wedge type="crescendo"/>')))],
            4: [(1, _dir(_dt('<wedge type="stop" spread="15"/>')))],
        })

        wedges = _elements(_reverse_directions(score, self.TOTAL), 'wedge')

        assert [(m, offset, e.get('type'), e.get('spread')) for m, offset, e, _d in wedges] == [
            (7, 1.0, 'diminuendo', '15'), (9, 2.0, 'stop', None)]
        assert wedges[0][3].findtext('.//{*}words') == 'poco'

    def test_wedge_pairs_are_matched_per_staff(self, tmp_path):
        """同じ number のペアが譜をまたいで交差しても取り違えない"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            2: [(0, _dir(_dt('<wedge type="crescendo"/>'), staff='1'))],
            3: [(0, _dir(_dt('<wedge type="crescendo"/>'), staff='2'))],
            4: [(0, _dir(_dt('<wedge type="stop"/>'), staff='2'))],
            5: [(0, _dir(_dt('<wedge type="stop"/>'), staff='1'))],
        })

        wedges = _elements(_reverse_directions(score, self.TOTAL), 'wedge')
        by_staff: dict[str, list] = {}
        for m, offset, e, d in wedges:
            by_staff.setdefault(d.findtext('{*}staff'), []).append((m, offset, e.get('type')))

        assert by_staff == {
            '1': [(6, 2.0, 'diminuendo'), (9, 2.0, 'stop')],
            '2': [(7, 2.0, 'diminuendo'), (8, 2.0, 'stop')],
        }

    def test_staff_divide_direction_is_flipped(self, tmp_path):
        """staff-divide は分割と合流が入れ替わる（down ↔ up）"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            3: [(0, _dir(_dt('<staff-divide type="down"/>')))],
        })

        divides = [(m, e.get('type')) for m, _offset, e, _d
                   in _elements(_reverse_directions(score, self.TOTAL), 'staff-divide')]

        assert divides == [(8, 'up')]


def _harp_pedals(d_alter: int) -> str:
    return (f'<harp-pedals><pedal-tuning><pedal-step>D</pedal-step>'
            f'<pedal-alter>{d_alter}</pedal-alter></pedal-tuning></harp-pedals>')


def _metronome(per_minute: int) -> str:
    return (f'<metronome><beat-unit>quarter</beat-unit>'
            f'<per-minute>{per_minute}</per-minute></metronome>')


class TestIssue74StatefulDirections:
    """Issue #74: 次の指示まで有効な記号（string-mute / harp-pedals / metronome）の有効範囲反転"""

    TOTAL = 10

    def test_string_mute_region_is_reversed_with_synthesized_off(self, tmp_path):
        """string-mute on@m3 の区間 m3〜曲末は、反転後 m1〜m8。解除の off を m9 に合成する"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            3: [(0, _dir(_dt('<string-mute type="on"/>')))],
        })

        events = _reverse_directions(score, self.TOTAL)
        mutes = [(m, offset, e.get('type')) for m, offset, e, _d in _elements(events, 'string-mute')]

        assert mutes == [(1, 0.0, 'on'), (9, 0.0, 'off')]
        assert _elements(events, 'words') == [], "記号で書かれた指示に words を合成しない"

    def test_string_mute_on_off_are_not_swapped(self, tmp_path):
        """on@m3頭 → off@m5 2拍目 は、反転後 on@m6 2拍目 → off@m9頭"""
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            3: [(0, _dir(_dt('<string-mute type="on"/>')))],
            5: [(1, _dir(_dt('<string-mute type="off"/>')))],
        })

        mutes = [(m, offset, e.get('type')) for m, offset, e, _d
                 in _elements(_reverse_directions(score, self.TOTAL), 'string-mute')]

        assert mutes == [(6, 1.0, 'on'), (9, 0.0, 'off')]

    def test_harp_pedals_move_to_region_start(self, tmp_path):
        """harp-pedals A@m3 / B@m7 の区間 m3–6 / m7–10 は、反転後 m5–8 / m1–4

        設定は区間の先頭に移る。最初の指示より前の区間（m1–2 → 反転後 m9–10）は
        設定が分からないので何も出さない。
        """
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            3: [(0, _dir(_dt(_harp_pedals(0))))],
            7: [(0, _dir(_dt(_harp_pedals(1))))],
        })

        pedals = [(m, offset, e.findtext('.//{*}pedal-alter')) for m, offset, e, _d
                  in _elements(_reverse_directions(score, self.TOTAL), 'harp-pedals')]

        assert pedals == [(1, 0.0, '1'), (5, 0.0, '0')]

    def test_scordatura_and_accordion_registration_are_settings(self):
        """scordatura / accordion-registration も設定として分離される"""
        from layout_preservation import _separate_setting_directions

        scordatura = _play_state_direction(2, 0.0, None, '', None)
        scordatura.direction_xml = _dir(_dt(
            '<scordatura><accord string="6"><tuning-step>D</tuning-step>'
            '<tuning-octave>2</tuning-octave></accord></scordatura>'))
        accordion = _play_state_direction(4, 0.0, None, '', None)
        accordion.direction_xml = _dir(_dt('<accordion-registration><accordion-high/>'
                                           '</accordion-registration>'))
        words = _play_state_direction(5, 0.0, None, 'espressivo', None)

        settings, others = _separate_setting_directions([scordatura, accordion, words])

        assert settings == [scordatura, accordion]
        assert others == [words]

    def test_metronome_only_tempo_is_range_reversed(self, tmp_path):
        """words を持たない metronome も words のテンポと同じく有効範囲で反転する

        ♩=120@m1（区間 m1–5）/ ♩=80@m6（区間 m6–10）→ 反転後 ♩=80@m1 / ♩=120@m6
        """
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            1: [(0, _dir(_dt(_metronome(120)), sound='<sound tempo="120"/>'))],
            6: [(0, _dir(_dt(_metronome(80)), sound='<sound tempo="80"/>'))],
        })

        tempos = [(m, e.findtext('{*}per-minute')) for m, _offset, e, _d
                  in _elements(_reverse_directions(score, self.TOTAL), 'metronome')]

        assert tempos == [(1, '80'), (6, '120')]

    def test_metric_modulation_is_a_boundary_with_swapped_units(self, tmp_path):
        """メトリック・モジュレーション（♩ = ♪.）は境界として鏡像位置に置き、左右を入れ替える

        元 m6 頭（m5|m6 の境界）→ 反転後 m5|m6 の境界 = m6 頭。テンポの境界にはならないので
        m1 の ♩=120（全曲が有効範囲）は反転後も m1 に来る。
        """
        score = tmp_path / 'score.xml'
        _write_direction_score(score, self.TOTAL, {
            1: [(0, _dir(_dt(_metronome(120)), sound='<sound tempo="120"/>'))],
            6: [(0, _dir(_dt('<metronome><beat-unit>quarter</beat-unit>'
                             '<beat-unit>eighth</beat-unit><beat-unit-dot/></metronome>')))],
        })

        metronomes = _elements(_reverse_directions(score, self.TOTAL), 'metronome')

        assert [(m, e.findtext('{*}per-minute')) for m, _o, e, _d in metronomes
                if e.find('{*}per-minute') is not None] == [(1, '120')]
        modulations = [(m, offset, [c.tag.split('}')[-1] + (':' + c.text if c.text else '')
                                    for c in e])
                       for m, offset, e, _d in metronomes if e.find('{*}per-minute') is None]
        assert modulations == [(6, 0.0, ['beat-unit:eighth', 'beat-unit-dot', 'beat-unit:quarter'])]
