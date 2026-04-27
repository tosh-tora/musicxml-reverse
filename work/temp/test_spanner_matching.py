#!/usr/bin/env python3
"""Test spanner matching logic"""

from music21 import converter, dynamics
from reverse_score import reverse_part
from pathlib import Path

# Load original
score = converter.parse('work/inbox/威風堂々ラスト - コピー.musicxml')

# Test first part with dynamics
part = score.parts[0]
print(f"Part 0: {len(list(part.spannerBundle))} spanners")

# Count dynamics before
dynamics_before = [sp for sp in part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]
print(f"Dynamics before: {len(dynamics_before)}")

for sp in dynamics_before:
    elems = list(sp.getSpannedElements())
    print(f"  {sp.__class__.__name__}: {len(elems)} elements")
    for elem in elems:
        # Find measure
        for m in part.getElementsByClass('Measure'):
            if elem in m.notesAndRests:
                print(f"    - measure={m.number}, offset={elem.offset}, pitch={getattr(elem, 'pitch', 'Rest')}")
                break

# Reverse
reversed_part = reverse_part(part)

# Count dynamics after
dynamics_after = [sp for sp in reversed_part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]
print(f"\nDynamics after: {len(dynamics_after)}")

for sp in dynamics_after:
    elems = list(sp.getSpannedElements())
    print(f"  {sp.__class__.__name__}: {len(elems)} elements")
    for elem in elems:
        # Find measure
        for m in reversed_part.getElementsByClass('Measure'):
            if elem in m.notesAndRests:
                print(f"    - measure={m.number}, offset={elem.offset}, pitch={getattr(elem, 'pitch', 'Rest')}")
                break

print(f"\nLost: {len(dynamics_before) - len(dynamics_after)} dynamics")
