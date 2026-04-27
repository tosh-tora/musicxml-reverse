"""MusicXMLでstart/stop順序を持つ要素の調査"""
from music21 import converter, stream
import os

# 既存のテストファイルを探す
test_files = []
if os.path.exists('work'):
    for f in os.listdir('work'):
        if f.endswith('.musicxml') or f.endswith('.mxl'):
            test_files.append(os.path.join('work', f))

if not test_files:
    print("No test files found")
    exit(0)

print("Investigation of start/stop elements\n")
print("=" * 60)

# 調査対象の要素タイプ
elements_to_check = {
    'Tie': 'tie (note connection)',
    'Beam': 'beam',
    'Tuplet': 'tuplet',
    'Slur': 'slur',
    'Crescendo': 'crescendo',
    'Diminuendo': 'diminuendo',
    'Trill': 'trill',
    'Glissando': 'glissando',
    'Pedal': 'pedal',
    'Ottava': 'ottava (8va, etc.)',
    'Vibrato': 'vibrato',
    'Tremolo': 'tremolo',
    'Bracket': 'bracket',
    'Dashes': 'dashes',
    'Wedge': 'wedge (dynamics)',
}

print("\n## Known start/stop elements\n")
for elem_type, description in elements_to_check.items():
    print(f"- {elem_type}: {description}")

# reverse_score.pyで対応済みの要素を確認
print("\n" + "=" * 60)
print("## Implementation status in reverse_score.py\n")

with open('reverse_score.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
implemented = []
not_implemented = []

for elem_type, description in elements_to_check.items():
    # 関数名やコメントで言及されているか確認
    if f'reverse_{elem_type.lower()}' in content.lower():
        implemented.append((elem_type, description))
    elif elem_type.lower() in content.lower():
        # 何らかの形で言及されている
        if 'spanner' in elem_type.lower() or elem_type in ['Slur', 'Crescendo', 'Diminuendo', 'Ottava']:
            implemented.append((elem_type, description, '(handled as spanner)'))
        else:
            not_implemented.append((elem_type, description, '(mentioned, needs verification)'))
    else:
        not_implemented.append((elem_type, description))

print("### [OK] Implemented\n")
for item in implemented:
    if len(item) == 3:
        print(f"- {item[0]}: {item[1]} {item[2]}")
    else:
        print(f"- {item[0]}: {item[1]}")

print("\n### [TODO] Not implemented\n")
for item in not_implemented:
    if len(item) == 3:
        print(f"- {item[0]}: {item[1]} {item[2]}")
    else:
        print(f"- {item[0]}: {item[1]}")

print("\n" + "=" * 60)
print("## Usage in actual files\n")

# 実際のファイルで使われている要素を確認
found_elements = {}
for test_file in test_files[:3]:  # 最初の3ファイルのみ
    try:
        score = converter.parse(test_file)
        print(f"\n### {os.path.basename(test_file)}\n")
        
        for part in score.parts:
            # Spannerをチェック
            for sp in part.spannerBundle:
                sp_type = type(sp).__name__
                if sp_type not in found_elements:
                    found_elements[sp_type] = 0
                found_elements[sp_type] += 1
            
            # 個別要素をチェック
            for measure in part.getElementsByClass(stream.Measure):
                for element in measure.flatten():
                    # Tie
                    if hasattr(element, 'tie') and element.tie is not None:
                        if 'Tie' not in found_elements:
                            found_elements['Tie'] = 0
                        found_elements['Tie'] += 1
                    
                    # Beam
                    if hasattr(element, 'beams') and element.beams is not None:
                        if len(element.beams.beamsList) > 0:
                            if 'Beam' not in found_elements:
                                found_elements['Beam'] = 0
                            found_elements['Beam'] += 1
                    
                    # Tuplet
                    if hasattr(element, 'duration') and element.duration.tuplets:
                        if 'Tuplet' not in found_elements:
                            found_elements['Tuplet'] = 0
                        found_elements['Tuplet'] += 1
        
        for elem_type, count in sorted(found_elements.items()):
            desc = elements_to_check.get(elem_type, '(no description)')
            print(f"- {elem_type}: {count} found - {desc}")
        
        found_elements = {}  # リセット
        
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "=" * 60)
