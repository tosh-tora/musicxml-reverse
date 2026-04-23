"""reverse_score.py を使った連符反転テスト"""
from music21 import stream, note, converter
import sys
sys.path.insert(0, '.')
from reverse_score import reverse_part

def create_test_score_with_tuplets():
    """様々な連符を含むテストスコアを作成"""
    s = stream.Score()
    p = stream.Part(id='P1')
    
    m1 = stream.Measure(number=1)
    # 3連符（triplet）
    for i in range(3):
        n = note.Note('C4', quarterLength=2.0/3)
        m1.append(n)
    
    m2 = stream.Measure(number=2)
    # 5連符
    for i in range(5):
        n = note.Note('D4', quarterLength=4.0/5)
        m2.append(n)
    
    m3 = stream.Measure(number=3)
    # 11連符
    for i in range(11):
        n = note.Note('E4', quarterLength=4.0/11)
        m3.append(n)
    
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
print("reverse_score.py を使った連符反転テスト")
original = create_test_score_with_tuplets()

# MusicXML経由でロード（music21が連符のtype情報を付与）
original.write('musicxml', 'work/test_tuplets_orig.musicxml')
loaded = converter.parse('work/test_tuplets_orig.musicxml')
analyze_tuplets(loaded, "Original (after MusicXML roundtrip)")

# reverse_score.py でパートを反転
print("\n=== Reversing using reverse_score.py ===")
reversed_part = reverse_part(loaded.parts[0])
reversed_score = stream.Score()
reversed_score.append(reversed_part)
analyze_tuplets(reversed_score, "After reverse_part()")

# 反転後のスコアを保存・再読み込み
reversed_score.write('musicxml', 'work/test_tuplets_reversed_by_script.musicxml')
reloaded = converter.parse('work/test_tuplets_reversed_by_script.musicxml')
analyze_tuplets(reloaded, "After reversed MusicXML roundtrip")

# 結果の検証
print("\n=== Validation ===")
all_ok = True
for part in reloaded.parts:
    for measure in part.getElementsByClass('Measure'):
        notes = list(measure.flatten().notes)
        if not notes:
            continue
        
        # 最初の音符は type=start を持つべき
        first_tuplets = notes[0].duration.tuplets
        if first_tuplets:
            if first_tuplets[0].type != 'start':
                print(f"[FAIL] Measure {measure.number}: first note type is {first_tuplets[0].type}, expected start")
                all_ok = False
        
        # 最後の音符は type=stop を持つべき
        last_tuplets = notes[-1].duration.tuplets
        if last_tuplets:
            if last_tuplets[0].type != 'stop':
                print(f"[FAIL] Measure {measure.number}: last note type is {last_tuplets[0].type}, expected stop")
                all_ok = False

if all_ok:
    print("[PASS] All tuplets reversed correctly")
else:
    print("[FAIL] Tuplet reversal has issues")
    sys.exit(1)
