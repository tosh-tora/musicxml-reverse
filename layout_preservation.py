#!/usr/bin/env python3
"""
MusicXML Layout Preservation Module

レイアウト属性（座標情報）を保存・変換・復元して、
反転後のスコアの視覚的品質を維持する。

処理フロー:
1. extract_layout_from_xml: 元のXMLからレイアウト情報を抽出
2. calculate_original_position: 反転後の位置から元の位置を逆算
3. transform_layout_for_reversal: 座標を反転用に変換
4. apply_layout_to_xml: 変換後のレイアウトを出力XMLに適用
"""

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ElementLayout:
    """単一要素のレイアウト属性"""
    # 座標属性
    default_x: Optional[float] = None
    default_y: Optional[float] = None
    relative_x: Optional[float] = None
    relative_y: Optional[float] = None
    placement: Optional[str] = None  # "above" | "below"

    # 識別用（マッチングキー）
    element_type: str = ""  # "note", "dynamics", "words", "wedge"
    offset: float = 0.0
    pitch: Optional[str] = None      # 音符の場合
    text: Optional[str] = None       # ダイナミクス/テキストの場合
    duration: float = 0.0


@dataclass
class MeasureLayout:
    """小節全体のレイアウト"""
    width: Optional[float] = None  # <measure width="X"> 属性
    elements: list[ElementLayout] = field(default_factory=list)


@dataclass
class LayoutMap:
    """スコア全体のレイアウト情報"""
    measures: dict[tuple[str, int], MeasureLayout] = field(default_factory=dict)
    # Key: (part_id, measure_number)


def _extract_mxl_content(mxl_path: Path) -> tuple[ET.Element, str]:
    """
    MXLファイルからXMLコンテンツを抽出

    Returns:
        (root, xml_filename): パースされたXMLルートと内部ファイル名
    """
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
        root = ET.fromstring(content)
        return root, xml_filename


