#!/usr/bin/env python3
"""強弱記号付きのテストMusicXMLを作成"""

from music21 import stream, note, dynamics, meter, clef

# スコアを作成
s = stream.Score()
p = stream.Part()

# 拍子記号: 4/4
ts = meter.TimeSignature('4/4')
p.insert(0, ts)
p.insert(0, clef.TrebleClef())

# 小節1: 4分音符4つ、1拍目にf（フォルテ）
m1 = stream.Measure(number=1)
m1.insert(0, dynamics.Dynamic('f'))  # 1拍目にフォルテ
m1.append(note.Note('C4', quarterLength=1))
m1.append(note.Note('D4', quarterLength=1))
m1.append(note.Note('E4', quarterLength=1))
m1.append(note.Note('F4', quarterLength=1))
p.append(m1)

# 小節2: 4分音符4つ、3拍目にp（ピアノ）
m2 = stream.Measure(number=2)
m2.append(note.Note('G4', quarterLength=1))
m2.append(note.Note('A4', quarterLength=1))
m2.insert(2.0, dynamics.Dynamic('p'))  # 3拍目にピアノ
m2.append(note.Note('B4', quarterLength=1))
m2.append(note.Note('C5', quarterLength=1))
p.append(m2)

s.append(p)

# 保存
output_path = 'work/inbox/test-dynamics.xml'
s.write('musicxml', fp=output_path)
print(f"Created: {output_path}")

# 確認
print("\n作成した内容:")
for measure in p.getElementsByClass('Measure'):
    print(f"\n小節{measure.number} (長さ: {measure.duration.quarterLength}拍):")
    for element in measure:
        offset = element.offset
        class_name = element.__class__.__name__
        if class_name == 'Note':
            print(f"  offset={offset:.2f}: {element.nameWithOctave} (duration={element.duration.quarterLength})")
        elif 'Dynamic' in class_name:
            print(f"  offset={offset:.2f}: {class_name}({element.value})")
