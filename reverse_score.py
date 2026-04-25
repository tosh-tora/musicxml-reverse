#!/usr/bin/env python3
"""
MusicXML スコア反転ツール

MXL ファイルを「逆から演奏できる」スコアに変換する。
- 小節順序を反転
- 各小節内の音符オフセットを反転
- Crescendo ↔ Diminuendo を変換
- タイの start/stop を反転
"""

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path

from music21 import converter, stream, dynamics, tie, spanner, clef
from music21.spanner import Ottava


@dataclass
class ProcessingIssue:
    """処理中に発生した問題を記録"""
    part_name: str
    measure_number: int
    error_message: str
    skipped: bool = True


class ErrorHandling:
    """エラー処理モード"""
    SKIP_PART = "skip_part"           # パート全体をスキップ
    SKIP_MEASURE_CONTENT = "skip_measure_content"  # 小節内の音符反転のみスキップ


@dataclass
class ProcessingReport:
    """ファイル処理のレポート"""
    filename: str
    success: bool = True
    issues: list[ProcessingIssue] = field(default_factory=list)
    input_note_count: int = 0
    output_note_count: int = 0
    part_count: int = 0
    skipped_measures: int = 0
    error_handling: str = ErrorHandling.SKIP_PART

    def add_issue(self, part_name: str, measure_number: int, error_message: str, skipped: bool = True):
        self.issues.append(ProcessingIssue(part_name, measure_number, error_message, skipped))
        if skipped:
            self.skipped_measures += 1

    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def print_report(self):
        """レポートを出力"""
        if not self.issues:
            return

        print(f"\n{'='*60}")
        print(f"問題レポート: {self.filename}")
        print(f"{'='*60}")
        print(f"スキップした小節数: {self.skipped_measures}")
        print(f"\n詳細:")

        # パートごとにグループ化
        by_part: dict[str, list[ProcessingIssue]] = {}
        for issue in self.issues:
            if issue.part_name not in by_part:
                by_part[issue.part_name] = []
            by_part[issue.part_name].append(issue)

        for part_name, issues in by_part.items():
            print(f"\n  [{part_name}]")
            for issue in issues:
                status = "スキップ" if issue.skipped else "警告"
                print(f"    小節 {issue.measure_number}: {status} - {issue.error_message}")


def reverse_note_offset(element, measure_duration: float) -> None:
    """小節内の要素のオフセットを反転する"""
    current_offset = element.offset
    element_duration = element.duration.quarterLength
    new_offset = measure_duration - current_offset - element_duration
    element.offset = max(0, new_offset)


def reverse_measure_contents(measure: stream.Measure) -> tuple[stream.Measure, str | None]:
    """小節内の音符・休符・表現記号のオフセットを反転する

    Grace notes are handled specially: they stay attached to their following note.
    When reversing, grace notes + main note are treated as atomic groups.

    Returns:
        tuple: (処理後の小節, エラーメッセージ or None)
    """
    measure_duration = measure.duration.quarterLength
    if measure_duration == 0:
        return measure, None

    try:
        # Create snapshot to avoid iterator corruption when modifying offsets
        elements_snapshot = list(measure.notesAndRests)

        # Group grace notes with their following main notes
        # Each group: [grace1, grace2, ..., main_note]
        note_groups = []
        current_graces = []

        for element in elements_snapshot:
            if element.duration.isGrace:
                # Collect grace notes
                current_graces.append(element)
            else:
                # Main note: create group with preceding grace notes
                group = current_graces + [element]
                note_groups.append(group)
                current_graces = []

        # Handle trailing grace notes (shouldn't happen in valid music, but be defensive)
        if current_graces:
            note_groups.append(current_graces)

        # Reverse the groups (so last main note becomes first)
        note_groups.reverse()

        # Within each group, reverse the grace notes so they appear before their main note
        # Example: [grace1, grace2, main] stays as [grace2, grace1, main] after group reversal
        # No - actually grace notes should stay in original order relative to their note!
        # When we reverse: [g1, g2, note1], [g3, g4, note2]
        # Should become: [note2, g3, g4], [note1, g1, g2]
        # But grace notes appear BEFORE their note in XML, so no intra-group reversal needed

        # Now calculate new offsets for each group
        current_offset = 0.0
        for group in note_groups:
            # Find the main note (last element with non-zero duration)
            main_note = None
            for elem in reversed(group):
                if not elem.duration.isGrace:
                    main_note = elem
                    break

            if main_note is None:
                # Group has only grace notes (edge case)
                for grace in group:
                    grace.offset = current_offset
                continue

            # Calculate reversed offset for the main note
            # Original position: measure_duration - original_offset - duration
            original_offset = main_note.offset
            original_duration = main_note.duration.quarterLength
            new_main_offset = measure_duration - original_offset - original_duration
            new_main_offset = max(0, new_main_offset)

            # Set main note offset
            main_note.offset = new_main_offset

            # Grace notes appear at the same offset as their main note
            for elem in group:
                if elem.duration.isGrace:
                    elem.offset = new_main_offset

            # Advance offset for next group
            current_offset = new_main_offset + original_duration

        # 表現記号（Dynamics, TextExpression等）を反転
        # Create snapshot to avoid iterator corruption when modifying offsets
        expression_snapshot = list(measure.getElementsByClass(['Dynamic', 'TextExpression',
                                                               'TempoText', 'RehearsalMark',
                                                               'MetronomeMark']))
        for element in expression_snapshot:
            reverse_note_offset(element, measure_duration)

        # 要素をオフセット順にソート
        measure.sort()
        return measure, None
    except Exception as e:
        return measure, str(e)


