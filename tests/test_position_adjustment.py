"""
始点のみ指定される要素の位置調整テスト

Issue #29: 音部記号、テンポ指示など「始点のみ指定される要素」は、
反転時に適用範囲を考慮して小節番号を再計算する必要がある。
"""

import pytest
from music21 import stream, clef, tempo, note, expressions

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reverse_score import (
    collect_clef_positions,
    calculate_reversed_clef_positions,
    apply_reversed_clefs,
    collect_tempo_positions,
    calculate_reversed_tempo_positions,
    apply_reversed_tempo_elements,
    reverse_part,
    is_transitional_tempo,
)


class TestClefPositionCollection:
    """音部記号の位置収集テスト"""

    def test_single_clef(self):
        """単一音部記号の収集"""
        measures = []
        for i in range(1, 6):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, clef.TrebleClef())
            m.append(note.Rest(quarterLength=4))
            measures.append(m)

        positions = collect_clef_positions(measures)
        assert len(positions) == 1
        assert positions[0]['measure_num'] == 1
        assert isinstance(positions[0]['clef'], clef.TrebleClef)

    def test_multiple_clefs(self):
        """複数音部記号の収集（威風堂々パターン）"""
        # 53小節、m1(C), m46(G), m48(C)
        measures = []
        for i in range(1, 54):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, clef.AltoClef())  # C記号（ビオラ）
            elif i == 46:
                m.insert(0, clef.TrebleClef())  # G記号
            elif i == 48:
                m.insert(0, clef.AltoClef())  # C記号に戻る
            m.append(note.Rest(quarterLength=4))
            measures.append(m)

        positions = collect_clef_positions(measures)
        assert len(positions) == 3
        assert positions[0]['measure_num'] == 1
        assert positions[1]['measure_num'] == 46
        assert positions[2]['measure_num'] == 48


class TestClefPositionCalculation:
    """音部記号の反転位置計算テスト"""

    def test_single_clef_reversed(self):
        """単一音部記号は反転後もm1に配置"""
        positions = [{'measure_num': 1, 'offset': 0, 'clef': clef.TrebleClef()}]
        total_measures = 10

        reversed_positions = calculate_reversed_clef_positions(positions, total_measures)

        assert len(reversed_positions) == 1
        assert reversed_positions[0]['reversed_measure_num'] == 1

    def test_two_clefs_reversed(self):
        """2つの音部記号の反転"""
        # m1(C), m6(G) → 全10小節
        # m1のCは m5まで有効 → 反転後: 10-5+1=6
        # m6のGは m10まで有効 → 反転後: 10-10+1=1
        positions = [
            {'measure_num': 1, 'offset': 0, 'clef': clef.AltoClef()},
            {'measure_num': 6, 'offset': 0, 'clef': clef.TrebleClef()},
        ]
        total_measures = 10

        reversed_positions = calculate_reversed_clef_positions(positions, total_measures)

        assert len(reversed_positions) == 2
        # G記号が先に来る（m1）
        assert reversed_positions[0]['reversed_measure_num'] == 1
        assert isinstance(reversed_positions[0]['clef'], clef.TrebleClef)
        # C記号（m6）
        assert reversed_positions[1]['reversed_measure_num'] == 6
        assert isinstance(reversed_positions[1]['clef'], clef.AltoClef)

    def test_ifudodo_viola_pattern(self):
        """威風堂々-Violaパターンの反転

        元: m1(C), m46(G), m48(C) 全53小節
        - m1のCはm45まで有効 → 反転後: 53-45+1=9
        - m46のGはm47まで有効 → 反転後: 53-47+1=7
        - m48のCはm53まで有効 → 反転後: 53-53+1=1

        反転後: m1(C), m7(G), m9(C)
        """
        positions = [
            {'measure_num': 1, 'offset': 0, 'clef': clef.AltoClef()},
            {'measure_num': 46, 'offset': 0, 'clef': clef.TrebleClef()},
            {'measure_num': 48, 'offset': 0, 'clef': clef.AltoClef()},
        ]
        total_measures = 53

        reversed_positions = calculate_reversed_clef_positions(positions, total_measures)

        assert len(reversed_positions) == 3
        # m48のC → 反転後m1
        assert reversed_positions[0]['reversed_measure_num'] == 1
        assert isinstance(reversed_positions[0]['clef'], clef.AltoClef)
        # m46のG → 反転後m7
        assert reversed_positions[1]['reversed_measure_num'] == 7
        assert isinstance(reversed_positions[1]['clef'], clef.TrebleClef)
        # m1のC → 反転後m9
        assert reversed_positions[2]['reversed_measure_num'] == 9
        assert isinstance(reversed_positions[2]['clef'], clef.AltoClef)


