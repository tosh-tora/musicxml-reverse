#!/usr/bin/env python3
"""
既存の Bassoon 出力ファイルに対して再マージを実行
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from layout_preservation import merge_split_directions

output_file = Path('work/outbox/test/威風堂々ラスト_out-Bassoon.mxl')

print("=== マージ前の direction 数 ===")
with zipfile.ZipFile(output_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_before = sum(len(m.findall('{*}direction')) for m in measures)
print(f"マージ前: {total_before} direction 要素")

# measure 9 の詳細
measure9 = part.find('.//{*}measure[@number="9"]')
if measure9:
    dirs_m9 = measure9.findall('{*}direction')
    print(f"  Measure 9: {len(dirs_m9)} directions")
    for i, d in enumerate(dirs_m9[:4], 1):
        dt = d.find('{*}direction-type')
        words = dt.find('{*}words') if dt is not None else None
        sound = d.find('{*}sound')
        w_text = (words.text if words is not None and words.text else '<empty>') if words is not None else 'None'
        s_text = f'tempo={sound.get("tempo")}' if sound is not None else 'no-sound'
        print(f"    {i}. words={w_text}, {s_text}")

print("\n=== マージを実行 ===")
merge_split_directions(output_file, verbose=True)

print("\n=== マージ後の direction 数 ===")
with zipfile.ZipFile(output_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_after = sum(len(m.findall('{*}direction')) for m in measures)
print(f"マージ後: {total_after} direction 要素 (差分: {total_after - total_before:+d})")

# measure 9 の詳細
measure9 = part.find('.//{*}measure[@number="9"]')
if measure9:
    dirs_m9 = measure9.findall('{*}direction')
    print(f"  Measure 9: {len(dirs_m9)} directions")
    for i, d in enumerate(dirs_m9[:4], 1):
        dt = d.find('{*}direction-type')
        words = dt.find('{*}words') if dt is not None else None
        sound = d.find('{*}sound')
        w_text = (words.text if words is not None and words.text else '<empty>') if words is not None else 'None'
        s_text = f'tempo={sound.get("tempo")}' if sound is not None else 'no-sound'
        print(f"    {i}. words={w_text}, {s_text}")

print(f"\n元の入力ファイルは 32 direction 要素でした。")
print(f"現在の出力: {total_after} direction 要素 (差分: {total_after - 32:+d})")
