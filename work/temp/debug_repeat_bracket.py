"""RepeatBracketの反転処理をデバッグ"""
from music21 import stream, note, spanner, converter
import sys
sys.path.insert(0, '.')

# reverse_score.pyを読み込んで一時的にデバッグ出力を追加
import reverse_score

# オリジナルのreverse_part関数を保存
original_reverse_part = reverse_score.reverse_part

def debug_reverse_part(part, report=None):
    """デバッグ情報を出力するreverse_part"""
    print("\n[DEBUG] Starting reverse_part()")
    
    measures = list(part.getElementsByClass(stream.Measure))
    print(f"[DEBUG] Found {len(measures)} measures")
    
    print(f"[DEBUG] Spanners in original part:")
    for sp in part.spannerBundle:
        sp_type = type(sp).__name__
        elements = list(sp.getSpannedElements())
        elem_types = [type(e).__name__ for e in elements]
        print(f"  {sp_type}: {elem_types}")
        
        if isinstance(elements[0], stream.Measure):
            print(f"    -> Measure-based spanner detected!")
            measure_numbers = [m.number for m in elements]
            print(f"    -> Measure numbers: {measure_numbers}")
    
    # オリジナルの関数を呼び出し
    result = original_reverse_part(part, report)
    
    print(f"\n[DEBUG] Spanners in reversed part:")
    for sp in result.spannerBundle:
        sp_type = type(sp).__name__
        elements = list(sp.getSpannedElements())
        elem_types = [type(e).__name__ for e in elements]
        print(f"  {sp_type}: {elem_types}")
    
    return result

# 関数を差し替え
reverse_score.reverse_part = debug_reverse_part

# テストスコア作成
s = stream.Score()
p = stream.Part(id='P1')

m1 = stream.Measure(number=1)
m1.append(note.Note('C4', quarterLength=4.0))

m2 = stream.Measure(number=2)
m2.append(note.Note('D4', quarterLength=4.0))

p.append([m1, m2])

# RepeatBracket
rb = spanner.RepeatBracket([m1, m2], number=1)
p.insert(0, rb)

s.append(p)

print("Original score:")
for sp in s.parts[0].spannerBundle:
    print(f"  {type(sp).__name__}")

# MusicXML roundtrip
s.write('musicxml', 'work/test_rb_debug.musicxml')
loaded = converter.parse('work/test_rb_debug.musicxml')

print("\nAfter MusicXML roundtrip:")
for sp in loaded.parts[0].spannerBundle:
    print(f"  {type(sp).__name__}")

# 反転
print("\n" + "=" * 60)
reversed_part = debug_reverse_part(loaded.parts[0])

print("\n" + "=" * 60)
print("\nFinal spanners:")
for sp in reversed_part.spannerBundle:
    print(f"  {type(sp).__name__}")
