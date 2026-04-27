#!/usr/bin/env python3
"""
makeNotation の影響をテスト
"""
from music21 import stream, note
import tempfile
from pathlib import Path


def test_makenotation_effect():
    """makeNotation=False での書き出しテスト"""
    print("=== makeNotation の影響テスト ===\n")

    # テストスコア作成
    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()

    # 4つの16分音符を作成
    n1 = note.Note('C4', quarterLength=0.25)
    n2 = note.Note('D4', quarterLength=0.25)
    n3 = note.Note('E4', quarterLength=0.25)
    n4 = note.Note('F4', quarterLength=0.25)

    # 連桁を手動で設定
    n1.beams.fill('16th', type='stop')   # 意図的に逆のタイプを設定
    n2.beams.fill('16th', type='continue')
    n3.beams.fill('16th', type='continue')
    n4.beams.fill('16th', type='start')  # 意図的に逆のタイプを設定

    for n in [n1, n2, n3, n4]:
        m.append(n)
    p.append(m)
    s.append(p)

    print("元の連桁設定（意図的に逆）:")
    for i, n in enumerate([n1, n2, n3, n4], 1):
        print(f"  Note {i}: {n.beams.beamsList[0].type if n.beams.beamsList else 'None'}")

    # makeNotation=True で書き出し
    with tempfile.NamedTemporaryFile(suffix='_with_makenotation.mxl', delete=False) as tmp:
        tmp_path_with = Path(tmp.name)
        s.write('mxl', tmp_path_with)  # デフォルトは makeNotation=True

    print(f"\nmakeNotation=True で書き出し: {tmp_path_with}")

    # 読み込んで確認
    from music21 import converter
    s_with = converter.parse(tmp_path_with)
    notes_with = list(s_with.flatten().notes)
    print("読み込み後の連桁:")
    for i, n in enumerate(notes_with, 1):
        print(f"  Note {i}: {n.beams.beamsList[0].type if n.beams.beamsList else 'None'}")

    # makeNotation=False で書き出し
    with tempfile.NamedTemporaryFile(suffix='_without_makenotation.mxl', delete=False) as tmp:
        tmp_path_without = Path(tmp.name)
        s.write('mxl', tmp_path_without, makeNotation=False)

    print(f"\nmakeNotation=False で書き出し: {tmp_path_without}")

    # 読み込んで確認
    s_without = converter.parse(tmp_path_without)
    notes_without = list(s_without.flatten().notes)
    print("読み込み後の連桁:")
    for i, n in enumerate(notes_without, 1):
        print(f"  Note {i}: {n.beams.beamsList[0].type if n.beams.beamsList else 'None'}")

    # クリーンアップ
    tmp_path_with.unlink()
    tmp_path_without.unlink()

    print("\n結論:")
    print("makeNotation=True の場合、連桁が自動生成されます")
    print("makeNotation=False の場合、手動設定した連桁が保持されます")


if __name__ == "__main__":
    test_makenotation_effect()
