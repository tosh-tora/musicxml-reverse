#!/usr/bin/env python3
"""Check the time order of spanner elements"""

from music21 import converter
from pathlib import Path

def check_spanner_order(filepath):
    score = converter.parse(str(filepath))
    part = score.parts[0]

    print(f"File: {filepath}")
    for i, sp in enumerate(part.spannerBundle):
        spanned = list(sp.getSpannedElements())
        print(f"\n  Spanner {i+1}: {len(spanned)} elements")

        for j, elem in enumerate(spanned):
            # Find measure number
            for measure in part.getElementsByClass('Measure'):
                if elem in measure.notesAndRests:
                    pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'Rest'
                    print(f"    Element {j+1}: {pitch_str} - measure {measure.number}, offset {elem.offset}")
                    break

print("=== Before reversal ===")
check_spanner_order(Path("work/inbox/test-slurs.xml"))

print("\n=== After minimal reversal ===")
check_spanner_order(Path("work/outbox/test-minimal-rev.xml"))
