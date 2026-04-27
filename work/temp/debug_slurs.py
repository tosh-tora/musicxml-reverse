"""Debug script to check slur collection"""
from music21 import converter
from pathlib import Path

input_file = Path('work/inbox/威風堂々ラスト_in-Concert_Snare_Drum.mxl')
print(f'Loading: {input_file}')
score = converter.parse(input_file)

part = score.parts[0]
print(f'\nTotal spanners in part: {len(part.spannerBundle)}')

slur_count = 0
for sp in part.spannerBundle:
    if 'Slur' in sp.__class__.__name__:
        slur_count += 1
        spanned = list(sp.getSpannedElements())
        print(f'\nSlur with {len(spanned)} elements:')
        for elem in spanned:
            elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
            print(f'  {elem_type}: offset={elem.offset}, dur={elem.duration.quarterLength}')

print(f'\nTotal slurs: {slur_count}')
