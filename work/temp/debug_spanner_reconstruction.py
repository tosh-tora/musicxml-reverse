#!/usr/bin/env python3
"""Debug script to understand spanner reconstruction"""

from music21 import converter, stream
from pathlib import Path

input_path = Path("work/inbox/test-slurs.xml")
score = converter.parse(str(input_path))

if not isinstance(score, stream.Score):
    new_score = stream.Score()
    new_score.append(score)
    score = new_score

part = score.parts[0]
measures = list(part.getElementsByClass(stream.Measure))

print("=== Original Part ===")
print(f"Measures: {len(measures)}")
for measure in measures:
    print(f"  Measure {measure.number}: duration={measure.duration.quarterLength}")
    for note in measure.notesAndRests:
        print(f"    {note.pitch if hasattr(note, 'pitch') else 'Rest'} offset={note.offset} duration={note.duration.quarterLength}")

print(f"\nSpanners: {len(part.spannerBundle)}")
for sp in part.spannerBundle:
    spanned = list(sp.getSpannedElements())
    print(f"  {type(sp).__name__}: {len(spanned)} elements")
    for elem in spanned:
        # Find which measure this element belongs to
        for measure in measures:
            if elem in measure.notesAndRests:
                print(f"    {elem.pitch if hasattr(elem, 'pitch') else 'Rest'} measure={measure.number} offset={elem.offset}")
                break

# Simulate reversal
print("\n=== Simulating Reversal ===")
reversed_measures = list(reversed(measures))
new_part = stream.Part()

for i, measure in enumerate(reversed_measures):
    # Reverse measure contents
    measure_duration = measure.duration.quarterLength
    for element in measure.notesAndRests:
        current_offset = element.offset
        element_duration = element.duration.quarterLength
        new_offset = measure_duration - current_offset - element_duration
        element.offset = max(0, new_offset)

    measure.number = i + 1
    new_part.append(measure)

print(f"\nNew part measures: {len(list(new_part.getElementsByClass(stream.Measure)))}")
for measure in new_part.getElementsByClass(stream.Measure):
    print(f"  Measure {measure.number}:")
    for note in measure.notesAndRests:
        print(f"    {note.pitch if hasattr(note, 'pitch') else 'Rest'} offset={note.offset}")

# Try to reconstruct spanners
print("\n=== Reconstructing Spanners ===")
for sp in part.spannerBundle:
    spanned_elements_original = list(sp.getSpannedElements())
    print(f"\nProcessing {type(sp).__name__} with {len(spanned_elements_original)} elements")

    if len(spanned_elements_original) < 2:
        print("  -> Skipped (not enough elements)")
        continue

    # Get position info
    note_positions = []
    for elem in spanned_elements_original:
        for measure in part.getElementsByClass(stream.Measure):
            if elem in measure.notesAndRests:
                note_positions.append((measure.number, elem.offset, elem))
                print(f"  Original: {elem.pitch if hasattr(elem, 'pitch') else 'Rest'} in measure {measure.number} at offset {elem.offset}")
                break

    print(f"  Found {len(note_positions)} position records")

    # Try to find corresponding notes in new part
    new_spanned_elements = []
    for original_measure_num, original_offset, original_elem in note_positions:
        reversed_measure_num = len(measures) - original_measure_num + 1
        print(f"  Looking for note in reversed measure {reversed_measure_num}")

        for new_measure in new_part.getElementsByClass(stream.Measure):
            if new_measure.number == reversed_measure_num:
                measure_duration = new_measure.duration.quarterLength
                element_duration = original_elem.duration.quarterLength
                reversed_offset = measure_duration - original_offset - element_duration
                reversed_offset = max(0, reversed_offset)
                print(f"    Expected offset: {reversed_offset}")

                for new_elem in new_measure.notesAndRests:
                    if abs(new_elem.offset - reversed_offset) < 0.01:
                        if hasattr(original_elem, 'pitch') and hasattr(new_elem, 'pitch'):
                            if original_elem.pitch == new_elem.pitch:
                                print(f"    -> MATCH: {new_elem.pitch} at offset {new_elem.offset}")
                                new_spanned_elements.append(new_elem)
                                break
                        else:
                            print(f"    -> MATCH (rest)")
                            new_spanned_elements.append(new_elem)
                            break
                else:
                    print(f"    -> NO MATCH FOUND")
                break

    print(f"  Final: matched {len(new_spanned_elements)} out of {len(spanned_elements_original)} elements")
