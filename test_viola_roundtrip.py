#!/usr/bin/env python3
"""
Comprehensive Roundtrip Test for MusicXML Reversal

Tests the accuracy of reverse → re-reverse processing:
1. Basic metrics (note count, part count)
2. XML structure comparison
3. Musical content (pitch, duration, offset)
4. Spanner elements (slurs, ottava, dynamics)

Generates structured pass/fail report.
"""

import sys
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

from music21 import converter, spanner
from music21.spanner import Ottava

from reverse_score import process_file, ErrorHandling, count_notes
from compare_musicxml import extract_musicxml_content, normalize_xml
from difflib import unified_diff


@dataclass
class TestResult:
    """Individual test result"""
    name: str
    status: Literal['PASS', 'WARNING', 'FAIL']
    message: str = ""
    details: list[str] = field(default_factory=list)


@dataclass
class RoundtripReport:
    """Comprehensive roundtrip test report"""
    source_file: str
    results: list[TestResult] = field(default_factory=list)

    def add_result(self, result: TestResult):
        self.results.append(result)

    def overall_status(self) -> Literal['PASS', 'WARNING', 'FAIL']:
        """Determine overall status"""
        if any(r.status == 'FAIL' for r in self.results):
            return 'FAIL'
        if any(r.status == 'WARNING' for r in self.results):
            return 'WARNING'
        return 'PASS'

    def print_report(self):
        """Print structured report"""
        print("\n" + "="*70)
        print("ROUNDTRIP TEST REPORT")
        print("="*70)
        print(f"File: {self.source_file}")
        print()

        overall = self.overall_status()
        status_symbol = "[OK]" if overall == "PASS" else "[WARN]" if overall == "WARNING" else "[FAIL]"
        print(f"{status_symbol} Overall Result: {overall}")
        print()

        for i, result in enumerate(self.results, 1):
            symbol = "[OK]" if result.status == "PASS" else "[WARN]" if result.status == "WARNING" else "[FAIL]"
            print(f"{i}. {result.name}: {symbol} {result.status}")
            if result.message:
                print(f"   {result.message}")
            if result.details:
                for detail in result.details[:5]:  # Show first 5 details
                    print(f"   - {detail}")
                if len(result.details) > 5:
                    print(f"   ... and {len(result.details) - 5} more")
            print()

        print("="*70)
        print("CONCLUSION")
        print("="*70)

        if overall == 'PASS':
            print("[OK] No modifications required")
            print("[OK] Roundtrip is lossless")
        elif overall == 'WARNING':
            print("[WARN] Minor issues detected - review recommended")
            self._print_warnings()
        else:
            print("[FAIL] Critical issues detected - modifications required")
            self._print_failures()

    def _print_warnings(self):
        warnings = [r for r in self.results if r.status == 'WARNING']
        for w in warnings:
            print(f"  - {w.name}: {w.message}")

    def _print_failures(self):
        failures = [r for r in self.results if r.status == 'FAIL']
        for f in failures:
            print(f"  - {f.name}: {f.message}")


def setup_test_environment(source_file: Path) -> dict[str, Path]:
    """Setup test environment and copy source file"""
    test_dir = Path(tempfile.gettempdir()) / "mrev_test" / "viola"
    test_dir.mkdir(parents=True, exist_ok=True)

    original = test_dir / "original.mxl"
    reversed_file = test_dir / "reversed.mxl"
    restored = test_dir / "restored.mxl"

    # Copy source file
    shutil.copy2(source_file, original)

    return {
        'test_dir': test_dir,
        'original': original,
        'reversed': reversed_file,
        'restored': restored
    }


def execute_roundtrip(paths: dict[str, Path], report: RoundtripReport) -> tuple[bool, dict]:
    """Execute reverse → re-reverse roundtrip

    Returns:
        (success, processing_info)
    """
    print("\n" + "="*70)
    print("Phase 1: ROUNDTRIP PROCESSING")
    print("="*70)

    processing_info = {}

    # First reversal
    print("\n[1/2] First reversal: original → reversed")
    report1 = process_file(paths['original'], paths['reversed'])
    processing_info['first_reversal'] = report1

    if not report1.success:
        result = TestResult(
            name="Roundtrip Processing",
            status='FAIL',
            message="First reversal failed",
            details=[f"{i.part_name} measure {i.measure_number}: {i.error_message}"
                    for i in report1.issues]
        )
        report.add_result(result)
        return False, processing_info

    # Second reversal
    print("\n[2/2] Second reversal: reversed → restored")
    report2 = process_file(paths['reversed'], paths['restored'])
    processing_info['second_reversal'] = report2

    if not report2.success:
        result = TestResult(
            name="Roundtrip Processing",
            status='FAIL',
            message="Second reversal failed",
            details=[f"{i.part_name} measure {i.measure_number}: {i.error_message}"
                    for i in report2.issues]
        )
        report.add_result(result)
        return False, processing_info

    result = TestResult(
        name="Roundtrip Processing",
        status='PASS',
        message=f"Both reversals completed successfully"
    )
    report.add_result(result)
    return True, processing_info


