import tempfile
from unittest.mock import MagicMock, patch

from django.test import TestCase
from lxml import etree

from ..services import (
    _deduplicate_entities,
    _extract_ner_entities,
    _table_has_borders,
    extract_entities_from_text,
    extract_table_with_styling,
)
from .base import NetworkBlockerMixin


class MockSpan:
    """A simple mock for a spaCy Span object."""

    def __init__(self, text, label_, start_char, end_char):
        self.text = text
        self.label_ = label_
        self.start_char = start_char
        self.end_char = end_char


class MockEnt:
    """A simple mock for a spaCy Entity object (from doc.ents)."""

    def __init__(self, text, label_, start_char, end_char):
        self.text = text
        self.label_ = label_
        self.start_char = start_char
        self.end_char = end_char


class ServicesTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        # Create a temporary file to act as the document path
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.file_path = self.temp_file.name

    def tearDown(self):
        import os

        os.remove(self.file_path)

    @patch("training.services.spaCyLayout")
    @patch("training.services.SpacyModelManager")
    def test_extract_entities_from_text_success(self, mock_model_manager, mock_spacy_layout):
        """
        Test successful entity extraction with hybrid NER + SpanCat.
        SpanCat returns OPERATIONAL spans; base NER returns PERSON/GPE mapped to THIRD_PARTY.
        """
        # Mock the custom SpanCat model
        mock_nlp = MagicMock()
        mock_spancat_doc = MagicMock()
        mock_spancat_doc.spans = {"sc": [MockSpan("ref-12345", "OPERATIONAL", 0, 9)]}
        mock_nlp.return_value = mock_spancat_doc

        # Mock the base NER model
        mock_base_nlp = MagicMock()
        mock_base_doc = MagicMock()
        mock_base_doc.ents = [
            MockEnt("John Doe", "PERSON", 12, 20),
            MockEnt("London", "GPE", 35, 41),
        ]
        mock_base_nlp.return_value = mock_base_doc

        mock_manager_instance = mock_model_manager.get_instance.return_value
        mock_manager_instance.get_model.return_value = mock_nlp
        mock_manager_instance.get_base_model.return_value = mock_base_nlp

        mock_layout_instance = MagicMock()
        mock_layout_doc = MagicMock()
        mock_layout_doc.text = "Hello, I'm John Doe and I live in London."
        mock_layout_instance.return_value = mock_layout_doc
        mock_spacy_layout.return_value = mock_layout_instance

        extracted_text, results, tables, structure = extract_entities_from_text(self.file_path)

        self.assertEqual(extracted_text, "Hello, I'm John Doe and I live in London.")
        # 1 SpanCat + 2 NER entities = 3 total
        self.assertEqual(len(results), 3)
        # SpanCat result comes first
        self.assertEqual(results[0]["text"], "ref-12345")
        self.assertEqual(results[0]["label"], "OPERATIONAL")
        # NER results mapped to THIRD_PARTY
        self.assertEqual(results[1]["text"], "John Doe")
        self.assertEqual(results[1]["label"], "THIRD_PARTY")
        self.assertEqual(results[2]["text"], "London")
        self.assertEqual(results[2]["label"], "THIRD_PARTY")
        self.assertEqual(tables, [])
        self.assertIsNone(structure)

    @patch("training.services.SpacyModelManager")
    def test_extract_entities_no_model_found(self, mock_model_manager):
        """
        Test that a ValueError is raised if no active model is found.
        """
        mock_model_manager.get_instance.return_value.get_model.return_value = None

        with self.assertRaisesMessage(ValueError, "No active spaCy model found."):
            extract_entities_from_text(self.file_path)

    @patch("training.services.spaCyLayout")
    @patch("training.services.SpacyModelManager")
    def test_extract_entities_no_text_in_document(self, mock_model_manager, mock_spacy_layout):
        """
        Test that a ValueError is raised if the document contains no text.
        """
        mock_nlp = MagicMock()
        mock_manager_instance = mock_model_manager.get_instance.return_value
        mock_manager_instance.get_model.return_value = mock_nlp

        mock_layout_instance = MagicMock()
        mock_layout_doc = MagicMock()
        mock_layout_doc.text = ""
        mock_layout_instance.return_value = mock_layout_doc
        mock_spacy_layout.return_value = mock_layout_instance

        with self.assertRaisesMessage(ValueError, "No text found in the document."):
            extract_entities_from_text(self.file_path)

    @patch("training.services.spaCyLayout")
    @patch("training.services.SpacyModelManager")
    def test_extract_entities_includes_tables(self, mock_model_manager, mock_spacy_layout):
        """
        Test that tables are extracted separately with HTML and text representations
        via the display_table callback.
        """
        mock_nlp = MagicMock()
        mock_spancat_doc = MagicMock()
        mock_spancat_doc.spans = {"sc": []}
        mock_nlp.return_value = mock_spancat_doc

        # Mock the base NER model (returns no entities for this test)
        mock_base_nlp = MagicMock()
        mock_base_doc = MagicMock()
        mock_base_doc.ents = []
        mock_base_nlp.return_value = mock_base_doc

        mock_manager_instance = mock_model_manager.get_instance.return_value
        mock_manager_instance.get_model.return_value = mock_nlp
        mock_manager_instance.get_base_model.return_value = mock_base_nlp

        # Mock spaCyLayout to capture and invoke the display_table callback
        def fake_spacy_layout(nlp, display_table=None):
            mock_layout_instance = MagicMock()

            def fake_call(path):
                mock_df = MagicMock()
                mock_df.to_html.return_value = (
                    "<table><tr><th>Name</th><th>Age</th></tr><tr><td>John</td><td>30</td></tr></table>"
                )
                mock_df.to_csv.return_value = "Name\tAge\nJohn\t30\n"

                # Simulate what spaCyLayout does: call display_table for each table
                table_placeholder = display_table(mock_df) if display_table else "TABLE"

                mock_doc = MagicMock()
                mock_doc.text = f"Document with a table:\n\n{table_placeholder}\n\nEnd of document."
                return mock_doc

            mock_layout_instance.side_effect = fake_call
            return mock_layout_instance

        mock_spacy_layout.side_effect = fake_spacy_layout

        extracted_text, results, tables, structure = extract_entities_from_text(self.file_path)

        # Tables should be extracted separately with position info
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["id"], 0)
        self.assertIn("<table>", tables[0]["html"])
        self.assertIn("Name\tAge", tables[0]["text"])
        self.assertIn("ner_start", tables[0])
        self.assertIn("ner_end", tables[0])

        # The NER text should have table text content (not HTML or placeholder)
        self.assertIn("Name\tAge", extracted_text)
        self.assertIn("Document with a table:", extracted_text)
        self.assertNotIn("{{TABLE:", extracted_text)

        # Verify ner_start/ner_end positions are correct
        table = tables[0]
        table_text_in_doc = extracted_text[table["ner_start"] : table["ner_end"]]
        self.assertEqual(table_text_in_doc, table["text"])

        # Structure is None for non-DOCX files
        self.assertIsNone(structure)


