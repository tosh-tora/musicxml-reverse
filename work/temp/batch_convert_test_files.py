#!/usr/bin/env python3
"""Batch convert all MusicXML files in work/inbox/test to work/outbox/test."""

from pathlib import Path
from reverse_score import process_file, ErrorHandling

def main():
    """Convert all test files."""
    inbox_dir = Path("work/inbox/test")
    outbox_dir = Path("work/outbox/test")

    # Create output directory
    outbox_dir.mkdir(parents=True, exist_ok=True)

    # Get all .mxl files
    input_files = sorted(inbox_dir.glob("*.mxl"))

    print(f"Found {len(input_files)} files to convert")
    print("-" * 80)

    success_count = 0
    error_count = 0

    for input_file in input_files:
        # Create output filename
        output_name = input_file.name.replace("_in", "_out")
        output_file = outbox_dir / output_name

        print(f"\nProcessing: {input_file.name}")
        print(f"  Output: {output_name}")

        try:
            report = process_file(input_file, output_file, ErrorHandling.SKIP_PART)
            print(f"  [OK] Success: {report.input_note_count} -> {report.output_note_count} notes")
            success_count += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            error_count += 1

    print("\n" + "=" * 80)
    print(f"Conversion complete: {success_count} succeeded, {error_count} failed")
    print(f"Output directory: {outbox_dir}")

if __name__ == "__main__":
    main()
