#!/usr/bin/env python3
"""
Bassoon ファイルを個別に反転処理してテスト
"""

from pathlib import Path
from music21 import converter

# ファイルパス
input_file = Path('work/inbox/test/威風堂々ラスト_in-Bassoon.mxl')
output_file = Path('work/test_bassoon_reversed.mxl')

print("=== Bassoon ファイルの個別反転テスト ===\n")

# Step 1: 入力ファイルを読み込み
print("Step 1: 入力ファイルを読み込み中...")
score = converter.parse(str(input_file))
print(f"  読み込み完了: {len(score.parts)} パート")

# Step 2: 反転処理（簡易版 — 小節順序のみ反転）
print("\nStep 2: 小節順序を反転中...")
for part in score.parts:
    measures = list(part.getElementsByClass('Measure'))
    # 小節を逆順に並べ替え
    for measure in reversed(measures):
        part.remove(measure)
    for measure in reversed(measures):
        part.append(measure)
print("  反転完了")

# Step 3: 書き出し
print("\nStep 3: 書き出し中...")
score.write('mxl', fp=str(output_file))
print(f"  書き出し完了: {output_file}")

# Step 4: direction 数を確認
print("\nStep 4: direction 数を確認...")
import xml.etree.ElementTree as ET
import zipfile

with zipfile.ZipFile(output_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_before_merge = sum(len(m.findall('{*}direction')) for m in measures)
print(f"  書き出し直後: {total_before_merge} direction 要素")

# Step 5: マージを実行
print("\nStep 5: direction をマージ中...")
from layout_preservation import merge_split_directions
merge_split_directions(output_file, verbose=True)

# Step 6: マージ後の direction 数を確認
print("\nStep 6: マージ後の direction 数を確認...")
with zipfile.ZipFile(output_file, 'r') as zf:
    container = ET.fromstring(zf.read('META-INF/container.xml'))
    rootfile = container.find('.//{*}rootfile')
    xml_filename = rootfile.get('full-path')
    content = zf.read(xml_filename).decode('utf-8')
    root = ET.fromstring(content)

part = root.find('.//{*}part')
measures = part.findall('.//{*}measure')
total_after_merge = sum(len(m.findall('{*}direction')) for m in measures)

print(f"  マージ後: {total_after_merge} direction 要素")
print()
print("=== 結果 ===")
print(f"入力: 32 direction 要素")
print(f"出力（マージ前）: {total_before_merge} direction 要素 ({total_before_merge - 32:+d})")
print(f"出力（マージ後）: {total_after_merge} direction 要素 ({total_after_merge - 32:+d})")
print()
if total_after_merge == 32:
    print("✓ PASS: direction 要素数が一致しました！")
else:
    print(f"⚠ 差異: {total_after_merge - 32:+d} direction 要素")