def _make_tbl_xml(border_values=None, include_tbl_pr=True, include_tbl_borders=True):
    """
    Build a minimal w:tbl lxml element for testing _table_has_borders.
    border_values: dict mapping border names to w:val values, e.g.
        {"top": "single", "bottom": "none"}
    """
    nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tbl = etree.Element(f"{{{nsmap['w']}}}tbl", nsmap=nsmap)

    if include_tbl_pr:
        tbl_pr = etree.SubElement(tbl, f"{{{nsmap['w']}}}tblPr")
        if include_tbl_borders and border_values is not None:
            tbl_borders = etree.SubElement(tbl_pr, f"{{{nsmap['w']}}}tblBorders")
            for name, val in border_values.items():
                border_el = etree.SubElement(tbl_borders, f"{{{nsmap['w']}}}{name}")
                border_el.set(f"{{{nsmap['w']}}}val", val)

    return tbl


class TableHasBordersTests(TestCase):
    def _make_mock_table(self, tbl_xml):
        mock_table = MagicMock()
        mock_table._tbl = tbl_xml
        return mock_table

    def test_single_borders_returns_true(self):
        tbl = _make_tbl_xml({"top": "single", "bottom": "single", "left": "single", "right": "single"})
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_double_borders_returns_true(self):
        tbl = _make_tbl_xml({"top": "double"})
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_all_none_borders_returns_false(self):
        tbl = _make_tbl_xml(
            {"top": "none", "bottom": "none", "left": "none", "right": "none", "insideH": "none", "insideV": "none"}
        )
        self.assertFalse(_table_has_borders(self._make_mock_table(tbl)))

    def test_all_nil_borders_returns_false(self):
        tbl = _make_tbl_xml(
            {"top": "nil", "bottom": "nil", "left": "nil", "right": "nil", "insideH": "nil", "insideV": "nil"}
        )
        self.assertFalse(_table_has_borders(self._make_mock_table(tbl)))

    def test_missing_tbl_borders_returns_true(self):
        tbl = _make_tbl_xml(include_tbl_borders=False)
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_missing_tbl_pr_returns_true(self):
        tbl = _make_tbl_xml(include_tbl_pr=False)
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_mixed_borders_returns_true(self):
        tbl = _make_tbl_xml({"top": "single", "bottom": "none", "left": "nil", "right": "none"})
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))


