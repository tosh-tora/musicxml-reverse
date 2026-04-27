"""追加Spanner要素（Slur, Trill, Tremolo, Glissando等）のテスト"""
from music21 import stream, note, spanner, converter
import sys

def create_test_with_slur():
    """Slurを含むテストスコア"""
    s = stream.Score()
    p = stream.Part(id='P1')
    m = stream.Measure(number=1)
    
    notes = [
        note.Note('C4', quarterLength=1.0),
        note.Note('D4', quarterLength=1.0),
        note.Note('E4', quarterLength=1.0),
        note.Note('F4', quarterLength=1.0),
    ]
    
    for n in notes:
        m.append(n)
    
    # Slur: C4 -> D4 -> E4
    sl = spanner.Slur(notes[0:3])
    p.append(m)
    p.insert(0, sl)
    
    s.append(p)
    return s

def create_test_with_glissando():
    """Glissandoを含むテストスコア"""
    s = stream.Score()
    p = stream.Part(id='P1')
    m = stream.Measure(number=1)
    
    n1 = note.Note('C4', quarterLength=2.0)
    n2 = note.Note('G4', quarterLength=2.0)
    m.append([n1, n2])
    
    # Glissando: C4 -> G4
    gl = spanner.Glissando(n1, n2)
    p.append(m)
    p.insert(0, gl)
    
    s.append(p)
    return s

def analyze_spanners(score, label):
    """Spanner情報を分析"""
    print(f"\n=== {label} ===")
    for part in score.parts:
        print(f"Part {part.id}:")
        spanner_count = {'Slur': 0, 'Glissando': 0, 'Trill': 0}
        
        for sp in part.spannerBundle:
            sp_type = type(sp).__name__
            if sp_type in spanner_count:
                spanner_count[sp_type] += 1
            
            elements = list(sp.getSpannedElements())
            if elements:
                first_note = elements[0].nameWithOctave if hasattr(elements[0], 'nameWithOctave') else '?'
                last_note = elements[-1].nameWithOctave if hasattr(elements[-1], 'nameWithOctave') else '?'
                print(f"  {sp_type}: {first_note} -> {last_note} ({len(elements)} elements)")
        
        for sp_type, count in spanner_count.items():
            if count == 0:
                print(f"  {sp_type}: 0")

print("Additional Spanner Elements Test\n")
print("=" * 60)

# Slurのテスト
print("\n## Test 1: Slur")
score_slur = create_test_with_slur()
analyze_spanners(score_slur, "Original")

score_slur.write('musicxml', 'work/test_slur_original.musicxml')
loaded_slur = converter.parse('work/test_slur_original.musicxml')
analyze_spanners(loaded_slur, "After MusicXML roundtrip")

# Glissandoのテスト
print("\n" + "=" * 60)
print("\n## Test 2: Glissando")
score_gliss = create_test_with_glissando()
analyze_spanners(score_gliss, "Original")

score_gliss.write('musicxml', 'work/test_glissando_original.musicxml')
loaded_gliss = converter.parse('work/test_glissando_original.musicxml')
analyze_spanners(loaded_gliss, "After MusicXML roundtrip")

print("\n" + "=" * 60)
print("\nTest files created:")
print("  - work/test_slur_original.musicxml")
print("  - work/test_glissando_original.musicxml")
