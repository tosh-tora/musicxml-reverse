#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze direction element multiplication in Viola MusicXML files."""

import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import sys

# Set UTF-8 encoding for stdout
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_directions(xml_file):
    """Analyze direction elements in a MusicXML file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Handle namespace if present
    ns = {'': 'http://www.w3.org/2001/MusicXML'}
    if root.tag.startswith('{'):
        namespace = root.tag[1:root.tag.index('}')]
        ns = {'': namespace}
        ns_prefix = f'{{{namespace}}}'
    else:
        ns_prefix = ''

    directions = []

    # Find all parts
    parts = root.findall(f'.//{ns_prefix}part')

    for part in parts:
        part_id = part.get('id', 'unknown')
        measures = part.findall(f'{ns_prefix}measure')

        for measure in measures:
            measure_num = measure.get('number', 'unknown')
            direction_elements = measure.findall(f'{ns_prefix}direction')

            for direction in direction_elements:
                # Extract direction details
                placement = direction.get('placement', 'none')
                voice_elem = direction.find(f'{ns_prefix}voice')
                voice = voice_elem.text if voice_elem is not None else 'none'
                staff_elem = direction.find(f'{ns_prefix}staff')
                staff = staff_elem.text if staff_elem is not None else 'none'
                offset_elem = direction.find(f'{ns_prefix}offset')
                offset = offset_elem.text if offset_elem is not None else '0'

                # Get direction type and content
                direction_type = direction.find(f'{ns_prefix}direction-type')
                content = []
                if direction_type is not None:
                    # Check for words
                    words = direction_type.findall(f'{ns_prefix}words')
                    for word in words:
                        content.append(('words', word.text or '', word.attrib))

                    # Check for dynamics
                    dynamics = direction_type.find(f'{ns_prefix}dynamics')
                    if dynamics is not None:
                        for child in dynamics:
                            content.append(('dynamics', child.tag.replace(ns_prefix, ''), child.attrib))

                    # Check for wedge
                    wedge = direction_type.find(f'{ns_prefix}wedge')
                    if wedge is not None:
                        content.append(('wedge', wedge.get('type', ''), wedge.attrib))

                    # Check for metronome
                    metronome = direction_type.find(f'{ns_prefix}metronome')
                    if metronome is not None:
                        content.append(('metronome', 'metronome', metronome.attrib))

                # Get sound element
                sound = direction.find(f'{ns_prefix}sound')
                sound_attrs = sound.attrib if sound is not None else {}

                directions.append({
                    'part_id': part_id,
                    'measure': measure_num,
                    'placement': placement,
                    'voice': voice,
                    'staff': staff,
                    'offset': offset,
                    'content': content,
                    'sound': sound_attrs
                })

    return directions

def format_direction(d):
    """Format a direction for display."""
    content_str = ', '.join([f"{ct[0]}:{ct[1]}" for ct in d['content']])
    sound_str = ', '.join([f"{k}={v}" for k, v in d['sound'].items()]) if d['sound'] else ''
    return (f"M{d['measure']} voice={d['voice']} staff={d['staff']} offset={d['offset']} "
            f"placement={d['placement']} [{content_str}] sound:[{sound_str}]")

def main():
    in_file = Path('work/temp_in_viola/score.xml')
    out_file = list(Path('work/temp_out_viola').glob('*.musicxml'))[0]

    print("=" * 80)
    print("ANALYZING INPUT FILE")
    print("=" * 80)
    in_directions = analyze_directions(in_file)
    print(f"\nTotal direction elements: {len(in_directions)}\n")

    # Group by measure
    by_measure = defaultdict(list)
    for d in in_directions:
        by_measure[d['measure']].append(d)

    for measure in sorted(by_measure.keys(), key=lambda x: int(x) if x.isdigit() else 9999):
        print(f"\n--- Measure {measure} ({len(by_measure[measure])} directions) ---")
        for d in by_measure[measure]:
            print(f"  {format_direction(d)}")

    print("\n" + "=" * 80)
    print("ANALYZING OUTPUT FILE")
    print("=" * 80)
    out_directions = analyze_directions(out_file)
    print(f"\nTotal direction elements: {len(out_directions)}\n")

    # Group by measure
    by_measure = defaultdict(list)
    for d in out_directions:
        by_measure[d['measure']].append(d)

    for measure in sorted(by_measure.keys(), key=lambda x: int(x) if x.isdigit() else 9999):
        print(f"\n--- Measure {measure} ({len(by_measure[measure])} directions) ---")
        for d in by_measure[measure]:
            print(f"  {format_direction(d)}")

    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"\nInput file: {len(in_directions)} direction elements")
    print(f"Output file: {len(out_directions)} direction elements")
    print(f"Difference: {len(out_directions) - len(in_directions)} ({'+' if len(out_directions) > len(in_directions) else ''}{len(out_directions) - len(in_directions)})")

    # Find duplicated content
    print("\n" + "=" * 80)
    print("CONTENT ANALYSIS")
    print("=" * 80)

    in_content_counts = defaultdict(int)
    for d in in_directions:
        content_key = tuple((ct[0], ct[1]) for ct in d['content'])
        if content_key:
            in_content_counts[content_key] += 1

    out_content_counts = defaultdict(int)
    for d in out_directions:
        content_key = tuple((ct[0], ct[1]) for ct in d['content'])
        if content_key:
            out_content_counts[content_key] += 1

    print("\nDirection content comparison:")
    all_keys = set(in_content_counts.keys()) | set(out_content_counts.keys())
    for key in sorted(all_keys):
        in_count = in_content_counts[key]
        out_count = out_content_counts[key]
        if in_count != out_count:
            print(f"  {key}: IN={in_count} OUT={out_count} (diff={out_count-in_count})")

if __name__ == '__main__':
    main()
