#!/usr/bin/env python3
"""スラーを含むテスト用 MusicXML ファイルを生成する"""

from music21 import stream, note, spanner

# スコアとパートを作成
score = stream.Score()
part = stream.Part()

# 小節1: スラーのある音符
m1 = stream.Measure(number=1)
n1 = note.Note('C4', quarterLength=1.0)
n2 = note.Note('D4', quarterLength=1.0)
n3 = note.Note('E4', quarterLength=1.0)
n4 = note.Note('F4', quarterLength=1.0)
m1.append([n1, n2, n3, n4])

# スラーを追加（最初の2音）
slur1 = spanner.Slur([n1, n2])
m1.insert(0, slur1)

# スラーを追加（後半の2音）
slur2 = spanner.Slur([n3, n4])
m1.insert(0, slur2)

part.append(m1)

# 小節2: 小節をまたぐスラー
m2 = stream.Measure(number=2)
n5 = note.Note('G4', quarterLength=1.0)
n6 = note.Note('A4', quarterLength=1.0)
n7 = note.Note('B4', quarterLength=1.0)
n8 = note.Note('C5', quarterLength=1.0)
m2.append([n5, n6, n7, n8])

# 小節をまたぐスラー（m1のn4 → m2のn5）
slur3 = spanner.Slur([n4, n5])
part.insert(0, slur3)

part.append(m2)

score.append(part)

# ファイルに保存
output_path = 'work/inbox/test-slurs.xml'
score.write('musicxml', fp=output_path)
print(f"作成完了: {output_path}")

# スラーの状態を確認
print("\n=== スラー情報 ===")
for i, sl in enumerate(part.spannerBundle, 1):
    if isinstance(sl, spanner.Slur):
        elements = list(sl.getSpannedElements())
        print(f"Slur {i}: {elements[0].nameWithOctave} → {elements[-1].nameWithOctave}")
