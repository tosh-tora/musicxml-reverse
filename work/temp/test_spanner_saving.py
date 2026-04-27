#!/usr/bin/env python3
"""Test the spanner reconstruction with saved info"""

from music21 import converter, stream
from pathlib import Path
import copy

input_path = Path("work/inbox/test-slurs.xml")
score = converter.parse(str(input_path))

if not isinstance(score, stream.Score):
    new_score = stream.Score()
    new_score.append(score)
    score = new_score

part = score.parts[0]
measures = list(part.getElementsByClass(stream.Measure))

print("=== Saving Spanner Info (BEFORE modification) ===")
spanner_info = []
for sp in part.spannerBundle:
    spanned_elements_original = list(sp.getSpannedElements())
    if len(spanned_elements_original) < 2:
        continue

    note_positions = []
    for elem in spanned_elements_original:
        for measure in measures:
            if elem in measure.notesAndRests:
                pitch_name = str(elem.pitch) if hasattr(elem, 'pitch') else None
                note_positions.append({
                    'measure_num': measure.number,
                    'offset': elem.offset,
                    'duration': elem.duration.quarterLength,
                    'pitch': pitch_name,
                    'is_rest': elem.isRest
                })
                print(f"  Saved: measure={measure.number}, offset={elem.offset}, pitch={pitch_name}")
                break

    if len(note_positions) == len(spanned_elements_original):
        spanner_info.append({
            'type': sp.__class__,
            'positions': note_positions
        })

print(f"\nSaved {len(spanner_info)} spanners")

# Now reverse
reversed_measures = list(reversed(measures))
new_part = stream.Part()

for i, measure in enumerate(reversed_measures):
    measure_duration = measure.duration.quarterLength
    for element in measure.notesAndRests:
        current_offset = element.offset
        element_duration = element.duration.quarterLength
        new_offset = measure_duration - current_offset - element_duration
        element.offset = max(0, new_offset)

    measure.number = i + 1
    new_part.append(measure)

print("\n=== New Part After Reversal ===")
for measure in new_part.getElementsByClass(stream.Measure):
    print(f"Measure {measure.number}:")
    for note in measure.notesAndRests:
        print(f"  {note.pitch if hasattr(note, 'pitch') else 'Rest'} offset={note.offset}")

# Reconstruct spanners
print("\n=== Reconstructing Spanners ===")
for idx, sp_info in enumerate(spanner_info):
    print(f"\nSpanner {idx+1}:")
    new_spanned_elements = []

    for pos in sp_info['positions']:
        # Calculate reversed measure number
        reversed_measure_num = len(measures) - pos['measure_num'] + 1
        print(f"  Looking for: pitch={pos['pitch']}, orig_measure={pos['measure_num']}, reversed_measure={reversed_measure_num}")

        for new_measure in new_part.getElementsByClass(stream.Measure):
            if new_measure.number == reversed_measure_num:
                measure_duration = new_measure.duration.quarterLength
                reversed_offset = measure_duration - pos['offset'] - pos['duration']
                reversed_offset = max(0, reversed_offset)
                print(f"    Expected offset: {reversed_offset}")

                found = False
                for new_elem in new_measure.notesAndRests:
                    offset_match = abs(new_elem.offset - reversed_offset) < 0.01
                    print(f"      Checking: pitch={new_elem.pitch if hasattr(new_elem, 'pitch') else 'Rest'}, offset={new_elem.offset}, match={offset_match}")
                    if offset_match:
                        if pos['is_rest'] and new_elem.isRest:
                            new_spanned_elements.append(new_elem)
                            print(f"      -> MATCHED (rest)")
                            found = True
                            break
                        elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                            if str(new_elem.pitch) == pos['pitch']:
                                new_spanned_elements.append(new_elem)
                                print(f"      -> MATCHED (pitch)")
                                found = True
                                break
                if not found:
                    print(f"      -> NOT FOUND")
                break

    print(f"  Result: {len(new_spanned_elements)} / {len(sp_info['positions'])} elements matched")
