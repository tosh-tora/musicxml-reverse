#!/usr/bin/env python3
"""トリル重複修正の検証スクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from reverse_score import process_file, ErrorHandling

# 入出力ファイル
input_file = project_root / "work/inbox/威風堂々ラスト_in-Concert_Snare_Drum.mxl"
output_file = project_root / "work/outbox/test/威風堂々ラスト_in-Concert_Snare_Drum_rev.mxl"

# 出力ディレクトリ作成
output_file.parent.mkdir(parents=True, exist_ok=True)

# 反転実行
print(f"入力: {input_file}")
print(f"出力: {output_file}")
print("反転処理開始...\n")

report = process_file(
    input_path=input_file,
    output_path=output_file,
    error_handling=ErrorHandling.SKIP_PART
)

if report.success:
    print(f"\n[OK] 反転成功: {output_file}")
    print(f"  パート数: {report.part_count}")
    print(f"  入力音符数: {report.input_note_count}")
    print(f"  出力音符数: {report.output_note_count}")
    if report.skipped_measures > 0:
        print(f"  スキップ小節数: {report.skipped_measures}")
    if report.has_issues():
        print("\n問題レポート:")
        report.print_report()
else:
    print(f"\n[ERROR] 反転失敗")
    report.print_report()
