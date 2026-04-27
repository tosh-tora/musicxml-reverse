#!/usr/bin/env python3
"""
MusicXML 詳細差分比較スクリプト
"""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from difflib import unified_diff

def extract_musicxml_content(mxl_path: Path) -> str:
    """MXLファイルからMusicXML内容を抽出"""
    with zipfile.ZipFile(mxl_path, 'r') as zf:
        # META-INF/container.xml から実際の MusicXML ファイル名を取得
        container = ET.fromstring(zf.read('META-INF/container.xml'))
        rootfile = container.find('.//{*}rootfile')
        xml_filename = rootfile.get('full-path') if rootfile is not None else None

        if not xml_filename:
            # フォールバック: .xml で終わる最初のファイルを使用
            for name in zf.namelist():
                if name.endswith('.xml') and not name.startswith('META-INF'):
                    xml_filename = name
                    break

        if not xml_filename:
            raise ValueError(f"MusicXML file not found in {mxl_path}")

        content = zf.read(xml_filename).decode('utf-8')
        return content

def normalize_xml(xml_str: str) -> list[str]:
    """XMLを正規化して比較しやすくする"""
    try:
        root = ET.fromstring(xml_str)
        # 再フォーマット（インデントを統一）
        ET.indent(root, space='  ')
        normalized = ET.tostring(root, encoding='unicode')
        return normalized.splitlines()
    except Exception as e:
        print(f"XML解析エラー: {e}")
        # フォールバック: 単純な行分割
        return xml_str.splitlines()

def compare_files(original_path: Path, restored_path: Path):
    """2つのMXLファイルを詳細比較"""
    print(f"比較対象:")
    print(f"  元ファイル: {original_path}")
    print(f"  再反転後:   {restored_path}")

    # MusicXML内容を抽出
    print("\n=== MusicXML内容を抽出中 ===")
    original_xml = extract_musicxml_content(original_path)
    restored_xml = extract_musicxml_content(restored_path)

    # 正規化
    print("=== XMLを正規化中 ===")
    original_lines = normalize_xml(original_xml)
    restored_lines = normalize_xml(restored_xml)

    # 差分を計算
    print("\n=== 差分を計算中 ===")
    diff = list(unified_diff(
        original_lines,
        restored_lines,
        fromfile='original.xml',
        tofile='restored.xml',
        lineterm=''
    ))

    if not diff:
        print("[OK] 完全に一致しています！差異はありません。")
        return

    print(f"\n[差異検出] {len([l for l in diff if l.startswith('+') or l.startswith('-')])} 行に差異があります\n")

    # 差異を分類
    added_lines = [l for l in diff if l.startswith('+') and not l.startswith('+++')]
    removed_lines = [l for l in diff if l.startswith('-') and not l.startswith('---')]

    # 差異の要約
    print("=== 差異の要約 ===")
    print(f"追加行: {len(added_lines)}")
    print(f"削除行: {len(removed_lines)}")

    # 差異の詳細（最初の50行のみ表示）
    print("\n=== 差異の詳細（最初の50行）===")
    for i, line in enumerate(diff[:50], 1):
        print(line)

    if len(diff) > 50:
        print(f"\n... 残り {len(diff) - 50} 行は省略 ...")

    # 差異パターンの分析
    print("\n=== 差異パターン分析 ===")
    analyze_differences(added_lines, removed_lines)

def analyze_differences(added_lines: list[str], removed_lines: list[str]):
    """差異のパターンを分析"""
    patterns = {
        'offset': 0,
        'duration': 0,
        'pitch': 0,
        'dynamics': 0,
        'slur': 0,
        'tie': 0,
        'beam': 0,
        'measure_number': 0,
        'other': 0
    }

    all_diff_lines = added_lines + removed_lines

    for line in all_diff_lines:
        if 'offset=' in line or '<offset>' in line:
            patterns['offset'] += 1
        elif 'duration=' in line or '<duration>' in line:
            patterns['duration'] += 1
        elif '<pitch>' in line or '<step>' in line or '<octave>' in line:
            patterns['pitch'] += 1
        elif '<dynamics>' in line or '<wedge' in line:
            patterns['dynamics'] += 1
        elif '<slur' in line:
            patterns['slur'] += 1
        elif '<tie' in line or '<tied' in line:
            patterns['tie'] += 1
        elif '<beam' in line:
            patterns['beam'] += 1
        elif 'number=' in line:
            patterns['measure_number'] += 1
        else:
            patterns['other'] += 1

    print("検出された差異の種類:")
    for key, count in patterns.items():
        if count > 0:
            print(f"  - {key}: {count} 箇所")

def main():
    original = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/original.mxl")
    restored = Path("C:/Users/I018970/AppData/Local/Temp/mrev_test/restored.mxl")

    if not original.exists():
        print(f"エラー: {original} が見つかりません")
        return

    if not restored.exists():
        print(f"エラー: {restored} が見つかりません")
        return

    compare_files(original, restored)

if __name__ == "__main__":
    main()
