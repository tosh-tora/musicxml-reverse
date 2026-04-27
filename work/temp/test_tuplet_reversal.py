"""連符（tuplet）の反転処理テスト"""
from music21 import stream, note, duration, converter
import sys

def create_test_score_with_tuplets():
    """様々な連符を含むテストスコアを作成"""
    s = stream.Score()
    p = stream.Part(id='P1')
    m1 = stream.Measure(number=1)
    
    # 3連符（triplet）
    tuplet3 = []
    for i in range(3):
        n = note.Note('C4', quarterLength=2.0/3)  # 3連符
        tuplet3.append(n)
    m1.append(tuplet3)
    
    m2 = stream.Measure(number=2)
    # 5連符
    tuplet5 = []
    for i in range(5):
        n = note.Note('D4', quarterLength=4.0/5)
        tuplet5.append(n)
    m2.append(tuplet5)
    
    m3 = stream.Measure(number=3)
    # 11連符
    tuplet11 = []
    for i in range(11):
        n = note.Note('E4', quarterLength=4.0/11)
        tuplet11.append(n)
    m3.append(tuplet11)
    
    p.append([m1, m2, m3])
    s.append(p)
    return s

def analyze_tuplets(s, label):
    """連符情報を詳細に分析"""
    print(f"\n=== {label} ===")
    for part in s.parts:
        print(f"Part {part.id}:")
        for measure in part.getElementsByClass('Measure'):
            print(f"  Measure {measure.number}:")
            notes = measure.flatten().notes
            for n in notes:
                if n.duration.tuplets:
                    tuplet_info = []
                    for t in n.duration.tuplets:
                        tuplet_info.append(
                            f"{t.numberNotesActual}:{t.numberNotesNormal} "
                            f"type={t.type}"
                        )
                    print(f"    {n.nameWithOctave} QL={n.quarterLength:.4f} "
                          f"Tuplets={', '.join(tuplet_info)}")
                else:
                    print(f"    {n.nameWithOctave} QL={n.quarterLength:.4f} "
                          f"(no tuplet)")

# テスト実行
print("連符反転テスト開始")
original = create_test_score_with_tuplets()
analyze_tuplets(original, "Original")

# MusicXMLで保存・読み込み（roundtrip）
original.write('musicxml', 'work/test_tuplets_original.musicxml')
loaded = converter.parse('work/test_tuplets_original.musicxml')
analyze_tuplets(loaded, "After MusicXML roundtrip")

# 小節内容を反転
print("\n=== Reversing measure contents ===")
for part in loaded.parts:
    for measure in part.getElementsByClass('Measure'):
        print(f"Reversing measure {measure.number}")
        elements = list(measure.notes)
        print(f"  Found {len(elements)} notes")
        
        # 要素を削除
        for el in elements:
            measure.remove(el)
        
        # 逆順で追加
        for el in reversed(elements):
            measure.insert(0, el)

analyze_tuplets(loaded, "After reversal")

# 反転後のMusicXML保存
loaded.write('musicxml', 'work/test_tuplets_reversed.musicxml')
reloaded = converter.parse('work/test_tuplets_reversed.musicxml')
analyze_tuplets(reloaded, "After reversed MusicXML roundtrip")

print("\n=== Test complete ===")
print("Files created:")
print("  work/test_tuplets_original.musicxml")
print("  work/test_tuplets_reversed.musicxml")