def reverse_ties(element) -> None:
    """タイの start/stop を反転する"""
    if hasattr(element, 'tie') and element.tie is not None:
        if element.tie.type == 'start':
            element.tie = tie.Tie('stop')
        elif element.tie.type == 'stop':
            element.tie = tie.Tie('start')
        # 'continue' はそのまま維持


def reverse_beams(element) -> None:
    """連桁の start/stop を反転する"""
    if hasattr(element, 'beams') and element.beams is not None:
        if len(element.beams.beamsList) > 0:
            for beam_obj in element.beams.beamsList:
                if beam_obj.type == 'start':
                    beam_obj.type = 'stop'
                elif beam_obj.type == 'stop':
                    beam_obj.type = 'start'
                # 'continue' と 'partial' はそのまま維持


def reverse_tuplets(element) -> None:
    """連符の start/stop を反転する"""
    if hasattr(element, 'duration') and element.duration.tuplets:
        for tuplet in element.duration.tuplets:
            if tuplet.type == 'start':
                tuplet.type = 'stop'
            elif tuplet.type == 'stop':
                tuplet.type = 'start'
            # None や 'continue' はそのまま維持


def reverse_dynamics_wedges(part: stream.Part) -> None:
    """Crescendo ↔ Diminuendo を変換する"""
    spanners_to_process = list(part.spannerBundle)

    for sp in spanners_to_process:
        if isinstance(sp, dynamics.Crescendo):
            # Crescendo → Diminuendo に変換
            spanned_elements = list(sp.getSpannedElements())
            part.remove(sp)
            new_wedge = dynamics.Diminuendo(spanned_elements)
            part.insert(0, new_wedge)
        elif isinstance(sp, dynamics.Diminuendo):
            # Diminuendo → Crescendo に変換
            spanned_elements = list(sp.getSpannedElements())
            part.remove(sp)
            new_wedge = dynamics.Crescendo(spanned_elements)
            part.insert(0, new_wedge)


def collect_clef_positions(measures: list[stream.Measure]) -> list[dict]:
    """パート内の全音部記号と小節番号を収集する

    Args:
        measures: 小節のリスト（元の順序）

    Returns:
        音部記号の情報リスト [{measure_num, offset, clef}]
    """
    clef_positions = []

    for measure in measures:
        measure_clefs = measure.getElementsByClass('Clef')
        for clef_obj in measure_clefs:
            clef_positions.append({
                'measure_num': measure.number,
                'offset': clef_obj.offset,
                'clef': clef_obj,
            })

    # 小節番号→オフセット順でソート
    clef_positions.sort(key=lambda x: (x['measure_num'], x['offset']))
    return clef_positions


def calculate_reversed_clef_positions(
    clef_positions: list[dict],
    total_measures: int
) -> list[dict]:
    """音部記号の反転後位置を計算する

    「始点のみ要素」は「次の同種要素が出現するまで有効」という性質を持つ。
    1. 各要素の適用終了位置を計算:
       effective_end[i] = element[i+1].measure_num - 1
       effective_end[last] = total_measures
    2. 反転後の開始位置を計算:
       reversed_start = total_measures - effective_end + 1

    Args:
        clef_positions: collect_clef_positions() の結果
        total_measures: 総小節数

    Returns:
        反転後の位置情報 [{reversed_measure_num, clef}]
    """
    if not clef_positions:
        return []

    reversed_positions = []

    for i, pos in enumerate(clef_positions):
        # 適用終了位置を計算
        if i + 1 < len(clef_positions):
            # 次の音部記号の直前まで有効
            effective_end = clef_positions[i + 1]['measure_num'] - 1
        else:
            # 最後の音部記号は曲の最後まで有効
            effective_end = total_measures

        # 反転後の開始位置を計算
        reversed_start = total_measures - effective_end + 1

        reversed_positions.append({
            'reversed_measure_num': reversed_start,
            'clef': copy.deepcopy(pos['clef']),
        })

    # 反転後の小節番号順でソート
    reversed_positions.sort(key=lambda x: x['reversed_measure_num'])
    return reversed_positions


def apply_reversed_clefs(
    new_part: stream.Part,
    reversed_clef_positions: list[dict]
) -> None:
    """反転後のパートに音部記号を挿入する

    Args:
        new_part: 反転後のパート（小節が追加済み）
        reversed_clef_positions: calculate_reversed_clef_positions() の結果
    """
    if not reversed_clef_positions:
        return

    # m1に最初の音部記号を挿入（パートレベル）
    first_clef = reversed_clef_positions[0]
    new_part.insert(0, first_clef['clef'])

    # m2以降に音部記号の変更を挿入
    for pos in reversed_clef_positions[1:]:
        target_measure_num = pos['reversed_measure_num']

        # 対象の小節を検索
        for measure in new_part.getElementsByClass(stream.Measure):
            if measure.number == target_measure_num:
                # 小節の先頭に音部記号を挿入
                measure.insert(0, pos['clef'])
                break


# 経過的テンポ表記のパターン
# これらは「一時的な変化」を示し、次の主要テンポ指示まで有効ではない
TRANSITIONAL_TEMPO_PATTERNS = [
    'rit',      # ritardando, ritenuto
    'rall',     # rallentando
    'accel',    # accelerando
    'string',   # stringendo
    'morendo',
    'calando',
    'slentando',
    'allarg',   # allargando
    'a tempo',
]


def is_transitional_tempo(text: str) -> bool:
    """テンポ表記が経過的（一時的な変化）かどうかを判定する

    経過的テンポ表記は、次の主要テンポ指示が出現するまでの間の
    漸進的な変化を示す。これらは反転時に有効範囲の計算から除外する。

    Args:
        text: テンポ表記のテキスト

    Returns:
        経過的テンポ表記の場合True
    """
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in TRANSITIONAL_TEMPO_PATTERNS)