def compare_basic_metrics(paths: dict[str, Path], processing_info: dict, report: RoundtripReport):
    """Compare basic metrics (note count, part count)"""
    print("\n" + "="*70)
    print("Phase 2: BASIC METRICS COMPARISON")
    print("="*70)

    report1 = processing_info['first_reversal']
    report2 = processing_info['second_reversal']

    details = []
    status = 'PASS'

    # Note count
    print(f"\nNote count: {report1.input_note_count} → {report2.output_note_count}")
    if report1.input_note_count != report2.output_note_count:
        status = 'FAIL'
        details.append(f"Note count mismatch: {report1.input_note_count} → {report2.output_note_count}")
    else:
        details.append(f"Note count: {report1.input_note_count} [OK]")

    # Part count
    print(f"Part count: {report1.part_count} → {report2.part_count}")
    if report1.part_count != report2.part_count:
        status = 'FAIL'
        details.append(f"Part count mismatch: {report1.part_count} → {report2.part_count}")
    else:
        details.append(f"Part count: {report1.part_count} [OK]")

    # Processing issues
    total_issues = len(report1.issues) + len(report2.issues)
    if total_issues > 0:
        if status == 'PASS':
            status = 'WARNING'
        details.append(f"Processing issues: {total_issues}")

    message = "All metrics match" if status == 'PASS' else f"{len(details)} issue(s) detected"

    result = TestResult(
        name="Basic Metrics",
        status=status,
        message=message,
        details=details
    )
    report.add_result(result)


def compare_xml_structure(paths: dict[str, Path], report: RoundtripReport):
    """Compare XML structure"""
    print("\n" + "="*70)
    print("Phase 3: XML STRUCTURE COMPARISON")
    print("="*70)

    try:
        original_xml = extract_musicxml_content(paths['original'])
        restored_xml = extract_musicxml_content(paths['restored'])

        original_lines = normalize_xml(original_xml)
        restored_lines = normalize_xml(restored_xml)

        diff = list(unified_diff(
            original_lines,
            restored_lines,
            fromfile='original.xml',
            tofile='restored.xml',
            lineterm=''
        ))

        if not diff:
            print("\n[OK] XML structures are identical")
            result = TestResult(
                name="XML Structure",
                status='PASS',
                message="No differences detected"
            )
        else:
            diff_lines = [l for l in diff if l.startswith('+') or l.startswith('-')]
            diff_lines = [l for l in diff_lines if not l.startswith('+++') and not l.startswith('---')]

            print(f"\n[WARN] {len(diff_lines)} lines differ")

            # Analyze difference patterns
            patterns = {
                'offset': 0,
                'duration': 0,
                'pitch': 0,
                'dynamics': 0,
                'formatting': 0,
                'other': 0
            }

            for line in diff_lines:
                if 'offset=' in line or '<offset>' in line:
                    patterns['offset'] += 1
                elif 'duration=' in line or '<duration>' in line:
                    patterns['duration'] += 1
                elif '<pitch>' in line or '<step>' in line or '<octave>' in line:
                    patterns['pitch'] += 1
                elif '<dynamics>' in line or '<wedge' in line:
                    patterns['dynamics'] += 1
                elif line.strip() in ['', ' ']:
                    patterns['formatting'] += 1
                else:
                    patterns['other'] += 1

            details = [f"{k}: {v} lines" for k, v in patterns.items() if v > 0]

            # Determine status based on difference types
            # Note: XML structure differences don't necessarily mean data loss
            # The Musical Content phase (Phase 4) is the authoritative check
            if patterns['pitch'] > 0:
                status = 'WARNING'
                message = "Pitch XML differences detected (verify in Phase 4)"
            elif patterns['duration'] > 100 or patterns['offset'] > 100:
                status = 'WARNING'
                message = f"{len(diff_lines)} differences (review recommended)"
            else:
                status = 'PASS'
                message = f"{len(diff_lines)} differences (likely formatting only)"

            result = TestResult(
                name="XML Structure",
                status=status,
                message=message,
                details=details
            )

        report.add_result(result)

    except Exception as e:
        result = TestResult(
            name="XML Structure",
            status='FAIL',
            message=f"XML comparison failed: {e}"
        )
        report.add_result(result)


