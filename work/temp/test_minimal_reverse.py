#!/usr/bin/env python3
"""Minimal test to verify spanner preservation logic"""

from music21 import converter, stream
from pathlib import Path

def simple_reverse_part(part):
    """Simplified version of reverse_part focusing on spanner preservation"""
    measures = list(part.getElementsByClass(stream.Measure))

    # Save spanner info BEFORE modification
    print("=== Saving spanner info ===")
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
                    print(f"  Saved: {pitch_name} measure={measure.number} offset={elem.offset}")
                    break

        if len(note_positions) == len(spanned_elements_original):
            spanner_info.append({
                'type': sp.__class__,
                'positions': note_positions
            })

    print(f"Saved {len(spanner_info)} spanners\n")

    # Reverse measures
    reversed_measures = list(reversed(measures))
    new_part = stream.Part()
    new_part.id = part.id

    for i, measure in enumerate(reversed_measures):
        # Reverse note offsets
        measure_duration = measure.duration.quarterLength
        for element in measure.notesAndRests:
            current_offset = element.offset
            element_duration = element.duration.quarterLength
            new_offset = measure_duration - current_offset - element_duration
            element.offset = max(0, new_offset)

        measure.number = i + 1
        new_part.append(measure)

    print("=== Reconstructing spanners ===")
    # Reconstruct spanners
    for idx, sp_info in enumerate(spanner_info):
        new_spanned_elements = []

        for pos in sp_info['positions']:
            reversed_measure_num = len(measures) - pos['measure_num'] + 1

            for new_measure in new_part.getElementsByClass(stream.Measure):
                if new_measure.number == reversed_measure_num:
                    measure_duration = new_measure.duration.quarterLength
                    reversed_offset = measure_duration - pos['offset'] - pos['duration']
                    reversed_offset = max(0, reversed_offset)

                    for new_elem in new_measure.notesAndRests:
                        offset_match = abs(new_elem.offset - reversed_offset) < 0.01
                        if offset_match:
                            if pos['is_rest'] and new_elem.isRest:
                                new_spanned_elements.append(new_elem)
                                print(f"  Matched rest at offset {new_elem.offset}")
                                break
                            elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                                if str(new_elem.pitch) == pos['pitch']:
                                    new_spanned_elements.append(new_elem)
                                    print(f"  Matched {new_elem.pitch} at offset {new_elem.offset}")
                                    break
                    break

        if len(new_spanned_elements) == len(sp_info['positions']) and len(new_spanned_elements) >= 2:
            new_spanner = sp_info['type'](new_spanned_elements)
            new_part.insert(0, new_spanner)
            print(f"  Created spanner with {len(new_spanned_elements)} elements")
        else:
            print(f"  FAILED: only found {len(new_spanned_elements)}/{len(sp_info['positions'])} elements")

    return new_part

# Test
input_path = Path("work/inbox/test-slurs.xml")
score = converter.parse(str(input_path))

if not isinstance(score, stream.Score):
    new_score = stream.Score()
    new_score.append(score)
    score = new_score

part = score.parts[0]
print(f"Original part spanners: {len(part.spannerBundle)}\n")

new_part = simple_reverse_part(part)

print(f"\n=== Result ===")
print(f"New part spanners: {len(new_part.spannerBundle)}")
for i, sp in enumerate(new_part.spannerBundle):
    spanned = list(sp.getSpannedElements())
    print(f"  Spanner {i+1}: {len(spanned)} elements")
    for elem in spanned:
        print(f"    - {elem.pitch if hasattr(elem, 'pitch') else 'Rest'}")

# Write to file
new_score = stream.Score()
new_score.append(new_part)
output_path = Path("work/outbox/test-minimal-rev.xml")
new_score.write('xml', fp=str(output_path))
print(f"\nWrote to: {output_path}")

# Re-read and verify
print("\n=== Verification (re-reading file) ===")
verify_score = converter.parse(str(output_path))
verify_part = verify_score.parts[0]
print(f"Spanners in written file: {len(verify_part.spannerBundle)}")
for i, sp in enumerate(verify_part.spannerBundle):
    spanned = list(sp.getSpannedElements())
    print(f"  Spanner {i+1}: {len(spanned)} elements")
    for elem in spanned:
        print(f"    - {elem.pitch if hasattr(elem, 'pitch') else 'Rest'}")