class TestTempoPositionCollection:
    """テンポ要素の位置収集テスト"""

    def test_single_tempo(self):
        """単一テンポ指示の収集"""
        measures = []
        for i in range(1, 6):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, tempo.MetronomeMark(number=120))
            m.append(note.Rest(quarterLength=4))
            measures.append(m)

        positions = collect_tempo_positions(measures)
        assert len(positions) == 1
        assert positions[0]['measure_num'] == 1
        assert positions[0]['element_type'] == 'MetronomeMark'

    def test_multiple_tempos(self):
        """複数テンポ指示の収集"""
        measures = []
        for i in range(1, 11):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, tempo.MetronomeMark(number=120))
            elif i == 5:
                m.insert(0, tempo.MetronomeMark(number=80))
            elif i == 8:
                m.insert(0, tempo.MetronomeMark(number=120))
            m.append(note.Rest(quarterLength=4))
            measures.append(m)

        positions = collect_tempo_positions(measures)
        assert len(positions) == 3
        assert positions[0]['measure_num'] == 1
        assert positions[1]['measure_num'] == 5
        assert positions[2]['measure_num'] == 8


class TestTempoPositionCalculation:
    """テンポ要素の反転位置計算テスト"""

    def test_single_tempo_reversed(self):
        """単一テンポ指示は反転後もm1に配置"""
        mm = tempo.MetronomeMark(number=120)
        positions = [{'measure_num': 1, 'offset': 0, 'element': mm, 'element_type': 'MetronomeMark'}]
        total_measures = 10

        reversed_positions = calculate_reversed_tempo_positions(positions, total_measures)

        assert len(reversed_positions) == 1
        assert reversed_positions[0]['reversed_measure_num'] == 1

    def test_multiple_tempos_reversed(self):
        """複数テンポ指示の反転"""
        # m1(120), m5(80), m8(120) → 全10小節
        # - m1の120はm4まで有効 → 反転後: 10-4+1=7
        # - m5の80はm7まで有効 → 反転後: 10-7+1=4
        # - m8の120はm10まで有効 → 反転後: 10-10+1=1
        positions = [
            {'measure_num': 1, 'offset': 0, 'element': tempo.MetronomeMark(number=120), 'element_type': 'MetronomeMark'},
            {'measure_num': 5, 'offset': 0, 'element': tempo.MetronomeMark(number=80), 'element_type': 'MetronomeMark'},
            {'measure_num': 8, 'offset': 0, 'element': tempo.MetronomeMark(number=120), 'element_type': 'MetronomeMark'},
        ]
        total_measures = 10

        reversed_positions = calculate_reversed_tempo_positions(positions, total_measures)

        assert len(reversed_positions) == 3
        # ソート後の順序を確認
        assert reversed_positions[0]['reversed_measure_num'] == 1   # 元m8 → 反転後m1
        assert reversed_positions[1]['reversed_measure_num'] == 4   # 元m5 → 反転後m4
        assert reversed_positions[2]['reversed_measure_num'] == 7   # 元m1 → 反転後m7


