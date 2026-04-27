"""実ファイルでのSlur使用状況を詳細確認"""
from music21 import converter
import os

test_files = []
if os.path.exists('work'):
    for f in os.listdir('work'):
        if f.endswith('.mxl'):
            test_files.append(os.path.join('work', f))

if not test_files:
    print("No .mxl files found")
    exit(0)

print("Slur usage in actual files\n")
print("=" * 60)

for test_file in test_files[:1]:  # 最初の1ファイルのみ
    try:
        print(f"\nAnalyzing: {os.path.basename(test_file)}\n")
        score = converter.parse(test_file)
        
        slur_count = 0
        glissando_count = 0
        trill_count = 0
        pedal_count = 0
        other_spanners = {}
        
        for part in score.parts:
            for sp in part.spannerBundle:
                sp_type = type(sp).__name__
                if sp_type == 'Slur':
                    slur_count += 1
                elif sp_type == 'Glissando':
                    glissando_count += 1
                elif sp_type.startswith('Trill'):
                    trill_count += 1
                elif sp_type == 'Pedal':
                    pedal_count += 1
                elif sp_type not in ['Crescendo', 'Diminuendo', 'Ottava']:
                    if sp_type not in other_spanners:
                        other_spanners[sp_type] = 0
                    other_spanners[sp_type] += 1
        
        print(f"Slur: {slur_count}")
        print(f"Glissando: {glissando_count}")
        print(f"Trill: {trill_count}")
        print(f"Pedal: {pedal_count}")
        
        if other_spanners:
            print(f"\nOther spanners:")
            for sp_type, count in sorted(other_spanners.items()):
                print(f"  - {sp_type}: {count}")
        
        # Slurの詳細を調査（最初の10個のみ）
        if slur_count > 0:
            print(f"\n--- First 10 Slurs ---")
            count = 0
            for part in score.parts:
                if count >= 10:
                    break
                for sp in part.spannerBundle:
                    if type(sp).__name__ == 'Slur':
                        elements = list(sp.getSpannedElements())
                        if elements:
                            first = elements[0]
                            last = elements[-1]
                            print(f"Slur: {len(elements)} elements, "
                                  f"from {first.nameWithOctave if hasattr(first, 'nameWithOctave') else type(first).__name__} "
                                  f"to {last.nameWithOctave if hasattr(last, 'nameWithOctave') else type(last).__name__}")
                        count += 1
                        if count >= 10:
                            break
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
