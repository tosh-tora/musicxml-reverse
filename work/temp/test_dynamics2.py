#!/usr/bin/env python3
"""強弱記号と他の要素の位置を確認"""

from music21 import converter

def check_all_elements(file_path):
    print(f"\n=== {file_path} ===")
    score = converter.parse(file_path)
    
    # 最初のパートの最初の数小節を詳細に表示
    part = score.parts[0]
    part_name = part.partName or "Unknown"
    print(f"\n{part_name} (最初の4小節):")
    
    measures = part.getElementsByClass('Measure')
    for i, measure in enumerate(measures[:4]):
        measure_num = measure.number if hasattr(measure, 'number') else i+1
        measure_duration = measure.duration.quarterLength
        
        print(f"\n小節{measure_num} (長さ: {measure_duration}拍):")
        
        # すべての要素を表示
        for element in measure:
            offset = element.offset
            class_name = element.__class__.__name__
            
            # 詳細情報
            if class_name in ['Note', 'Rest']:
                duration = element.duration.quarterLength
                print(f"  offset={offset:.2f}: {class_name} (duration={duration})")
            elif 'Dynamic' in class_name:
                value = element.value if hasattr(element, 'value') else str(element)
                print(f"  offset={offset:.2f}: {class_name} ({value})")
            elif class_name not in ['Clef', 'KeySignature', 'TimeSignature', 'Instrument']:
                print(f"  offset={offset:.2f}: {class_name}")

if __name__ == '__main__':
    print("元のファイル:")
    check_all_elements('work/inbox/pomp-and-circumstance-march-no-1.mxl')
    
    print("\n\n反転後:")
    check_all_elements('work/outbox/pomp-and-circumstance-march-no-1_rev.mxl')