def collect_tempo_positions(measures: list[stream.Measure]) -> list[dict]:
    """パート内の全テンポ関連要素と小節番号を収集する

    Args:
        measures: 小節のリスト（元の順序）

    Returns:
        テンポ要素の情報リスト [{measure_num, offset, element, element_type, is_transitional}]
    """
    tempo_positions = []
    tempo_classes = ['TempoText', 'TextExpression', 'MetronomeMark']

    for measure in measures:
        for tempo_class in tempo_classes:
            tempo_elements = measure.getElementsByClass(tempo_class)
            for elem in tempo_elements:
                # テンポ要素からテキストを取得
                text = getattr(elem, 'text', '') or getattr(elem, 'content', '') or ''

                tempo_positions.append({
                    'measure_num': measure.number,
                    'offset': elem.offset,
                    'element': elem,
                    'element_type': tempo_class,
                    'is_transitional': is_transitional_tempo(text),
                })

    # 小節番号→オフセット順でソート
    tempo_positions.sort(key=lambda x: (x['measure_num'], x['offset']))
    return tempo_positions


def calculate_reversed_tempo_positions(
    tempo_positions: list[dict],
    total_measures: int
) -> list[dict]:
    """テンポ要素の反転後位置を計算する

    主要テンポ指示と経過的テンポ指示を分けて処理:
    - 主要テンポ: 有効範囲ベースで反転（次の主要テンポまでの範囲を考慮）
    - 経過的テンポ（rit., accel.等）: 単純な位置反転（相対位置を維持）

    Args:
        tempo_positions: collect_tempo_positions() の結果
        total_measures: 総小節数

    Returns:
        反転後の位置情報 [{reversed_measure_num, element, element_type}]
    """
    if not tempo_positions:
        return []

    # 主要テンポ指示と経過的テンポ指示を分離
    main_tempos = [p for p in tempo_positions if not p.get('is_transitional')]
    transitional_tempos = [p for p in tempo_positions if p.get('is_transitional')]

    reversed_positions = []

    # 主要テンポの有効範囲ベース反転
    for i, pos in enumerate(main_tempos):
        # 適用終了位置を計算（次の「異なる小節」の主要テンポの直前まで）
        effective_end = total_measures  # デフォルトは曲の最後
        for j in range(i + 1, len(main_tempos)):
            next_measure = main_tempos[j]['measure_num']
            if next_measure > pos['measure_num']:
                # 次の異なる小節のテンポを見つけた
                effective_end = next_measure - 1
                break

        # 反転後の開始位置を計算
        reversed_start = total_measures - effective_end + 1

        reversed_positions.append({
            'reversed_measure_num': reversed_start,
            'element': copy.deepcopy(pos['element']),
            'element_type': pos['element_type'],
        })

    # 経過的テンポは単純な位置反転（小節番号のみ反転）
    for pos in transitional_tempos:
        reversed_start = total_measures - pos['measure_num'] + 1

        reversed_positions.append({
            'reversed_measure_num': reversed_start,
            'element': copy.deepcopy(pos['element']),
            'element_type': pos['element_type'],
        })

    # 反転後の小節番号順でソート
    reversed_positions.sort(key=lambda x: x['reversed_measure_num'])
    return reversed_positions


def apply_reversed_tempo_elements(
    new_part: stream.Part,
    reversed_tempo_positions: list[dict]
) -> None:
    """反転後のパートにテンポ要素を挿入する

    Args:
        new_part: 反転後のパート（小節が追加済み）
        reversed_tempo_positions: calculate_reversed_tempo_positions() の結果
    """
    if not reversed_tempo_positions:
        return

    for pos in reversed_tempo_positions:
        target_measure_num = pos['reversed_measure_num']
        element = pos['element']
        # オフセットをリセット（小節先頭に配置）
        element.offset = 0

        # 対象の小節を検索
        for measure in new_part.getElementsByClass(stream.Measure):
            if measure.number == target_measure_num:
                # 小節の先頭にテンポ要素を挿入
                measure.insert(0, element)
                break


