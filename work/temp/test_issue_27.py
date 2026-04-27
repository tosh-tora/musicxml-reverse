#!/usr/bin/env python3
"""
Issue #27 テスト: direction要素の増殖を検証

威風堂々のViolaファイルで、Tempo primo.やrit.などのdirection要素が
増殖しないことを確認する。
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def count_directions(mxl_path: Path) -> dict:
    """MXLファイル内のdirection要素をカウント"""
    with zipfile.ZipFile(mxl_path, 'r') as zf:
        # container.xmlから実際のMusicXMLファイル名を取得
        container = ET.fromstring(zf.read('META-INF/container.xml'))
        rootfile = container.find('.//{*}rootfile')
        xml_filename = rootfile.get('full-path') if rootfile is not None else None

        if not xml_filename:
            for name in zf.namelist():
                if name.endswith('.xml') and not name.startswith('META-INF'):
                    xml_filename = name
                    break

        content = zf.read(xml_filename).decode('utf-8')
        root = ET.fromstring(content)

    # direction要素を収集
    directions = []
    for part in root.findall('.//{*}part'):
        for measure in part.findall('.//{*}measure'):
            measure_num = measure.get('number', '?')
            for direction in measure.findall('.//{*}direction'):
                # direction内の情報を収集
                info = {
                    'measure': measure_num,
                    'placement': direction.get('placement'),
                }

                # wordsテキストを取得
                words = direction.find('.//{*}direction-type/{*}words')
                if words is not None and words.text:
                    info['words'] = words.text.strip()
                else:
                    info['words'] = ''

                # sound要素の有無
                sound = direction.find('.//{*}sound')
                info['has_sound'] = sound is not None
                if sound is not None:
                    info['tempo'] = sound.get('tempo')

                directions.append(info)

    return {
        'total': len(directions),
        'details': directions
    }


def main():
    """メイン処理"""
    # テストファイル
    input_file = Path('work/inbox/test/威風堂々ラスト_in-Viola.mxl')
    output_file = Path('work/outbox/test/威風堂々ラスト_out-Viola.mxl')

    if not input_file.exists():
        print(f"エラー: 入力ファイルが見つかりません: {input_file}")
        return

    print("=== Issue #27 検証: direction要素の増殖 ===\n")

    # 入力ファイルのdirection要素をカウント
    print(f"入力ファイル: {input_file.name}")
    input_dirs = count_directions(input_file)
    print(f"  direction要素数: {input_dirs['total']}")

    # 詳細を表示（最初の5個）
    print("\n  最初の5個:")
    for i, d in enumerate(input_dirs['details'][:5], 1):
        print(f"    {i}. measure={d['measure']}, words=\"{d['words']}\", "
              f"has_sound={d['has_sound']}, tempo={d.get('tempo', 'N/A')}")

    # reverse_score.pyを実行
    print("\n反転処理を実行中...")
    import subprocess
    result = subprocess.run(['python', 'reverse_score.py'], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"エラー: reverse_score.py の実行に失敗しました")
        print(result.stderr)
        return

    if not output_file.exists():
        print(f"エラー: 出力ファイルが生成されませんでした: {output_file}")
        return

    # 出力ファイルのdirection要素をカウント
    print(f"\n出力ファイル: {output_file.name}")
    output_dirs = count_directions(output_file)
    print(f"  direction要素数: {output_dirs['total']}")

    # 詳細を表示（最初の5個）
    print("\n  最初の5個:")
    for i, d in enumerate(output_dirs['details'][:5], 1):
        print(f"    {i}. measure={d['measure']}, words=\"{d['words']}\", "
              f"has_sound={d['has_sound']}, tempo={d.get('tempo', 'N/A')}")

    # 結果を比較
    print("\n=== 結果 ===")
    diff = output_dirs['total'] - input_dirs['total']

    if diff == 0:
        print(f"✓ PASS: direction要素数は変わっていません ({input_dirs['total']} → {output_dirs['total']})")
    elif diff > 0:
        print(f"✗ FAIL: direction要素が {diff} 個増加しました ({input_dirs['total']} → {output_dirs['total']})")

        # 増加した要素を特定
        print("\n  増加の詳細:")
        # 空のwords要素をカウント
        empty_words_count = sum(1 for d in output_dirs['details'] if d['words'] == '')
        print(f"    空のwords要素: {empty_words_count}")

        # 重複をカウント（同じwordsテキストが複数回）
        from collections import Counter
        words_counter = Counter(d['words'] for d in output_dirs['details'] if d['words'])
        duplicates = {w: c for w, c in words_counter.items() if c > 1}
        if duplicates:
            print(f"    重複しているwords:")
            for words, count in duplicates.items():
                print(f"      \"{words}\": {count}回")
    else:
        print(f"⚠ WARNING: direction要素が {-diff} 個減少しました ({input_dirs['total']} → {output_dirs['total']})")


if __name__ == '__main__':
    main()
