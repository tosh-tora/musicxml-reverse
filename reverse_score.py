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

from music21 import converter, stream, dynamics, tie, spanner


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

    Returns:
        tuple: (処理後の小節, エラーメッセージ or None)
    """
    measure_duration = measure.duration.quarterLength
    if measure_duration == 0:
        return measure, None

    try:
        # 音符、休符、和音を取得して反転
        for element in measure.notesAndRests:
            reverse_note_offset(element, measure_duration)

        # 表現記号（Dynamics, TextExpression等）を反転
        for element in measure.getElementsByClass(['Dynamic', 'TextExpression',
                                                    'TempoText', 'RehearsalMark']):
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
    for sp in part.spannerBundle:
        spanned_elements_original = list(sp.getSpannedElements())
        if len(spanned_elements_original) < 2:
            continue

        # 各音符の位置情報を記録（小節番号、オフセット、ピッチ）
        note_positions = []
        for elem in spanned_elements_original:
            for measure in measures:
                if elem in measure.notesAndRests:
                    pitch_name = str(elem.pitch) if hasattr(elem, 'pitch') else None
                    note_positions.append({
                        'measure_num': measure.number,
                        'offset': elem.offset,
                        'duration': elem.duration.quarterLength,
                        'pitch': pitch_name,
                        'is_rest': elem.isRest
                    })
                    break

        if len(note_positions) == len(spanned_elements_original):
            spanner_info.append({
                'type': sp.__class__,
                'positions': note_positions
            })

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

    # 最初の小節から楽器、音部記号、調号、拍子記号を取得してコピー
    first_original_measure = measures[0]

    # 楽器をコピー
    for inst in part.getElementsByClass('Instrument'):
        new_part.insert(0, inst)

    # 音部記号をコピー (Clef)
    clefs = first_original_measure.getElementsByClass('Clef')
    if clefs:
        first_clef = clefs.first()
        if first_clef:
            new_part.insert(0, first_clef)

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

        # SKIP_MEASURE_CONTENT モードでは反転前にコピーを作成
        if error_handling == ErrorHandling.SKIP_MEASURE_CONTENT:
            measure_to_process = copy.deepcopy(measure)
        else:
            measure_to_process = measure

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

                # タイは反転する（小節順序が変わるため）
                for element in fallback.notesAndRests:
                    reverse_ties(element)
                    if hasattr(element, 'notes'):
                        for note in element.notes:
                            reverse_ties(note)
                new_part.append(fallback)
                continue

        # タイを反転
        for element in processed_measure.notesAndRests:
            reverse_ties(element)
            # 和音内の音符のタイも処理
            if hasattr(element, 'notes'):
                for note in element.notes:
                    reverse_ties(note)

            # 小節番号を再割り当て
        processed_measure.number = i + 1
        new_part.append(processed_measure)

    # 保存したSpanner情報を使って、新しいパートでSpannerを再構築
    for sp_info in spanner_info:
        new_spanned_elements = []

        for pos in sp_info['positions']:
            # 反転後の小節番号を計算
            reversed_measure_num = len(measures) - pos['measure_num'] + 1

            # 新しいパートから対応する小節を取得
            for new_measure in new_part.getElementsByClass(stream.Measure):
                if new_measure.number == reversed_measure_num:
                    # 小節内で反転後のオフセットを計算
                    measure_duration = new_measure.duration.quarterLength
                    reversed_offset = measure_duration - pos['offset'] - pos['duration']
                    reversed_offset = max(0, reversed_offset)

                    # 反転後のオフセットとピッチが一致する音符を探す
                    for new_elem in new_measure.notesAndRests:
                        offset_match = abs(new_elem.offset - reversed_offset) < 0.01
                        if offset_match:
                            # ピッチまたは休符かをチェック
                            if pos['is_rest'] and new_elem.isRest:
                                new_spanned_elements.append(new_elem)
                                break
                            elif pos['pitch'] and hasattr(new_elem, 'pitch'):
                                if str(new_elem.pitch) == pos['pitch']:
                                    new_spanned_elements.append(new_elem)
                                    break
                    break

        # すべての音符が見つかった場合のみSpannerを作成
        if len(new_spanned_elements) == len(sp_info['positions']) and len(new_spanned_elements) >= 2:
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
            new_spanner = sp_info['type'](new_spanned_elements_sorted)
            new_part.insert(0, new_spanner)

    # ダイナミクスのウェッジを反転
    reverse_dynamics_wedges(new_part)

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