def reverse_part(part: stream.Part, report: ProcessingReport | None = None) -> stream.Part:
    """パート全体を反転する"""
    measures = list(part.getElementsByClass(stream.Measure))
    if not measures:
        return part

    part_name = part.partName or part.id or "Unknown"
    error_handling = report.error_handling if report else ErrorHandling.SKIP_PART

    # Spannerの情報を保存（小節内容を変更する前に）
    # 各Spannerについて、どの音符をつなぐかの位置情報を記録
    spanner_info = []
    measure_based_spanners = []  # RepeatBracket等の小節ベースSpanner

    for sp in part.spannerBundle:
        spanned_elements_original = list(sp.getSpannedElements())
        # Allow single-element spanners for dynamics wedges
        if len(spanned_elements_original) < 2:
            if not isinstance(sp, (dynamics.Crescendo, dynamics.Diminuendo)):
                continue
            # For dynamics with < 2 elements, skip if no elements at all
            if len(spanned_elements_original) == 0:
                continue

        # 小節ベースのSpanner（RepeatBracket等）を特別扱い
        if spanned_elements_original and isinstance(spanned_elements_original[0], stream.Measure):
            measure_numbers = [m.number for m in spanned_elements_original]
            measure_based_spanners.append({
                'type': sp.__class__,
                'measure_numbers': measure_numbers,
                'number': getattr(sp, 'number', None),  # RepeatBracketのnumber属性
            })
            continue

        # 各音符の位置情報を記録（小節番号、オフセット、ピッチ、小節内インデックス）
        note_positions = []
        for elem in spanned_elements_original:
            found = False

            # まず、要素が属する小節をgetContextByClassで特定
            containing_measure = elem.getContextByClass(stream.Measure)
            if containing_measure is not None:
                # 特定の小節のみを検索（誤マッチング防止）
                target_measures = [m for m in measures if m.number == containing_measure.number]
            else:
                # フォールバック：全小節を検索（従来の動作）
                target_measures = measures

            for measure in target_measures:
                measure_notes = list(measure.notesAndRests)
                for note_idx, note in enumerate(measure_notes):
                    # プロパティで一致を判定
                    offset_match = abs(elem.offset - note.offset) < 0.0001
                    duration_match = abs(elem.duration.quarterLength - note.duration.quarterLength) < 0.0001

                    pitch_match = False
                    if elem.isRest and note.isRest:
                        pitch_match = True
                    elif hasattr(elem, 'pitches') and hasattr(note, 'pitches'):
                        # Chord: compare all pitches
                        elem_pitches = sorted(p.nameWithOctave for p in elem.pitches)
                        note_pitches = sorted(p.nameWithOctave for p in note.pitches)
                        pitch_match = (elem_pitches == note_pitches)
                    elif hasattr(elem, 'pitch') and hasattr(note, 'pitch'):
                        pitch_match = (str(elem.pitch) == str(note.pitch))
                    elif not elem.isRest and not note.isRest:
                        # Both are notes but neither has pitch (unpitched percussion)
                        # Match by grace status instead
                        pitch_match = (elem.duration.isGrace == note.duration.isGrace)

                    if offset_match and duration_match and pitch_match:
                        # 単音符と和音の両方に対応
                        if hasattr(note, 'pitches'):
                            pitch_name = None  # Chordの場合はpitchはNone
                            pitches_list = sorted(p.nameWithOctave for p in note.pitches)
                        elif hasattr(note, 'pitch'):
                            pitch_name = str(note.pitch)
                            pitches_list = None
                        else:
                            pitch_name = None
                            pitches_list = None
                        note_positions.append({
                            'measure_num': measure.number,
                            'offset': note.offset,
                            'duration': note.duration.quarterLength,
                            'pitch': pitch_name,
                            'pitches': pitches_list,  # 和音用
                            'is_rest': note.isRest,
                            'is_grace': note.duration.isGrace,  # Grace note flag for matching
                            'note_index': note_idx
                        })
                        found = True
                        break
                if found:
                    break

        if len(note_positions) == len(spanned_elements_original):
            # Sanity check for slurs: skip if span is unreasonably long
            # music21 sometimes creates incorrect slur associations across distant measures
            if 'Slur' in sp.__class__.__name__ and len(note_positions) >= 2:
                measure_nums = [pos['measure_num'] for pos in note_positions]
                span_length = max(measure_nums) - min(measure_nums)
                # Skip slurs spanning more than 8 measures (likely a music21 bug)
                if span_length > 8:
                    continue

            sp_data = {
                'type': sp.__class__,
                'positions': note_positions
            }

            # Ottavaの場合、追加のプロパティを保存
            if isinstance(sp, Ottava):
                sp_data['ottava_type'] = sp.type
                sp_data['transposing'] = sp.transposing
                sp_data['placement'] = sp.placement

            spanner_info.append(sp_data)

    # SKIP_MEASURE_CONTENT モードでは元の小節を保持
    if error_handling == ErrorHandling.SKIP_MEASURE_CONTENT:
        original_measures = [copy.deepcopy(m) for m in measures]
    else:
        original_measures = None

    # 小節を逆順に処理
    reversed_measures = list(reversed(measures))

    # 新しいパートを作成
    new_part = stream.Part()
    new_part.id = part.id

    # パート名などのメタデータをコピー
    if part.partName:
        new_part.partName = part.partName
    if part.partAbbreviation:
        new_part.partAbbreviation = part.partAbbreviation

    # 最初の小節から楽器、調号、拍子記号を取得してコピー
    first_original_measure = measures[0]
    total_measures = len(measures)

    # 楽器をコピー
    for inst in part.getElementsByClass('Instrument'):
        new_part.insert(0, inst)

    # 音部記号は反転ロジックで処理するため、ここではスキップ
    # （全小節処理後に apply_reversed_clefs() で挿入）
    clef_positions = collect_clef_positions(measures)

    # テンポ要素も同様に反転ロジックで処理
    tempo_positions = collect_tempo_positions(measures)

    # 調号をコピー (KeySignature)
    key_sigs = first_original_measure.getElementsByClass('KeySignature')
    if key_sigs:
        first_key = key_sigs.first()
        if first_key:
            new_part.insert(0, first_key)

    # 拍子記号をコピー (TimeSignature)
    time_sigs = first_original_measure.getElementsByClass('TimeSignature')
    if time_sigs:
        first_time = time_sigs.first()
        if first_time:
            new_part.insert(0, first_time)

    # 各小節を処理して追加
    for i, measure in enumerate(reversed_measures):
        original_measure_num = measure.number
        original_index = len(measures) - 1 - i  # 元の配列でのインデックス

        # 小節のディープコピーを作成
        # IMPORTANT: reverse_measure_contents() は要素のオフセットをin-placeで変更するため、
        # 元の小節を変更しないよう、常にコピーを使用する必要がある
        # (Spanner情報の収集時に記録した位置情報が狂うのを防ぐため)
        measure_to_process = copy.deepcopy(measure)

        # テンポ要素を小節から削除（反転ロジックで再配置するため）
        for tempo_class in ['TempoText', 'TextExpression', 'MetronomeMark']:
            for elem in list(measure_to_process.getElementsByClass(tempo_class)):
                measure_to_process.remove(elem)

        # 音部記号を小節から削除（反転ロジックで再配置するため）
        for elem in list(measure_to_process.getElementsByClass('Clef')):
            measure_to_process.remove(elem)

        # 小節内の音符を反転
        processed_measure, error = reverse_measure_contents(measure_to_process)

        if error:
            if report:
                report.add_issue(part_name, original_measure_num, f"反転処理エラー: {error}")
            # エラー時は元の小節をそのまま使用（反転せず）
            if original_measures:
                fallback = copy.deepcopy(original_measures[original_index])
            else:
                fallback = measure
            fallback.number = i + 1
            new_part.append(fallback)
            continue

        # 書き出し可能かテスト（SKIP_MEASURE_CONTENT モードの場合）
        if error_handling == ErrorHandling.SKIP_MEASURE_CONTENT:
            write_error = test_measure_write(processed_measure)
            if write_error:
                if report:
                    report.add_issue(part_name, original_measure_num,
                                     f"書き出しエラー（音符反転スキップ）: {write_error}")
                # 元の小節（反転前）を使用
                fallback = copy.deepcopy(original_measures[original_index])
                fallback.number = i + 1

                # 元の小節も書き出せるかテスト
                fallback_error = test_measure_write(fallback)
                if fallback_error:
                    # 元の小節も問題がある場合は音価を修正
                    try:
                        fix_measure_durations(fallback)
                    except Exception:
                        pass  # 修正失敗しても続行

                # タイと連桁は反転する（小節順序が変わるため）
                for element in fallback.notesAndRests:
                    reverse_ties(element)
                    reverse_beams(element)
                    reverse_tuplets(element)
                    if hasattr(element, 'notes'):
                        for note in element.notes:
                            reverse_ties(note)
                            reverse_beams(note)
                            reverse_tuplets(note)
                new_part.append(fallback)
                continue

        # タイと連桁を反転
        for element in processed_measure.notesAndRests:
            reverse_ties(element)
            reverse_beams(element)
            reverse_tuplets(element)
            # 和音内の音符のタイと連桁も処理
            if hasattr(element, 'notes'):
                for note in element.notes:
                    reverse_ties(note)
                    reverse_beams(note)
                    reverse_tuplets(note)

            # 小節番号を再割り当て
        processed_measure.number = i + 1
        new_part.append(processed_measure)

    # 音部記号を反転して適用
    reversed_clef_positions = calculate_reversed_clef_positions(clef_positions, total_measures)
    apply_reversed_clefs(new_part, reversed_clef_positions)

    # テンポ要素を反転して適用
    reversed_tempo_positions = calculate_reversed_tempo_positions(tempo_positions, total_measures)
    apply_reversed_tempo_elements(new_part, reversed_tempo_positions)

    # 保存したSpanner情報を使って、新しいパートでSpannerを再構築
    for sp_info in spanner_info:
        new_spanned_elements = []

        for pos in sp_info['positions']:
            reversed_measure_num = len(measures) - pos['measure_num'] + 1

            # 新しいパートから対応する小節を取得
            for new_measure in new_part.getElementsByClass(stream.Measure):
                if new_measure.number == reversed_measure_num:
                    # 小節内で反転後のオフセットを計算
                    measure_duration = new_measure.duration.quarterLength
                    reversed_offset = measure_duration - pos['offset'] - pos['duration']
                    reversed_offset = max(0, reversed_offset)

                    # 元の小節内のインデックスから、反転後のインデックスを計算
                    # 反転により、notesAndRestsリストも逆順になるため
                    original_note_index = pos.get('note_index')
                    notes_list = list(new_measure.notesAndRests)

                    # note_indexが記録されている場合は、それを使って一意に識別
                    # SKIP for unpitched percussion (pitch is None) because grace note grouping changes indices
                    use_note_index = (original_note_index is not None and
                                     (pos.get('pitch') is not None or pos.get('pitches') is not None or pos['is_rest']))

                    if use_note_index:
                        # 反転後のインデックスを計算（逆順になるため）
                        reversed_note_index = len(notes_list) - 1 - original_note_index

                        if 0 <= reversed_note_index < len(notes_list):
                            new_elem = notes_list[reversed_note_index]
                            # Check grace status first (critical for grace notes that share offsets)
                            grace_match = (pos.get('is_grace', False) == new_elem.duration.isGrace)
                            if not grace_match:
                                # Wrong grace status, skip to fallback
                                pass
                            else:
                                # オフセットとピッチの最終確認（sanity check）
                                # For grace notes, use looser offset matching since they now share offset with main note
                                offset_tolerance = 0.5 if pos.get('is_grace', False) else 0.01
                                offset_match = abs(new_elem.offset - reversed_offset) < offset_tolerance
                                # 和音と単音符の両方に対応
                                pitch_match = False
                                if pos['is_rest'] and new_elem.isRest:
                                    pitch_match = True
                                elif pos.get('pitches') and hasattr(new_elem, 'pitches'):
                                    new_pitches = sorted(p.nameWithOctave for p in new_elem.pitches)
                                    pitch_match = (pos['pitches'] == new_pitches)
                                elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                                    pitch_match = (str(new_elem.pitch) == pos['pitch'])
                                if offset_match and pitch_match:
                                    new_spanned_elements.append(new_elem)
                                    break

                    # フォールバック: note_indexが使えない場合、オフセット+ピッチ+grace状態で検索
                    # For unpitched percussion, match by grace status + duration instead of offset
                    if len(new_spanned_elements) < len([p for p in sp_info['positions'] if sp_info['positions'].index(p) <= sp_info['positions'].index(pos)]):
                        for new_elem in notes_list:
                            # Check grace status match
                            grace_match = (pos.get('is_grace', False) == new_elem.duration.isGrace)
                            if not grace_match:
                                continue

                            # For unpitched percussion (no pitch info), match by duration
                            # For others, use offset matching
                            is_unpitched = (not pos.get('pitch') and not pos.get('pitches') and not pos['is_rest'])
                            if is_unpitched:
                                # Unpitched note: match by duration
                                duration_match = abs(new_elem.duration.quarterLength - pos['duration']) < 0.01
                                if duration_match:
                                    new_spanned_elements.append(new_elem)
                                    break
                            else:
                                # Pitched note or rest: use offset matching
                                # Looser offset matching for grace notes
                                offset_tolerance = 0.5 if pos.get('is_grace', False) else 0.01
                                offset_match = abs(new_elem.offset - reversed_offset) < offset_tolerance
                                if offset_match:
                                    # ピッチまたは休符かをチェック（和音対応）
                                    if pos['is_rest'] and new_elem.isRest:
                                        new_spanned_elements.append(new_elem)
                                        break
                                    elif pos.get('pitches') and hasattr(new_elem, 'pitches'):
                                        new_pitches = sorted(p.nameWithOctave for p in new_elem.pitches)
                                        if pos['pitches'] == new_pitches:
                                            new_spanned_elements.append(new_elem)
                                            break
                                    elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                                        if str(new_elem.pitch) == pos['pitch']:
                                            new_spanned_elements.append(new_elem)
                                            break
                    break

        # すべての音符が見つかった場合のみSpannerを作成
        # ダイナミクスは1要素でもOK、それ以外は2要素以上必要
        min_elements = 1 if issubclass(sp_info['type'], (dynamics.Crescendo, dynamics.Diminuendo)) else 2

        if len(new_spanned_elements) == len(sp_info['positions']) and len(new_spanned_elements) >= min_elements:
            # IMPORTANT: Spannerは時系列順(小節番号→オフセット順)に要素を持つ必要がある
            # 反転後、要素が逆順になっている可能性があるため、ソートする
            new_spanned_elements_sorted = sorted(
                new_spanned_elements,
                key=lambda elem: (
                    # 要素が属する小節番号を取得
                    next((m.number for m in new_part.getElementsByClass(stream.Measure)
                          if elem in m.notesAndRests), 0),
                    # 小節内のオフセット
                    elem.offset
                )
            )

            # Create spanner with type conversion for dynamics
            spanner_class = sp_info['type']
            if issubclass(spanner_class, dynamics.Crescendo):
                new_spanner = dynamics.Diminuendo(new_spanned_elements_sorted)
            elif issubclass(spanner_class, dynamics.Diminuendo):
                new_spanner = dynamics.Crescendo(new_spanned_elements_sorted)
            else:
                new_spanner = spanner_class(new_spanned_elements_sorted)

            # Ottavaの場合、保存したプロパティを復元
            if isinstance(new_spanner, Ottava):
                new_spanner.type = sp_info.get('ottava_type', '8va')
                new_spanner.transposing = sp_info.get('transposing', False)
                new_spanner.placement = sp_info.get('placement', 'above')

            new_part.insert(0, new_spanner)

    # 小節ベースSpanner（RepeatBracket等）を再構築
    for mb_sp in measure_based_spanners:
        # 元の小節番号を反転後の小節番号にマッピング
        total_measures = len(measures)
        reversed_measure_numbers = [total_measures - m_num + 1 for m_num in mb_sp['measure_numbers']]
        reversed_measure_numbers.sort()  # 昇順にソート

        # 反転後の小節を取得
        reversed_measures_for_spanner = []
        for m_num in reversed_measure_numbers:
            for measure in new_part.getElementsByClass(stream.Measure):
                if measure.number == m_num:
                    reversed_measures_for_spanner.append(measure)
                    break

        if len(reversed_measures_for_spanner) == len(mb_sp['measure_numbers']):
            spanner_class = mb_sp['type']
            if mb_sp['number'] is not None:
                # RepeatBracketの場合、number引数が必要
                new_spanner = spanner_class(reversed_measures_for_spanner, number=mb_sp['number'])
            else:
                new_spanner = spanner_class(reversed_measures_for_spanner)
            new_part.insert(0, new_spanner)

    # ダイナミクスのウェッジを反転
    # DEPRECATED: now handled in spanner restoration above with type conversion
    # reverse_dynamics_wedges(new_part)

    return new_part


