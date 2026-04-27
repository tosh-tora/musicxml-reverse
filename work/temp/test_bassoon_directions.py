#!/usr/bin/env python3
"""
Bassoonファイルの direction 増殖を詳細調査
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from music21 import converter

# 入力ファイル
input_file = Path('work/inbox/test/威風堂々ラスト_in-Bassoon.mxl')
temp_output = Path('work/temp_bassoon_test.mxl')

print("=== Step 1: 入力ファイルの direction 数 ===")
with zipfile.ZipFile(input_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_in = sum(len(m.findall('{*}direction')) for m in measures)
print(f"入力: {total_in} direction 要素")

# measure 1 の詳細
measure1 = part.find('.//{*}measure[@number="1"]')
dirs_m1 = measure1.findall('{*}direction')
print(f"  Measure 1: {len(dirs_m1)} directions")
for i, d in enumerate(dirs_m1[:5], 1):
    dt = d.find('{*}direction-type')
    words = dt.find('{*}words') if dt is not None else None
    sound = d.find('{*}sound')
    w_text = (words.text if words is not None and words.text else '<empty>') if words is not None else 'None'
    s_text = f'tempo={sound.get("tempo")}' if sound is not None else 'no-sound'
    print(f"    {i}. words={w_text}, {s_text}")

print("\n=== Step 2: music21 で読み込んで書き出し ===")
score = converter.parse(str(input_file))
score.write('mxl', fp=str(temp_output))
print(f"書き出し完了: {temp_output}")

print("\n=== Step 3: 書き出し直後の direction 数 ===")
with zipfile.ZipFile(temp_output, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_out = sum(len(m.findall('{*}direction')) for m in measures)
print(f"出力: {total_out} direction 要素 ({total_out - total_in:+d})")

# measure 1 の詳細（反転後は measure 53 になるが、ここでは反転前なので measure 1）
# 実際には music21 が番号を変更する可能性があるので、最初の measure を確認
measures_list = part.findall('.//{*}measure')
if measures_list:
    measure_first = measures_list[0]
    mnum = measure_first.get('number', '?')
    dirs_first = measure_first.findall('{*}direction')
    print(f"  First measure ({mnum}): {len(dirs_first)} directions")
    for i, d in enumerate(dirs_first[:8], 1):
        dt = d.find('{*}direction-type')
        words = dt.find('{*}words') if dt is not None else None
        sound = d.find('{*}sound')
        w_text = (words.text if words is not None and words.text else '<empty>') if words is not None else 'None'
        s_text = f'tempo={sound.get("tempo")}' if sound is not None else 'no-sound'
        print(f"    {i}. words={w_text}, {s_text}")

print("\n=== Step 4: マージを実行 ===")
from layout_preservation import merge_split_directions
merge_split_directions(temp_output, verbose=True)

print("\n=== Step 5: マージ後の direction 数 ===")
with zipfile.ZipFile(temp_output, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_merged = sum(len(m.findall('{*}direction')) for m in measures)
print(f"マージ後: {total_merged} direction 要素 ({total_merged - total_in:+d})")

# クリーンアップ
temp_output.unlink()
