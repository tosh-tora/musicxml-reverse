#!/usr/bin/env python3
"""
MusicXML 反転→再反転→差分検証スクリプト
"""
from pathlib import Path
from reverse_score import process_file, ErrorHandling

def main():
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    reversed1 = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/reversed.mxl")
    reversed2 = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    print("=== 1回目の反転（元→reversed）===")
    report1 = process_file(original, reversed1, ErrorHandling.SKIP_PART)

    print("\n=== 2回目の反転（reversed→restored）===")
    report2 = process_file(reversed1, reversed2, ErrorHandling.SKIP_PART)

    print("\n=== 音符数の比較 ===")
    print(f"元ファイル:        {report1.input_note_count} notes")
    print(f"1回目反転後:       {report1.output_note_count} notes")
    print(f"2回目反転後:       {report2.output_note_count} notes")

    if report1.input_note_count == report2.output_note_count:
        print("[OK] 音符数は一致しています")
    else:
        print(f"[NG] 音符数が不一致: {report1.input_note_count} → {report2.output_note_count}")

    print("\n=== 処理レポート ===")
    if report1.has_issues():
        print("\n1回目の反転で検出された問題:")
        report1.print_report()

    if report2.has_issues():
        print("\n2回目の反転で検出された問題:")
        report2.print_report()

    if not report1.has_issues() and not report2.has_issues():
        print("[OK] 問題なく処理完了")

if __name__ == "__main__":
    main()
