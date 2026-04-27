"""RepeatBracketの構造を調査"""
from music21 import stream, note, spanner

s = stream.Score()
p = stream.Part()

m1 = stream.Measure(number=1)
m1.append(note.Note('C4', quarterLength=4.0))

m2 = stream.Measure(number=2)
m2.append(note.Note('D4', quarterLength=4.0))

p.append([m1, m2])

# RepeatBracket: 小節を直接参照
rb = spanner.RepeatBracket([m1, m2], number=1)
p.insert(0, rb)

s.append(p)

print("RepeatBracket structure:")
print(f"RepeatBracket type: {type(rb)}")
print(f"Spanned elements: {rb.getSpannedElements()}")
print(f"Number of elements: {len(list(rb.getSpannedElements()))}")

for elem in rb.getSpannedElements():
    print(f"  Element type: {type(elem).__name__}")
    if hasattr(elem, 'number'):
        print(f"    Measure number: {elem.number}")