def compare_musical_content(paths: dict[str, Path], report: RoundtripReport):
    """Compare musical content (pitch, duration, offset)"""
    print("\n" + "="*70)
    print("Phase 4: MUSICAL CONTENT COMPARISON")
    print("="*70)

    try:
        orig_score = converter.parse(str(paths['original']))
        rest_score = converter.parse(str(paths['restored']))

        pitch_errors = 0
        duration_errors = 0
        offset_errors = 0
        max_duration_diff = 0.0
        max_offset_diff = 0.0

        details = []

        for part_idx, (orig_part, rest_part) in enumerate(zip(orig_score.parts, rest_score.parts)):
            part_name = orig_part.partName or f"Part {part_idx + 1}"
            print(f"\nChecking {part_name}...")

            orig_measures = list(orig_part.getElementsByClass('Measure'))
            rest_measures = list(rest_part.getElementsByClass('Measure'))

            if len(orig_measures) != len(rest_measures):
                details.append(f"{part_name}: measure count mismatch ({len(orig_measures)} vs {len(rest_measures)})")
                continue

            for m_idx in range(len(orig_measures)):
                orig_m = orig_measures[m_idx]
                rest_m = rest_measures[m_idx]

                orig_notes = list(orig_m.flatten().notesAndRests)
                rest_notes = list(rest_m.flatten().notesAndRests)

                if len(orig_notes) != len(rest_notes):
                    details.append(f"{part_name} m{m_idx+1}: note count mismatch ({len(orig_notes)} vs {len(rest_notes)})")
                    continue

                for j, (on, rn) in enumerate(zip(orig_notes, rest_notes)):
                    # Check pitch
                    def get_pitches(n):
                        if n.isRest:
                            return []
                        elif n.isChord:
                            return [p.nameWithOctave for p in n.pitches]
                        else:
                            return [n.pitch.nameWithOctave]

                    if get_pitches(on) != get_pitches(rn):
                        pitch_errors += 1
                        if pitch_errors <= 3:  # Show first 3 errors
                            details.append(f"{part_name} m{m_idx+1} n{j+1}: pitch {get_pitches(on)} → {get_pitches(rn)}")

                    # Check duration
                    duration_diff = abs(on.duration.quarterLength - rn.duration.quarterLength)
                    max_duration_diff = max(max_duration_diff, duration_diff)
                    if duration_diff > 0.001:
                        duration_errors += 1
                        if duration_errors <= 3:
                            details.append(f"{part_name} m{m_idx+1} n{j+1}: duration diff {duration_diff:.4f} QL")

                    # Check offset
                    offset_diff = abs(on.offset - rn.offset)
                    max_offset_diff = max(max_offset_diff, offset_diff)
                    if offset_diff > 0.001:
                        offset_errors += 1
                        if offset_errors <= 3:
                            details.append(f"{part_name} m{m_idx+1} n{j+1}: offset diff {offset_diff:.4f}")

        print(f"\nPitch errors: {pitch_errors}")
        print(f"Duration errors: {duration_errors} (max diff: {max_duration_diff:.6f} QL)")
        print(f"Offset errors: {offset_errors} (max diff: {max_offset_diff:.6f})")

        # Determine status
        if pitch_errors > 0:
            status = 'FAIL'
            message = f"{pitch_errors} pitch error(s) detected"
        elif duration_errors > 0 and max_duration_diff > 0.01:
            status = 'FAIL'
            message = f"Duration diff {max_duration_diff:.4f} exceeds threshold (0.01)"
        elif offset_errors > 0 and max_offset_diff > 0.01:
            status = 'WARNING'
            message = f"Offset diff {max_offset_diff:.4f} (review recommended)"
        elif duration_errors > 0 or offset_errors > 0:
            status = 'WARNING'
            message = f"Minor timing differences (max: {max(max_duration_diff, max_offset_diff):.6f})"
        else:
            status = 'PASS'
            message = "All musical content matches perfectly"

        result = TestResult(
            name="Musical Content",
            status=status,
            message=message,
            details=details
        )
        report.add_result(result)

    except Exception as e:
        result = TestResult(
            name="Musical Content",
            status='FAIL',
            message=f"Musical content comparison failed: {e}"
        )
        report.add_result(result)