def extract_layout_from_xml(xml_path: Path) -> LayoutMap:
    """
    元のMusicXMLファイルからレイアウト属性を抽出

    Phase 1で使用: music21処理前に元のレイアウトを保存

    Args:
        xml_path: MusicXMLファイル(.xml または .mxl)

    Returns:
        LayoutMap: 抽出されたレイアウト情報
    """
    layout_map = LayoutMap()

    # ファイルを読み込み
    if xml_path.suffix == '.mxl':
        root, _ = _extract_mxl_content(xml_path)
    else:
        tree = ET.parse(xml_path)
        root = tree.getroot()

    # 名前空間を考慮した検索（MusicXMLは名前空間を使う場合がある）
    ns = {'': root.tag.split('}')[0].strip('{') if '}' in root.tag else ''}

    # 各パートを走査
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        # 各小節を走査
        for measure in part.findall('.//{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str is None:
                continue

            try:
                measure_num = int(measure_num_str)
            except ValueError:
                continue

            measure_key = (part_id, measure_num)
            measure_layout = MeasureLayout()

            # 小節幅を抽出
            width_str = measure.get('width')
            if width_str:
                try:
                    measure_layout.width = float(width_str)
                except ValueError:
                    pass

            # 現在のオフセット（divisions単位）を追跡
            current_offset = 0.0
            divisions = 1.0  # デフォルト

            # attributes要素からdivisionsを取得
            for attributes in measure.findall('.//{*}attributes'):
                div_elem = attributes.find('.//{*}divisions')
                if div_elem is not None and div_elem.text:
                    try:
                        divisions = float(div_elem.text)
                    except ValueError:
                        pass

            # 小節内の要素を走査
            for elem in measure:
                # direction要素（ダイナミクス、テキストなど）
                if elem.tag.endswith('direction'):
                    # offset属性（direction要素内のオフセット）
                    offset_elem = elem.find('.//{*}offset')
                    direction_offset = 0.0
                    if offset_elem is not None and offset_elem.text:
                        try:
                            direction_offset = float(offset_elem.text)
                        except ValueError:
                            pass

                    # ダイナミクス
                    dynamics = elem.find('.//{*}dynamics')
                    if dynamics is not None:
                        # ダイナミクスのタイプを取得（f, p, mf, etc.）
                        dynamic_type = None
                        for child in dynamics:
                            if child.tag.endswith(('f', 'p', 'mf', 'mp', 'ff', 'pp',
                                                     'fff', 'ppp', 'fp', 'sf', 'sfz')):
                                dynamic_type = child.tag.split('}')[-1]
                                break

                        if dynamic_type:
                            # 座標属性を抽出
                            default_x = dynamics.get('default-x')
                            default_y = dynamics.get('default-y')
                            relative_x = dynamics.get('relative-x')
                            relative_y = dynamics.get('relative-y')
                            placement = elem.get('placement')

                            elem_layout = ElementLayout(
                                element_type='dynamics',
                                offset=current_offset + direction_offset,
                                text=dynamic_type,
                                default_x=float(default_x) if default_x else None,
                                default_y=float(default_y) if default_y else None,
                                relative_x=float(relative_x) if relative_x else None,
                                relative_y=float(relative_y) if relative_y else None,
                                placement=placement
                            )
                            measure_layout.elements.append(elem_layout)

                # note要素の後にオフセットを更新
                elif elem.tag.endswith('note'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            # chord要素がない場合のみオフセットを進める
                            if elem.find('.//{*}chord') is None:
                                current_offset += duration / divisions
                        except ValueError:
                            pass

                # backup要素でオフセットを戻す
                elif elem.tag.endswith('backup'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            current_offset -= duration / divisions
                            current_offset = max(0.0, current_offset)
                        except ValueError:
                            pass

                # forward要素でオフセットを進める
                elif elem.tag.endswith('forward'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            current_offset += duration / divisions
                        except ValueError:
                            pass

            layout_map.measures[measure_key] = measure_layout

    return layout_map


def calculate_original_position(
    reversed_measure_num: int,
    reversed_offset: float,
    element_duration: float,
    measure_duration: float,
    total_measures: int
) -> tuple[int, float]:
    """
    反転後の位置から元の位置を逆算

    Args:
        reversed_measure_num: 反転後の小節番号
        reversed_offset: 反転後のオフセット（四分音符単位）
        element_duration: 要素の長さ（四分音符単位）
        measure_duration: 小節の長さ（四分音符単位）
        total_measures: 総小節数

    Returns:
        (original_measure_num, original_offset): 元の小節番号とオフセット
    """
    # 小節番号を反転
    original_measure_num = total_measures - reversed_measure_num + 1

    # 小節内オフセットを反転（reverse_score.pyのreverse_note_offsetと同じロジック）
    original_offset = measure_duration - reversed_offset - element_duration
    original_offset = max(0.0, original_offset)

    return original_measure_num, original_offset


def transform_layout_for_reversal(
    original_layout: ElementLayout,
    measure_width: Optional[float]
) -> ElementLayout:
    """
    レイアウト座標を反転用に変換

    Args:
        original_layout: 元のレイアウト情報
        measure_width: 小節幅（tenths単位）

    Returns:
        ElementLayout: 変換後のレイアウト情報
    """
    # レイアウトをコピー
    transformed = ElementLayout(
        element_type=original_layout.element_type,
        offset=original_layout.offset,
        pitch=original_layout.pitch,
        text=original_layout.text,
        duration=original_layout.duration,
        default_y=original_layout.default_y,      # Y座標はそのまま
        relative_x=original_layout.relative_x,    # relative座標はそのまま
        relative_y=original_layout.relative_y,
        placement=original_layout.placement       # placementはそのまま
    )

    # X座標のみ鏡像反転
    if original_layout.default_x is not None and measure_width is not None:
        transformed.default_x = measure_width - original_layout.default_x
    else:
        transformed.default_x = original_layout.default_x  # 変換不可の場合はそのまま

    return transformed


def merge_split_directions(output_xml_path: Path, verbose: bool = False) -> None:
    """
    music21が誤って分割したdirection要素をマージする

    music21のバグ: <words>と<sound>を含むdirection要素を、
    - <words />と<sound>の組
    - <words>テキストのみ
    の2つに分割してしまう。これらを元の1つに統合する。

    重要: 分割された direction は小節内の異なる位置に配置されることがあるため、
    placement 属性とsound/words パターンでマッチングする。

    Args:
        output_xml_path: 出力MusicXMLファイル(.xml または .mxl)
        verbose: デバッグログを出力する
    """
    # ファイルを読み込み
    is_mxl = output_xml_path.suffix == '.mxl'

    if is_mxl:
        root, xml_filename = _extract_mxl_content(output_xml_path)
    else:
        tree = ET.parse(output_xml_path)
        root = tree.getroot()

    merge_count = 0

    # 各パートを走査
    for part in root.findall('.//{*}part'):
        # 各小節を走査
        for measure in part.findall('.//{*}measure'):
            measure_num = measure.get('number', '?')

            # 小節内のdirection要素をすべて収集
            directions = list(measure.findall('{*}direction'))  # 直接の子要素のみ

            if len(directions) < 2:
                continue

            if verbose and len(directions) > 1:
                print(f"  measure {measure_num}: {len(directions)} directions before merge")

            # 空words+soundのdirection（マージ元）を収集
            empty_word_dirs = []
            for i, d in enumerate(directions):
                words = d.find('.//{*}direction-type/{*}words')
                sound = d.find('.//{*}sound')
                if (words is not None and
                    sound is not None and
                    (words.text is None or words.text.strip() == '')):
                    empty_word_dirs.append(i)

            # wordsのみのdirection（マージ先）を収集
            text_only_dirs = []
            for i, d in enumerate(directions):
                words = d.find('.//{*}direction-type/{*}words')
                sound = d.find('.//{*}sound')
                if (words is not None and
                    words.text is not None and
                    words.text.strip() != '' and
                    sound is None):
                    text_only_dirs.append(i)

            if verbose and (empty_word_dirs or text_only_dirs):
                print(f"    empty_word_dirs: {empty_word_dirs}, text_only_dirs: {text_only_dirs}")

            # マッチングしてマージ
            merged_indices = set()
            for empty_idx in empty_word_dirs:
                if empty_idx in merged_indices:
                    continue

                dir_empty = directions[empty_idx]
                placement_empty = dir_empty.get('placement')

                # 同じplacement属性を持つtext_only directionを探す
                for text_idx in text_only_dirs:
                    if text_idx in merged_indices:
                        continue

                    dir_text = directions[text_idx]
                    placement_text = dir_text.get('placement')

                    if placement_empty == placement_text:
                        # マッチ！マージを実行
                        if verbose:
                            print(f"    merging: empty_idx={empty_idx} + text_idx={text_idx}")

                        # dir_textのwordsテキストをdir_emptyのwordsにコピー
                        words_empty = dir_empty.find('.//{*}direction-type/{*}words')
                        words_text = dir_text.find('.//{*}direction-type/{*}words')
                        if words_empty is not None and words_text is not None:
                            words_empty.text = words_text.text

                        # dir_textの他の属性もdir_emptyに復元
                        for attr_name, attr_value in dir_text.attrib.items():
                            if attr_name not in dir_empty.attrib or attr_name == 'system':
                                dir_empty.set(attr_name, attr_value)

                        # dir_textを削除
                        measure.remove(dir_text)
                        merged_indices.add(empty_idx)
                        merged_indices.add(text_idx)
                        merge_count += 1
                        break  # 1対1マッチング

            if verbose and merge_count > 0:
                remaining = len(list(measure.findall('{*}direction')))
                print(f"  measure {measure_num}: {remaining} directions after merge")

    if verbose:
        print(f"  Total merged: {merge_count} direction pairs")

    # 変更後のXMLを書き出し
    if is_mxl:
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_mxl = Path(tmpdir) / 'output.mxl'
            shutil.copy2(output_xml_path, tmp_mxl)

            xml_content = ET.tostring(root, encoding='utf-8', xml_declaration=True)

            with zipfile.ZipFile(output_xml_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
                with zipfile.ZipFile(tmp_mxl, 'r') as zf_in:
                    for item in zf_in.namelist():
                        if item == xml_filename:
                            zf_out.writestr(item, xml_content)
                        else:
                            zf_out.writestr(item, zf_in.read(item))
    else:
        tree = ET.ElementTree(root)
        tree.write(output_xml_path, encoding='utf-8', xml_declaration=True)


def apply_layout_to_xml(
    output_xml_path: Path,
    original_layout_map: LayoutMap,
    total_measures: int
) -> None:
    """
    music21の出力XMLにレイアウト属性を適用

    Phase 3で使用: 反転処理後のXMLにレイアウトを復元

    Args:
        output_xml_path: 出力MusicXMLファイル(.xml または .mxl)
        original_layout_map: 元のレイアウト情報
        total_measures: 総小節数（反転計算用）
    """
    # ファイルを読み込み
    is_mxl = output_xml_path.suffix == '.mxl'

    if is_mxl:
        root, xml_filename = _extract_mxl_content(output_xml_path)
    else:
        tree = ET.parse(output_xml_path)
        root = tree.getroot()

    # 各パートを走査
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        # 各小節を走査
        for measure in part.findall('.//{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str is None:
                continue

            try:
                reversed_measure_num = int(measure_num_str)
            except ValueError:
                continue

            # 現在のオフセット（四分音符単位）を追跡
            current_offset = 0.0
            divisions = 1.0
            measure_duration = 4.0  # デフォルト4/4拍子

            # attributes要素からdivisionsとtime signatureを取得
            for attributes in measure.findall('.//{*}attributes'):
                div_elem = attributes.find('.//{*}divisions')
                if div_elem is not None and div_elem.text:
                    try:
                        divisions = float(div_elem.text)
                    except ValueError:
                        pass

                time_elem = attributes.find('.//{*}time')
                if time_elem is not None:
                    beats_elem = time_elem.find('.//{*}beats')
                    beat_type_elem = time_elem.find('.//{*}beat-type')
                    if beats_elem is not None and beat_type_elem is not None:
                        try:
                            beats = float(beats_elem.text)
                            beat_type = float(beat_type_elem.text)
                            measure_duration = beats * (4.0 / beat_type)
                        except (ValueError, ZeroDivisionError):
                            pass

            # 小節内の要素を走査
            for elem in measure:
                # direction要素（ダイナミクス、テキストなど）
                if elem.tag.endswith('direction'):
                    # offset属性
                    offset_elem = elem.find('.//{*}offset')
                    direction_offset = 0.0
                    if offset_elem is not None and offset_elem.text:
                        try:
                            direction_offset = float(offset_elem.text)
                        except ValueError:
                            pass

                    reversed_offset = current_offset + direction_offset

                    # ダイナミクス
                    dynamics = elem.find('.//{*}dynamics')
                    if dynamics is not None:
                        # ダイナミクスのタイプを取得
                        dynamic_type = None
                        for child in dynamics:
                            if child.tag.endswith(('f', 'p', 'mf', 'mp', 'ff', 'pp',
                                                     'fff', 'ppp', 'fp', 'sf', 'sfz')):
                                dynamic_type = child.tag.split('}')[-1]
                                break

                        if dynamic_type:
                            # 元の位置を計算
                            original_measure_num, original_offset = calculate_original_position(
                                reversed_measure_num=reversed_measure_num,
                                reversed_offset=reversed_offset,
                                element_duration=0.0,  # ダイナミクスは長さ0
                                measure_duration=measure_duration,
                                total_measures=total_measures
                            )

                            # 元のレイアウトを検索
                            measure_key = (part_id, original_measure_num)
                            if measure_key in original_layout_map.measures:
                                original_measure_layout = original_layout_map.measures[measure_key]

                                # マッチングする要素を探す（ダイナミクスタイプとオフセットで）
                                matched_layout = None
                                min_offset_diff = float('inf')

                                for elem_layout in original_measure_layout.elements:
                                    if (elem_layout.element_type == 'dynamics' and
                                        elem_layout.text == dynamic_type):
                                        offset_diff = abs(elem_layout.offset - original_offset)
                                        if offset_diff < min_offset_diff:
                                            min_offset_diff = offset_diff
                                            matched_layout = elem_layout

                                # マッチした場合、座標を変換して適用
                                if matched_layout and min_offset_diff < 0.1:  # 許容範囲
                                    transformed = transform_layout_for_reversal(
                                        matched_layout,
                                        original_measure_layout.width
                                    )

                                    # XML属性をセット
                                    if transformed.default_x is not None:
                                        dynamics.set('default-x', str(transformed.default_x))
                                    if transformed.default_y is not None:
                                        dynamics.set('default-y', str(transformed.default_y))
                                    if transformed.relative_x is not None:
                                        dynamics.set('relative-x', str(transformed.relative_x))
                                    if transformed.relative_y is not None:
                                        dynamics.set('relative-y', str(transformed.relative_y))
                                    if transformed.placement is not None:
                                        elem.set('placement', transformed.placement)

                # note要素の後にオフセットを更新
                elif elem.tag.endswith('note'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            if elem.find('.//{*}chord') is None:
                                current_offset += duration / divisions
                        except ValueError:
                            pass

                # backup/forward
                elif elem.tag.endswith('backup'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            current_offset -= duration / divisions
                            current_offset = max(0.0, current_offset)
                        except ValueError:
                            pass

                elif elem.tag.endswith('forward'):
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            current_offset += duration / divisions
                        except ValueError:
                            pass

    # 変更後のXMLを書き出し
    if is_mxl:
        # MXLファイルの場合、既存のzipを更新
        # 一時ファイルに書き出してから置換
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_mxl = Path(tmpdir) / 'output.mxl'

            # 元のMXLをコピー
            shutil.copy2(output_xml_path, tmp_mxl)

            # XML内容を更新
            xml_content = ET.tostring(root, encoding='utf-8', xml_declaration=True)

            with zipfile.ZipFile(tmp_mxl, 'a') as zf:
                # 既存のXMLファイルを削除（zipfileは直接削除できないので再作成）
                pass  # 実際には一度展開して再パックする必要がある

            # 簡易実装: 新しいMXLを作成
            with zipfile.ZipFile(output_xml_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
                with zipfile.ZipFile(tmp_mxl, 'r') as zf_in:
                    for item in zf_in.namelist():
                        if item == xml_filename:
                            # 更新されたXMLを書き込み
                            zf_out.writestr(item, xml_content)
                        else:
                            # その他のファイルはそのままコピー
                            zf_out.writestr(item, zf_in.read(item))
    else:
        # XMLファイルの場合、直接書き出し
        tree = ET.ElementTree(root)
        tree.write(output_xml_path, encoding='utf-8', xml_declaration=True)
