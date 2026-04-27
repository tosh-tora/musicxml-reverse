#!/usr/bin/env python3
"""Debug Part 7 dynamics loss"""

from music21 import converter, dynamics, stream
import copy

# Load original
score = converter.parse('work/inbox/威風堂々ラスト - コピー.musicxml')
part = score.parts[7]

print(f"Part 7: {len(list(part.spannerBundle))} total spanners")

# Get dynamics
dynamics_spanners = [sp for sp in part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]
print(f"Dynamics spanners: {len(dynamics_spanners)}")

for idx, sp in enumerate(dynamics_spanners):
    print(f"\n{idx+1}. {sp.__class__.__name__}:")
    elems = list(sp.getSpannedElements())
    print(f"   Elements: {len(elems)}")

    for elem in elems:
        # Find measure
        measure_num = None
        for m in part.getElementsByClass(stream.Measure):
            if elem in m.notesAndRests:
                measure_num = m.number
                break

        pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'Rest'
        print(f"   - measure={measure_num}, offset={elem.offset:.2f}, dur={elem.duration.quarterLength:.2f}, pitch={pitch_str}")

# Now trace through the spanner save logic manually
print("\n" + "="*60)
print("Simulating spanner save logic")
print("="*60)

measures = list(part.getElementsByClass(stream.Measure))
print(f"Total measures: {len(measures)}")

for idx, sp in enumerate(dynamics_spanners):
    print(f"\n{idx+1}. {sp.__class__.__name__}:")
    spanned_elements_original = list(sp.getSpannedElements())

    note_positions = []
    for elem in spanned_elements_original:
        found = False
        for measure in measures:
            measure_notes = list(measure.notesAndRests)
            for note_idx, note in enumerate(measure_notes):
                # Check match
                offset_match = abs(elem.offset - note.offset) < 0.0001
                duration_match = abs(elem.duration.quarterLength - note.duration.quarterLength) < 0.0001

                pitch_match = False
                if elem.isRest and note.isRest:
                    pitch_match = True
                elif hasattr(elem, 'pitch') and hasattr(note, 'pitch'):
                    pitch_match = (str(elem.pitch) == str(note.pitch))

                if offset_match and duration_match and pitch_match:
                    note_positions.append({
                        'measure_num': measure.number,
                        'offset': note.offset,
                        'duration': note.duration.quarterLength,
                        'pitch': str(note.pitch) if hasattr(note, 'pitch') else None,
                        'is_rest': note.isRest,
                        'note_index': note_idx
                    })
                    found = True
                    break
            if found:
                break

        if not found:
            print(f"   [ERROR] Could not find match for element: offset={elem.offset}, pitch={getattr(elem, 'pitch', 'Rest')}")

    print(f"   Matched {len(note_positions)}/{len(spanned_elements_original)} elements")

    if len(note_positions) == len(spanned_elements_original):
        print(f"   [OK] Would be saved")
    else:
        print(f"   [FAIL] Would be skipped (not all elements found)")
