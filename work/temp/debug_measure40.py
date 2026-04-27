"""Debug script to trace what happens to measure 40 during reversal"""
from music21 import converter, stream
import copy

def reverse_note_offset(element, measure_duration: float) -> None:
    """小節内の要素のオフセットを反転する"""
    current_offset = element.offset
    element_duration = element.duration.quarterLength
    new_offset = measure_duration - current_offset - element_duration
    element.offset = max(0, new_offset)

# Load the input file
input_file = '../../work/inbox/威風堂々ラスト_in-Concert_Snare_Drum.mxl'
print(f"Loading: {input_file}")
score = converter.parse(input_file)

# Find measure 40
for part in score.parts:
    measures = list(part.getElementsByClass(stream.Measure))
    for measure in measures:
        if measure.number == 40:
            print(f"\n=== ORIGINAL MEASURE 40 ===")
            print(f"Measure duration: {measure.duration.quarterLength}")
            print(f"Number of elements: {len(list(measure.notesAndRests))}")

            for i, elem in enumerate(measure.notesAndRests):
                elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
                print(f"  [{i+1}] {elem_type}: offset={elem.offset}, duration={elem.duration.quarterLength}, type={elem.duration.type}")

            # Now test reversal
            print(f"\n=== TESTING REVERSAL (no snapshot) ===")
            measure_copy1 = copy.deepcopy(measure)
            measure_duration = measure_copy1.duration.quarterLength

            print(f"Before reversal - iterating over measure.notesAndRests:")
            for i, element in enumerate(measure_copy1.notesAndRests):
                print(f"  Iteration {i+1}: processing element at offset {element.offset}")
                reverse_note_offset(element, measure_duration)

            print(f"\nAfter reversal (no snapshot):")
            print(f"Number of elements: {len(list(measure_copy1.notesAndRests))}")
            for i, elem in enumerate(measure_copy1.notesAndRests):
                elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
                print(f"  [{i+1}] {elem_type}: offset={elem.offset}, duration={elem.duration.quarterLength}, type={elem.duration.type}")

            # Now test with snapshot
            print(f"\n=== TESTING REVERSAL (with snapshot) ===")
            measure_copy2 = copy.deepcopy(measure)
            measure_duration = measure_copy2.duration.quarterLength

            elements_snapshot = list(measure_copy2.notesAndRests)
            print(f"Snapshot created with {len(elements_snapshot)} elements")

            for i, element in enumerate(elements_snapshot):
                print(f"  Iteration {i+1}: processing element at offset {element.offset}")
                reverse_note_offset(element, measure_duration)

            print(f"\nAfter reversal (with snapshot):")
            print(f"Number of elements: {len(list(measure_copy2.notesAndRests))}")
            for i, elem in enumerate(measure_copy2.notesAndRests):
                elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
                print(f"  [{i+1}] {elem_type}: offset={elem.offset}, duration={elem.duration.quarterLength}, type={elem.duration.type}")

            break