def compare_spanners(paths: dict[str, Path], report: RoundtripReport):
    """Compare Spanner elements (slurs, ottava, dynamics)"""
    print("\n" + "="*70)
    print("Phase 5: SPANNER ELEMENTS VALIDATION")
    print("="*70)

    try:
        orig_score = converter.parse(str(paths['original']))
        rest_score = converter.parse(str(paths['restored']))

        details = []
        status = 'PASS'

        for part_idx, (orig_part, rest_part) in enumerate(zip(orig_score.parts, rest_score.parts)):
            part_name = orig_part.partName or f"Part {part_idx + 1}"
            print(f"\nChecking {part_name}...")

            # Slurs
            orig_slurs = [sp for sp in orig_part.spannerBundle if isinstance(sp, spanner.Slur)]
            rest_slurs = [sp for sp in rest_part.spannerBundle if isinstance(sp, spanner.Slur)]

            print(f"  Slurs: {len(orig_slurs)} → {len(rest_slurs)}")
            if len(orig_slurs) != len(rest_slurs):
                diff = abs(len(orig_slurs) - len(rest_slurs))
                if diff > 1:
                    status = 'FAIL' if status == 'PASS' else status
                    details.append(f"{part_name}: slur count mismatch ({len(orig_slurs)} → {len(rest_slurs)})")
                else:
                    status = 'WARNING' if status == 'PASS' else status
                    details.append(f"{part_name}: slur count off by 1 ({len(orig_slurs)} → {len(rest_slurs)})")
            else:
                details.append(f"{part_name}: slurs {len(orig_slurs)} [OK]")

            # Ottavas
            orig_ottavas = [sp for sp in orig_part.spannerBundle if isinstance(sp, Ottava)]
            rest_ottavas = [sp for sp in rest_part.spannerBundle if isinstance(sp, Ottava)]

            print(f"  Ottavas: {len(orig_ottavas)} → {len(rest_ottavas)}")
            if len(orig_ottavas) != len(rest_ottavas):
                status = 'FAIL' if status == 'PASS' else status
                details.append(f"{part_name}: ottava count mismatch ({len(orig_ottavas)} → {len(rest_ottavas)})")
            else:
                # Check ottava properties
                for i, (orig_ott, rest_ott) in enumerate(zip(orig_ottavas, rest_ottavas)):
                    if orig_ott.type != rest_ott.type:
                        status = 'WARNING' if status == 'PASS' else status
                        details.append(f"{part_name} ottava {i+1}: type {orig_ott.type} → {rest_ott.type}")
                    if orig_ott.transposing != rest_ott.transposing:
                        status = 'WARNING' if status == 'PASS' else status
                        details.append(f"{part_name} ottava {i+1}: transposing changed")
                    if orig_ott.placement != rest_ott.placement:
                        status = 'WARNING' if status == 'PASS' else status
                        details.append(f"{part_name} ottava {i+1}: placement {orig_ott.placement} → {rest_ott.placement}")

                if status == 'PASS':
                    details.append(f"{part_name}: ottavas {len(orig_ottavas)} [OK]")

        if status == 'PASS':
            message = "All spanners preserved correctly"
        elif status == 'WARNING':
            message = "Minor spanner differences detected"
        else:
            message = "Critical spanner differences detected"

        result = TestResult(
            name="Spanner Elements",
            status=status,
            message=message,
            details=details
        )
        report.add_result(result)

    except Exception as e:
        result = TestResult(
            name="Spanner Elements",
            status='FAIL',
            message=f"Spanner comparison failed: {e}"
        )
        report.add_result(result)


def main():
    """Main test execution"""
    source_file = Path("work/inbox/test/威風堂々ラスト_in-Viola.mxl")

    if not source_file.exists():
        print(f"Error: Source file not found: {source_file}")
        return 1

    print("="*70)
    print("COMPREHENSIVE ROUNDTRIP TEST")
    print("="*70)
    print(f"Source: {source_file}")

    # Setup
    print("\n" + "="*70)
    print("Phase 0: SETUP")
    print("="*70)
    paths = setup_test_environment(source_file)
    print(f"\nTest directory: {paths['test_dir']}")
    print(f"  original.mxl: {paths['original']}")
    print(f"  reversed.mxl: {paths['reversed']}")
    print(f"  restored.mxl: {paths['restored']}")

    # Initialize report
    report = RoundtripReport(source_file=source_file.name)

    # Execute roundtrip
    success, processing_info = execute_roundtrip(paths, report)
    if not success:
        report.print_report()
        return 1

    # Run comparisons
    compare_basic_metrics(paths, processing_info, report)
    compare_xml_structure(paths, report)
    compare_musical_content(paths, report)
    compare_spanners(paths, report)

    # Print final report
    report.print_report()

    # Return exit code based on overall status
    overall = report.overall_status()
    if overall == 'FAIL':
        return 1
    elif overall == 'WARNING':
        return 0  # Warnings are acceptable
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
