#!/usr/bin/env python3
"""強弱記号の位置を確認"""

from music21 import converter, dynamics

def check_dynamics(file_path):
    print(f"\n=== {file_path} ===")
    score = converter.parse(file_path)
    
    for part in score.parts[:3]:  # 最初の3パートのみ
        part_name = part.partName or "Unknown"
        print(f"\n{part_name}:")
        
        measures = part.getElementsByClass('Measure')
        for i, measure in enumerate(measures[:8]):  # 最初の8小節
            measure_num = measure.number if hasattr(measure, 'number') else i+1
            
            # 小節内の強弱記号を取得
            dyns = measure.getElementsByClass('Dynamic')
            if dyns:
                for dyn in dyns:
                    offset = dyn.offset
                    value = dyn.value if hasattr(dyn, 'value') else str(dyn)
                    print(f"  小節{measure_num}: offset={offset:.2f}, {dyn.__class__.__name__}({value})")

if __name__ == '__main__':
    print("元のファイル:")
    check_dynamics('work/inbox/pomp-and-circumstance-march-no-1.mxl')
    
    print("\n\n反転後:")
    check_dynamics('work/outbox/pomp-and-circumstance-march-no-1_rev.mxl')
