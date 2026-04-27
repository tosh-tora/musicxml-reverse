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
class TechnicalElement:
    """Technical要素の保存用（music21が読み込まないもの）"""
    measure_num: int
    note_index: int  # 小節内の音符インデックス
    pitch: Optional[str] = None  # 音符のピッチ（マッチング用）
    pitches: Optional[list[str]] = None  # 和音の場合
    offset: float = 0.0
    technical_xml: str = ""  # technical要素のXML文字列


@dataclass
class DirectionElement:
    """Direction要素の保存用（music21が分割するもの）

    music21はMusicXMLのdirection要素を読み込んで書き出す際、
    words+soundを含む単一のdirection要素を2つに分割してしまう。
    元のXMLを保存し、反転後に復元することでこの問題を回避する。
    """
    measure_num: int
    element_index: int  # 小節内でのdirection要素の出現順
    direction_xml: str  # direction要素全体のXML文字列
    placement: Optional[str] = None  # placement属性
    has_sound: bool = False  # sound子要素を持つか
    has_words: bool = False  # words子要素を持つか
    words_text: Optional[str] = None  # wordsのテキスト内容
    offset_quarters: float = 0.0  # 小節内オフセット（四分音符単位）
    measure_duration_quarters: float = 0.0  # 小節全体の長さ（四分音符単位）