def test_measure_write(measure: stream.Measure) -> str | None:
    """小節が書き出し可能かテストする

    Returns:
        エラーメッセージ or None（成功時）
    """
    try:
        test_part = stream.Part()
        test_measure = copy.deepcopy(measure)
        test_part.append(test_measure)
        test_score = stream.Score()
        test_score.append(test_part)
        test_score.write('musicxml')  # メモリ上でテスト
        return None
    except Exception as e:
        return str(e)


def reverse_score(score: stream.Score, report: ProcessingReport | None = None) -> stream.Score:
    """スコア全体を反転する"""
    new_score = stream.Score()

    # メタデータをコピー
    if score.metadata:
        new_score.metadata = score.metadata

    # 各パートを反転
    for part in score.parts:
        reversed_part = reverse_part(part, report)
        new_score.append(reversed_part)

    return new_score


def count_notes(score: stream.Score) -> int:
    """スコア内の音符数をカウント"""
    count = 0
    for part in score.parts:
        for element in part.recurse().notesAndRests:
            count += 1
    return count


def process_file(input_path: Path, output_path: Path,
                  error_handling: str = ErrorHandling.SKIP_PART) -> ProcessingReport:
    """単一ファイルを処理する

    Args:
        input_path: 入力ファイルパス
        output_path: 出力ファイルパス
        error_handling: エラー処理モード
            - SKIP_PART: 問題のあるパート全体をスキップ
            - SKIP_MEASURE_CONTENT: 問題の小節内の音符反転のみスキップ（他の反転処理は実行）
    """
    report = ProcessingReport(filename=input_path.name, error_handling=error_handling)
    print(f"処理中: {input_path.name}")
    if error_handling == ErrorHandling.SKIP_MEASURE_CONTENT:
        print(f"  モード: 問題小節の音符反転をスキップ")

    try:
        # ========== Phase 1: レイアウト抽出 ==========
        print(f"  [Phase 1] レイアウト情報を抽出中...")
        from layout_preservation import extract_layout_from_xml
        try:
            original_layout = extract_layout_from_xml(input_path)
            layout_extraction_success = True
        except Exception as layout_error:
            print(f"  警告: レイアウト抽出に失敗しました: {layout_error}")
            original_layout = None
            layout_extraction_success = False

        # ========== Phase 2: 音楽反転処理 ==========
        # MXL ファイルを読み込み
        score = converter.parse(str(input_path))

        if not isinstance(score, stream.Score):
            # 単一パートの場合はスコアに変換
            new_score = stream.Score()
            new_score.append(score)
            score = new_score

        # SKIP_MEASURE_CONTENT モードでは元のスコアを保持
        if error_handling == ErrorHandling.SKIP_MEASURE_CONTENT:
            original_score = copy.deepcopy(score)

        report.input_note_count = count_notes(score)
        report.part_count = len(score.parts)
        print(f"  入力音符数: {report.input_note_count}")
        print(f"  パート数: {report.part_count}")

        # 反転処理
        reversed_score = reverse_score(score, report)

        report.output_note_count = count_notes(reversed_score)
        print(f"  出力音符数: {report.output_note_count}")

        if report.input_note_count != report.output_note_count:
            print(f"  警告: 音符数が一致しません！")

        # 出力ファイルを書き出し（エラー時はスキップして続行）
        try:
            # 入力ファイルの形式に応じて出力形式を決定
            output_format = 'mxl' if input_path.suffix == '.mxl' else 'xml'
            reversed_score.write(output_format, fp=str(output_path))
            print(f"  出力: {output_path.name}")

            # ========== Phase 3: XML後処理 ==========
            try:
                # music21のバグで分割されたdirection要素をマージ
                print(f"  [Phase 3] 分割されたdirection要素をマージ中...")
                from layout_preservation import merge_split_directions, normalize_slur_numbers
                merge_split_directions(output_path, verbose=True)
                print(f"  [Phase 3] direction要素のマージ完了")

                # スラーのnumber属性を正規化
                print(f"  [Phase 3] スラー番号を正規化中...")
                normalize_slur_numbers(output_path, verbose=False)
                print(f"  [Phase 3] スラー番号の正規化完了")
            except Exception as merge_error:
                print(f"  警告: direction要素のマージに失敗しました: {merge_error}")
                import traceback
                traceback.print_exc()

            # ========== Phase 4: レイアウト復元 ==========
            if layout_extraction_success and original_layout is not None:
                print(f"  [Phase 4] レイアウト情報を復元中...")
                from layout_preservation import apply_layout_to_xml, merge_split_directions
                try:
                    total_measures = len(list(reversed_score.parts[0].getElementsByClass('Measure')))
                    apply_layout_to_xml(output_path, original_layout, total_measures)
                    print(f"  [Phase 4] レイアウト復元完了")

                    # レイアウト復元後に再度マージ（XMLシリアライズで再分割される可能性があるため）
                    print(f"  [Phase 4] direction要素を再マージ中...")
                    merge_split_directions(output_path, verbose=False)
                    print(f"  [Phase 4] direction要素の再マージ完了")
                except Exception as layout_apply_error:
                    print(f"  警告: レイアウト復元に失敗しました: {layout_apply_error}")
                    # レイアウト適用失敗は警告のみ（反転処理自体は成功）

        except Exception as write_error:
            # 書き出しエラーの詳細を解析してレポートに追加
            error_msg = str(write_error)
            # music21 のエラーメッセージからパート名と小節番号を抽出
            if "part (" in error_msg and "measure (" in error_msg:
                import re
                match = re.search(r'part \(([^)]+)\).*measure \((\d+)\)', error_msg)
                if match:
                    part_name = match.group(1)
                    measure_num = int(match.group(2))
                    report.add_issue(part_name, measure_num, f"書き出しエラー: {error_msg}")

            # 問題のあるパートをスキップして再試行
            print(f"  書き出しエラー発生、問題箇所をスキップして再試行...")
            success = write_with_fallback(reversed_score, output_path, report)
            if success:
                print(f"  出力: {output_path.name} (一部をスキップ)")
            else:
                report.success = False
                print(f"  エラー: 書き出しに失敗しました")

        return report

    except Exception as e:
        print(f"  エラー: {e}")
        report.success = False
        return report


