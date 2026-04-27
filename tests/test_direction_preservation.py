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

        assert output_count == input_count, f"Direction count mismatch: input={input_count}, output={output_count}"

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

        # direction要素数は同じであるべき
        assert output_count == input_count, f"Direction elements multiplied: {input_count} -> {output_count}"