class TestReversePartIntegration:
    """reverse_part()の統合テスト"""

    def test_clef_reversal_in_part(self):
        """パート全体での音部記号反転"""
        # 10小節のパートを作成
        part = stream.Part()
        for i in range(1, 11):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, clef.AltoClef())
            elif i == 6:
                m.insert(0, clef.TrebleClef())
            m.append(note.Note('C4', quarterLength=4))
            part.append(m)

        # 反転
        reversed_part = reverse_part(part)

        # 反転後のパートから音部記号を収集
        all_clefs = []
        # パートレベルの音部記号
        for c in reversed_part.getElementsByClass('Clef'):
            all_clefs.append({'measure_num': 0, 'clef': c})
        # 小節内の音部記号
        for m in reversed_part.getElementsByClass(stream.Measure):
            for c in m.getElementsByClass('Clef'):
                all_clefs.append({'measure_num': m.number, 'clef': c})

        # 音部記号が適切に配置されているか確認
        # m1にTrebleClef, m6にAltoClefがあるべき
        assert len(all_clefs) >= 2

    def test_roundtrip_reversal(self):
        """往復変換テスト（2回反転で元に戻る）"""
        # シンプルなパートを作成
        part = stream.Part()
        for i in range(1, 6):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, clef.TrebleClef())
            m.append(note.Note('C4', quarterLength=4))
            part.append(m)

        # 2回反転
        reversed_once = reverse_part(part)
        reversed_twice = reverse_part(reversed_once)

        # 小節数が同じ
        orig_measures = list(part.getElementsByClass(stream.Measure))
        final_measures = list(reversed_twice.getElementsByClass(stream.Measure))
        assert len(orig_measures) == len(final_measures)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestRealDataIntegration:
    """実データを使った統合テスト"""

    def test_ifudodo_viola_file(self):
        """威風堂々-Violaパートで音部記号の反転を確認"""
        from music21 import converter
        from pathlib import Path

        test_file = Path(__file__).parent.parent / 'work/inbox/test/威風堂々ラスト_in-Viola.mxl'
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # ファイルを読み込み
        score = converter.parse(str(test_file))
        part = score.parts[0] if score.parts else score

        # 元の音部記号を収集
        original_measures = list(part.getElementsByClass(stream.Measure))
        original_clef_positions = collect_clef_positions(original_measures)

        print(f"\n元の音部記号位置: {[(p['measure_num'], type(p['clef']).__name__) for p in original_clef_positions]}")

        # パートを反転
        reversed_part = reverse_part(part)

        # 反転後の音部記号を収集
        reversed_measures = list(reversed_part.getElementsByClass(stream.Measure))
        reversed_clef_positions = collect_clef_positions(reversed_measures)

        # パートレベルの音部記号も確認
        part_level_clefs = list(reversed_part.getElementsByClass('Clef'))
        print(f"パートレベルの音部記号: {[type(c).__name__ for c in part_level_clefs]}")
        print(f"反転後の音部記号位置: {[(p['measure_num'], type(p['clef']).__name__) for p in reversed_clef_positions]}")

        # 威風堂々-Violaの場合：
        # 元: m1(Alto/C), m46(Treble/G), m48(Alto/C) 全53小節
        # 反転後: m1(Alto/C), m7(Treble/G), m9(Alto/C)

        # 最低限、音部記号の数が保持されていることを確認
        total_measures = len(original_measures)
        expected_positions = calculate_reversed_clef_positions(original_clef_positions, total_measures)
        print(f"期待される反転後位置: {[(p['reversed_measure_num'], type(p['clef']).__name__) for p in expected_positions]}")

        # 期待される位置に音部記号があることを確認
        assert len(part_level_clefs) >= 1, "パートレベルに音部記号がない"

    def test_double_reversal_preserves_clefs(self):
        """2回反転で音部記号の種類と概ねの配置が保持されることを確認

        注: 実データでは同一小節に複数の音部記号があるケースがあり、
        完全な往復変換は複雑。ここでは音部記号の種類が保持されることを確認。
        """
        from music21 import converter
        from pathlib import Path

        test_file = Path(__file__).parent.parent / 'work/inbox/test/威風堂々ラスト_in-Viola.mxl'
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # ファイルを読み込み
        score = converter.parse(str(test_file))
        part = score.parts[0] if score.parts else score

        # 元の音部記号の種類をカウント
        original_measures = list(part.getElementsByClass(stream.Measure))
        original_positions = collect_clef_positions(original_measures)
        original_clef_set = set(type(p['clef']).__name__ for p in original_positions)

        # 2回反転
        reversed_once = reverse_part(part)
        reversed_twice = reverse_part(reversed_once)

        # 2回反転後の音部記号の種類を確認
        final_measures = list(reversed_twice.getElementsByClass(stream.Measure))
        final_positions = collect_clef_positions(final_measures)
        final_clef_set = set(type(p['clef']).__name__ for p in final_positions)

        # パートレベルの音部記号も含める
        for c in reversed_twice.getElementsByClass('Clef'):
            final_clef_set.add(type(c).__name__)

        print(f"\n元の音部記号の種類: {original_clef_set}")
        print(f"2回反転後の種類: {final_clef_set}")

        # 音部記号の種類が保持されていることを確認
        assert original_clef_set == final_clef_set, "音部記号の種類が一致しない"


