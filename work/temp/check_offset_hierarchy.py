#!/usr/bin/env python3
"""Check if getOffsetInHierarchy helps"""

from music21 import converter, dynamics, stream

# Load original
score = converter.parse('work/inbox/威風堂々ラスト - コピー.musicxml')
part = score.parts[7]

dynamics_spanners = [sp for sp in part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]

for idx, sp in enumerate(dynamics_spanners[:2]):  # Just first 2
    print(f"\n{idx+1}. {sp.__class__.__name__}:")
    elems = list(sp.getSpannedElements())

    for elem in elems:
        # Try different offset methods
        try:
            offset_local = elem.offset
            offset_hierarchy = elem.getOffsetInHierarchy(part)
            activeSite = elem.activeSite
            pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'Rest'

            print(f"   - offset={offset_local:.2f}, offsetInHierarchy={offset_hierarchy:.2f}, activeSite={activeSite}, pitch={pitch_str}")
        except Exception as e:
            print(f"   - ERROR: {e}")
