#!/usr/bin/env python3
"""
連桁（beam）の保存をテストする
"""
from pathlib import Path
import tempfile
from music21 import converter, stream, note

from reverse_score import reverse_score


def test_beam_preservation_simple():
    """単純な16分音符の連桁が保存されるかテスト"""
    print("=== 単純な連桁テスト ===")

    # テストスコアを作成: 4つの16分音符をbeamでつなぐ
    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()

    # 16分音符4つ
    n1 = note.Note('C4', quarterLength=0.25)
    n2 = note.Note('D4', quarterLength=0.25)
    n3 = note.Note('E4', quarterLength=0.25)
    n4 = note.Note('F4', quarterLength=0.25)

    # 連桁を設定
    n1.beams.fill('16th', type='start')
    n2.beams.fill('16th', type='continue')
    n3.beams.fill('16th', type='continue')
    n4.beams.fill('16th', type='stop')

    for n in [n1, n2, n3, n4]:
        m.append(n)

    p.append(m)
    s.append(p)

    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(suffix='.mxl', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        s.write('mxl', tmp_path)

    print(f"元ファイル: {tmp_path}")
    print(f"元の連桁情報:")
    for i, n in enumerate([n1, n2, n3, n4], 1):
        print(f"  Note {i}: {n.beams}")

    # 反転処理
    reversed_score_obj = reverse_score(s)

    # 反転後のファイルに保存
    reversed_path = tmp_path.with_name(tmp_path.stem + '_reversed.mxl')
    reversed_score_obj.write('mxl', reversed_path)

    print(f"\n反転後: {reversed_path}")
    reversed_notes = list(reversed_score_obj.flatten().notes)

    print(f"反転後の連桁情報:")
    for i, n in enumerate(reversed_notes, 1):
        print(f"  Note {i}: {n.beams}")

    # 検証
    # 反転後は順序が逆になり、連桁の start/stop も反転される
    # Original: C4(start) - D4(continue) - E4(continue) - F4(stop)
    # Reversed: F4(start) - E4(continue) - D4(continue) - C4(stop)

    beams_after = [n.beams for n in reversed_notes]

    # 少なくとも連桁が失われていないことを確認
    assert all(len(b.beamsList) > 0 for b in beams_after), "連桁が失われています！"

    # start/stop が適切に反転されているか確認
    assert beams_after[0].beamsList[0].type == 'start', f"最初の音符のbeamは'start'であるべき: {beams_after[0].beamsList[0].type}"
    assert beams_after[-1].beamsList[0].type == 'stop', f"最後の音符のbeamは'stop'であるべき: {beams_after[-1].beamsList[0].type}"

    print("\nOK: 連桁が正しく保存されています！")

    # クリーンアップ
    tmp_path.unlink()
    reversed_path.unlink()


def test_beam_preservation_mixed():
    """混在した音価（8分音符と16分音符）の連桁テスト"""
    print("\n=== 混在した連桁テスト ===")

    # テストスコア: 16分、16分、8分（すべて連桁）
    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()

    n1 = note.Note('C4', quarterLength=0.25)
    n2 = note.Note('D4', quarterLength=0.25)
    n3 = note.Note('E4', quarterLength=0.5)

    # 16分、16分、8分の連桁パターン
    n1.beams.fill('16th', type='start')
    n2.beams.append('continue')
    n2.beams.append('stop')
    n3.beams.fill('eighth', type='stop')

    for n in [n1, n2, n3]:
        m.append(n)

    p.append(m)
    s.append(p)

    with tempfile.NamedTemporaryFile(suffix='.mxl', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        s.write('mxl', tmp_path)

    print(f"元ファイル: {tmp_path}")
    print(f"元の連桁情報:")
    for i, n in enumerate([n1, n2, n3], 1):
        print(f"  Note {i}: {n.beams}")

    # 反転処理
    reversed_score_obj = reverse_score(s)

    # 反転後のファイルに保存
    reversed_path = tmp_path.with_name(tmp_path.stem + '_reversed.mxl')
    reversed_score_obj.write('mxl', reversed_path)

    print(f"\n反転後: {reversed_path}")
    reversed_notes = list(reversed_score_obj.flatten().notes)

    print(f"反転後の連桁情報:")
    for i, n in enumerate(reversed_notes, 1):
        print(f"  Note {i}: {n.beams}")

    # 検証: 連桁が失われていないこと
    beams_after = [n.beams for n in reversed_notes]
    assert all(len(b.beamsList) > 0 for b in beams_after), "連桁が失われています！"

    print("\nOK: 混在した連桁も正しく保存されています！")

    # クリーンアップ
    tmp_path.unlink()
    reversed_path.unlink()


if __name__ == "__main__":
    test_beam_preservation_simple()
    test_beam_preservation_mixed()
    print("\n=== すべてのテストが成功しました ===")
