"""すべてのSpanner要素の動作確認"""
from music21 import stream, note, spanner, expressions, converter
import sys
sys.path.insert(0, '.')
from reverse_score import reverse_part

def create_comprehensive_test():
    """様々なSpannerを含む包括的テストスコア"""
    s = stream.Score()
    p = stream.Part(id='P1')
    
    # Measure 1: Slur
    m1 = stream.Measure(number=1)
    notes_m1 = [note.Note(pitch, quarterLength=1.0) for pitch in ['C4', 'D4', 'E4', 'F4']]
    for n in notes_m1:
        m1.append(n)
    sl = spanner.Slur(notes_m1[0:3])
    p.insert(0, sl)
    
    # Measure 2: Glissando
    m2 = stream.Measure(number=2)
    n1 = note.Note('G4', quarterLength=2.0)
    n2 = note.Note('C5', quarterLength=2.0)
    m2.append([n1, n2])
    gl = spanner.Glissando(n1, n2)
    p.insert(0, gl)
    
    # Measure 3: Trill (TrillExtension)
    m3 = stream.Measure(number=3)
    n3 = note.Note('A4', quarterLength=4.0)
    m3.append(n3)
    # music21ではTrillはexpressions.Trillとして処理される
    n3.expressions.append(expressions.Trill())
    
    # Measure 4: RepeatBracket
    m4 = stream.Measure(number=4)
    notes_m4 = [note.Note('B4', quarterLength=2.0), note.Note('C5', quarterLength=2.0)]
    for n in notes_m4:
        m4.append(n)
    
    p.append([m1, m2, m3, m4])
    
    # RepeatBracketを追加（小節4）
    rb = spanner.RepeatBracket(m4, number=1)
    p.insert(0, rb)
    
    s.append(p)
    return s

def analyze_all_elements(score, label):
    """すべてのSpannerと表現記号を分析"""
    print(f"\n=== {label} ===")
    for part in score.parts:
        print(f"Part {part.id}:")
        
        # Spanners
        spanners = {}
        for sp in part.spannerBundle:
            sp_type = type(sp).__name__
            if sp_type not in spanners:
                spanners[sp_type] = []
            elements = list(sp.getSpannedElements())
            if elements:
                if hasattr(elements[0], 'nameWithOctave'):
                    desc = ' -> '.join([e.nameWithOctave for e in elements])
                else:
                    desc = f"{len(elements)} elements"
                spanners[sp_type].append(desc)
        
        if spanners:
            print("  Spanners:")
            for sp_type, descs in sorted(spanners.items()):
                for desc in descs:
                    print(f"    {sp_type}: {desc}")
        
        # Expressions (Trill等)
        expressions_found = {}
        for measure in part.getElementsByClass(stream.Measure):
            for n in measure.flatten().notes:
                if n.expressions:
                    for expr in n.expressions:
                        expr_type = type(expr).__name__
                        if expr_type not in expressions_found:
                            expressions_found[expr_type] = 0
                        expressions_found[expr_type] += 1
        
        if expressions_found:
            print("  Expressions:")
            for expr_type, count in sorted(expressions_found.items()):
                print(f"    {expr_type}: {count}")

print("Comprehensive Spanner Test\n")
print("=" * 60)

# テストスコア作成
original = create_comprehensive_test()
analyze_all_elements(original, "Original")

# MusicXML roundtrip
original.write('musicxml', 'work/test_all_spanners_orig.musicxml')
loaded = converter.parse('work/test_all_spanners_orig.musicxml')
analyze_all_elements(loaded, "After MusicXML roundtrip")

# 反転
print("\n" + "=" * 60)
print("Reversing...")
reversed_part = reverse_part(loaded.parts[0])
reversed_score = stream.Score()
reversed_score.append(reversed_part)
analyze_all_elements(reversed_score, "After reverse_part()")

# 反転後のroundtrip
reversed_score.write('musicxml', 'work/test_all_spanners_reversed.musicxml')
reloaded = converter.parse('work/test_all_spanners_reversed.musicxml')
analyze_all_elements(reloaded, "After reversed MusicXML roundtrip")

print("\n" + "=" * 60)
