#!/usr/bin/env python3
"""ダイナミクスウェッジ（Crescendo/Diminuendo）の反転処理をデバッグするスクリプト"""

from music21 import converter, stream, dynamics
from pathlib import Path
from reverse_score import reverse_score


def analyze_dynamics_wedges(score: stream.Score, label: str):
    """ダイナミクスウェッジの詳細を解析"""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")

    total_wedges = 0
    single_element_wedges = 0
    multi_element_wedges = 0

    for part_idx, part in enumerate(score.parts):
        spanners = list(part.spannerBundle)
        dynamics_wedges = [sp for sp in spanners
                          if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]

        if not dynamics_wedges:
            continue

        print(f"\nPart {part_idx + 1}:")
        for sp in dynamics_wedges:
            spanned = list(sp.getSpannedElements())
            sp_type = sp.__class__.__name__
            total_wedges += 1

            if len(spanned) < 2:
                single_element_wedges += 1
                marker = " [WARNING: < 2 elements]"
            else:
                multi_element_wedges += 1
                marker = ""

            print(f"  {sp_type}: {len(spanned)} elements{marker}")

            # 要素の詳細を表示
            for elem in spanned:
                # 要素が属する小節を探す
                measure_num = None
                for measure in part.getElementsByClass(stream.Measure):
                    if elem in measure.notesAndRests:
                        measure_num = measure.number
                        break

                pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'Rest'
                print(f"    - {pitch_str} (measure {measure_num}, offset={elem.offset:.2f})")

    print(f"\n{'='*60}")
    print(f"Summary: {label}")
    print(f"  Total wedges: {total_wedges}")
    print(f"  Single-element wedges: {single_element_wedges}")
    print(f"  Multi-element wedges: {multi_element_wedges}")
    print(f"{'='*60}")


def main():
    """メイン処理"""
    # 実際のファイルを読み込む
    input_path = Path("work/inbox/威風堂々ラスト - コピー.musicxml")

    if not input_path.exists():
        print(f"File not found: {input_path}")
        return

    print(f"Loading: {input_path.name}")
    original_score = converter.parse(str(input_path))

    # 反転前の解析
    analyze_dynamics_wedges(original_score, "BEFORE Reversal")

    # 反転処理
    print(f"\n{'='*60}")
    print("Performing reversal...")
    print(f"{'='*60}")
    reversed_score = reverse_score(original_score)

    # 反転後の解析
    analyze_dynamics_wedges(reversed_score, "AFTER Reversal")

    # 出力ファイルに保存
    output_path = Path("work/debug_dynamics_reversal.xml")
    reversed_score.write('musicxml', fp=str(output_path))
    print(f"\nReversed score saved to: {output_path}")


if __name__ == '__main__':
    main()