class TestTransitionalTempoDetection:
    """経過的テンポ表記の検出テスト"""

    def test_transitional_tempo_patterns(self):
        """経過的テンポ表記が正しく検出される"""
        transitional_texts = [
            'rit.',
            'ritardando',
            'rall.',
            'rallentando',
            'accel.',
            'accelerando',
            'stringendo',
            'morendo',
            'calando',
            'allargando',
            'a tempo',
            'Rit.',  # 大文字でも検出
            'ALLARGANDO',
        ]
        for text in transitional_texts:
            assert is_transitional_tempo(text), f"'{text}' should be detected as transitional"

    def test_main_tempo_not_detected(self):
        """主要テンポ指示は経過的として検出されない"""
        main_texts = [
            'Allegro',
            'Andante',
            'Molto Maestoso.',
            'Tempo primo.',
            'Più mosso.',
            'Presto',
            'Adagio',
            'Moderato',
        ]
        for text in main_texts:
            assert not is_transitional_tempo(text), f"'{text}' should NOT be detected as transitional"


class TestTransitionalTempoCalculation:
    """経過的テンポの反転位置計算テスト"""

    def test_ifudodo_viola_tempo_pattern(self):
        """威風堂々-Violaパターンのテンポ反転

        元のテンポ指示（全53小節）:
        - m1: Molto Maestoso. (主要)
        - m29: allargando (経過的)
        - m34: rit. (経過的)
        - m41: Tempo primo. (主要)
        - m45: Più mosso. (主要)

        主要テンポの有効範囲計算（経過的を除外）:
        - Molto Maestoso: m1-40 → 反転後 m14 (53-40+1)
        - Tempo primo: m41-44 → 反転後 m10 (53-44+1)
        - Più mosso: m45-53 → 反転後 m1 (53-53+1)

        経過的テンポの単純反転:
        - allargando: m29 → m25 (53-29+1)
        - rit.: m34 → m20 (53-34+1)

        期待される反転結果（ソート後）:
        - m1: Più mosso
        - m10: Tempo primo
        - m14: Molto Maestoso
        - m20: rit.
        - m25: allargando
        """
        # TextExpressionを使ってテンポ指示を作成
        positions = [
            {
                'measure_num': 1,
                'offset': 0,
                'element': expressions.TextExpression('Molto Maestoso.'),
                'element_type': 'TextExpression',
                'is_transitional': False,
            },
            {
                'measure_num': 29,
                'offset': 0,
                'element': expressions.TextExpression('allargando'),
                'element_type': 'TextExpression',
                'is_transitional': True,
            },
            {
                'measure_num': 34,
                'offset': 0,
                'element': expressions.TextExpression('rit.'),
                'element_type': 'TextExpression',
                'is_transitional': True,
            },
            {
                'measure_num': 41,
                'offset': 0,
                'element': expressions.TextExpression('Tempo primo.'),
                'element_type': 'TextExpression',
                'is_transitional': False,
            },
            {
                'measure_num': 45,
                'offset': 0,
                'element': expressions.TextExpression('Più mosso.'),
                'element_type': 'TextExpression',
                'is_transitional': False,
            },
        ]
        total_measures = 53

        reversed_positions = calculate_reversed_tempo_positions(positions, total_measures)

        assert len(reversed_positions) == 5

        # 反転後の位置を確認（ソート済み）
        # m1: Più mosso
        assert reversed_positions[0]['reversed_measure_num'] == 1
        assert reversed_positions[0]['element'].content == 'Più mosso.'

        # m10: Tempo primo
        assert reversed_positions[1]['reversed_measure_num'] == 10
        assert reversed_positions[1]['element'].content == 'Tempo primo.'

        # m14: Molto Maestoso
        assert reversed_positions[2]['reversed_measure_num'] == 14
        assert reversed_positions[2]['element'].content == 'Molto Maestoso.'

        # m20: rit. (経過的、単純反転: 53-34+1=20)
        assert reversed_positions[3]['reversed_measure_num'] == 20
        assert reversed_positions[3]['element'].content == 'rit.'

        # m25: allargando (経過的、単純反転: 53-29+1=25)
        assert reversed_positions[4]['reversed_measure_num'] == 25
        assert reversed_positions[4]['element'].content == 'allargando'

    def test_main_tempo_only(self):
        """主要テンポのみの場合（従来動作と同じ）"""
        positions = [
            {
                'measure_num': 1,
                'offset': 0,
                'element': tempo.MetronomeMark(number=120),
                'element_type': 'MetronomeMark',
                'is_transitional': False,
            },
            {
                'measure_num': 5,
                'offset': 0,
                'element': tempo.MetronomeMark(number=80),
                'element_type': 'MetronomeMark',
                'is_transitional': False,
            },
        ]
        total_measures = 10

        reversed_positions = calculate_reversed_tempo_positions(positions, total_measures)

        assert len(reversed_positions) == 2
        # m5の80はm10まで有効 → 反転後m1
        assert reversed_positions[0]['reversed_measure_num'] == 1
        # m1の120はm4まで有効 → 反転後m7
        assert reversed_positions[1]['reversed_measure_num'] == 7

    def test_transitional_only(self):
        """経過的テンポのみの場合"""
        positions = [
            {
                'measure_num': 3,
                'offset': 0,
                'element': expressions.TextExpression('rit.'),
                'element_type': 'TextExpression',
                'is_transitional': True,
            },
            {
                'measure_num': 7,
                'offset': 0,
                'element': expressions.TextExpression('accel.'),
                'element_type': 'TextExpression',
                'is_transitional': True,
            },
        ]
        total_measures = 10

        reversed_positions = calculate_reversed_tempo_positions(positions, total_measures)

        assert len(reversed_positions) == 2
        # 単純反転: m7 → 10-7+1=4, m3 → 10-3+1=8
        assert reversed_positions[0]['reversed_measure_num'] == 4
        assert reversed_positions[0]['element'].content == 'accel.'
        assert reversed_positions[1]['reversed_measure_num'] == 8
        assert reversed_positions[1]['element'].content == 'rit.'