def write_with_fallback(score: stream.Score, output_path: Path, report: ProcessingReport) -> bool:
    """問題のある小節をスキップしながら書き出しを試行"""
    import re
    from music21 import note

    # 各パートの各小節を個別に検証・修正
    for part in score.parts:
        part_name = part.partName or part.id or "Unknown"
        measures = list(part.getElementsByClass(stream.Measure))

        for measure in measures:
            measure_num = measure.number
            try:
                # 小節単体でのシリアライズをテスト
                test_part = stream.Part()
                test_measure = copy.deepcopy(measure)
                test_part.append(test_measure)
                test_score = stream.Score()
                test_score.append(test_part)
                test_score.write('musicxml')  # メモリ上でテスト
            except Exception as e:
                error_msg = str(e)
                report.add_issue(part_name, measure_num, f"小節エラー: {error_msg}")
                print(f"    問題小節を修正: {part_name} 小節{measure_num}")

                # 問題のある小節の音価を修正（quantize で丸める）
                try:
                    fix_measure_durations(measure)
                    # 修正後に再テスト
                    test_part2 = stream.Part()
                    test_measure2 = copy.deepcopy(measure)
                    test_part2.append(test_measure2)
                    test_score2 = stream.Score()
                    test_score2.append(test_part2)
                    test_score2.write('musicxml')
                except Exception:
                    # 修正できない場合は小節を空にする
                    for el in list(measure.notesAndRests):
                        measure.remove(el)
                    # 全休符を挿入
                    r = note.Rest()
                    r.duration.quarterLength = measure.duration.quarterLength or 4.0
                    measure.insert(0, r)

    # 修正後に書き出しを試行
    try:
        # output_path から形式を判定
        output_format = 'mxl' if output_path.suffix == '.mxl' else 'xml'
        score.write(output_format, fp=str(output_path))
        return True
    except Exception:
        # それでもダメな場合はパート単位でスキップ
        return write_with_part_fallback(score, output_path, report)


