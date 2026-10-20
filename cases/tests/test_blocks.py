from django.test import SimpleTestCase

from cases.blocks import BlockKind, block_for_span, build_blocks


def _paragraph(text, start, kind="paragraph"):
    return {
        "type": kind,
        "level": None,
        "text": text,
        "start": start,
        "end": start + len(text),
    }


def _cell(row, col, text, start, continuation=False):
    return {
        "row": row,
        "col": col,
        "text": text,
        "start": start,
        "end": start if continuation else start + len(text),
        "isMergedContinuation": continuation,
    }


class StructuredBlockTests(SimpleTestCase):
    """DOCX documents, where the element list is available."""

    def test_paragraph_and_heading_each_become_one_block(self):
        text = "Case Notes\nJoe attended on Tuesday."
        structure = [
            _paragraph("Case Notes", 0, kind="heading"),
            _paragraph("Joe attended on Tuesday.", 11),
        ]

        blocks = build_blocks(text, structure, [])

        self.assertEqual(
            [(b.start, b.end, b.kind) for b in blocks],
            [(0, 10, BlockKind.HEADING), (11, 35, BlockKind.PARAGRAPH)],
        )
        self.assertEqual(text[blocks[0].start : blocks[0].end], "Case Notes")

    def test_table_becomes_one_block_per_row(self):
        """
        A record puts a person in one cell and their details in sibling cells
        of the same row, so the row is the unit that groups them. One block for
        the whole table would merge every person in it into one group.
        """
        structure = [{"type": "table", "table_id": 0, "start": 0, "end": 60}]
        tables = [
            {
                "id": 0,
                "cells": [
                    _cell(0, 0, "Name", 0),
                    _cell(0, 1, "Phone", 5),
                    _cell(1, 0, "BLOGGS, Joe", 11),
                    _cell(1, 1, "07700 900000", 23),
                    _cell(2, 0, "HUGHES, Grace", 36),
                    _cell(2, 1, "07700 900111", 50),
                ],
            }
        ]

        blocks = build_blocks("x" * 62, structure, tables)

        self.assertEqual(
            [(b.start, b.end) for b in blocks], [(0, 10), (11, 35), (36, 62)]
        )
        self.assertTrue(all(b.kind == BlockKind.TABLE_ROW for b in blocks))

    def test_merged_continuation_cells_do_not_widen_a_row(self):
        """
        A continuation cell occupies no text — its start and end are both the
        cursor position — so counting it would drag the row's range leftward.
        """
        structure = [{"type": "table", "table_id": 0, "start": 0, "end": 30}]
        tables = [
            {
                "id": 0,
                "cells": [
                    _cell(1, 0, "BLOGGS, Joe", 11),
                    _cell(1, 1, "", 0, continuation=True),
                    _cell(1, 2, "07700 900000", 23),
                ],
            }
        ]

        blocks = build_blocks("x" * 40, structure, tables)

        self.assertEqual([(b.start, b.end) for b in blocks], [(11, 35)])

    def test_tables_and_paragraphs_interleave_in_document_order(self):
        structure = [
            _paragraph("Officers involved", 0),
            {"type": "table", "table_id": 0, "start": 18, "end": 40},
            _paragraph("End of report", 41),
        ]
        tables = [
            {
                "id": 0,
                "cells": [
                    _cell(0, 0, "HUGHES, R.", 18),
                    _cell(1, 0, "SMITH, J.", 29),
                ],
            }
        ]

        blocks = build_blocks("x" * 60, structure, tables)

        self.assertEqual(
            [(b.start, b.end) for b in blocks],
            [(0, 17), (18, 28), (29, 38), (41, 54)],
        )

    def test_table_with_no_usable_cells_falls_back_to_one_block(self):
        """
        Nothing to split on, so the table becomes a single block. Attribution
        then finds several people in it and resolves nothing, which is the
        right outcome for a table whose layout could not be read.
        """
        structure = [{"type": "table", "table_id": 0, "start": 5, "end": 40}]

        for tables in ([], [{"id": 0, "cells": []}], [{"id": 9, "cells": []}]):
            with self.subTest(tables=tables):
                blocks = build_blocks("x" * 50, structure, tables)
                self.assertEqual(
                    [(b.start, b.end, b.kind) for b in blocks],
                    [(5, 40, BlockKind.TABLE_ROW)],
                )

    def test_elements_without_offsets_are_skipped(self):
        structure = [
            {"type": "paragraph", "text": "no offsets"},
            {"type": "paragraph", "text": "empty", "start": 7, "end": 7},
            _paragraph("real", 20),
        ]

        blocks = build_blocks("x" * 40, structure, [])

        self.assertEqual([(b.start, b.end) for b in blocks], [(20, 24)])

    def test_empty_structure_yields_no_blocks(self):
        self.assertEqual(build_blocks("some text", [], []), [])


