#!/usr/bin/env python3
"""
Debug script to trace slur loss during reversal
"""

from music21 import converter, spanner
from pathlib import Path
import copy

def analyze_slur_matching(original_file: Path):
    """Analyze why slurs are not being matched after reversal"""

    print("="*70)
    print("SLUR MATCHING ANALYSIS")
    print("="*70)

    score = converter.parse(str(original_file))
    part = score.parts[0]

    # Get original slurs
    slurs = [sp for sp in part.spannerBundle if isinstance(sp, spanner.Slur)]
    print(f"\nOriginal slurs: {len(slurs)}")

    # Simulate the spanner info collection (from reverse_score.py lines 154-189)
    measures = list(part.getElementsByClass('Measure'))

    spanner_info = []
    for i, sl in enumerate(slurs):
        print(f"\n{'='*70}")
        print(f"Slur {i+1}:")
        spanned_elements_original = list(sl.getSpannedElements())
        print(f"  Spanned elements: {len(spanned_elements_original)}")

        if len(spanned_elements_original) < 2:
            print("  SKIPPED: Less than 2 elements")
            continue

        # Collect note positions
        note_positions = []
        for elem in spanned_elements_original:
            for measure in measures:
                if elem in measure.notesAndRests:
                    pitch_name = str(elem.pitch) if hasattr(elem, 'pitch') else None
                    pos = {
                        'measure_num': measure.number,
                        'offset': elem.offset,
                        'duration': elem.duration.quarterLength,
                        'pitch': pitch_name,
                        'is_rest': elem.isRest
                    }
                    note_positions.append(pos)
                    print(f"    Note: m{pos['measure_num']} offset={pos['offset']:.4f} dur={pos['duration']:.4f} pitch={pos['pitch']}")
                    break

        if len(note_positions) == len(spanned_elements_original):
            sp_data = {
                'type': sl.__class__,
                'positions': note_positions
            }
            spanner_info.append(sp_data)
            print(f"  COLLECTED: {len(note_positions)} positions")
        else:
            print(f"  FAILED: Found {len(note_positions)} / {len(spanned_elements_original)} notes")

    print(f"\n{'='*70}")
    print(f"Total spanners collected: {len(spanner_info)} / {len(slurs)}")
    print(f"Lost during collection: {len(slurs) - len(spanner_info)}")

    # Now simulate the reconstruction (from reverse_score.py lines 305-357)
    print(f"\n{'='*70}")
    print("RECONSTRUCTION SIMULATION")
    print(f"{'='*70}")

    # Process the file to get the reversed version
    from reverse_score import process_file, ErrorHandling

    test_dir = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/viola")
    reversed_file = test_dir / "reversed.mxl"

    if not reversed_file.exists():
        print("\nReversed file not found, skipping reconstruction simulation")
        return

    reversed_score = converter.parse(str(reversed_file))
    reversed_part = reversed_score.parts[0]
    reversed_measures = list(reversed_part.getElementsByClass('Measure'))

    reconstructed_count = 0

    for i, sp_info in enumerate(spanner_info):
        print(f"\n{'='*70}")
        print(f"Reconstructing Slur {i+1}:")
        print(f"  Original positions: {len(sp_info['positions'])}")

        new_spanned_elements = []

        for j, pos in enumerate(sp_info['positions']):
            print(f"\n  Looking for note {j+1}:")
            print(f"    Original: m{pos['measure_num']} offset={pos['offset']:.4f} pitch={pos['pitch']}")

            # Calculate reversed position
            reversed_measure_num = len(measures) - pos['measure_num'] + 1
            print(f"    Reversed measure: {reversed_measure_num}")

            # Find the reversed measure
            found_measure = False
            for new_measure in reversed_measures:
                if new_measure.number == reversed_measure_num:
                    found_measure = True
                    measure_duration = new_measure.duration.quarterLength
                    reversed_offset = measure_duration - pos['offset'] - pos['duration']
                    reversed_offset = max(0, reversed_offset)

                    print(f"    Looking for offset={reversed_offset:.4f} in measure (duration={measure_duration:.4f})")

                    # Search for matching note
                    found_note = False
                    for new_elem in new_measure.notesAndRests:
                        offset_match = abs(new_elem.offset - reversed_offset) < 0.01
                        if offset_match:
                            print(f"      Candidate: offset={new_elem.offset:.4f} ", end="")

                            # Check pitch/rest match
                            if pos['is_rest'] and new_elem.isRest:
                                print("REST MATCH [OK]")
                                new_spanned_elements.append(new_elem)
                                found_note = True
                                break
                            elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                                if str(new_elem.pitch) == pos['pitch']:
                                    print(f"PITCH MATCH [OK] ({new_elem.pitch})")
                                    new_spanned_elements.append(new_elem)
                                    found_note = True
                                    break
                                else:
                                    print(f"pitch mismatch ({new_elem.pitch} != {pos['pitch']})")
                            else:
                                print("type mismatch")

                    if not found_note:
                        print(f"      NO MATCH FOUND")
                        print(f"      Available notes in measure:")
                        for elem in new_measure.notesAndRests:
                            pitch_str = str(elem.pitch) if hasattr(elem, 'pitch') else 'REST'
                            print(f"        offset={elem.offset:.4f} pitch={pitch_str}")

                    break

            if not found_measure:
                print(f"    MEASURE NOT FOUND: {reversed_measure_num}")

        # Check if reconstruction succeeded
        if len(new_spanned_elements) == len(sp_info['positions']) and len(new_spanned_elements) >= 2:
            print(f"\n  RECONSTRUCTED: {len(new_spanned_elements)} / {len(sp_info['positions'])} notes found")
            reconstructed_count += 1
        else:
            print(f"\n  FAILED: {len(new_spanned_elements)} / {len(sp_info['positions'])} notes found")

    print(f"\n{'='*70}")
    print(f"RECONSTRUCTION SUMMARY")
    print(f"{'='*70}")
    print(f"Spanners collected: {len(spanner_info)}")
    print(f"Successfully reconstructed: {reconstructed_count}")
    print(f"Failed to reconstruct: {len(spanner_info) - reconstructed_count}")
    print(f"Total loss: {len(slurs)} → {reconstructed_count}")


if __name__ == "__main__":
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/viola/original.mxl")
    if not original.exists():
        print(f"Error: {original} not found")
        print("Run test_viola_roundtrip.py first to generate test files")
    else:
        analyze_slur_matching(original)
