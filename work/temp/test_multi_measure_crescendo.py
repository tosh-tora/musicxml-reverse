#!/usr/bin/env python3
"""小節をまたぐクレッシェンド・ディミヌエンドの反転テスト"""

from music21 import stream, note, dynamics
from pathlib import Path
from reverse_score import reverse_score


def create_test_score() -> stream.Score:
    """小節をまたぐクレッシェンドを含むテストスコアを作成"""
    score = stream.Score()
    part = stream.Part()

    # 小節1: C4 全音符
    m1 = stream.Measure(number=1)
    m1.append(note.Note('C4', quarterLength=4.0))
    part.append(m1)

    # 小節2: D4 全音符
    m2 = stream.Measure(number=2)
    m2.append(note.Note('D4', quarterLength=4.0))
    part.append(m2)

    # 小節3: E4 全音符
    m3 = stream.Measure(number=3)
    m3.append(note.Note('E4', quarterLength=4.0))
    part.append(m3)

    # 小節4: F4 全音符
    m4 = stream.Measure(number=4)
    m4.append(note.Note('F4', quarterLength=4.0))
    part.append(m4)

    score.append(part)

    # 小節1〜3にまたがるクレッシェンドを追加
    notes_for_cresc = [
        m1.notes[0],
        m2.notes[0],
        m3.notes[0]
    ]
    cresc = dynamics.Crescendo(notes_for_cresc)
    part.insert(0, cresc)

    return score


def check_spanners(score: stream.Score, label: str):
    """スコア内のSpannerを確認"""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")

    for part_idx, part in enumerate(score.parts):
        print(f"\nPart {part_idx + 1}:")
        spanners = list(part.spannerBundle)

        if not spanners:
            print("  Spannerなし")
            continue

        for sp in spanners:
            sp_type = sp.__class__.__name__
            spanned = list(sp.getSpannedElements())
            print(f"  {sp_type}: {len(spanned)} 要素")

            for elem in spanned:
                # 要素が属する小節を探す
                measure_num = None
                for measure in part.getElementsByClass(stream.Measure):
                    if elem in measure.notesAndRests:
                        measure_num = measure.number
                        break

                pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'Rest'
                print(f"    - {pitch_str} (小節{measure_num}, offset={elem.offset})")


def main():
    """メイン処理"""
    # テストスコアを作成
    print("小節をまたぐクレッシェンドのテストケースを作成...")
    original_score = create_test_score()

    # 元のSpannerを確認
    check_spanners(original_score, "反転前のSpanner")

    # ファイルに保存
    work_dir = Path("work")
    work_dir.mkdir(exist_ok=True)

    original_path = work_dir / "multi_measure_crescendo.xml"
    original_score.write('musicxml', fp=str(original_path))
    print(f"\n元のファイル: {original_path}")

    # 反転処理
    print("\n反転処理実行中...")
    reversed_score = reverse_score(original_score)

    # 反転後のSpannerを確認
    check_spanners(reversed_score, "反転後のSpanner")

    # 反転後のファイルを保存
    reversed_path = work_dir / "multi_measure_crescendo_rev.xml"
    reversed_score.write('musicxml', fp=str(reversed_path))
    print(f"\n反転後のファイル: {reversed_path}")

    # 検証
    print("\n" + "="*60)
    print("検証結果")
    print("="*60)

    original_spanners = list(original_score.parts[0].spannerBundle)
    reversed_spanners = list(reversed_score.parts[0].spannerBundle)

    print(f"反転前のSpanner数: {len(original_spanners)}")
    print(f"反転後のSpanner数: {len(reversed_spanners)}")

    if len(original_spanners) != len(reversed_spanners):
        print("\n[ERROR] Spanner count mismatch!")
        return False

    # Crescendo → Diminuendo の変換を確認
    original_cresc = [sp for sp in original_spanners if isinstance(sp, dynamics.Crescendo)]
    reversed_dim = [sp for sp in reversed_spanners if isinstance(sp, dynamics.Diminuendo)]

    print(f"\n反転前のCrescendo数: {len(original_cresc)}")
    print(f"反転後のDiminuendo数: {len(reversed_dim)}")

    if len(original_cresc) != len(reversed_dim):
        print("\n[ERROR] Crescendo -> Diminuendo conversion failed!")
        return False

    print("\n[OK] Test passed: multi-measure crescendo preserved correctly")
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