class LineBlockTests(SimpleTestCase):
    """
    Pasted text and PDFs, which have no element list.

    This is the path most documents take when a team pastes records in rather
    than uploading files, so it carries real weight — it is not a fallback.
    """

    def test_each_non_blank_line_is_a_block(self):
        text = "BLOGGS, Joe\t07700 900000\nHUGHES, Grace\t07700 900111"

        blocks = build_blocks(text, None, [])

        self.assertEqual(len(blocks), 2)
        self.assertTrue(all(b.kind == BlockKind.LINE for b in blocks))
        self.assertEqual(
            [text[b.start : b.end] for b in blocks],
            ["BLOGGS, Joe\t07700 900000", "HUGHES, Grace\t07700 900111"],
        )

    def test_a_pasted_report_does_not_collapse_into_one_block(self):
        """
        Grouping by blank line would put this whole report in one block, and a
        block holding two people attributes nothing — so the feature would do
        no work at all on the format the team actually pastes.
        """
        text = (
            "Reporting officer: HUGHES, R. #0723222\n"
            "Victim: BLOGGS, Joe\n"
            "Contact: 07700 900000\n"
            "Witness: SMITH, Jane\n"
            "Contact: 07700 900111"
        )

        blocks = build_blocks(text, None, [])

        self.assertEqual(len(blocks), 5)

    def test_blank_and_whitespace_only_lines_are_skipped(self):
        text = "First line\n\n   \nSecond line"

        blocks = build_blocks(text, None, [])

        self.assertEqual(
            [text[b.start : b.end] for b in blocks],
            ["First line", "Second line"],
        )

    def test_surrounding_whitespace_is_not_claimed_by_a_block(self):
        text = "\t  BLOGGS, Joe  \t\n  07700 900000"

        blocks = build_blocks(text, None, [])

        self.assertEqual(
            [text[b.start : b.end] for b in blocks],
            ["BLOGGS, Joe", "07700 900000"],
        )

    def test_crlf_line_endings_do_not_leave_a_stray_return_in_a_block(self):
        text = "BLOGGS, Joe\r\n07700 900000"

        blocks = build_blocks(text, None, [])

        self.assertEqual(
            [text[b.start : b.end] for b in blocks],
            ["BLOGGS, Joe", "07700 900000"],
        )

    def test_empty_text_yields_no_blocks(self):
        for text in ("", "   \n\n  ", None):
            with self.subTest(text=text):
                self.assertEqual(build_blocks(text, None, []), [])


class BlockForSpanTests(SimpleTestCase):
    def setUp(self):
        self.text = "BLOGGS, Joe\n07700 900000"
        self.blocks = build_blocks(self.text, None, [])

    def test_contained_span_finds_its_block(self):
        block = block_for_span(self.blocks, 12, 24)
        self.assertEqual((block.start, block.end), (12, 24))

    def test_span_straddling_two_blocks_belongs_to_neither(self):
        """
        A span crossing a block boundary has no single subject, and guessing
        one would attribute a detail to a person it may not describe.
        """
        self.assertIsNone(block_for_span(self.blocks, 5, 18))

    def test_span_outside_every_block_returns_none(self):
        self.assertIsNone(block_for_span(self.blocks, 90, 95))

    def test_span_exactly_filling_a_block_is_contained(self):
        block = block_for_span(self.blocks, 0, 11)
        self.assertEqual((block.start, block.end), (0, 11))