@dataclass
class LayoutMap:
    """スコア全体のレイアウト情報"""
    measures: dict[tuple[str, int], MeasureLayout] = field(default_factory=dict)
    # Key: (part_id, measure_number)
    technical_elements: dict[str, list[TechnicalElement]] = field(default_factory=dict)
    # Key: part_id
    directions: dict[str, list[DirectionElement]] = field(default_factory=dict)
    # Key: part_id
    defaults_xml: Optional[str] = None  # defaults要素をXML文字列として保存
    credits_xml: list[str] = field(default_factory=list)  # credit要素のXML文字列（順序保持）
    part_name: Optional[str] = None  # 表示用パート名（part-name credit のマッチング用）


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

    # defaults要素を抽出して保存（music21が変更してしまうため）
    defaults_elem = root.find('.//{*}defaults')
    if defaults_elem is not None:
        layout_map.defaults_xml = ET.tostring(defaults_elem, encoding='unicode')

    # credit要素を抽出して保存（music21が消してしまうため）
    for credit_elem in root.findall('.//{*}credit'):
        layout_map.credits_xml.append(ET.tostring(credit_elem, encoding='unicode'))

    # 表示用パート名を抽出（part-name credit のマッチング用）
    misc_field = root.find('.//{*}miscellaneous/{*}miscellaneous-field[@name="partName"]')
    if misc_field is not None and misc_field.text:
        layout_map.part_name = misc_field.text.strip()
    else:
        instr_name = root.find('.//{*}score-part/{*}score-instrument/{*}instrument-name')
        if instr_name is not None and instr_name.text:
            layout_map.part_name = instr_name.text.strip()
        else:
            part_name_elem = root.find('.//{*}score-part/{*}part-name')
            if part_name_elem is not None and part_name_elem.text:
                layout_map.part_name = part_name_elem.text.strip()

    # 名前空間を考慮した検索（MusicXMLは名前空間を使う場合がある）
    ns = {'': root.tag.split('}')[0].strip('{') if '}' in root.tag else ''}

    # music21が読み込まないtechnical要素のリスト
    unsupported_technicals = {'open', 'stopped', 'snap-pizzicato', 'thumb-position'}

    # 各パートを走査
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')
        layout_map.technical_elements[part_id] = []
        layout_map.directions[part_id] = []

        # divisions はパート全体で持ち越す（MusicXML は最初の measure で
        # 1 度だけ宣言されることが多い）
        divisions = 1.0

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
            note_index = 0  # 小節内の音符インデックス
            direction_index = 0  # 小節内のdirection要素のインデックス

            # attributes要素からdivisionsを取得
            for attributes in measure.findall('.//{*}attributes'):
                div_elem = attributes.find('.//{*}divisions')
                if div_elem is not None and div_elem.text:
                    try:
                        divisions = float(div_elem.text)
                    except ValueError:
                        pass

            # 小節全体の長さ（四分音符単位）を事前計算
            _scan_offset = 0.0
            _scan_max = 0.0
            for _e in measure:
                if _e.tag.endswith('note'):
                    _d = _e.find('.//{*}duration')
                    if _d is not None and _d.text and _e.find('.//{*}chord') is None:
                        try:
                            _scan_offset += float(_d.text) / divisions
                        except ValueError:
                            pass
                elif _e.tag.endswith('backup'):
                    _d = _e.find('.//{*}duration')
                    if _d is not None and _d.text:
                        try:
                            _scan_offset = max(0.0, _scan_offset - float(_d.text) / divisions)
                        except ValueError:
                            pass
                elif _e.tag.endswith('forward'):
                    _d = _e.find('.//{*}duration')
                    if _d is not None and _d.text:
                        try:
                            _scan_offset += float(_d.text) / divisions
                        except ValueError:
                            pass
                if _scan_offset > _scan_max:
                    _scan_max = _scan_offset
            measure_duration_quarters = _scan_max

            # 小節内の要素を走査
            for elem in measure:
                # direction要素（ダイナミクス、テキストなど）
                if elem.tag.endswith('direction'):
                    # direction要素をXMLとして保存（music21分割問題対策）
                    placement = elem.get('placement')
                    sound = elem.find('.//{*}sound')
                    words = elem.find('.//{*}direction-type/{*}words')

                    has_sound = sound is not None
                    has_words = words is not None
                    words_text = None
                    if words is not None and words.text:
                        words_text = words.text.strip()

                    # direction内のoffset要素も加味して時間位置を計算
                    _offset_elem = elem.find('.//{*}offset')
                    _direction_offset_q = 0.0
                    if _offset_elem is not None and _offset_elem.text:
                        try:
                            _direction_offset_q = float(_offset_elem.text) / divisions
                        except ValueError:
                            pass

                    direction_elem = DirectionElement(
                        measure_num=measure_num,
                        element_index=direction_index,
                        direction_xml=ET.tostring(elem, encoding='unicode'),
                        placement=placement,
                        has_sound=has_sound,
                        has_words=has_words,
                        words_text=words_text,
                        offset_quarters=current_offset + _direction_offset_q,
                        measure_duration_quarters=measure_duration_quarters,
                    )
                    layout_map.directions[part_id].append(direction_elem)
                    direction_index += 1

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

                # note要素の処理
                elif elem.tag.endswith('note'):
                    # technical要素を探す
                    notations = elem.find('.//{*}notations')
                    if notations is not None:
                        technical = notations.find('.//{*}technical')
                        if technical is not None:
                            # music21がサポートしていないtechnical子要素を探す
                            has_unsupported = False
                            for tech_child in technical:
                                tech_name = tech_child.tag.split('}')[-1]
                                if tech_name in unsupported_technicals:
                                    has_unsupported = True
                                    break

                            if has_unsupported:
                                # 音符のピッチ情報を取得
                                pitch_elem = elem.find('.//{*}pitch')
                                pitch_str = None
                                if pitch_elem is not None:
                                    step = pitch_elem.find('.//{*}step')
                                    octave = pitch_elem.find('.//{*}octave')
                                    alter = pitch_elem.find('.//{*}alter')
                                    if step is not None and octave is not None:
                                        pitch_str = step.text + octave.text
                                        if alter is not None:
                                            alter_val = int(float(alter.text))
                                            if alter_val == 1:
                                                pitch_str = step.text + '#' + octave.text
                                            elif alter_val == -1:
                                                pitch_str = step.text + '-' + octave.text

                                # technical要素をXML文字列として保存
                                tech_xml = ET.tostring(technical, encoding='unicode')

                                tech_elem = TechnicalElement(
                                    measure_num=measure_num,
                                    note_index=note_index,
                                    pitch=pitch_str,
                                    offset=current_offset,
                                    technical_xml=tech_xml
                                )
                                layout_map.technical_elements[part_id].append(tech_elem)

                    # オフセット更新
                    duration_elem = elem.find('.//{*}duration')
                    if duration_elem is not None and duration_elem.text:
                        try:
                            duration = float(duration_elem.text)
                            # chord要素がない場合のみオフセットを進める＆インデックスを増やす
                            if elem.find('.//{*}chord') is None:
                                current_offset += duration / divisions
                                note_index += 1
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

    重要: default-x は変換しない（music21が適切な位置を生成するため）
    Y座標と placement 属性のみを復元する

    Args:
        original_layout: 元のレイアウト情報
        measure_width: 小節幅（tenths単位）- 未使用だが互換性のため保持

    Returns:
        ElementLayout: 変換後のレイアウト情報
    """
    transformed = ElementLayout(
        element_type=original_layout.element_type,
        offset=original_layout.offset,
        pitch=original_layout.pitch,
        text=original_layout.text,
        duration=original_layout.duration,
        # X座標は変換しない（music21に任せる）
        default_x=None,
        default_y=original_layout.default_y,      # Y座標はそのまま
        relative_x=None,  # 音符との相対位置も music21 に任せる
        relative_y=original_layout.relative_y,    # Y方向の相対位置は保持
        placement=original_layout.placement       # placementはそのまま
    )

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


# 経過的テンポパターン（reverse_score.pyからの抜粋）
# rit., accel.などの一時的な速度変化を示すパターン
TRANSITIONAL_TEMPO_PATTERNS = [
    'ritardando', 'rit.', 'rit', 'ritenuto', 'riten.', 'riten',
    'rallentando', 'rall.', 'rall', 'rallent.',
    'allargando', 'allarg.', 'allarg',
    'calando', 'cal.',
    'smorzando', 'smorz.', 'smorz',
    'morendo', 'mor.',
    'perdendosi', 'perd.',
    'accelerando', 'accel.', 'accel',
    'stringendo', 'string.', 'string',
    'affrettando', 'affrett.', 'affrett',
    'incalzando', 'incalz.', 'incalz',
    'animando', 'animand.', 'animand',
    'stretto',
]


def _is_transitional_tempo_text(text: str) -> bool:
    """テンポ表記が経過的（一時的な変化）かどうかを判定する"""
    if not text:
        return False
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in TRANSITIONAL_TEMPO_PATTERNS)


def _measure_divisions(measure: ET.Element, default: float = 1.0) -> float:
    """小節（または直前の attributes）から divisions を取得"""
    div_elem = measure.find('.//{*}attributes/{*}divisions')
    if div_elem is not None and div_elem.text:
        try:
            return float(div_elem.text)
        except ValueError:
            pass
    return default


def _find_part_divisions(part: ET.Element, default: float = 1.0) -> float:
    """パート内のいずれかの measure/attributes から divisions を取得"""
    div_elem = part.find('.//{*}attributes/{*}divisions')
    if div_elem is not None and div_elem.text:
        try:
            return float(div_elem.text)
        except ValueError:
            pass
    return default


def _measure_total_quarters(measure: ET.Element, divisions: float) -> float:
    """小節内の note/backup/forward から実時間長（四分音符単位）を計算"""
    offset = 0.0
    max_offset = 0.0
    for child in measure:
        if child.tag.endswith('note'):
            d = child.find('.//{*}duration')
            if d is not None and d.text and child.find('.//{*}chord') is None:
                try:
                    offset += float(d.text) / divisions
                except ValueError:
                    pass
        elif child.tag.endswith('backup'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    offset = max(0.0, offset - float(d.text) / divisions)
                except ValueError:
                    pass
        elif child.tag.endswith('forward'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    offset += float(d.text) / divisions
                except ValueError:
                    pass
        if offset > max_offset:
            max_offset = offset
    return max_offset


def _insert_direction_at_offset(
    measure: ET.Element,
    direction: ET.Element,
    target_offset_quarters: float,
    divisions: Optional[float] = None,
) -> None:
    """target_offset_quarters の時間位置に direction を挿入する。

    note/backup/forward を走査してオフセットが target に達した時点で
    その子要素の直前に挿入する。target が小節末以降なら barline の直前
    （barline がなければ末尾）に挿入する。
    """
    if divisions is None:
        divisions = _measure_divisions(measure)
    offset = 0.0
    epsilon = 1e-6

    # 既に target_offset_quarters <= 0 なら冒頭（attributes 直後）に挿入
    if target_offset_quarters <= epsilon:
        insert_pos = 0
        for idx, child in enumerate(measure):
            if child.tag.endswith('attributes'):
                insert_pos = idx + 1
        measure.insert(insert_pos, direction)
        return

    children = list(measure)
    for idx, child in enumerate(children):
        if child.tag.endswith('note'):
            if child.find('.//{*}chord') is None:
                if offset + epsilon >= target_offset_quarters:
                    measure.insert(idx, direction)
                    return
                d = child.find('.//{*}duration')
                if d is not None and d.text:
                    try:
                        offset += float(d.text) / divisions
                    except ValueError:
                        pass
        elif child.tag.endswith('backup'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    offset = max(0.0, offset - float(d.text) / divisions)
                except ValueError:
                    pass
        elif child.tag.endswith('forward'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    offset += float(d.text) / divisions
                except ValueError:
                    pass
        elif child.tag.endswith('barline'):
            # barline 直前に挿入
            measure.insert(idx, direction)
            return

    # 走査完了 → 末尾に追加
    measure.append(direction)


def _flip_wedge_type(t: Optional[str]) -> str:
    if t == 'crescendo':
        return 'diminuendo'
    if t in ('diminuendo', 'decrescendo'):
        return 'crescendo'
    return t or ''


def _wedge_only_direction(dir_elem: 'DirectionElement') -> Optional[ET.Element]:
    """direction が wedge 単独要素ならその wedge 要素を返す。それ以外は None。"""
    try:
        root = ET.fromstring(dir_elem.direction_xml)
    except ET.ParseError:
        return None
    direction_type = root.find('{*}direction-type')
    if direction_type is None:
        return None
    children = list(direction_type)
    if len(children) != 1:
        return None
    child = children[0]
    if not child.tag.endswith('wedge'):
        return None
    return child


def _separate_wedge_pairs(
    dir_elems: list['DirectionElement']
) -> tuple[list[tuple['DirectionElement', 'DirectionElement']], list['DirectionElement']]:
    """direction リストから wedge start/stop ペアと、それ以外に分離する。

    ペアリングは出現順に number 属性で対応付ける。ペアにならなかった
    wedge direction は他の direction として扱う（フォールバック）。
    """
    pairs: list[tuple[DirectionElement, DirectionElement]] = []
    others: list[DirectionElement] = []
    open_starts: dict[str, DirectionElement] = {}

    classified: list[tuple[DirectionElement, Optional[ET.Element]]] = []
    for d in dir_elems:
        wedge = _wedge_only_direction(d)
        classified.append((d, wedge))

    for d, wedge in classified:
        if wedge is None:
            others.append(d)
            continue
        number = wedge.get('number') or '1'
        wtype = wedge.get('type') or ''
        if wtype in ('crescendo', 'diminuendo', 'decrescendo'):
            # 既に開いている同 number の start は孤立扱い
            if number in open_starts:
                others.append(open_starts.pop(number))
            open_starts[number] = d
        elif wtype == 'stop':
            start = open_starts.pop(number, None)
            if start is not None:
                pairs.append((start, d))
            else:
                others.append(d)
        else:
            others.append(d)

    # 未クローズの start は孤立扱い
    for d in open_starts.values():
        others.append(d)

    return pairs, others


def _strip_dynamics_x_attributes(direction_root: ET.Element) -> None:
    """direction 内の <dynamics> から default-x/relative-x を除去する。

    時間反転に伴い音符の水平位置が変化するため、保存時の元 default-x を
    そのまま復元すると音符との位置がずれる（Issue #30 と同様の問題）。
    X 座標は楽譜ソフト/music21 の自動配置に任せ、ここでは Y 座標と
    placement のみが復元 XML に残るようにする。
    """
    for dyn in direction_root.iter():
        if dyn.tag.endswith('dynamics'):
            for attr in ('default-x', 'relative-x'):
                if attr in dyn.attrib:
                    del dyn.attrib[attr]


def _is_tempo_direction(dir_elem: DirectionElement) -> bool:
    """direction要素がテンポ関連かどうかを判定する

    sound子要素を持つwordsはテンポ指示と判断する。
    """
    return dir_elem.has_sound and dir_elem.has_words


def _calculate_reversed_tempo_directions(
    directions: list[DirectionElement],
    total_measures: int
) -> list[tuple[DirectionElement, int]]:
    """テンポ関連direction要素の反転後位置を計算する

    主要テンポ指示と経過的テンポ指示を分けて処理:
    - 主要テンポ: 有効範囲ベースで反転（次の主要テンポまでの範囲を考慮）
    - 経過的テンポ（rit., accel.等）: 単純な位置反転（相対位置を維持）

    Args:
        directions: テンポ関連のDirectionElementリスト
        total_measures: 総小節数

    Returns:
        (DirectionElement, reversed_measure_num)のタプルリスト
    """
    if not directions:
        return []

    # 主要テンポ指示と経過的テンポ指示を分離
    main_tempos = []
    transitional_tempos = []

    for d in directions:
        if d.words_text and _is_transitional_tempo_text(d.words_text):
            transitional_tempos.append(d)
        else:
            main_tempos.append(d)

    result = []

    # 主要テンポの有効範囲ベース反転
    for i, dir_elem in enumerate(main_tempos):
        # 適用終了位置を計算（次の「異なる小節」の主要テンポの直前まで）
        effective_end = total_measures  # デフォルトは曲の最後
        for j in range(i + 1, len(main_tempos)):
            next_measure = main_tempos[j].measure_num
            if next_measure > dir_elem.measure_num:
                # 次の異なる小節のテンポを見つけた
                effective_end = next_measure - 1
                break

        # 反転後の開始位置を計算
        reversed_start = total_measures - effective_end + 1
        result.append((dir_elem, reversed_start))

    # 経過的テンポは単純な位置反転（小節番号のみ反転）
    for dir_elem in transitional_tempos:
        reversed_start = total_measures - dir_elem.measure_num + 1
        result.append((dir_elem, reversed_start))

    return result


def restore_direction_elements(
    output_xml_path: Path,
    original_layout_map: LayoutMap,
    total_measures: int
) -> None:
    """
    保存したdirection要素を反転後の小節に復元する

    music21が出力したdirection要素を削除し、元のXMLから保存した
    direction要素を反転後の正しい小節に挿入する。

    テンポ関連direction要素（sound+wordsを持つもの）は有効範囲ベースで反転し、
    経過的テンポ（rit., accel.等）のwordsテキストには←記号を付与する。

    Args:
        output_xml_path: 出力MusicXMLファイル(.xml または .mxl)
        original_layout_map: 元のレイアウト情報（direction要素を含む）
        total_measures: 総小節数（反転計算用）
    """
    # ファイルを読み込み
    is_mxl = output_xml_path.suffix == '.mxl'

    if is_mxl:
        root, xml_filename = _extract_mxl_content(output_xml_path)
    else:
        tree = ET.parse(output_xml_path)
        root = tree.getroot()

    # 各パートを処理
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        if part_id not in original_layout_map.directions:
            continue

        # 小節をインデックスでアクセスできるようにマップを作成
        measure_map = {}
        for measure in part.findall('.//{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str:
                try:
                    measure_map[int(measure_num_str)] = measure
                except ValueError:
                    pass

        # 各小節からmusic21が生成したdirection要素を削除
        for measure in part.findall('.//{*}measure'):
            directions_to_remove = list(measure.findall('{*}direction'))
            for d in directions_to_remove:
                measure.remove(d)

        # direction要素を3カテゴリに分離:
        # 1. wedge ペア (cresc/dim) → type 反転 + 時間反転オフセットで再配置
        # 2. テンポ関連 (sound + words) → 有効範囲ベースで反転
        # 3. その他 (ダイナミクス、テキスト等) → 単純な位置反転
        all_directions = original_layout_map.directions[part_id]
        wedge_pairs, non_wedge_dirs = _separate_wedge_pairs(all_directions)
        tempo_directions = [d for d in non_wedge_dirs if _is_tempo_direction(d)]
        other_directions = [d for d in non_wedge_dirs if not _is_tempo_direction(d)]

        def _insert_into_measure(target_measure, restored):
            insert_pos = 0
            for idx, child in enumerate(target_measure):
                if child.tag.endswith('attributes'):
                    insert_pos = idx + 1
                    break
            target_measure.insert(insert_pos, restored)

        # 反転後の小節は <attributes>/<divisions> を持たないことが多いので
        # パートレベルから divisions を取得しておく
        part_divisions = _find_part_divisions(part)

        # 1. テンポ関連direction要素の反転位置を計算（有効範囲ベース）して挿入
        reversed_tempo_positions = _calculate_reversed_tempo_directions(
            tempo_directions, total_measures
        )

        for dir_elem, reversed_measure_num in reversed_tempo_positions:
            if reversed_measure_num not in measure_map:
                continue

            target_measure = measure_map[reversed_measure_num]

            try:
                restored_direction = ET.fromstring(dir_elem.direction_xml)
                _strip_dynamics_x_attributes(restored_direction)

                # 経過的テンポのwordsテキストに←記号を付与
                if dir_elem.words_text and _is_transitional_tempo_text(dir_elem.words_text):
                    words_elem = restored_direction.find('.//{*}direction-type/{*}words')
                    if words_elem is not None and words_elem.text:
                        if not words_elem.text.startswith('←'):
                            words_elem.text = '←' + words_elem.text

                _insert_into_measure(target_measure, restored_direction)
            except ET.ParseError:
                pass

        # 2. wedge ペアの復元（時間反転に伴い type を反転、配置を入れ替え）
        for start_dir, stop_dir in wedge_pairs:
            # 元: start at measure A, offset SA → stop at measure B, offset SB
            # 時間反転すると、反転後の各 direction の小節内オフセットは
            # (反転後の小節長) - (元のオフセット) になる。
            # さらに start/stop のロールが入れ替わるため:
            #   新 start (type 反転) = 反転後の B 小節, offset = M(B') - SB
            #   新 stop                = 反転後の A 小節, offset = M(A') - SA
            new_start_measure = total_measures - stop_dir.measure_num + 1
            new_stop_measure = total_measures - start_dir.measure_num + 1

            try:
                if new_start_measure in measure_map:
                    target = measure_map[new_start_measure]
                    new_start_xml = ET.fromstring(start_dir.direction_xml)
                    _strip_dynamics_x_attributes(new_start_xml)
                    wedge_elem = new_start_xml.find('.//{*}direction-type/{*}wedge')
                    if wedge_elem is not None:
                        cur_type = wedge_elem.get('type')
                        wedge_elem.set('type', _flip_wedge_type(cur_type))
                    # 反転後の小節長は元の対応小節（stop の元小節）と等しい
                    target_dur = stop_dir.measure_duration_quarters
                    target_offset = max(0.0, target_dur - stop_dir.offset_quarters)
                    _insert_direction_at_offset(
                        target, new_start_xml, target_offset, part_divisions
                    )

                if new_stop_measure in measure_map:
                    target = measure_map[new_stop_measure]
                    new_stop_xml = ET.fromstring(stop_dir.direction_xml)
                    _strip_dynamics_x_attributes(new_stop_xml)
                    target_dur = start_dir.measure_duration_quarters
                    target_offset = max(0.0, target_dur - start_dir.offset_quarters)
                    _insert_direction_at_offset(
                        target, new_stop_xml, target_offset, part_divisions
                    )
            except ET.ParseError:
                pass

        # 3. その他のdirection要素は単純な位置反転で挿入
        for dir_elem in other_directions:
            reversed_measure_num = total_measures - dir_elem.measure_num + 1

            if reversed_measure_num not in measure_map:
                continue

            target_measure = measure_map[reversed_measure_num]

            try:
                restored_direction = ET.fromstring(dir_elem.direction_xml)
                _strip_dynamics_x_attributes(restored_direction)
                _insert_into_measure(target_measure, restored_direction)
            except ET.ParseError:
                pass

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


def normalize_slur_numbers(output_xml_path: Path, verbose: bool = False) -> None:
    """
    スラーのnumber属性を正規化する

    music21は同じnumber属性を複数の独立したスラーに使い回すことがあり、
    これにより楽譜ソフトが異なるスラーを接続してしまう問題がある。

    また、反転処理によりスラーの方向が逆転した場合、music21は
    XMLに stop, start の順序で出力することがある。

    この関数は各スラーペア(start-stop)に一意のnumber属性を割り当てる。
    同じ元number属性を持つstart-stopを正しくペアリングする。

    Args:
        output_xml_path: 処理対象のMusicXMLファイル(.xml または .mxl)
        verbose: デバッグ出力を有効にする
    """
    is_mxl = output_xml_path.suffix == '.mxl'

    if is_mxl:
        root, xml_filename = _extract_mxl_content(output_xml_path)
    else:
        tree = ET.parse(output_xml_path)
        root = tree.getroot()

    # 各パートを処理
    for part in root.findall('.//{*}part'):
        part_id = part.get('id', 'unknown')

        # スラー情報を収集
        slur_events = []

        for measure in part.findall('.//{*}measure'):
            measure_num = measure.get('number')
            if measure_num is None:
                continue

            note_index = 0
            for elem in measure:
                if elem.tag.endswith('note'):
                    # 和音の場合はインデックスを進めない
                    is_chord = elem.find('.//{*}chord') is not None
                    if not is_chord:
                        note_index += 1

                    # notations内のslur要素を探す
                    for notations in elem.findall('.//{*}notations'):
                        for slur in notations.findall('.//{*}slur'):
                            slur_type = slur.get('type')
                            slur_num = slur.get('number', '1')
                            slur_events.append({
                                'measure_num': int(measure_num),
                                'note_index': note_index,
                                'slur_type': slur_type,
                                'original_number': slur_num,
                                'slur_element': slur,
                                'used': False
                            })

        if not slur_events:
            continue

        # イベントを時系列順にソート
        slur_events.sort(key=lambda x: (x['measure_num'], x['note_index']))

        # 2パスでスラーをペアリング
        # Pass 1: 同じ元番号でstart→stopの順序のペアを見つける（正常なスラー）
        # Pass 2: 同じ元番号でstop→startの順序のペアを見つける（反転されたスラー）

        next_new_number = 1

        # Pass 1: start → stop (FIFO順)
        for i, event in enumerate(slur_events):
            if event['used'] or event['slur_type'] != 'start':
                continue

            orig_num = event['original_number']
            # このstartに対応するstopを探す（時系列的に後にある、同じ元番号）
            for j in range(i + 1, len(slur_events)):
                other = slur_events[j]
                if other['used']:
                    continue
                if other['original_number'] == orig_num and other['slur_type'] == 'stop':
                    # ペア発見
                    new_number = next_new_number
                    next_new_number += 1
                    event['slur_element'].set('number', str(new_number))
                    other['slur_element'].set('number', str(new_number))
                    event['used'] = True
                    other['used'] = True
                    if verbose:
                        print(f"  Paired slur {new_number}: m{event['measure_num']} start -> m{other['measure_num']} stop (orig={orig_num})")
                    break

        # Pass 2: stop → start (反転されたスラー)
        # この場合、stopを見つけたら、それより後のstartを探す
        for i, event in enumerate(slur_events):
            if event['used'] or event['slur_type'] != 'stop':
                continue

            orig_num = event['original_number']
            # このstopに対応するstartを探す（時系列的に後にある、同じ元番号）
            for j in range(i + 1, len(slur_events)):
                other = slur_events[j]
                if other['used']:
                    continue
                if other['original_number'] == orig_num and other['slur_type'] == 'start':
                    # 反転されたスラーのペア発見
                    # XMLではstart/stopの順序を入れ替える必要がある
                    new_number = next_new_number
                    next_new_number += 1

                    # stopをstartに、startをstopに変更
                    event['slur_element'].set('type', 'start')
                    event['slur_element'].set('number', str(new_number))
                    other['slur_element'].set('type', 'stop')
                    other['slur_element'].set('number', str(new_number))
                    event['used'] = True
                    other['used'] = True
                    if verbose:
                        print(f"  Reversed slur {new_number}: m{event['measure_num']} (was stop->start) -> m{other['measure_num']} (was start->stop) (orig={orig_num})")
                    break

        # 未使用のスラー（孤立したstart/stop）に新しい番号を割り当て
        for event in slur_events:
            if not event['used']:
                new_number = next_new_number
                next_new_number += 1
                event['slur_element'].set('number', str(new_number))
                if verbose:
                    print(f"  Warning: Orphan {event['slur_type']} (orig={event['original_number']}) at m{event['measure_num']} -> slur {new_number}")

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


def _restore_credits_with_retrograde(
    root: ET.Element,
    credits_xml: list[str],
    part_name: Optional[str],
    retrograde_label: str = "(retrograde)"
) -> None:
    """
    保存されたcredit要素を復元し、part-name credit に retrograde ラベルを付与

    music21はcredit要素を出力XMLから削除してしまうため、
    元のXMLから抽出したcredit要素を再挿入する。
    パート名を表示しているcredit-wordsには " (retrograde)" を追記する。

    Args:
        root: 出力XMLのルート要素
        credits_xml: 元のcredit要素のXML文字列リスト
        part_name: パート名（マッチングに使用）
        retrograde_label: 追記するラベル
    """
    if not credits_xml:
        return

    # 既存のcredit要素を全て削除（重複防止）
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.split('}')[-1] == 'credit':
                parent.remove(child)

    # 挿入位置: part-list の直前
    part_list = root.find('.//{*}part-list')
    if part_list is None:
        return

    parent = None
    for elem in root.iter():
        if part_list in list(elem):
            parent = elem
            break
    if parent is None:
        return

    insert_idx = list(parent).index(part_list)

    pn = part_name.strip() if part_name else None

    for credit_xml in credits_xml:
        try:
            credit_elem = ET.fromstring(credit_xml)
        except ET.ParseError:
            continue

        # 名前空間を除去した新しい credit 要素を構築
        new_credit = ET.Element('credit')
        new_credit.attrib = {k.split('}')[-1]: v for k, v in credit_elem.attrib.items()}
        _copy_element_children(credit_elem, new_credit)

        # part-name credit を判定し、retrograde ラベルを追記
        if pn:
            credit_type_elem = new_credit.find('credit-type')
            credit_type = (credit_type_elem.text or "").strip().lower() if credit_type_elem is not None and credit_type_elem.text else ""

            # 既知の非パート名タイプはスキップ
            non_part_types = {'title', 'subtitle', 'composer', 'arranger',
                              'lyricist', 'rights', 'page number'}
            if credit_type not in non_part_types:
                # credit-words のテキストがパート名と一致するか確認
                for words_elem in new_credit.findall('credit-words'):
                    if words_elem.text and words_elem.text.strip() == pn:
                        words_elem.text = f"{pn}\n{retrograde_label}"
                        break

        parent.insert(insert_idx, new_credit)
        insert_idx += 1


def _restore_defaults_element(root: ET.Element, defaults_xml: str) -> None:
    """
    保存されたdefaults要素を復元

    music21はdefaults要素を適切に保持しないため、
    元のファイルから抽出したdefaults要素で置換する。

    Args:
        root: XMLルート要素
        defaults_xml: 保存されたdefaults要素のXML文字列
    """
    # 保存されたdefaultsをパース
    try:
        saved_defaults = ET.fromstring(defaults_xml)
    except ET.ParseError:
        return

    # 名前空間を削除（必要に応じて）
    saved_tag = saved_defaults.tag.split('}')[-1]

    # 既存のdefaults要素を探す
    existing_defaults = root.find('.//{*}defaults')

    if existing_defaults is not None:
        # 既存のdefaults要素の親を取得
        parent = None
        for elem in root.iter():
            if existing_defaults in list(elem):
                parent = elem
                break

        if parent is not None:
            # 既存要素のインデックスを取得
            index = list(parent).index(existing_defaults)
            # 既存要素を削除
            parent.remove(existing_defaults)
            # 新しい要素を同じ位置に挿入
            new_defaults = ET.Element('defaults')
            for child in saved_defaults:
                # 名前空間を削除したタグ名を使用
                child_tag = child.tag.split('}')[-1]
                new_child = ET.SubElement(new_defaults, child_tag)
                new_child.attrib = {k.split('}')[-1]: v for k, v in child.attrib.items()}
                new_child.text = child.text
                # 孫要素もコピー
                _copy_element_children(child, new_child)
            parent.insert(index, new_defaults)
    else:
        # defaults要素がない場合、適切な位置に挿入
        # MusicXMLの構造: score-partwise > work? > identification? > defaults? > credit* > part-list > part+
        # defaultsはpart-listの前に来る
        part_list = root.find('.//{*}part-list')
        if part_list is not None:
            parent = None
            for elem in root.iter():
                if part_list in list(elem):
                    parent = elem
                    break

            if parent is not None:
                index = list(parent).index(part_list)
                new_defaults = ET.Element('defaults')
                for child in saved_defaults:
                    child_tag = child.tag.split('}')[-1]
                    new_child = ET.SubElement(new_defaults, child_tag)
                    new_child.attrib = {k.split('}')[-1]: v for k, v in child.attrib.items()}
                    new_child.text = child.text
                    _copy_element_children(child, new_child)
                parent.insert(index, new_defaults)


def _copy_element_children(source: ET.Element, dest: ET.Element) -> None:
    """
    ソース要素の子孫を再帰的にコピー

    Args:
        source: コピー元の要素
        dest: コピー先の要素
    """
    for child in source:
        child_tag = child.tag.split('}')[-1]
        new_child = ET.SubElement(dest, child_tag)
        new_child.attrib = {k.split('}')[-1]: v for k, v in child.attrib.items()}
        new_child.text = child.text
        new_child.tail = child.tail
        _copy_element_children(child, new_child)


def _restore_technical_elements(
    root: ET.Element,
    original_layout_map: LayoutMap,
    total_measures: int
) -> None:
    """
    music21が読み込まなかったtechnical要素を復元

    Args:
        root: XMLルート要素
        original_layout_map: 元のレイアウト情報（technical_elementsを含む）
        total_measures: 総小節数（反転計算用）
    """
    # 各パートを走査
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        if part_id not in original_layout_map.technical_elements:
            continue

        tech_elements = original_layout_map.technical_elements[part_id]
        if not tech_elements:
            continue

        # 各小節を走査
        for measure in part.findall('.//{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str is None:
                continue

            try:
                reversed_measure_num = int(measure_num_str)
            except ValueError:
                continue

            # 元の小節番号を計算
            original_measure_num = total_measures - reversed_measure_num + 1

            # 元の小節に該当するtechnical要素を探す
            matching_techs = [t for t in tech_elements if t.measure_num == original_measure_num]
            if not matching_techs:
                continue

            # 小節内の音符を収集
            note_index = 0
            divisions = 1.0

            # divisionsを取得
            for attributes in measure.findall('.//{*}attributes'):
                div_elem = attributes.find('.//{*}divisions')
                if div_elem is not None and div_elem.text:
                    try:
                        divisions = float(div_elem.text)
                    except ValueError:
                        pass

            # 小節内の音符数をカウント
            notes = [elem for elem in measure if elem.tag.endswith('note') and
                     elem.find('.//{*}chord') is None]
            total_notes = len(notes)

            # 各音符を走査
            for elem in measure:
                if not elem.tag.endswith('note'):
                    continue

                # chordは音符インデックスをインクリメントしない
                is_chord = elem.find('.//{*}chord') is not None
                if is_chord:
                    continue

                # 反転後のインデックスから元のインデックスを計算
                original_note_index = total_notes - 1 - note_index

                # マッチするtechnical要素を探す
                for tech in matching_techs:
                    if tech.note_index == original_note_index:
                        # notations要素を取得または作成
                        notations = elem.find('.//{*}notations')
                        if notations is None:
                            notations = ET.SubElement(elem, 'notations')

                        # 既存のtechnical要素を取得または新規作成
                        technical = notations.find('.//{*}technical')
                        if technical is None:
                            technical = ET.SubElement(notations, 'technical')

                        # 保存されたtechnical要素をパースして子要素を追加
                        try:
                            saved_tech = ET.fromstring(tech.technical_xml)
                            for child in saved_tech:
                                # 名前空間を削除
                                child_tag = child.tag.split('}')[-1]
                                # 既存の子要素を確認
                                existing = technical.find(f'.//{child_tag}')
                                if existing is None:
                                    new_elem = ET.SubElement(technical, child_tag)
                                    new_elem.attrib = child.attrib
                                    new_elem.text = child.text
                        except ET.ParseError:
                            pass

                        break

                note_index += 1


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

    # defaults要素の復元（music21が変更してしまうスケーリングやページレイアウト）
    if original_layout_map.defaults_xml is not None:
        _restore_defaults_element(root, original_layout_map.defaults_xml)

    # credit要素の復元（music21が削除してしまう） + part-name に retrograde ラベル付与
    _restore_credits_with_retrograde(
        root,
        original_layout_map.credits_xml,
        original_layout_map.part_name,
    )

    # technical要素の復元（music21が読み込まなかった要素）
    _restore_technical_elements(root, original_layout_map, total_measures)

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
