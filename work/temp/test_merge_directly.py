#!/usr/bin/env python3
"""
merge_split_directions()を直接テストする
"""

from pathlib import Path
from layout_preservation import merge_split_directions
import xml.etree.ElementTree as ET
import zipfile

# テストファイル
test_file = Path('work/outbox/test/威風堂々ラスト_out-Viola.mxl')

print("=== マージ前の状態 ===")
# マージ前の状態を確認
with zipfile.ZipFile(test_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measure = part.find('.//{*}measure[@number="53"]')
directions = measure.findall('{*}direction')
print(f'Measure 53: {len(directions)} directions')

# マージを実行
print("\n=== マージ実行 ===")
merge_split_directions(test_file, verbose=True)

# マージ後の状態を確認
print("\n=== マージ後の状態 ===")
with zipfile.ZipFile(test_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measure = part.find('.//{*}measure[@number="53"]')
directions = measure.findall('{*}direction')
print(f'Measure 53: {len(directions)} directions')

for i, d in enumerate(directions[:4], 1):
    dt = d.find('{*}direction-type')
    words = dt.find('{*}words') if dt is not None else None
    sound = d.find('{*}sound')

    words_text = 'None' if words is None else (words.text if words.text else '<empty>')
    sound_info = f'tempo={sound.get("tempo")}' if sound is not None else 'no sound'

    print(f'  {i}. words={words_text}, {sound_info}')
