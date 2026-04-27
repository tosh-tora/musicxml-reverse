import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

input_file = Path('work/temp/Flute_no_layout.mxl')

results = []

# XMLを読み込み
with zipfile.ZipFile(input_file, 'r') as z:
    for name in z.namelist():
        if name.endswith('.xml') and 'META' not in name:
            content = z.read(name).decode('utf-8')
            lines_with_slur_before = [line.strip() for line in content.split('\n') if 'slur' in line.lower()]
            results.append(f'Before ET.parse - Slurs: {len(lines_with_slur_before)}')

            # ET.fromstringでパース
            root = ET.fromstring(content)

            # 再度シリアライズ
            xml_bytes = ET.tostring(root, encoding='utf-8')
            xml_content = xml_bytes.decode('utf-8')
            lines_with_slur_after = [line.strip() for line in xml_content.split('\n') if 'slur' in line.lower()]
            results.append(f'After ET.tostring - Slurs: {len(lines_with_slur_after)}')

            break

# 結果をファイルに書き出し
with open('work/temp/test_et_result.txt', 'w') as f:
    f.write('\n'.join(results))
