#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract specific measure direction XML for detailed analysis."""

import xml.etree.ElementTree as ET
from pathlib import Path
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_measure_directions(xml_file, measure_num):
    """Extract all direction elements from a specific measure."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Handle namespace
    ns_prefix = ''
    if root.tag.startswith('{'):
        namespace = root.tag[1:root.tag.index('}')]
        ns_prefix = f'{{{namespace}}}'

    # Find the measure
    measures = root.findall(f'.//{ns_prefix}measure[@number="{measure_num}"]')

    if not measures:
        print(f"Measure {measure_num} not found")
        return

    for measure in measures:
        print(f"\n{'='*80}")
        print(f"MEASURE {measure_num}")
        print('='*80)

        directions = measure.findall(f'{ns_prefix}direction')
        print(f"\nTotal directions: {len(directions)}\n")

        for i, direction in enumerate(directions, 1):
            print(f"--- Direction {i} ---")
            # Pretty print the XML
            xml_str = ET.tostring(direction, encoding='unicode', method='xml')
            # Basic formatting
            lines = xml_str.split('><')
            for j, line in enumerate(lines):
                if j > 0:
                    line = '<' + line
                if j < len(lines) - 1:
                    line = line + '>'
                # Add indentation based on depth
                depth = line.count('<') - line.count('</') - line.count('/>')
                if '</' in line:
                    depth += 1
                indent = '  ' * max(0, depth - 1)
                print(indent + line)
            print()

def main():
    in_file = Path('work/temp_in_viola/score.xml')
    out_file = list(Path('work/temp_out_viola').glob('*.musicxml'))[0]

    print("INPUT FILE - Measure 41 (Tempo primo)")
    extract_measure_directions(in_file, "41")

    print("\n" + "="*80)
    print("OUTPUT FILE - Measure 13 (reversed Tempo primo)")
    print("="*80)
    extract_measure_directions(out_file, "13")

    print("\n" + "="*80)
    print("INPUT FILE - Measure 1 (Molto Maestoso)")
    extract_measure_directions(in_file, "1")

    print("\n" + "="*80)
    print("OUTPUT FILE - Measure 53 (reversed Molto Maestoso)")
    print("="*80)
    extract_measure_directions(out_file, "53")

if __name__ == '__main__':
    main()
