"""reverse_score.pyを使ったSpanner反転テスト"""
from music21 import stream, note, spanner, converter
import sys
sys.path.insert(0, '.')
from reverse_score import reverse_part

def create_test_with_multiple_spanners():
    """複数のSpannerを含むテストスコア"""
    s = stream.Score()
    p = stream.Part(id='P1')
    
    # Measure 1: Slur
    m1 = stream.Measure(number=1)
    notes_m1 = [
        note.Note('C4', quarterLength=1.0),
        note.Note('D4', quarterLength=1.0),
        note.Note('E4', quarterLength=1.0),
        note.Note('F4', quarterLength=1.0),
    ]
    for n in notes_m1:
        m1.append(n)
    
    # Slur: C4 -> D4 -> E4
    sl = spanner.Slur(notes_m1[0:3])
    p.insert(0, sl)
    
    # Measure 2: Glissando
    m2 = stream.Measure(number=2)
    notes_m2 = [
        note.Note('G4', quarterLength=2.0),
        note.Note('C5', quarterLength=2.0),
    ]
    for n in notes_m2:
        m2.append(n)
    
    # Glissando: G4 -> C5
    gl = spanner.Glissando(notes_m2[0], notes_m2[1])
    p.insert(0, gl)
    
    p.append([m1, m2])
    s.append(p)
    return s

def analyze_spanners(score, label):
    """Spanner情報を詳細分析"""
    print(f"\n=== {label} ===")
    for part in score.parts:
        print(f"Part {part.id}:")
        for measure in part.getElementsByClass(stream.Measure):
            print(f"  Measure {measure.number}:")
            notes_in_measure = list(measure.flatten().notes)
            for n in notes_in_measure:
                print(f"    {n.nameWithOctave} offset={n.offset}")
        
        print(f"  Spanners:")
        for sp in part.spannerBundle:
            sp_type = type(sp).__name__
            elements = list(sp.getSpannedElements())
            if elements:
                note_names = [e.nameWithOctave if hasattr(e, 'nameWithOctave') else '?' 
                             for e in elements]
                print(f"    {sp_type}: {' -> '.join(note_names)}")

print("Spanner Reversal Test with reverse_score.py\n")
print("=" * 60)

# テストスコア作成
original = create_test_with_multiple_spanners()
analyze_spanners(original, "Original")

# MusicXML経由でロード
original.write('musicxml', 'work/test_multi_spanner_orig.musicxml')
loaded = converter.parse('work/test_multi_spanner_orig.musicxml')
analyze_spanners(loaded, "After MusicXML roundtrip (before reversal)")

# reverse_score.py で反転
print("\n" + "=" * 60)
print("Reversing with reverse_part()...")
reversed_part = reverse_part(loaded.parts[0])
reversed_score = stream.Score()
reversed_score.append(reversed_part)
analyze_spanners(reversed_score, "After reverse_part()")

# 反転後のMusicXML保存・再読み込み
reversed_score.write('musicxml', 'work/test_multi_spanner_reversed.musicxml')
reloaded = converter.parse('work/test_multi_spanner_reversed.musicxml')
analyze_spanners(reloaded, "After reversed MusicXML roundtrip")

print("\n" + "=" * 60)
print("\nValidation:")
print("Expected after reversal:")
print("  Measure 1: G4 -> C5 (Glissando from original M2)")
print("  Measure 2: C4 -> D4 -> E4 -> F4 (Slur from original M1)")

# 検証
all_ok = True
for part in reloaded.parts:
    spanner_types = [type(sp).__name__ for sp in part.spannerBundle]
    
    if 'Slur' not in spanner_types:
        print("\n[FAIL] Slur is missing after reversal")
        all_ok = False
    
    if 'Glissando' not in spanner_types:
        print("\n[FAIL] Glissando is missing after reversal")
        all_ok = False

if all_ok and len(spanner_types) >= 2:
    print("\n[PASS] All spanners preserved after reversal")
else:
    print(f"\n[FAIL] Some spanners were lost (found: {spanner_types})")