def fix_measure_durations(measure: stream.Measure) -> None:
    """小節内の音価を修正（quantize）"""
    for element in measure.notesAndRests:
        # 音価を最も近い標準的な値に丸める
        ql = element.duration.quarterLength
        # 標準的な音価: 4, 2, 1, 0.5, 0.25, 0.125, etc.
        # 付点: 3, 1.5, 0.75, 0.375, etc.
        standard_values = [
            4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.375,
            0.25, 0.1875, 0.125, 0.0625
        ]

        # 極端に短い音価（0.0625未満）は最小値に修正
        if ql < 0.0625:
            element.duration.quarterLength = 0.0625  # 64分音符
            continue

        closest = min(standard_values, key=lambda x: abs(x - ql))
        if abs(closest - ql) > 0.001:
            element.duration.quarterLength = closest


def write_with_part_fallback(score: stream.Score, output_path: Path, report: ProcessingReport) -> bool:
    """問題のあるパートをスキップしながら書き出しを試行"""
    import re

    # 各パートを個別に検証
    valid_parts = []
    for part in score.parts:
        part_name = part.partName or part.id or "Unknown"
        try:
            # パート単体でのシリアライズをテスト
            test_score = stream.Score()
            test_score.append(copy.deepcopy(part))
            test_score.write('musicxml')  # メモリ上でテスト
            valid_parts.append(part)
        except Exception as e:
            error_msg = str(e)
            # 小節番号を抽出
            match = re.search(r'measure \((\d+)\)', error_msg)
            measure_num = int(match.group(1)) if match else 0
            report.add_issue(part_name, measure_num, f"パート書き出しエラー: {error_msg}")
            print(f"    スキップ: {part_name}")

    if not valid_parts:
        return False

    # 有効なパートのみで新しいスコアを作成
    new_score = stream.Score()
    if score.metadata:
        new_score.metadata = score.metadata
    for part in valid_parts:
        new_score.append(part)

    try:
        # output_path から形式を判定
        output_format = 'mxl' if output_path.suffix == '.mxl' else 'xml'
        new_score.write(output_format, fp=str(output_path))
        return True
    except Exception:
        return False


