#!/usr/bin/env python3
"""Debug script to investigate spanner preservation"""

from music21 import converter, stream, dynamics
from pathlib import Path

def debug_reverse_other_spanners(part: stream.Part) -> None:
    """Debug version of reverse_other_spanners"""
    print(f"\n=== reverse_other_spanners called ===")
    print(f"Input part.spannerBundle items: {len(part.spannerBundle)}")

    spanners_to_process = list(part.spannerBundle)
    print(f"Spanners to process: {len(spanners_to_process)}")

    for sp in spanners_to_process:
        print(f"\n  Processing spanner: {type(sp).__name__}")

        # Crescendo/Diminuendoは reverse_dynamics_wedges() で処理済みなのでスキップ
        if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo)):
            print(f"    -> Skipping (Crescendo/Diminuendo)")
            continue

        # それ以外のSpanner（Slur, Glissando等）を保持
        spanned_elements = list(sp.getSpannedElements())
        print(f"    -> Spanned elements: {len(spanned_elements)}")

        if len(spanned_elements) >= 2:
            print(f"    -> Removing old spanner")
            part.remove(sp)

            # 新しいSpannerを作成（同じ型で再構築）
            print(f"    -> Creating new spanner: {sp.__class__.__name__}")
            new_spanner = sp.__class__(spanned_elements)
            part.insert(0, new_spanner)
            print(f"    -> Inserted new spanner")
        else:
            print(f"    -> Skipping (not enough elements)")

    print(f"\nFinal part.spannerBundle items: {len(part.spannerBundle)}")

# Test with the original file
input_path = Path("work/inbox/test-slurs.xml")
print(f"Loading: {input_path}")
score = converter.parse(str(input_path))

if not isinstance(score, stream.Score):
    new_score = stream.Score()
    new_score.append(score)
    score = new_score

print(f"\n=== Original score ===")
for i, part in enumerate(score.parts):
    print(f"Part {i+1}: {len(part.spannerBundle)} spanners")
    for sp in part.spannerBundle:
        print(f"  - {type(sp).__name__}: {len(list(sp.getSpannedElements()))} elements")

# Simulate creating a new part (like in reverse_part)
print(f"\n=== Simulating reverse_part ===")
original_part = score.parts[0]
measures = list(original_part.getElementsByClass(stream.Measure))

# Create new part
new_part = stream.Part()
new_part.id = original_part.id
if original_part.partName:
    new_part.partName = original_part.partName

print(f"Original part spanners: {len(original_part.spannerBundle)}")
print(f"New part spanners (before adding measures): {len(new_part.spannerBundle)}")

# Add reversed measures
for measure in reversed(measures):
    new_part.append(measure)

print(f"New part spanners (after adding measures): {len(new_part.spannerBundle)}")

# Now try to apply reverse_other_spanners
debug_reverse_other_spanners(new_part)
