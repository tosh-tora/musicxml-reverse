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
class InstrumentRef:
    """打楽器パート等でのper-note <instrument>参照の保存用（music21が読み込まないもの）

    打楽器パートでは、1つの<part>内で音符ごとに異なる<instrument id="...">を
    参照することで複数の音高/音色を表現する（MuseScoreのドラムマップ等）。
    music21はこの参照をパースしないため、反転後に出力XMLへ復元する必要がある。
    """
    measure_num: int
    voice: str  # voice番号（反転はvoiceごとに独立して行われるため）
    note_index: int  # voice内の音符インデックス
    instrument_id: str


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
    has_rehearsal: bool = False  # rehearsal（練習番号）子要素を持つか
    staff: Optional[str] = None  # staff子要素の値（複数譜パートでの所属譜）
    sound_pizzicato: Optional[str] = None  # sound要素のpizzicato属性（'yes'/'no'）


@dataclass
class MeasureStyleElement:
    """複数小節休符（multiple-rest）の保存用

    <multiple-rest>N</multiple-rest> は「この小節から N 小節」という前方向スパン。
    時間反転するとブロックの開始小節が変わるため、元の位置と長さを保存しておき
    反転後のブロック先頭に置き直す。
    """
    measure_num: int  # 元譜でのブロック開始小節
    count: int  # ブロックの小節数
    measure_style_xml: str  # measure-style要素全体のXML文字列


@dataclass
class LayoutMap:
    """スコア全体のレイアウト情報"""
    measures: dict[tuple[str, int], MeasureLayout] = field(default_factory=dict)
    # Key: (part_id, measure_number)
    technical_elements: dict[str, list[TechnicalElement]] = field(default_factory=dict)
    # Key: part_id
    instrument_refs: dict[str, list[InstrumentRef]] = field(default_factory=dict)
    # Key: part_id
    directions: dict[str, list[DirectionElement]] = field(default_factory=dict)
    # Key: part_id
    measure_styles: dict[str, list[MeasureStyleElement]] = field(default_factory=dict)
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
        layout_map.instrument_refs[part_id] = []
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
            voice_note_index: dict[str, int] = {}  # voice別の音符インデックス（instrument参照用）

            # attributes要素からdivisionsを取得
            for attributes in measure.findall('.//{*}attributes'):
                div_elem = attributes.find('.//{*}divisions')
                if div_elem is not None and div_elem.text:
                    try:
                        divisions = float(div_elem.text)
                    except ValueError:
                        pass

                # 複数小節休符（前方向スパン）を保存
                for measure_style in attributes.findall('{*}measure-style'):
                    multiple_rest = measure_style.find('{*}multiple-rest')
                    if multiple_rest is None or not multiple_rest.text:
                        continue
                    try:
                        count = int(multiple_rest.text)
                    except ValueError:
                        continue
                    layout_map.measure_styles.setdefault(part_id, []).append(
                        MeasureStyleElement(
                            measure_num=measure_num,
                            count=count,
                            measure_style_xml=ET.tostring(measure_style, encoding='unicode'),
                        )
                    )

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
                    rehearsal = elem.find('.//{*}direction-type/{*}rehearsal')

                    has_sound = sound is not None
                    has_words = words is not None
                    has_rehearsal = rehearsal is not None
                    words_text = None
                    if words is not None and words.text:
                        words_text = words.text.strip()

                    # staff（複数譜パートでは奏法状態が譜ごとに独立するため必要）
                    staff_elem = elem.find('{*}staff')
                    staff_value = None
                    if staff_elem is not None and staff_elem.text:
                        staff_value = staff_elem.text.strip()

                    # sound の pizzicato 属性（pizz./arco の状態判定に使用）
                    sound_pizzicato = sound.get('pizzicato') if sound is not None else None

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
                        has_rehearsal=has_rehearsal,
                        staff=staff_value,
                        sound_pizzicato=sound_pizzicato,
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

                    # per-note instrument参照を保存（打楽器パート等、music21が読み込まない）
                    # 反転はvoiceごとに独立して行われる（reverse_measure_contents）ため、
                    # インデックスもvoice単位で数える（chord要素はインデックスを増やさない）
                    if elem.find('.//{*}chord') is None:
                        voice_elem = elem.find('{*}voice')
                        voice_value = voice_elem.text.strip() if voice_elem is not None and voice_elem.text else '1'
                        voice_note_idx = voice_note_index.get(voice_value, 0)

                        instrument_elem = elem.find('{*}instrument')
                        if instrument_elem is not None:
                            inst_id = instrument_elem.get('id')
                            if inst_id:
                                layout_map.instrument_refs[part_id].append(
                                    InstrumentRef(
                                        measure_num=measure_num,
                                        voice=voice_value,
                                        note_index=voice_note_idx,
                                        instrument_id=inst_id,
                                    )
                                )

                        voice_note_index[voice_value] = voice_note_idx + 1

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


# テキスト形式の強弱変化指示 (cresc./decresc.) の反転マッピング
# 時間反転に伴い crescendo ↔ decrescendo をフリップする
_DYNAMICS_TEXT_FLIP_MAP = {
    'cresc.': 'decresc.',
    'cresc': 'decresc.',
    'crescendo': 'decrescendo',
    'decresc.': 'cresc.',
    'decresc': 'cresc.',
    'decrescendo': 'crescendo',
    'dim.': 'cresc.',
    'dim': 'cresc.',
    'diminuendo': 'crescendo',
}


def _is_dynamics_text_direction(dir_elem: DirectionElement) -> bool:
    """direction要素がテキスト形式の強弱変化指示（cresc./decresc.等）かどうかを判定する"""
    if not dir_elem.has_words or not dir_elem.words_text:
        return False
    return dir_elem.words_text.strip().lower() in _DYNAMICS_TEXT_FLIP_MAP


def _flip_dynamics_text(text: str) -> str:
    """cresc. ↔ decresc. を反転する"""
    key = text.strip().lower()
    return _DYNAMICS_TEXT_FLIP_MAP.get(key, text)


# 臨時の（アクセント系）強弱記号
# これらは音符単位で適用されるため、有効範囲ベースの反転対象外
ACCIDENTAL_DYNAMICS = {
    'sforzando', 'sforzato', 'sfz', 'sf',
    'forzando', 'forzato', 'fz',
    'rinforzando', 'rfz', 'rf',
    'sfp', 'fp',
}


def _is_dynamics_direction(dir_elem: DirectionElement) -> bool:
    """direction要素がダイナミクス（強弱記号）を含むかどうかを判定する"""
    try:
        root = ET.fromstring(dir_elem.direction_xml)
        return root.find('.//{*}dynamics') is not None
    except ET.ParseError:
        return False


def _get_dynamics_type(dir_elem: DirectionElement) -> Optional[str]:
    """ダイナミクスのタイプ名を取得する（例: 'ff', 'p', 'sf'）

    Returns:
        ダイナミクスタイプの文字列、見つからない場合はNone
    """
    try:
        root = ET.fromstring(dir_elem.direction_xml)
        dynamics = root.find('.//{*}dynamics')
        if dynamics is not None:
            for child in dynamics:
                tag = child.tag.split('}')[-1]
                if tag != 'other-dynamics':
                    return tag
            # other-dynamics の場合はテキストを返す
            other = dynamics.find('.//{*}other-dynamics')
            if other is not None and other.text:
                return other.text.strip()
        return None
    except ET.ParseError:
        return None


