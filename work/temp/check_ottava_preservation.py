#!/usr/bin/env python3
"""
Ottava spanner の保存・復元状況を確認
"""
from music21 import converter
from music21.spanner import Ottava
from pathlib import Path

def check_ottava_preservation():
    """Ottavaが正しく保存・復元されているか確認"""
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    restored = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    print("=== Ottava Spanner の保存状況確認 ===\n")

    orig_score = converter.parse(str(original))
    rest_score = converter.parse(str(restored))

    for i, (orig_part, rest_part) in enumerate(zip(orig_score.parts, rest_score.parts)):
        print(f"パート {i+1}: {orig_part.partName}")

        orig_ottavas = [sp for sp in orig_part.spannerBundle if isinstance(sp, Ottava)]
        rest_ottavas = [sp for sp in rest_part.spannerBundle if isinstance(sp, Ottava)]

        print(f"  元ファイル: {len(orig_ottavas)} 個のOttava")
        for j, ott in enumerate(orig_ottavas):
            elems = list(ott.getSpannedElements())
            print(f"    Ottava {j+1}:")
            print(f"      type: {ott.type}")
            print(f"      transposing: {ott.transposing}")
            print(f"      placement: {ott.placement}")
            print(f"      対象音符: {len(elems)} 個")
            if elems:
                first_elem = elems[0]
                last_elem = elems[-1]
                print(f"        開始: 小節{first_elem.measureNumber}, offset={first_elem.offset}")
                print(f"        終了: 小節{last_elem.measureNumber}, offset={last_elem.offset}")

        print(f"\n  再反転後: {len(rest_ottavas)} 個のOttava")
        for j, ott in enumerate(rest_ottavas):
            elems = list(ott.getSpannedElements())
            print(f"    Ottava {j+1}:")
            print(f"      type: {ott.type}")
            print(f"      transposing: {ott.transposing}")
            print(f"      placement: {ott.placement}")
            print(f"      対象音符: {len(elems)} 個")
            if elems:
                first_elem = elems[0]
                last_elem = elems[-1]
                print(f"        開始: 小節{first_elem.measureNumber}, offset={first_elem.offset}")
                print(f"        終了: 小節{last_elem.measureNumber}, offset={last_elem.offset}")

        print()

if __name__ == "__main__":
    check_ottava_preservation()
