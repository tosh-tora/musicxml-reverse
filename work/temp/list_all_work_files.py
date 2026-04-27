"""workディレクトリ内のすべてのMusicXMLファイルを調査"""
import os
from music21 import converter

if not os.path.exists('work'):
    print("work directory not found")
    exit(0)

files = []
for f in os.listdir('work'):
    if f.endswith('.musicxml') or f.endswith('.mxl'):
        files.append(f)

print(f"Found {len(files)} files in work/\n")
print("=" * 60)

# 各ファイルでspanner情報を収集
all_spanners = {}
for filename in files[:10]:  # 最初の10ファイル
    filepath = os.path.join('work', filename)
    try:
        score = converter.parse(filepath)
        spanners = set()
        for part in score.parts:
            for sp in part.spannerBundle:
                spanners.add(type(sp).__name__)
        
        if spanners:
            print(f"\n{filename}:")
            for sp_type in sorted(spanners):
                print(f"  - {sp_type}")
                if sp_type not in all_spanners:
                    all_spanners[sp_type] = 0
                all_spanners[sp_type] += 1
    except Exception as e:
        print(f"\n{filename}: Error - {e}")

print("\n" + "=" * 60)
print("\nSummary of all spanners:\n")
for sp_type, count in sorted(all_spanners.items()):
    print(f"- {sp_type}: found in {count} file(s)")

print("\n" + "=" * 60)