def main():
    """メイン処理"""
    import argparse

    parser = argparse.ArgumentParser(description="MusicXML スコア反転ツール")
    parser.add_argument("--skip-measure-content", "-s", action="store_true",
                        help="問題のある小節の音符反転のみスキップ（小節順序・タイ・ダイナミクスは反転）")
    args = parser.parse_args()

    error_handling = (ErrorHandling.SKIP_MEASURE_CONTENT if args.skip_measure_content
                      else ErrorHandling.SKIP_PART)

    inbox = Path("work/inbox")
    outbox = Path("work/outbox")

    # ディレクトリの存在確認
    if not inbox.exists():
        print(f"エラー: 入力ディレクトリが見つかりません: {inbox}")
        sys.exit(1)

    outbox.mkdir(parents=True, exist_ok=True)

    # MusicXML ファイルを検索 (.mxl, .xml, .musicxml)
    input_files = []
    for pattern in ["*.mxl", "*.xml", "*.musicxml"]:
        input_files.extend(inbox.glob(pattern))

    if not input_files:
        print(f"MusicXML ファイルが見つかりません: {inbox}")
        sys.exit(0)

    print(f"処理対象: {len(input_files)} ファイル\n")

    success_count = 0
    all_reports: list[ProcessingReport] = []

    for input_path in input_files:
        # 出力ファイル名を生成（入力形式を保持）
        output_name = input_path.stem + "_rev" + input_path.suffix
        output_path = outbox / output_name

        report = process_file(input_path, output_path, error_handling)
        all_reports.append(report)

        if report.success:
            success_count += 1
        print()

    print(f"完了: {success_count}/{len(input_files)} ファイル処理成功")

    # 問題レポートを出力
    reports_with_issues = [r for r in all_reports if r.has_issues()]
    if reports_with_issues:
        print(f"\n{'#'*60}")
        print(f"# 問題サマリー: {len(reports_with_issues)} ファイルで問題が検出されました")
        print(f"{'#'*60}")
        for report in reports_with_issues:
            report.print_report()


if __name__ == "__main__":
    main()
