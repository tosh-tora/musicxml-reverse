"""More comprehensive debug to trace measure 40 through the entire pipeline"""
from music21 import converter, stream
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import sys

# Patch reverse_score to add logging
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import reverse_score

# Intercept the reverse_measure_contents function
original_reverse_measure_contents = reverse_score.reverse_measure_contents

def logged_reverse_measure_contents(measure):
    measure_num = measure.number
    before_count = len(list(measure.notesAndRests))

    result_measure, error = original_reverse_measure_contents(measure)

    after_count = len(list(result_measure.notesAndRests))

    if measure_num == 40:
        print(f"\n*** MEASURE 40 REVERSAL ***")
        print(f"Before: {before_count} elements")
        print(f"After: {after_count} elements")
        if before_count != after_count:
            print(f"!!! CORRUPTION DETECTED IN reverse_measure_contents !!!")

    return result_measure, error

# Intercept reverse_part
original_reverse_part = reverse_score.reverse_part

def logged_reverse_part(part, error_handling, report=None, part_name=None):
    # Check measure 40 before processing
    measures = list(part.getElementsByClass(stream.Measure))
    for m in measures:
        if m.number == 40:
            print(f"\n=== BEFORE reverse_part: Measure 40 has {len(list(m.notesAndRests))} elements")

    # Patch the function
    reverse_score.reverse_measure_contents = logged_reverse_measure_contents

    result = original_reverse_part(part, error_handling, report, part_name)

    # Check measure 40 after processing
    for m in result.getElementsByClass(stream.Measure):
        if m.number == 40:
            print(f"=== AFTER reverse_part: Measure 40 has {len(list(m.notesAndRests))} elements")
            for i, elem in enumerate(m.notesAndRests):
                elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
                print(f"  [{i+1}] {elem_type}: offset={elem.offset}, duration={elem.duration.quarterLength}")

    # Restore
    reverse_score.reverse_measure_contents = original_reverse_measure_contents

    return result

reverse_score.reverse_part = logged_reverse_part

# Now run the processing
print("Loading input file...")
input_file = Path('work/inbox/威風堂々ラスト_in-Concert_Snare_Drum.mxl')
score = converter.parse(input_file)

print("Processing...")
reversed_score, report = reverse_score.process_score(
    score,
    error_handling=reverse_score.ErrorHandling.SKIP_MEASURE_CONTENT
)

print("\n=== CHECKING OUTPUT ===")
# Check measure 40 in the final output
for part in reversed_score.parts:
    for m in part.getElementsByClass(stream.Measure):
        if m.number == 40:
            print(f"FINAL OUTPUT: Measure 40 has {len(list(m.notesAndRests))} elements")
            for i, elem in enumerate(m.notesAndRests):
                elem_type = 'grace' if elem.duration.isGrace else ('rest' if elem.isRest else 'note')
                print(f"  [{i+1}] {elem_type}: offset={elem.offset}, duration={elem.duration.quarterLength}")
