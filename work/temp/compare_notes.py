#!/usr/bin/env python3
"""
MusicXML 音楽データのみ比較（メタデータ除外）
"""
from music21 import converter
from pathlib import Path

def compare_musical_content(original_path: Path, restored_path: Path):
    """音楽データのみを比較（ピッチ・リズム・小節数など）"""
    print("=== music21で音楽データを比較 ===\n")

    # スコアを読み込み
    original = converter.parse(str(original_path))
    restored = converter.parse(str(restored_path))

    # 基本情報
    print(f"元ファイル: {original_path.name}")
    print(f"  パート数: {len(original.parts)}")
    print(f"  小節数: {len(original.parts[0].getElementsByClass('Measure'))}")

    print(f"\n再反転後: {restored_path.name}")
    print(f"  パート数: {len(restored.parts)}")
    print(f"  小節数: {len(restored.parts[0].getElementsByClass('Measure'))}")

    # 各パートを比較
    print("\n=== パート別詳細比較 ===")
    for i, (orig_part, rest_part) in enumerate(zip(original.parts, restored.parts)):
        print(f"\nパート {i+1}:")
        print(f"  元: {orig_part.partName or 'Unknown'}")
        print(f"  再反転: {rest_part.partName or 'Unknown'}")

        orig_measures = orig_part.getElementsByClass('Measure')
        rest_measures = rest_part.getElementsByClass('Measure')

        print(f"  小節数: 元={len(orig_measures)}, 再反転={len(rest_measures)}")

        # 最初の5小節を詳細比較
        print(f"\n  最初の5小節の音符比較:")
        for m_idx in range(min(5, len(orig_measures), len(rest_measures))):
            orig_m = list(orig_measures)[m_idx]
            rest_m = list(rest_measures)[m_idx]

            orig_notes = list(orig_m.flatten().notesAndRests)
            rest_notes = list(rest_m.flatten().notesAndRests)

            print(f"    小節 {m_idx+1}: 元={len(orig_notes)}音, 再反転={len(rest_notes)}音", end="")

            # 音符のピッチとリズムを比較
            if len(orig_notes) == len(rest_notes):
                def get_pitches(n):
                    """音符またはコードからピッチを取得"""
                    if n.isRest:
                        return []
                    elif n.isChord:
                        return [p.nameWithOctave for p in n.pitches]
                    else:
                        return [n.pitch.nameWithOctave]

                pitch_match = all(
                    get_pitches(on) == get_pitches(rn)
                    for on, rn in zip(orig_notes, rest_notes)
                )
                duration_match = all(
                    abs(on.duration.quarterLength - rn.duration.quarterLength) < 0.001
                    for on, rn in zip(orig_notes, rest_notes)
                )
                offset_match = all(
                    abs(on.offset - rn.offset) < 0.001
                    for on, rn in zip(orig_notes, rest_notes)
                )

                if pitch_match and duration_match and offset_match:
                    print(" -> [OK] 完全一致")
                else:
                    print(f" -> [差異] pitch={pitch_match}, dur={duration_match}, offset={offset_match}")
                    # 詳細表示
                    for j, (on, rn) in enumerate(zip(orig_notes, rest_notes)):
                        if get_pitches(on) != get_pitches(rn):
                            print(f"      音符{j+1}: {get_pitches(on)} -> {get_pitches(rn)}")
                        if abs(on.duration.quarterLength - rn.duration.quarterLength) > 0.001:
                            print(f"      音価{j+1}: {on.duration.quarterLength} -> {rn.duration.quarterLength}")
                        if abs(on.offset - rn.offset) > 0.001:
                            print(f"      オフセット{j+1}: {on.offset} -> {rn.offset}")
            else:
                print(" -> [差異] 音符数が不一致")

        # 全小節の音符数合計を比較
        total_orig = sum(len(list(m.flatten().notesAndRests)) for m in orig_measures)
        total_rest = sum(len(list(m.flatten().notesAndRests)) for m in rest_measures)
        print(f"\n  全小節合計: 元={total_orig}音, 再反転={total_rest}音")

def main():
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    restored = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    if not original.exists() or not restored.exists():
        print("エラー: ファイルが見つかりません")
        return

    compare_musical_content(original, restored)

if __name__ == "__main__":
    main()
