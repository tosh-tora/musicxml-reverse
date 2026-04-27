#!/usr/bin/env python3
from music21 import converter, dynamics
from reverse_score import reverse_part

# Load original
score = converter.parse('work/inbox/威風堂々ラスト - コピー.musicxml')

# Check each part
total_before = 0
total_after = 0

for part_idx, part in enumerate(score.parts):
    dynamics_before = [sp for sp in part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]

    if len(dynamics_before) > 0:
        reversed_part = reverse_part(part)
        dynamics_after = [sp for sp in reversed_part.spannerBundle if isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo))]

        total_before += len(dynamics_before)
        total_after += len(dynamics_after)

        if len(dynamics_before) != len(dynamics_after):
            print(f'Part {part_idx}: {len(dynamics_before)} → {len(dynamics_after)} (LOST {len(dynamics_before) - len(dynamics_after)})')

print(f'\nTotal: {total_before} → {total_after} (LOST {total_before - total_after})')