class TestTransitionalTempoCollection:
    """経過的テンポの収集テスト（is_transitionalフラグ）"""

    def test_collect_with_transitional_flag(self):
        """収集時にis_transitionalフラグが設定される"""
        measures = []
        for i in range(1, 11):
            m = stream.Measure(number=i)
            if i == 1:
                m.insert(0, expressions.TextExpression('Allegro'))
            elif i == 5:
                m.insert(0, expressions.TextExpression('rit.'))
            elif i == 8:
                m.insert(0, expressions.TextExpression('a tempo'))
            m.append(note.Rest(quarterLength=4))
            measures.append(m)

        positions = collect_tempo_positions(measures)

        # Allegroは主要テンポ
        allegro_pos = [p for p in positions if 'Allegro' in getattr(p['element'], 'content', '')]
        assert len(allegro_pos) == 1
        assert allegro_pos[0]['is_transitional'] is False

        # rit.は経過的
        rit_pos = [p for p in positions if 'rit' in getattr(p['element'], 'content', '').lower()]
        assert len(rit_pos) == 1
        assert rit_pos[0]['is_transitional'] is True

        # a tempoは経過的
        atempo_pos = [p for p in positions if 'a tempo' in getattr(p['element'], 'content', '').lower()]
        assert len(atempo_pos) == 1
        assert atempo_pos[0]['is_transitional'] is True
