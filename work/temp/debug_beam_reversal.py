#!/usr/bin/env python3
"""
連桁反転処理のデバッグスクリプト
"""
from music21 import stream, note, converter
from reverse_score import reverse_score
import tempfile
from pathlib import Path


def debug_beam_reversal():
    """連桁反転処理を詳細にデバッグ"""
    print("=== 連桁反転デバッグ ===\n")

    # テストスコア作成
    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()

    # 4つの16分音符を作成
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

    print("元のスコア:")
    for i, n in enumerate([n1, n2, n3, n4], 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type if n.beams.beamsList else 'None'}, id={id(n.beams.beamsList[0])}")

    print("\n反転処理実行...")
    reversed_score_obj = reverse_score(s)

    print("\n反転後のスコア（メモリ上）:")
    reversed_notes_memory = list(reversed_score_obj.flatten().notes)
    for i, n in enumerate(reversed_notes_memory, 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type if n.beams.beamsList else 'None'}, id={id(n.beams.beamsList[0])}")

    # ファイルに書き出して再読み込み
    with tempfile.NamedTemporaryFile(suffix='.mxl', delete=False) as tmp:
        tmp_path = Path(tmp.name)
        reversed_score_obj.write('mxl', tmp_path, makeNotation=False)

    print(f"\nファイルに書き出し: {tmp_path}")

    # 読み込んで確認
    s_reloaded = converter.parse(tmp_path)
    reversed_notes_reloaded = list(s_reloaded.flatten().notes)

    print("\nファイルから再読み込み後:")
    for i, n in enumerate(reversed_notes_reloaded, 1):
        print(f"  Note {i} ({n.pitch}): offset={n.offset:.2f}, beams={n.beams.beamsList[0].type if n.beams.beamsList else 'None'}")

    print("\n期待される結果:")
    print("  Note 1 (F4): beam=stop  (元は stop だったが順序が逆)")
    print("  Note 2 (E4): beam=continue")
    print("  Note 3 (D4): beam=continue")
    print("  Note 4 (C4): beam=start (元は start だったが順序が逆)")

    # クリーンアップ
    tmp_path.unlink()


if __name__ == "__main__":
    debug_beam_reversal()
