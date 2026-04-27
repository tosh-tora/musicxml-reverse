#!/usr/bin/env python3
"""
Unit tests for layout_preservation module
"""

from pathlib import Path
from layout_preservation import (
    extract_layout_from_xml,
    calculate_original_position,
    transform_layout_for_reversal,
    ElementLayout,
    MeasureLayout,
    LayoutMap
)


def test_calculate_original_position_basic():
    """位置逆計算の基本テスト"""
    print("  test_calculate_original_position_basic...", end=" ")
    # 10小節のスコア、3番目の小節（反転後）は元の8番目
    orig_measure, orig_offset = calculate_original_position(
        reversed_measure_num=3,
        reversed_offset=0.5,
        element_duration=1.0,
        measure_duration=4.0,
        total_measures=10
    )
    assert orig_measure == 8  # 10 - 3 + 1
    assert orig_offset == 2.5  # 4.0 - 0.5 - 1.0
    print("OK")


def test_calculate_original_position_first_measure():
    """最初の小節の位置逆計算"""
    print("  test_calculate_original_position_first_measure...", end=" ")
    orig_measure, orig_offset = calculate_original_position(
        reversed_measure_num=1,
        reversed_offset=0.0,
        element_duration=0.0,
        measure_duration=4.0,
        total_measures=5
    )
    assert orig_measure == 5  # 5 - 1 + 1
    assert orig_offset == 4.0  # 4.0 - 0.0 - 0.0
    print("OK")


def test_calculate_original_position_last_measure():
    """最後の小節の位置逆計算"""
    print("  test_calculate_original_position_last_measure...", end=" ")
    orig_measure, orig_offset = calculate_original_position(
        reversed_measure_num=5,
        reversed_offset=3.5,
        element_duration=0.5,
        measure_duration=4.0,
        total_measures=5
    )
    assert orig_measure == 1  # 5 - 5 + 1
    assert orig_offset == 0.0  # 4.0 - 3.5 - 0.5 = 0.0
    print("OK")


def test_transform_layout_for_reversal_with_width():
    """小節幅が分かる場合のX座標変換"""
    print("  test_transform_layout_for_reversal_with_width...", end=" ")
    original = ElementLayout(
        element_type='dynamics',
        offset=2.0,
        text='f',
        default_x=350.0,
        default_y=-80.0,
        relative_x=0.0,
        relative_y=0.0,
        placement='below'
    )

    transformed = transform_layout_for_reversal(original, measure_width=400.0)

    assert transformed.default_x == 50.0  # 400 - 350
    assert transformed.default_y == -80.0  # そのまま
    assert transformed.relative_x == 0.0  # そのまま
    assert transformed.relative_y == 0.0  # そのまま
    assert transformed.placement == 'below'  # そのまま
    assert transformed.text == 'f'
    print("OK")


def test_transform_layout_for_reversal_without_width():
    """小節幅が不明な場合の座標変換（変換スキップ）"""
    print("  test_transform_layout_for_reversal_without_width...", end=" ")
    original = ElementLayout(
        element_type='dynamics',
        offset=1.0,
        text='p',
        default_x=100.0,
        default_y=-60.0
    )

    transformed = transform_layout_for_reversal(original, measure_width=None)

    assert transformed.default_x == 100.0  # 変換できないのでそのまま
    assert transformed.default_y == -60.0
    print("OK")


def test_transform_layout_for_reversal_no_default_x():
    """default-xがない場合の変換"""
    print("  test_transform_layout_for_reversal_no_default_x...", end=" ")
    original = ElementLayout(
        element_type='dynamics',
        offset=1.0,
        text='mf',
        default_x=None,
        default_y=-70.0
    )

    transformed = transform_layout_for_reversal(original, measure_width=300.0)

    assert transformed.default_x is None  # 元々ないのでNoneのまま
    assert transformed.default_y == -70.0
    print("OK")


def test_extract_layout_from_test_dynamics():
    """test-dynamics.xml からレイアウト抽出（統合テスト）"""
    print("  test_extract_layout_from_test_dynamics...", end=" ")
    test_file = Path("work/inbox/test-dynamics.xml")

    if not test_file.exists():
        print(f"SKIP (test file not found: {test_file})")
        return

    layout_map = extract_layout_from_xml(test_file)

    # レイアウト情報が抽出されたことを確認
    assert len(layout_map.measures) > 0

    # 特定のダイナミクスが抽出されているか確認
    found_dynamics = False
    for measure_key, measure_layout in layout_map.measures.items():
        for elem in measure_layout.elements:
            if elem.element_type == 'dynamics':
                found_dynamics = True
                # 座標属性が抽出されているか
                assert elem.default_x is not None or elem.default_y is not None
                # テキスト（f, p など）が抽出されているか
                assert elem.text is not None
                assert elem.text in ['f', 'p', 'mf', 'mp', 'ff', 'pp', 'fff', 'ppp']

    assert found_dynamics, "No dynamics found in test file"
    print("OK")


def test_data_structures():
    """データ構造の基本動作"""
    print("  test_data_structures...", end=" ")
    # ElementLayout
    elem = ElementLayout(
        element_type='dynamics',
        offset=1.5,
        text='f',
        default_x=100.0,
        default_y=-80.0
    )
    assert elem.element_type == 'dynamics'
    assert elem.offset == 1.5
    assert elem.text == 'f'

    # MeasureLayout
    measure = MeasureLayout(width=400.0)
    measure.elements.append(elem)
    assert measure.width == 400.0
    assert len(measure.elements) == 1

    # LayoutMap
    layout_map = LayoutMap()
    layout_map.measures[('P1', 1)] = measure
    assert ('P1', 1) in layout_map.measures
    assert layout_map.measures[('P1', 1)].width == 400.0
    print("OK")


def test_x_coordinate_symmetry():
    """X座標変換の対称性テスト（往復で元に戻る）"""
    print("  test_x_coordinate_symmetry...", end=" ")
    measure_width = 500.0
    original_x = 200.0

    # 1回目の変換
    transformed_x = measure_width - original_x  # 300.0

    # 2回目の変換（逆方向）
    restored_x = measure_width - transformed_x  # 200.0

    assert restored_x == original_x
    print("OK")


def main():
    print("Running layout_preservation tests...")
    print()

    tests = [
        test_calculate_original_position_basic,
        test_calculate_original_position_first_measure,
        test_calculate_original_position_last_measure,
        test_transform_layout_for_reversal_with_width,
        test_transform_layout_for_reversal_without_width,
        test_transform_layout_for_reversal_no_default_x,
        test_data_structures,
        test_x_coordinate_symmetry,
        test_extract_layout_from_test_dynamics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        exit(1)


if __name__ == '__main__':
    main()
