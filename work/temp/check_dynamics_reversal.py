#!/usr/bin/env python3
"""強弱記号の反転を検証するスクリプト"""

from music21 import converter
from pathlib import Path

def check_dynamics(file_path: str, label: str):
    """ファイルから強弱記号の位置を抽出して表示"""
    print(f"\n{'='*60}")
    print(f"{label}: {Path(file_path).name}")
    print(f"{'='*60}")

    score = converter.parse(file_path)

    for i, part in enumerate(score.parts):
        print(f"\nPart {i+1}:")
        for j, measure in enumerate(part.getElementsByClass('Measure')):
            measure_num = j + 1
            duration = measure.duration.quarterLength

            # 強弱記号を抽出
            dynamics = measure.getElementsByClass('Dynamic')
            if dynamics:
                print(f"  小節 {measure_num} (duration={duration}):")
                for dyn in dynamics:
                    print(f"    - {dyn.value} at offset={dyn.offset}")

if __name__ == '__main__':
    # 反転前のファイルをチェック
    original = 'work/inbox/test-dynamics.xml'
    check_dynamics(original, "反転前")

    # 反転後のファイルをチェック
    reversed_file = 'work/outbox/test-dynamics_rev.xml'
    if Path(reversed_file).exists():
        check_dynamics(reversed_file, "反転後")
    else:
        print(f"\n[WARNING] 反転後のファイルが見つかりません: {reversed_file}")
        print("先に reverse_score.py を実行してください。")