def _is_accidental_dynamics(dyn_type: str) -> bool:
    """臨時の強弱記号（アクセント系）かどうかを判定する"""
    return dyn_type in ACCIDENTAL_DYNAMICS


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


def _compute_reversed_insert_offset(
    reversed_measure: ET.Element,
    original_offset_q: float,
    measure_duration_q: float,
    divisions: float,
) -> float:
    """元の measure の original_offset_q に紐付く direction を
    反転後の measure に挿入する際の目標オフセットを計算する。

    反転後の measure を走査し、終端時刻が
    (measure_duration_q - original_offset_q) を超える
    最初の非コード音符の開始位置を返す。これにより、direction が
    元の音符と同じ音符の直前に挿入される。
    """
    epsilon = 1e-6
    target_end = measure_duration_q - original_offset_q

    if target_end <= epsilon:
        return 0.0  # 小節冒頭に挿入

    cumulative = 0.0
    for child in reversed_measure:
        tag = child.tag
        if tag.endswith('note'):
            if child.find('.//{*}chord') is None:
                d = child.find('.//{*}duration')
                dur = 0.0
                if d is not None and d.text:
                    try:
                        dur = float(d.text) / divisions
                    except ValueError:
                        pass
                if cumulative + dur > target_end - epsilon:
                    return cumulative
                cumulative += dur
        elif tag.endswith('backup'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    cumulative = max(0.0, cumulative - float(d.text) / divisions)
                except ValueError:
                    pass
        elif tag.endswith('forward'):
            d = child.find('.//{*}duration')
            if d is not None and d.text:
                try:
                    cumulative += float(d.text) / divisions
                except ValueError:
                    pass

    return measure_duration_q  # フォールバック: 末尾に追加


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


def _octave_shift_only_direction(dir_elem: 'DirectionElement') -> Optional[ET.Element]:
    """direction が octave-shift 単独要素ならその octave-shift 要素を返す。それ以外は None。"""
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
    if not child.tag.endswith('octave-shift'):
        return None
    return child


def _separate_octave_shift_pairs(
    dir_elems: list['DirectionElement']
) -> tuple[list[tuple['DirectionElement', 'DirectionElement']], list['DirectionElement']]:
    """direction リストから octave-shift start/stop ペアと、それ以外に分離する。

    ペアリングは出現順に number 属性で対応付ける。ペアにならなかった
    octave-shift direction は他の direction として扱う（フォールバック）。
    """
    pairs: list[tuple[DirectionElement, DirectionElement]] = []
    others: list[DirectionElement] = []
    open_starts: dict[str, DirectionElement] = {}

    for d in dir_elems:
        os_elem = _octave_shift_only_direction(d)
        if os_elem is None:
            others.append(d)
            continue
        number = os_elem.get('number') or '1'
        otype = os_elem.get('type') or ''
        if otype in ('up', 'down'):
            # 既に開いている同 number の start は孤立扱い
            if number in open_starts:
                others.append(open_starts.pop(number))
            open_starts[number] = d
        elif otype == 'stop':
            start = open_starts.pop(number, None)
            if start is not None:
                pairs.append((start, d))
            else:
                others.append(d)
        else:
            # 'continue' などはフォールバック
            others.append(d)

    # 未クローズの start は孤立扱い
    for d in open_starts.values():
        others.append(d)

    return pairs, others


@dataclass(frozen=True)
class StateMarkingGroup:
    """「次の指示まで有効」な状態指示のグループ

    pizz./arco のような奏法状態は、位置を鏡像移動するだけでは足りず、
    区間ごと時間反転して状態が変化する境界にマーカーを置き直す必要がある。
    グループ内の状態は互いに排他で、曲頭には暗黙の既定状態がある。
    """
    name: str
    default_state: str  # 曲頭の暗黙状態
    text_to_state: dict[str, str]  # 正規化テキスト → 状態名
    state_to_text: dict[str, str]  # 状態名 → 合成用テキスト
    sound_attribute: Optional[str] = None  # 状態を表す <sound> の属性名
    state_to_sound_value: dict[str, str] = field(default_factory=dict)
    cancel_text_overrides: dict[str, str] = field(default_factory=dict)
    # 打ち消しマーカーを合成する際の表記の上書き（キー: 打ち消される状態名）

    def cancel_text(self, cancelled_state: str) -> Optional[str]:
        """cancelled_state を打ち消して既定状態に戻すときの表記"""
        override = self.cancel_text_overrides.get(cancelled_state)
        if override is not None:
            return override
        return self.state_to_text.get(self.default_state)


# 語彙で定義できる状態指示のグループ
# ここに登録された words / sound を持つ direction は有効範囲ベースで反転される。
# 語彙を列挙できない状態指示（打楽器の持ち替え、オルガンのレジストレーション等）は
# 誤検出を避けるため対象外とする（Issue #73）。
STATE_MARKING_GROUPS = (
    # 奏法: pizz. ↔ arco
    StateMarkingGroup(
        name='play',
        default_state='arco',
        text_to_state={
            'pizz.': 'pizz', 'pizz': 'pizz', 'pizzicato': 'pizz',
            'arco': 'arco',
        },
        state_to_text={'pizz': 'pizz.', 'arco': 'arco'},
        sound_attribute='pizzicato',
        state_to_sound_value={'pizz': 'yes', 'arco': 'no'},
    ),
    # 分割・人数: div. / unis. / a 2. / I. / II.
    # 'a 2.' と 'unis.' はどちらも「分割していない」状態なので同一状態として扱い、
    # 打ち消し表記だけを div.→unis.、I./II.→a 2. と使い分ける。
    # アラビア数字の '1.' '2.' は反復括弧・運指と紛れるため語彙に含めない。
    StateMarkingGroup(
        name='divisi',
        default_state='tutti',
        text_to_state={
            'div.': 'div', 'div': 'div', 'divisi': 'div',
            'unis.': 'tutti', 'unis': 'tutti', 'unison': 'tutti', 'unisono': 'tutti',
            'a 2.': 'tutti', 'a 2': 'tutti', 'a2': 'tutti',
            'a2.': 'tutti', 'a due': 'tutti',
            'i.': 'first', 'i': 'first',
            'ii.': 'second', 'ii': 'second',
        },
        state_to_text={'tutti': 'a 2.', 'div': 'div.', 'first': 'I.', 'second': 'II.'},
        cancel_text_overrides={'div': 'unis.'},
    ),
    # ミュート: con sord. ↔ senza sord.
    StateMarkingGroup(
        name='mute',
        default_state='open',
        text_to_state={
            'con sord.': 'muted', 'con sord': 'muted', 'con sordino': 'muted',
            'con sordini': 'muted', 'mit dämpfer': 'muted',
            'senza sord.': 'open', 'senza sord': 'open', 'senza sordino': 'open',
            'senza sordini': 'open', 'via sord.': 'open', 'via sordini': 'open',
            'ohne dämpfer': 'open',
        },
        state_to_text={'muted': 'con sord.', 'open': 'senza sord.'},
    ),
    # 弓の位置・奏法: sul pont. / sul tasto / col legno ↔ ord.
    StateMarkingGroup(
        name='bowing',
        default_state='ord',
        text_to_state={
            'sul pont.': 'pont', 'sul pont': 'pont', 'sul ponticello': 'pont',
            'sul tasto': 'tasto', 'sul t.': 'tasto',
            'col legno': 'legno', 'col l.': 'legno',
            'ord.': 'ord', 'ord': 'ord', 'ordinario': 'ord',
            'naturale': 'ord', 'nat.': 'ord', 'modo ord.': 'ord',
        },
        state_to_text={
            'pont': 'sul pont.', 'tasto': 'sul tasto',
            'legno': 'col legno', 'ord': 'ord.',
        },
    ),
)


def _normalize_state_text(text: str) -> str:
    """状態指示のテキストを語彙照合用に正規化する（小文字化＋空白の畳み込み）"""
    return ' '.join(text.lower().split())


def _direction_words_variants(dir_elem: 'DirectionElement') -> list[str]:
    """語彙照合に使うテキスト候補を返す

    楽譜ソフトは 'con sord.' を <words>con</words><words>sord.</words> のように
    分割して出力することがあるため、全 <words> を連結したものと先頭単体の
    両方を候補にする。語彙に無いテキスト（'Tambourine' + 'ad lib.' 等）は
    どちらでも一致しないので安全。
    """
    variants: list[str] = []
    try:
        root = ET.fromstring(dir_elem.direction_xml)
    except ET.ParseError:
        root = None

    if root is not None:
        texts = [w.text.strip() for w in root.iter()
                 if w.tag.endswith('words') and w.text and w.text.strip()]
        if texts:
            variants.append(_normalize_state_text(' '.join(texts)))
            variants.append(_normalize_state_text(''.join(texts)))
            variants.append(_normalize_state_text(texts[0]))

    if dir_elem.words_text:
        variants.append(_normalize_state_text(dir_elem.words_text))

    # 重複を除いて順序を保つ
    seen: set[str] = set()
    return [v for v in variants if v and not (v in seen or seen.add(v))]


def _get_state_marking(
    dir_elem: 'DirectionElement'
) -> Optional[tuple[StateMarkingGroup, str]]:
    """direction が状態指示ならその (グループ, 状態名) を返す。それ以外は None。

    グループが sound 属性を持つ場合はそれを優先し（楽譜ソフトによっては
    arco に sound 属性が付かないため）、無ければ words テキストで判定する。
    """
    # <sound> 属性による判定（現状は pizzicato のみ）
    if dir_elem.sound_pizzicato is not None:
        for group in STATE_MARKING_GROUPS:
            if group.sound_attribute != 'pizzicato':
                continue
            for state, value in group.state_to_sound_value.items():
                if value == dir_elem.sound_pizzicato:
                    return group, state

    variants = _direction_words_variants(dir_elem)
    for group in STATE_MARKING_GROUPS:
        for variant in variants:
            state = group.text_to_state.get(variant)
            if state is not None:
                return group, state
    return None


def _separate_state_marking_directions(
    dir_elems: list['DirectionElement']
) -> tuple[list['DirectionElement'], list['DirectionElement']]:
    """direction リストから状態指示（pizz./arco, a 2./div. 等）と、それ以外に分離する。

    pizz./arco は words + sound を持つため、そのままでは _is_tempo_direction() が
    真になりテンポ指示として誤分類される。テンポ判定より前に分離する必要がある。
    """
    state_dirs: list[DirectionElement] = []
    others: list[DirectionElement] = []

    for d in dir_elems:
        if _get_state_marking(d) is not None:
            state_dirs.append(d)
        else:
            others.append(d)

    return state_dirs, others


def _mirror_direction_position(
    dir_elem: 'DirectionElement',
    total_measures: int,
) -> tuple[int, float]:
    """direction の時間位置を時間反転後の (小節番号, 小節内オフセット) に写す。

    反転後の小節 total-N+1 は元の小節 N の内容を反転したものなので、小節長は同じ。
    小節頭（offset 0）の境界は反転後の小節末に相当するため、次の小節の頭に正規化する。
    """
    measure_num = total_measures - dir_elem.measure_num + 1
    measure_duration = dir_elem.measure_duration_quarters
    epsilon = 1e-6

    if measure_duration <= epsilon:
        return measure_num, 0.0

    offset = measure_duration - dir_elem.offset_quarters
    if offset >= measure_duration - epsilon:
        # 元が小節頭 → 反転後は小節末に相当するので、次の小節の頭に正規化する
        return measure_num + 1, 0.0
    return measure_num, max(0.0, offset)


@dataclass
class StateMarker:
    """反転後に配置する状態マーカー"""
    group: StateMarkingGroup
    state: str
    staff: Optional[str]
    measure_num: int
    offset_quarters: float
    template: Optional['DirectionElement'] = None
    replaces: Optional[str] = None  # このマーカーが打ち消す直前の状態


def _calculate_reversed_state_markers(
    state_dirs: list['DirectionElement'],
    total_measures: int,
) -> list[StateMarker]:
    """状態指示（pizz./arco, a 2./div. 等）の反転後マーカーを算出する

    状態指示は「その位置から次の指示まで有効」な区間として振る舞うため、
    ダイナミクスやテンポと同様に有効範囲ベースで反転する。ただし区間の終端では
    直前の状態に戻るため、元譜に無い打ち消しマーカーを新たに出力する必要がある。

    元譜の区間列（暗黙の曲頭の既定状態を含む）を時間反転し、状態が変化する境界に
    だけマーカーを出す。反転後の曲頭が既定状態なら曲頭マーカーは出さない。

    グループと staff の組ごとに独立した状態として扱う
    （複数譜パートでは譜ごとに、また奏法と分割は互いに独立）。

    Args:
        state_dirs: 状態指示のDirectionElementリスト
        total_measures: 総小節数

    Returns:
        StateMarker のリスト
    """
    if not state_dirs:
        return []

    # (グループ名, staff) ごとに独立した状態として扱う
    by_scope: dict[tuple[str, Optional[str]], list[DirectionElement]] = {}
    markings: dict[int, tuple[StateMarkingGroup, str]] = {}
    for d in state_dirs:
        marking = _get_state_marking(d)
        if marking is None:
            continue
        group, _state = marking
        markings[id(d)] = marking
        by_scope.setdefault((group.name, d.staff), []).append(d)

    # 状態ごとのテンプレート（同 scope を優先、無ければ他 staff から流用）
    global_templates: dict[tuple[str, str], DirectionElement] = {}
    for d in state_dirs:
        marking = markings.get(id(d))
        if marking is not None:
            group, state = marking
            global_templates.setdefault((group.name, state), d)

    result: list[StateMarker] = []

    for (group_name, staff), dirs in by_scope.items():
        boundaries = sorted(dirs, key=lambda d: (d.measure_num, d.offset_quarters))
        group = markings[id(boundaries[0])][0]
        states = [markings[id(d)][1] for d in boundaries]

        scope_templates: dict[str, DirectionElement] = {}
        for d, state in zip(boundaries, states):
            scope_templates.setdefault(state, d)

        # 反転後の区間列: (状態, 開始位置)。開始位置 None は曲頭
        reversed_regions: list[tuple[str, Optional[tuple[int, float]]]] = [
            (states[-1], None)
        ]
        for k in range(len(boundaries) - 1, 0, -1):
            reversed_regions.append(
                (states[k - 1], _mirror_direction_position(boundaries[k], total_measures))
            )
        reversed_regions.append(
            (group.default_state,
             _mirror_direction_position(boundaries[0], total_measures))
        )

        # 状態が変化する境界にだけマーカーを出す
        previous_state = group.default_state
        for state, position in reversed_regions:
            if state == previous_state:
                continue
            replaced_state = previous_state
            previous_state = state

            if position is None:
                measure_num, offset = 1, 0.0
            else:
                measure_num, offset = position
            if measure_num < 1 or measure_num > total_measures:
                # 区間が曲の範囲外（長さ 0）ならマーカー不要
                continue

            template = (scope_templates.get(state)
                        or global_templates.get((group_name, state)))
            result.append(StateMarker(
                group=group,
                state=state,
                staff=staff,
                measure_num=measure_num,
                offset_quarters=offset,
                template=template,
                replaces=replaced_state,
            ))

        # 元譜で状態を変えていなかった指示（既に有効な状態の再掲）は、
        # 反転後も鏡像位置に再掲として残す。これらは有効範囲の境界ではないので
        # 消してしまうと元譜の情報が失われる（例: div. を持たないパートの a 2.）。
        previous_original_state = group.default_state
        for d, state in zip(boundaries, states):
            if state == previous_original_state:
                measure_num, offset = _mirror_direction_position(d, total_measures)
                if measure_num > total_measures:
                    # 元 m1 頭の指示は反転後では曲末に対応するため最終小節に置く
                    # （練習番号の復元 と同じクランプ）
                    measure_num, offset = total_measures, 0.0
                if 1 <= measure_num <= total_measures:
                    result.append(StateMarker(
                        group=group,
                        state=state,
                        staff=staff,
                        measure_num=measure_num,
                        offset_quarters=offset,
                        template=d,
                    ))
            previous_original_state = state

    # 境界マーカーと再掲が同じ位置に重なった場合は片方だけ残す
    unique: list[StateMarker] = []
    seen: set[tuple[str, str, Optional[str], int, float]] = set()
    for marker in result:
        key = (marker.group.name, marker.state, marker.staff,
               marker.measure_num, marker.offset_quarters)
        if key in seen:
            continue
        seen.add(key)
        unique.append(marker)

    return unique


def _strip_words_x_attributes(direction_root: ET.Element) -> None:
    """direction / words から default-x/relative-x を除去する。

    時間反転でマーカーの時間位置が変わるため、元の水平位置を復元すると
    音符との位置がずれる（_strip_dynamics_x_attributes と同じ理由）。
    """
    for attr in ('default-x', 'relative-x'):
        if attr in direction_root.attrib:
            del direction_root.attrib[attr]
    for elem in direction_root.iter():
        if elem.tag.endswith('words'):
            for attr in ('default-x', 'relative-x'):
                if attr in elem.attrib:
                    del elem.attrib[attr]


def _build_state_marking_direction(marker: 'StateMarker') -> Optional[ET.Element]:
    """状態マーカーの direction 要素を組み立てる

    同じ状態の元 direction があればそれを流用して書式（placement, default-y, font）を
    保ち、無ければ最小構成を合成する。既定状態に戻す打ち消しマーカーで元譜に
    該当する direction が無い場合は、打ち消される状態に応じた表記を使う
    （div. の解除は unis.、I./II. の解除は a 2.）。
    """
    group, state = marker.group, marker.state

    if marker.template is not None:
        try:
            direction = ET.fromstring(marker.template.direction_xml)
        except ET.ParseError:
            direction = None
        if direction is not None:
            _strip_words_x_attributes(direction)
            _strip_dynamics_x_attributes(direction)
            _set_direction_staff(direction, marker.staff)
            _set_direction_state_sound(direction, group, state)
            return direction

    if state == group.default_state and marker.replaces is not None:
        words_text = group.cancel_text(marker.replaces)
    else:
        words_text = group.state_to_text.get(state)
    if words_text is None:
        return None

    direction = ET.Element('direction', {'placement': 'above'})
    direction_type = ET.SubElement(direction, 'direction-type')
    words = ET.SubElement(direction_type, 'words')
    words.text = words_text
    # <direction> の子要素順は direction-type → offset → voice → staff → sound
    _set_direction_staff(direction, marker.staff)
    _set_direction_state_sound(direction, group, state)
    return direction


def _set_direction_state_sound(
    direction: ET.Element,
    group: StateMarkingGroup,
    state: str,
) -> None:
    """direction の <sound> 属性を状態に合わせる（無ければ末尾に追加）

    元譜の arco に pizzicato 属性が無いことがあるため、生成したマーカーでは
    再生時にも奏法が戻るよう明示する。<sound> で表現できないグループ
    （分割・ミュート等）では何もしない。
    """
    if group.sound_attribute is None:
        return
    value = group.state_to_sound_value.get(state)
    if value is None:
        return

    for child in direction:
        if child.tag.endswith('sound'):
            child.set(group.sound_attribute, value)
            return

    # <sound> は <direction> の最後の子要素
    ET.SubElement(direction, 'sound', {group.sound_attribute: value})


def _set_direction_staff(direction: ET.Element, staff: Optional[str]) -> None:
    """direction の <staff> を staff に合わせる（無ければ sound の直前に追加）"""
    if staff is None:
        return

    for child in direction:
        if child.tag.endswith('staff'):
            child.text = staff
            return

    staff_elem = ET.Element('staff')
    staff_elem.text = staff
    # <sound> より前、それ以外の要素より後ろに置く
    insert_pos = len(direction)
    for idx, child in enumerate(direction):
        if child.tag.endswith('sound'):
            insert_pos = idx
            break
    direction.insert(insert_pos, staff_elem)


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


def _calculate_reversed_dynamics_directions(
    directions: list[DirectionElement],
    total_measures: int,
    text_dynamics_measures: Optional[list[int]] = None,
) -> list[tuple[DirectionElement, int, Optional[tuple[str, int]]]]:
    """ダイナミクスdirection要素の反転後位置を計算する

    非臨時ダイナミクス: 有効範囲ベースで反転 + 括弧付きマーカー
    臨時ダイナミクス: 単純な位置反転（従来通り）

    テキスト形式の強弱変化指示（cresc./decresc.）の小節番号も境界として
    考慮し、ダイナミクスの有効範囲をその手前で切る。

    Args:
        directions: ダイナミクスのDirectionElementリスト
        total_measures: 総小節数
        text_dynamics_measures: テキスト形式の強弱変化指示がある小節番号のリスト

    Returns:
        (DirectionElement, reversed_measure_num, optional (dyn_type, paren_measure_num))
        のタプルリスト。paren_info は非臨時ダイナミクスの括弧付きマーカー情報。
    """
    if not directions:
        return []

    # 臨時 vs 非臨時ダイナミクスを分離
    main_dynamics = []
    accidental_dynamics = []

    for d in directions:
        dyn_type = _get_dynamics_type(d)
        if dyn_type and _is_accidental_dynamics(dyn_type):
            accidental_dynamics.append(d)
        else:
            main_dynamics.append(d)

    # 有効範囲の境界マーカー: 非臨時ダイナミクスの小節 + テキスト強弱変化の小節
    boundary_measures = sorted(set(
        [d.measure_num for d in main_dynamics]
        + (text_dynamics_measures or [])
    ))

    result = []

    # 非臨時ダイナミクスの有効範囲ベース反転
    for i, dir_elem in enumerate(main_dynamics):
        dyn_type = _get_dynamics_type(dir_elem)
        # 適用終了位置を計算（次の境界マーカーの直前まで）
        effective_end = total_measures  # デフォルトは曲の最後
        for bm in boundary_measures:
            if bm > dir_elem.measure_num:
                effective_end = bm - 1
                break

        # 反転後の開始位置を計算（有効範囲の終端を基準に）
        reversed_start = total_measures - effective_end + 1

        # 括弧付きマーカーの位置（単純反転 = 元の開始位置の反転）
        simple_reversed = total_measures - dir_elem.measure_num + 1

        # 有効範囲反転位置と単純反転位置が同じ場合はマーカー不要
        paren_info = None
        if dyn_type and simple_reversed != reversed_start:
            paren_info = (dyn_type, simple_reversed)

        result.append((dir_elem, reversed_start, paren_info))

    # 臨時ダイナミクスは単純な位置反転
    for dir_elem in accidental_dynamics:
        reversed_start = total_measures - dir_elem.measure_num + 1
        result.append((dir_elem, reversed_start, None))

    return result


def _create_parenthesized_dynamics_direction(
    dir_elem: DirectionElement, dyn_type: str
) -> Optional[ET.Element]:
    """括弧付きダイナミクスのdirection要素を生成する

    元のdirection XMLをベースに、<ff/> → <other-dynamics>(ff)</other-dynamics> に変換する。

    Args:
        dir_elem: 元のDirectionElement
        dyn_type: ダイナミクスタイプ（例: 'ff'）

    Returns:
        変換されたdirection要素、失敗時はNone
    """
    try:
        root = ET.fromstring(dir_elem.direction_xml)
        dynamics = root.find('.//{*}dynamics')
        if dynamics is None:
            return None

        # 既存のダイナミクス子要素を全て削除
        for child in list(dynamics):
            dynamics.remove(child)

        # <other-dynamics>(ff)</other-dynamics> を追加
        # 名前空間を検出
        ns = ''
        tag = dynamics.tag
        if '}' in tag:
            ns = tag[:tag.index('}') + 1]

        other_dyn = ET.SubElement(dynamics, f'{ns}other-dynamics')
        other_dyn.text = f'({dyn_type})'

        _strip_dynamics_x_attributes(root)

        return root
    except ET.ParseError:
        return None


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

    ダイナミクス（強弱記号）も有効範囲ベースで反転し、元の開始位置には
    括弧付きの強弱記号（例: (ff)）を配置する。臨時のダイナミクス（sfz等）は
    単純な位置反転のまま処理する。

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

        # direction要素をカテゴリに分離:
        # 1. wedge ペア (cresc/dim) → type 反転 + 時間反転オフセットで再配置
        # 2. 奏法状態 (pizz./arco) → 有効範囲ベースで反転 + 打ち消しマーカー生成
        # 3. テンポ関連 (sound + words) → 有効範囲ベースで反転
        # 4. ダイナミクス → 有効範囲ベースで反転 + 括弧付きマーカー
        # 5. その他 (テキスト等) → 単純な位置反転
        #
        # 奏法状態は words + sound を持つためテンポ判定より前に分離する
        # （テンポとして誤分類されるだけでなく、テンポの有効範囲境界も汚染するため）
        all_directions = original_layout_map.directions[part_id]
        wedge_pairs, non_wedge_dirs = _separate_wedge_pairs(all_directions)
        octave_shift_pairs, non_pair_dirs = _separate_octave_shift_pairs(non_wedge_dirs)
        state_marking_directions, non_state_dirs = _separate_state_marking_directions(non_pair_dirs)
        tempo_directions = [d for d in non_state_dirs if _is_tempo_direction(d)]
        non_tempo_dirs = [d for d in non_state_dirs if not _is_tempo_direction(d)]
        rehearsal_directions = [d for d in non_tempo_dirs if d.has_rehearsal]
        non_rehearsal_dirs = [d for d in non_tempo_dirs if not d.has_rehearsal]
        dynamics_directions = [d for d in non_rehearsal_dirs
                               if _is_dynamics_direction(d)]
        other_directions = [d for d in non_rehearsal_dirs
                            if not _is_dynamics_direction(d)]

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

        # 2b. octave-shift ペアの復元（時間反転に伴い start/stop の位置を入れ替える）
        # wedge と異なり type は反転せず、start (down/up) と stop の役割だけが入れ替わる:
        #   元: start (down/up) at measure A offset SA → stop at measure B offset SB
        #   新 start (down/up と同じ) = 反転後の B 小節, offset = M(B') - SB
        #   新 stop                     = 反転後の A 小節, offset = M(A') - SA
        for start_dir, stop_dir in octave_shift_pairs:
            new_start_measure = total_measures - stop_dir.measure_num + 1
            new_stop_measure = total_measures - start_dir.measure_num + 1

            try:
                if new_start_measure in measure_map:
                    target = measure_map[new_start_measure]
                    new_start_xml = ET.fromstring(start_dir.direction_xml)
                    _strip_dynamics_x_attributes(new_start_xml)
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

        # 3. ダイナミクスの有効範囲ベース反転
        # テキスト形式の強弱変化指示（cresc./decresc.）の小節番号を境界として渡す
        text_dyn_measures = [
            d.measure_num for d in other_directions
            if _is_dynamics_text_direction(d)
        ]
        reversed_dynamics = _calculate_reversed_dynamics_directions(
            dynamics_directions, total_measures, text_dyn_measures
        )

        for dir_elem, reversed_measure_num, paren_info in reversed_dynamics:
            if reversed_measure_num not in measure_map:
                continue

            target_measure = measure_map[reversed_measure_num]

            try:
                restored_direction = ET.fromstring(dir_elem.direction_xml)
                _strip_dynamics_x_attributes(restored_direction)

                if paren_info is not None:
                    # 有効範囲ベースで別の小節に移動 → 小節先頭に配置
                    _insert_into_measure(target_measure, restored_direction)
                else:
                    # 臨時ダイナミクス or 有効範囲=1小節 → オフセット反転で配置
                    target_offset = _compute_reversed_insert_offset(
                        target_measure,
                        dir_elem.offset_quarters,
                        dir_elem.measure_duration_quarters,
                        part_divisions,
                    )
                    _insert_direction_at_offset(
                        target_measure, restored_direction, target_offset, part_divisions
                    )
            except ET.ParseError:
                pass

            # 括弧付きマーカーを単純反転位置に挿入
            if paren_info is not None:
                paren_dyn_type, paren_measure_num = paren_info
                if paren_measure_num in measure_map:
                    paren_direction = _create_parenthesized_dynamics_direction(
                        dir_elem, paren_dyn_type
                    )
                    if paren_direction is not None:
                        paren_target = measure_map[paren_measure_num]
                        paren_offset = _compute_reversed_insert_offset(
                            paren_target,
                            dir_elem.offset_quarters,
                            dir_elem.measure_duration_quarters,
                            part_divisions,
                        )
                        _insert_direction_at_offset(
                            paren_target, paren_direction,
                            paren_offset, part_divisions
                        )

        # 4. その他のdirection要素（テキスト等）は小節内オフセットを反転して挿入
        for dir_elem in other_directions:
            reversed_measure_num = total_measures - dir_elem.measure_num + 1

            if reversed_measure_num not in measure_map:
                continue

            target_measure = measure_map[reversed_measure_num]

            try:
                restored_direction = ET.fromstring(dir_elem.direction_xml)
                _strip_dynamics_x_attributes(restored_direction)

                # テキスト形式の cresc./decresc. を反転し、小節先頭に配置
                if _is_dynamics_text_direction(dir_elem):
                    words_elem = restored_direction.find('.//{*}direction-type/{*}words')
                    if words_elem is not None and words_elem.text:
                        words_elem.text = _flip_dynamics_text(words_elem.text)
                    _insert_into_measure(target_measure, restored_direction)
                else:
                    target_offset = _compute_reversed_insert_offset(
                        target_measure,
                        dir_elem.offset_quarters,
                        dir_elem.measure_duration_quarters,
                        part_divisions,
                    )
                    _insert_direction_at_offset(
                        target_measure, restored_direction, target_offset, part_divisions
                    )
            except ET.ParseError:
                pass

        # 5. 練習番号（rehearsal）は小節境界に紐付くため +1 シフトした位置に挿入
        # 元 m_N の頭の練習番号 = m_(N-1) と m_N の境界。時間反転すると
        # その境界は反転後 m_(total-N+1) と m_(total-N+2) の間になり、
        # MusicXML上は反転後 m_(total-N+2) の頭に置く。
        for dir_elem in rehearsal_directions:
            reversed_measure_num = total_measures - dir_elem.measure_num + 2
            if reversed_measure_num > total_measures:
                # 元 m_1 の練習番号は反転後では曲末に対応するため最終小節に置く
                reversed_measure_num = total_measures

            if reversed_measure_num not in measure_map:
                continue

            target_measure = measure_map[reversed_measure_num]

            try:
                restored_direction = ET.fromstring(dir_elem.direction_xml)
                _strip_dynamics_x_attributes(restored_direction)
                _insert_into_measure(target_measure, restored_direction)
            except ET.ParseError:
                pass

        # 6. 状態指示（pizz./arco, a 2./div. 等）を有効範囲ベースで反転して挿入
        # 区間の終端では直前の状態に戻るため、元譜に無い打ち消しマーカーも生成される
        reversed_state_markers = _calculate_reversed_state_markers(
            state_marking_directions, total_measures
        )

        for state_marker in reversed_state_markers:
            if state_marker.measure_num not in measure_map:
                continue

            marker = _build_state_marking_direction(state_marker)
            if marker is None:
                continue

            _insert_direction_at_offset(
                measure_map[state_marker.measure_num], marker,
                state_marker.offset_quarters, part_divisions
            )

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


# 調号（fifths）で変化する音名の順序
_SHARP_STEP_ORDER = 'FCGDAEB'
_FLAT_STEP_ORDER = 'BEADGCF'

# alter 値と <accidental> の表記の対応
_ALTER_TO_ACCIDENTAL = {
    0: 'natural',
    1: 'sharp',
    -1: 'flat',
    2: 'sharp-sharp',
    -2: 'flat-flat',
}

# <note> 内で <accidental> より後ろに来る子要素（MusicXMLの子要素順を守るため）
_NOTE_ELEMENTS_AFTER_ACCIDENTAL = (
    'time-modification', 'stem', 'notehead', 'notehead-text', 'staff',
    'beam', 'notations', 'lyric', 'play', 'listen',
)


def _key_alter_map(fifths: int) -> dict[str, int]:
    """調号から音名 → alter の対応表を作る"""
    alters = {step: 0 for step in 'ABCDEFG'}
    if fifths > 0:
        for step in _SHARP_STEP_ORDER[:fifths]:
            alters[step] = 1
    elif fifths < 0:
        for step in _FLAT_STEP_ORDER[:-fifths]:
            alters[step] = -1
    return alters


def _note_alter(note: ET.Element) -> Optional[int]:
    """音符の alter を返す。ピッチを持たない（休符・不確定音高）場合は None"""
    pitch = note.find('{*}pitch')
    if pitch is None:
        return None
    alter_elem = pitch.find('{*}alter')
    if alter_elem is None or not alter_elem.text:
        return 0
    try:
        return int(round(float(alter_elem.text)))
    except ValueError:
        return 0


def _set_note_accidental(note: ET.Element, alter: int) -> None:
    """音符に <accidental> を設定する（既にあれば何もしない）"""
    accidental_text = _ALTER_TO_ACCIDENTAL.get(alter)
    if accidental_text is None:
        return

    accidental = ET.Element('accidental')
    accidental.text = accidental_text

    # <type>/<dot> の後、<stem> 等より前に挿入する
    insert_pos = len(note)
    for idx, child in enumerate(note):
        tag = child.tag.split('}')[-1]
        if tag in _NOTE_ELEMENTS_AFTER_ACCIDENTAL:
            insert_pos = idx
            break
    note.insert(insert_pos, accidental)


def _measure_notes_in_time_order(measure: ET.Element) -> list[tuple[float, int, ET.Element]]:
    """小節内の音符を (時間位置, 文書順, 要素) のリストで時間順に返す

    <chord> の音符は直前の非和音音符と同じ時間位置に置き、<backup>/<forward> で
    カーソルを移動する。同時刻の音符は文書順を保つ。
    """
    divisions = _measure_divisions(measure)
    notes: list[tuple[float, int, ET.Element]] = []
    cursor = 0.0
    chord_position = 0.0

    def _duration(elem: ET.Element) -> float:
        duration_elem = elem.find('{*}duration')
        if duration_elem is None or not duration_elem.text:
            return 0.0
        try:
            return float(duration_elem.text) / divisions
        except ValueError:
            return 0.0

    for index, elem in enumerate(measure):
        tag = elem.tag.split('}')[-1]
        if tag == 'note':
            is_chord = elem.find('{*}chord') is not None
            notes.append((chord_position if is_chord else cursor, index, elem))
            if not is_chord:
                chord_position = cursor
                cursor += _duration(elem)
        elif tag == 'backup':
            cursor = max(0.0, cursor - _duration(elem))
            chord_position = cursor
        elif tag == 'forward':
            cursor += _duration(elem)
            chord_position = cursor

    notes.sort(key=lambda item: (item[0], item[1]))
    return notes


def recalculate_accidentals(output_xml_path: Path, verbose: bool = False) -> None:
    """臨時記号（<accidental>）を有効範囲から再計算する

    <accidental> は「表示する記号」であり、必要かどうかは調号と、同一小節・同一
    staff・同一オクターブで直前に現れた臨時記号（＝臨時記号の有効範囲）で決まる。
    時間反転すると小節内の音符順が変わるため、元譜の <accidental> をそのまま
    音符に付けて動かすと冗長な記号が残り、必要な記号が欠ける。

    出力XMLを走査して各音符に必要な <accidental> だけを残す:
    - alter が有効な alter と異なる → <accidental> が必要（無ければ追加）
    - 一致する → <accidental> は不要（あれば削除。cautionary/parentheses も対象）
    - タイで繋がれた音（<tie type="stop">）は記号を繰り返さないが状態は更新する

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

    added = 0
    removed = 0

    for part in root.findall('.//{*}part'):
        # staff 別の調号（number 属性なしの <key> は全 staff 共通）
        key_alters: dict[Optional[str], dict[str, int]] = {None: _key_alter_map(0)}

        for measure in part.findall('{*}measure'):
            for attributes in measure.findall('{*}attributes'):
                for key in attributes.findall('{*}key'):
                    fifths_elem = key.find('{*}fifths')
                    if fifths_elem is None or not fifths_elem.text:
                        continue
                    try:
                        fifths = int(fifths_elem.text)
                    except ValueError:
                        continue
                    staff_number = key.get('number')
                    if staff_number is None:
                        key_alters = {None: _key_alter_map(fifths)}
                    else:
                        key_alters[staff_number] = _key_alter_map(fifths)

            # 小節内の臨時記号の有効範囲: (staff, step, octave) → alter
            measure_alters: dict[tuple[str, str, str], int] = {}

            for _position, _index, note in _measure_notes_in_time_order(measure):
                alter = _note_alter(note)
                if alter is None:
                    continue

                pitch = note.find('{*}pitch')
                step_elem = pitch.find('{*}step')
                octave_elem = pitch.find('{*}octave')
                if step_elem is None or not step_elem.text:
                    continue
                step = step_elem.text.strip()
                octave = octave_elem.text.strip() if octave_elem is not None and octave_elem.text else ''

                staff_elem = note.find('{*}staff')
                staff = staff_elem.text.strip() if staff_elem is not None and staff_elem.text else '1'

                staff_key_alters = key_alters.get(staff, key_alters.get(None, {}))
                scope_key = (staff, step, octave)
                effective_alter = measure_alters.get(scope_key, staff_key_alters.get(step, 0))

                # タイで繋がれた音は臨時記号を繰り返さない
                is_tie_stop = any(
                    tie.get('type') == 'stop' for tie in note.findall('{*}tie')
                )
                needs_accidental = (alter != effective_alter) and not is_tie_stop
                measure_alters[scope_key] = alter

                accidental = note.find('{*}accidental')
                if needs_accidental and accidental is None:
                    _set_note_accidental(note, alter)
                    added += 1
                    if verbose:
                        print(f"  + m{measure.get('number')} staff{staff} {step}{octave} "
                              f"alter={alter} -> {_ALTER_TO_ACCIDENTAL.get(alter)}")
                elif not needs_accidental and accidental is not None:
                    note.remove(accidental)
                    removed += 1
                    if verbose:
                        print(f"  - m{measure.get('number')} staff{staff} {step}{octave} "
                              f"alter={alter} ({accidental.text} を削除)")

    if verbose:
        print(f"  臨時記号: {added} 個追加, {removed} 個削除")

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


# 反転で無効になる水平位置の属性
_HORIZONTAL_POSITION_ATTRIBUTES = ('default-x', 'relative-x')


def _remove_horizontal_attributes(element: ET.Element) -> int:
    """要素から水平位置の属性を取り除き、取り除いた個数を返す"""
    removed = 0
    for attr in _HORIZONTAL_POSITION_ATTRIBUTES:
        if attr in element.attrib:
            del element.attrib[attr]
            removed += 1
    return removed


def strip_horizontal_layout_hints(output_xml_path: Path, verbose: bool = False) -> None:
    """反転で無効になる横方向のレイアウト情報を出力から取り除く

    元のMusicXMLが持つ水平位置は「元の音符順・元の行組み」を前提にした値なので、
    時間反転すると整合しなくなる:

    - 音符の default-x は小節先頭からの絶対位置。反転すると音符順が変わるため、
      値をそのまま残すと水平位置が右から左に並ぶ
    - <measure width> は段の幅に合わせて justify された結果。反転で段の構成が変わると
      行頭に必要な音部記号・調号のぶんが入らず、段からはみ出した小節が
      単独で1行を占めてしまう（Issue #76）

    横方向の配置は楽譜ソフトに任せる。これは元々このプロジェクトの方針
    （transform_layout_for_reversal の「X座標は変換しない」）だが、
    music21 が往復で持ち回る値には適用されていなかった。

    縦方向（default-y / relative-y / placement）と、<notations> 配下の
    音符基準の微調整（accent, tenuto 等）はそのまま残す。

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

    removed_attrs = 0
    removed_widths = 0

    for measure in root.findall('.//{*}measure'):
        if 'width' in measure.attrib:
            del measure.attrib['width']
            removed_widths += 1

        for note in measure.findall('{*}note'):
            removed_attrs += _remove_horizontal_attributes(note)

        # direction 配下（words, rehearsal, dynamics, wedge, octave-shift 等）も
        # 小節先頭基準なので取り除く
        for direction in measure.findall('{*}direction'):
            removed_attrs += _remove_horizontal_attributes(direction)
            for child in direction.iter():
                if child is not direction:
                    removed_attrs += _remove_horizontal_attributes(child)

    if verbose:
        print(f"  水平位置: 属性 {removed_attrs} 個, measure width {removed_widths} 個を除去")

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


def _measure_attributes_for_insert(measure: ET.Element) -> ET.Element:
    """小節の <attributes> を返す（無ければ小節先頭に作る）

    <attributes> は影響する音符より前に置く必要があるため、<print> があれば
    その直後、無ければ小節の先頭に挿入する。
    """
    for child in measure:
        if child.tag.endswith('attributes'):
            return child

    attributes = ET.Element('attributes')
    insert_pos = 0
    for idx, child in enumerate(measure):
        if child.tag.endswith('print'):
            insert_pos = idx + 1
        else:
            break
    measure.insert(insert_pos, attributes)
    return attributes


def restore_multiple_rests(
    output_xml_path: Path,
    original_layout_map: LayoutMap,
    total_measures: int,
    verbose: bool = False,
) -> None:
    """複数小節休符（multiple-rest）を反転後のブロック先頭に置き直す

    <multiple-rest>N</multiple-rest> は「この小節から N 小節」という前方向スパン。
    時間反転すると元の小節 M..M+N-1 のブロックは反転後の
    (total-(M+N-1)+1)..(total-M+1) に移るため、マーカーはブロックの先頭
    total-M-N+2 に置く必要がある。小節と一緒に運ばれるとブロック末尾に付いたままになり、
    音符のある小節を休符として結合してしまう。

    出力に残っているものを動かすのではなく、元譜から保存した情報で置き直す
    （music21 が N=1 の multiple-rest を落とすため、消失も同時に回復できる）。

    Args:
        output_xml_path: 処理対象のMusicXMLファイル(.xml または .mxl)
        original_layout_map: 元のレイアウト情報（measure_styles を含む）
        total_measures: 総小節数（反転計算用）
        verbose: デバッグ出力を有効にする
    """
    if not original_layout_map or not original_layout_map.measure_styles:
        return

    is_mxl = output_xml_path.suffix == '.mxl'

    if is_mxl:
        root, xml_filename = _extract_mxl_content(output_xml_path)
    else:
        tree = ET.parse(output_xml_path)
        root = tree.getroot()

    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        if part_id not in original_layout_map.measure_styles:
            continue

        measure_map: dict[int, ET.Element] = {}
        for measure in part.findall('{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str:
                try:
                    measure_map[int(measure_num_str)] = measure
                except ValueError:
                    pass

        # music21 が出力した multiple-rest を全て削除する
        for measure in part.findall('{*}measure'):
            for attributes in list(measure.findall('{*}attributes')):
                for measure_style in list(attributes.findall('{*}measure-style')):
                    if measure_style.find('{*}multiple-rest') is None:
                        continue
                    attributes.remove(measure_style)
                if len(attributes) == 0:
                    measure.remove(attributes)

        # 反転後のブロック先頭に挿入する
        for style in original_layout_map.measure_styles[part_id]:
            target = total_measures - style.measure_num - style.count + 2
            if target not in measure_map:
                if verbose:
                    print(f"  警告: multiple-rest の反転先 m{target} が見つかりません "
                          f"(元 m{style.measure_num}, {style.count}小節)")
                continue

            try:
                restored = ET.fromstring(style.measure_style_xml)
            except ET.ParseError:
                continue

            attributes = _measure_attributes_for_insert(measure_map[target])
            # <measure-style> は <attributes> の子要素順（divisions, key, time, ...,
            # transpose, directive, measure-style）で最後なので末尾に追加する
            attributes.append(restored)
            if verbose:
                print(f"  multiple-rest: 元 m{style.measure_num} ({style.count}小節) "
                      f"→ 反転後 m{target}")

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


def _insert_instrument_element(note_elem: ET.Element, instrument_id: str) -> None:
    """<note>にper-note<instrument id="...">を正しいスキーマ順で挿入する

    MusicXMLのnote要素は (pitch|unpitched|rest), duration, tie*, instrument,
    voice, type, ... の順を取る。<voice>があればその直前、無ければ最後の
    <tie>（無ければ<duration>）の直後に挿入する。既に<instrument>があれば何もしない。
    """
    if note_elem.find('{*}instrument') is not None:
        return

    new_elem = ET.Element('instrument')
    new_elem.set('id', instrument_id)

    children = list(note_elem)
    voice_elem = note_elem.find('{*}voice')
    if voice_elem is not None:
        note_elem.insert(children.index(voice_elem), new_elem)
        return

    insert_idx = len(children)
    last_tie_idx = None
    for i, child in enumerate(children):
        if child.tag.split('}')[-1] == 'tie':
            last_tie_idx = i
    if last_tie_idx is not None:
        insert_idx = last_tie_idx + 1
    else:
        duration_elem = note_elem.find('{*}duration')
        if duration_elem is not None:
            insert_idx = children.index(duration_elem) + 1

    note_elem.insert(insert_idx, new_elem)


def _note_voice(note_elem: ET.Element) -> str:
    """<note>の<voice>値を返す（無ければデフォルトの'1'）"""
    voice_elem = note_elem.find('{*}voice')
    return voice_elem.text.strip() if voice_elem is not None and voice_elem.text else '1'


def _restore_instrument_refs(
    root: ET.Element,
    original_layout_map: LayoutMap,
    total_measures: int
) -> None:
    """打楽器パート等でmusic21が読み込まなかったper-note<instrument>参照を復元

    Issue #78: 1つの<part>内で音符ごとに異なる<instrument id="...">を参照して
    複数の音高/音色を表現する打楽器パート（例: グロッケンシュピールの音高を
    打楽器譜内に記譜する構成）では、music21がこの参照を読み込まないため、
    反転後に書き出すと全音符が同じ音（デフォルトの音色）になってしまう。
    元譜から保存した参照を、反転後の音符インデックスに対応付けて復元する。

    Args:
        root: XMLルート要素
        original_layout_map: 元のレイアウト情報（instrument_refsを含む）
        total_measures: 総小節数（反転計算用）
    """
    for part_idx, part in enumerate(root.findall('.//{*}part')):
        part_id = part.get('id', f'P{part_idx + 1}')

        if part_id not in original_layout_map.instrument_refs:
            continue

        inst_refs = original_layout_map.instrument_refs[part_id]
        if not inst_refs:
            continue

        for measure in part.findall('.//{*}measure'):
            measure_num_str = measure.get('number')
            if measure_num_str is None:
                continue

            try:
                reversed_measure_num = int(measure_num_str)
            except ValueError:
                continue

            original_measure_num = total_measures - reversed_measure_num + 1

            matching_refs = [r for r in inst_refs if r.measure_num == original_measure_num]
            if not matching_refs:
                continue

            # 反転はvoiceごとに独立して行われる（reverse_measure_contents）ため、
            # voiceごとにnote_indexを数え、voice内で反転後→元のインデックスを求める
            notes = [elem for elem in measure if elem.tag.endswith('note') and
                     elem.find('.//{*}chord') is None]
            total_notes_by_voice: dict[str, int] = {}
            for n in notes:
                v = _note_voice(n)
                total_notes_by_voice[v] = total_notes_by_voice.get(v, 0) + 1

            voice_note_index: dict[str, int] = {}
            for elem in measure:
                if not elem.tag.endswith('note'):
                    continue

                is_chord = elem.find('.//{*}chord') is not None
                if is_chord:
                    continue

                voice_value = _note_voice(elem)
                idx = voice_note_index.get(voice_value, 0)
                original_note_index = total_notes_by_voice[voice_value] - 1 - idx
                voice_note_index[voice_value] = idx + 1

                for ref in matching_refs:
                    if ref.voice == voice_value and ref.note_index == original_note_index:
                        _insert_instrument_element(elem, ref.instrument_id)
                        break


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

    # per-note instrument参照の復元（打楽器パート等、music21が読み込まない）
    _restore_instrument_refs(root, original_layout_map, total_measures)

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