class ExtractTableWithStylingBorderTests(TestCase):
    def _make_mock_table(self, has_borders):
        """Create a minimal mock table with one cell."""
        mock_table = MagicMock()
        mock_cell = MagicMock()
        mock_cell.text = "test"

        # Mock cell XML properties
        mock_tc_pr = MagicMock()
        mock_tc_pr.find.return_value = None
        mock_cell._tc.get_or_add_tcPr.return_value = mock_tc_pr

        # Mock paragraph/run for cell content
        mock_run = MagicMock()
        mock_run.text = "test"
        mock_run.bold = False
        mock_run.italic = False
        mock_run.font.color = None

        mock_para = MagicMock()
        mock_para.runs = [mock_run]
        mock_cell.paragraphs = [mock_para]

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table.rows = [mock_row]

        return mock_table

    def test_has_borders_true_includes_border_in_style(self):
        table = self._make_mock_table(has_borders=True)
        html, cells = extract_table_with_styling(table, 0, has_borders=True)
        self.assertIn("border: 1px solid #000", cells[0]["style"])
        self.assertIn("border: 1px solid #000", html)

    def test_has_borders_false_excludes_border_from_style(self):
        table = self._make_mock_table(has_borders=False)
        html, cells = extract_table_with_styling(table, 0, has_borders=False)
        self.assertNotIn("border", cells[0]["style"])
        # The <td> style should not contain border (border-collapse on the <table> is fine)
        self.assertNotIn("border: 1px solid #000", html)


class ExtractNerEntitiesTests(TestCase):
    def test_extracts_matching_labels(self):
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_doc.ents = [
            MockEnt("John", "PERSON", 0, 4),
            MockEnt("London", "GPE", 10, 16),
            MockEnt("$500", "MONEY", 20, 24),  # Not in NER_LABELS_TO_THIRD_PARTY
        ]
        mock_nlp.return_value = mock_doc

        results = _extract_ner_entities(mock_nlp, "John lives London earns $500")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["text"], "John")
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[1]["text"], "London")
        self.assertEqual(results[1]["label"], "THIRD_PARTY")

    def test_returns_empty_for_no_matching_labels(self):
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_doc.ents = [MockEnt("$500", "MONEY", 0, 4)]
        mock_nlp.return_value = mock_doc

        results = _extract_ner_entities(mock_nlp, "$500")
        self.assertEqual(results, [])


class DeduplicateEntitiesTests(TestCase):
    def test_no_overlap_keeps_all(self):
        spancat = [{"text": "ref-123", "label": "OPERATIONAL", "start_char": 0, "end_char": 7}]
        ner = [{"text": "John", "label": "THIRD_PARTY", "start_char": 10, "end_char": 14}]
        result = _deduplicate_entities(spancat, ner)
        self.assertEqual(len(result), 2)

    def test_overlap_removes_ner_entity(self):
        spancat = [{"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8}]
        ner = [{"text": "John", "label": "THIRD_PARTY", "start_char": 0, "end_char": 4}]
        result = _deduplicate_entities(spancat, ner)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Doe")

    def test_partial_overlap_removes_ner_entity(self):
        spancat = [{"text": "John Doe ref", "label": "OPERATIONAL", "start_char": 0, "end_char": 12}]
        ner = [{"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8}]
        result = _deduplicate_entities(spancat, ner)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "OPERATIONAL")

    def test_empty_inputs(self):
        self.assertEqual(_deduplicate_entities([], []), [])
        spancat = [{"text": "a", "label": "OPERATIONAL", "start_char": 0, "end_char": 1}]
        self.assertEqual(len(_deduplicate_entities(spancat, [])), 1)
        ner = [{"text": "b", "label": "THIRD_PARTY", "start_char": 5, "end_char": 6}]
        self.assertEqual(len(_deduplicate_entities([], ner)), 1)
