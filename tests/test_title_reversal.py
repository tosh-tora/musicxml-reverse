#!/usr/bin/env python3
"""
タイトルへの「反転」付与のテスト

反転後のスコアであることが分かるように、work-title / movement-title と
タイトル用credit要素（credit-type=title）のテキストに " 反転" を追記する。
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reverse_score import process_file, ErrorHandling


def _write_score(path: Path, title: str, part_name: str = "P1",
                  composer: str = "Test Composer") -> None:
    """最小構成のMusicXMLを書き出す(1小節・1音符・タイトル/composer/part-name credit付き)"""
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        f'  <work><work-title>{title}</work-title></work>\n'
        '  <credit page="1"><credit-type>title</credit-type>'
        f'<credit-words>{title}</credit-words></credit>\n'
        '  <credit page="1"><credit-type>composer</credit-type>'
        f'<credit-words>{composer}</credit-words></credit>\n'
        f'  <credit page="1"><credit-words>{part_name}</credit-words></credit>\n'
        f'  <part-list><score-part id="P1"><part-name>{part_name}</part-name></score-part></part-list>\n'
        '  <part id="P1">\n'
        '    <measure number="1">'
        '<attributes><divisions>1</divisions>'
        '<key><fifths>0</fifths></key>'
        '<time><beats>4</beats><beat-type>4</beat-type></time>'
        '<clef><sign>G</sign><line>2</line></clef></attributes>'
        '<note><pitch><step>C</step><octave>4</octave></pitch>'
        '<duration>4</duration><voice>1</voice><type>quarter</type></note>'
        '</measure>\n'
        '  </part>\n'
        '</score-partwise>\n',
        encoding='utf-8',
    )


def _parse_output(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


class TestTitleSuffix:
    """work-title / movement-title への反転付与"""

    def test_work_title_gets_suffix(self, tmp_path):
        input_file = tmp_path / 'input.xml'
        output_file = tmp_path / 'output.xml'
        _write_score(input_file, 'Pomp and Circumstance March No. 1')

        process_file(input_file, output_file, ErrorHandling.SKIP_PART)

        root = _parse_output(output_file)
        work_title = root.find('.//{*}work/{*}work-title')
        movement_title = root.find('.//{*}movement-title')
        title_text = (work_title.text if work_title is not None else None) \
            or (movement_title.text if movement_title is not None else None)
        assert title_text == 'Pomp and Circumstance March No. 1 反転'

    def test_no_title_does_not_error(self, tmp_path):
        input_file = tmp_path / 'input.xml'
        output_file = tmp_path / 'output.xml'
        input_file.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<score-partwise version="3.1">\n'
            '  <part-list><score-part id="P1"><part-name>P1</part-name></score-part></part-list>\n'
            '  <part id="P1">\n'
            '    <measure number="1">'
            '<attributes><divisions>1</divisions>'
            '<time><beats>4</beats><beat-type>4</beat-type></time></attributes>'
            '<note><pitch><step>C</step><octave>4</octave></pitch>'
            '<duration>4</duration><voice>1</voice><type>quarter</type></note>'
            '</measure>\n'
            '  </part>\n'
            '</score-partwise>\n',
            encoding='utf-8',
        )

        process_file(input_file, output_file, ErrorHandling.SKIP_PART)

        assert output_file.exists()


class TestTitleCreditSuffix:
    """タイトル用credit要素への反転付与"""

    def test_title_credit_gets_suffix(self, tmp_path):
        input_file = tmp_path / 'input.xml'
        output_file = tmp_path / 'output.xml'
        _write_score(input_file, 'Pomp and Circumstance March No. 1')

        process_file(input_file, output_file, ErrorHandling.SKIP_PART)

        root = _parse_output(output_file)
        credits = {}
        for credit in root.findall('.//{*}credit'):
            ct = credit.find('{*}credit-type')
            cw = credit.find('{*}credit-words')
            key = ct.text.strip() if ct is not None and ct.text else None
            credits[key] = cw.text if cw is not None else None

        assert credits['title'] == 'Pomp and Circumstance March No. 1 反転'

    def test_other_credits_unaffected(self, tmp_path):
        input_file = tmp_path / 'input.xml'
        output_file = tmp_path / 'output.xml'
        _write_score(input_file, 'Pomp and Circumstance March No. 1',
                     part_name='Viola', composer='Edward Elgar')

        process_file(input_file, output_file, ErrorHandling.SKIP_PART)

        root = _parse_output(output_file)
        credits = {}
        part_name_credit_words = None
        for credit in root.findall('.//{*}credit'):
            ct = credit.find('{*}credit-type')
            cw = credit.find('{*}credit-words')
            if ct is not None and ct.text:
                credits[ct.text.strip()] = cw.text if cw is not None else None
            elif cw is not None:
                part_name_credit_words = cw.text

        # composer は変更されない
        assert credits.get('composer') == 'Edward Elgar'
        # パート名credit は既存の "(retrograde)" ラベルが付く（反転ラベルとは無関係）
        assert part_name_credit_words == 'Viola\n(retrograde)'

    def test_idempotent_when_title_already_suffixed(self, tmp_path):
        """既に「反転」で終わるタイトルには二重付与しない"""
        input_file = tmp_path / 'input.xml'
        output_file = tmp_path / 'output.xml'
        _write_score(input_file, 'Already Reversed 反転')

        process_file(input_file, output_file, ErrorHandling.SKIP_PART)

        root = _parse_output(output_file)
        work_title = root.find('.//{*}work/{*}work-title')
        movement_title = root.find('.//{*}movement-title')
        title_text = (work_title.text if work_title is not None else None) \
            or (movement_title.text if movement_title is not None else None)
        assert title_text == 'Already Reversed 反転'
