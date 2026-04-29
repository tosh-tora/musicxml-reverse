#!/usr/bin/env python3
"""
direction要素の保存と復元のテスト

Issue #27: Tempo primo. や rit. などの指示が増殖する問題のリグレッションテスト
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import converter, stream, expressions, tempo
from layout_preservation import (
    extract_layout_from_xml,
    restore_direction_elements,
    DirectionElement,
    LayoutMap,
    _is_transitional_tempo_text,
)
from reverse_score import reverse_score


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
