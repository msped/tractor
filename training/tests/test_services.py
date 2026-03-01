import tempfile
from unittest.mock import MagicMock, patch

from django.test import TestCase
from lxml import etree

from ..services import (
    _deduplicate_entities,
    _table_has_borders,
    extract_entities_from_text,
    extract_table_with_styling,
)
from .base import NetworkBlockerMixin


class ServicesTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.temp_file.close()
        self.file_path = self.temp_file.name

    def tearDown(self):
        import os

        os.remove(self.file_path)

    @patch("training.services._extract_text_from_pdf")
    @patch("training.extractors.presidio_extractor.extract_operational_with_presidio")
    @patch("training.extractors.presidio_extractor.extract_with_presidio")
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_extract_entities_from_text_success(
        self, mock_gliner_mgr, mock_spancat_mgr, mock_gliner, mock_presidio, mock_presidio_op, mock_pdf
    ):
        """
        Test successful entity extraction with GLiNER + Presidio for a non-DOCX file.
        SpanCat returns None (not yet trained) — graceful degradation.
        """
        mock_gliner_model = MagicMock()
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = mock_gliner_model
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = None

        mock_pdf.return_value = "Hello, I'm John Doe and I live in London."

        mock_gliner.return_value = [
            {"text": "John Doe", "label": "THIRD_PARTY", "start_char": 12, "end_char": 20},
        ]
        mock_presidio.return_value = [
            {"text": "London", "label": "THIRD_PARTY", "start_char": 35, "end_char": 41},
        ]
        mock_presidio_op.return_value = []

        extracted_text, results, tables, structure = extract_entities_from_text(self.file_path)

        self.assertEqual(extracted_text, "Hello, I'm John Doe and I live in London.")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["text"], "John Doe")
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[1]["text"], "London")
        self.assertEqual(results[1]["label"], "THIRD_PARTY")
        self.assertEqual(tables, [])
        self.assertIsNone(structure)

        mock_gliner.assert_called_once_with(mock_gliner_model, "Hello, I'm John Doe and I live in London.")
        mock_presidio.assert_called_once_with("Hello, I'm John Doe and I live in London.")

    @patch("training.services._extract_text_from_pdf")
    @patch("training.extractors.presidio_extractor.extract_operational_with_presidio")
    @patch("training.extractors.presidio_extractor.extract_with_presidio")
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.extractors.spancat_extractor.extract_with_spancat")
    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_extract_entities_with_spancat(
        self, mock_gliner_mgr, mock_spancat_mgr, mock_spancat, mock_gliner, mock_presidio, mock_presidio_op, mock_pdf
    ):
        """
        Test that SpanCat results take priority over GLiNER and Presidio.
        """
        mock_gliner_model = MagicMock()
        mock_spancat_nlp = MagicMock()
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = mock_gliner_model
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = mock_spancat_nlp

        mock_pdf.return_value = "John Doe attended the scene."

        mock_spancat.return_value = [
            {"text": "attended the scene", "label": "OPERATIONAL", "start_char": 9, "end_char": 27},
        ]
        mock_gliner.return_value = [
            {"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8},
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        _, results, _, _ = extract_entities_from_text(self.file_path)

        self.assertEqual(len(results), 2)
        labels = {r["label"] for r in results}
        self.assertIn("OPERATIONAL", labels)
        self.assertIn("THIRD_PARTY", labels)
        mock_spancat.assert_called_once_with(mock_spancat_nlp, "John Doe attended the scene.")

    @patch("training.services._extract_text_from_pdf")
    @patch("training.extractors.presidio_extractor.extract_operational_with_presidio")
    @patch("training.extractors.presidio_extractor.extract_with_presidio")
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_spancat_none_skips_spancat_extractor(
        self, mock_gliner_mgr, mock_spancat_mgr, mock_gliner, mock_presidio, mock_presidio_op, mock_pdf
    ):
        """
        When SpanCat returns None (not trained), extract_with_spancat is not called.
        """
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = MagicMock()
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = None

        mock_pdf.return_value = "Some text here."
        mock_gliner.return_value = []
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        with patch("training.extractors.spancat_extractor.extract_with_spancat") as mock_spancat:
            _, results, _, _ = extract_entities_from_text(self.file_path)
            mock_spancat.assert_not_called()

    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_extract_entities_no_model_found(self, mock_manager, mock_spancat_mgr):
        """
        Test that a ValueError is raised if get_model() returns None.
        """
        mock_manager.get_instance.return_value.get_model.return_value = None

        with self.assertRaisesMessage(ValueError, "No GLiNER model available."):
            extract_entities_from_text(self.file_path)

    @patch("training.services._extract_text_from_pdf")
    @patch("training.extractors.presidio_extractor.extract_operational_with_presidio")
    @patch("training.extractors.presidio_extractor.extract_with_presidio")
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_extract_entities_no_text_in_document(
        self, mock_manager, mock_spancat_mgr, mock_gliner, mock_presidio, mock_presidio_op, mock_pdf
    ):
        """
        Test that a ValueError is raised if the document contains no text.
        """
        mock_manager.get_instance.return_value.get_model.return_value = MagicMock()
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = None
        mock_pdf.return_value = ""

        with self.assertRaisesMessage(ValueError, "No text found in the document."):
            extract_entities_from_text(self.file_path)

    @patch("training.services._extract_text_from_pdf")
    @patch("training.extractors.presidio_extractor.extract_operational_with_presidio")
    @patch("training.extractors.presidio_extractor.extract_with_presidio")
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.services.SpanCatModelManager")
    @patch("training.services.GLiNERModelManager")
    def test_extract_entities_deduplicates_overlapping(
        self, mock_manager, mock_spancat_mgr, mock_gliner, mock_presidio, mock_presidio_op, mock_pdf
    ):
        """
        Test that overlapping GLiNER and Presidio results are deduplicated,
        with GLiNER taking priority.
        """
        mock_manager.get_instance.return_value.get_model.return_value = MagicMock()
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = None
        mock_pdf.return_value = "John Doe lives in London."

        # GLiNER finds "John Doe" at 0-8
        mock_gliner.return_value = [
            {"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8},
        ]
        # Presidio also finds "John" at 0-4 (overlaps with GLiNER result)
        mock_presidio.return_value = [
            {"text": "John", "label": "THIRD_PARTY", "start_char": 0, "end_char": 4},
        ]
        mock_presidio_op.return_value = []

        _, results, _, _ = extract_entities_from_text(self.file_path)

        # Only "John Doe" should remain (overlap removed)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "John Doe")


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


class DeduplicateEntitiesTests(TestCase):
    def test_no_overlap_keeps_all(self):
        primary = [{"text": "ref-123", "label": "OPERATIONAL", "start_char": 0, "end_char": 7}]
        secondary = [{"text": "John", "label": "THIRD_PARTY", "start_char": 10, "end_char": 14}]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 2)

    def test_overlap_removes_secondary_entity(self):
        primary = [{"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8}]
        secondary = [{"text": "John", "label": "THIRD_PARTY", "start_char": 0, "end_char": 4}]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Doe")

    def test_partial_overlap_removes_secondary_entity(self):
        primary = [{"text": "John Doe ref", "label": "OPERATIONAL", "start_char": 0, "end_char": 12}]
        secondary = [{"text": "John Doe", "label": "THIRD_PARTY", "start_char": 0, "end_char": 8}]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "OPERATIONAL")

    def test_empty_inputs(self):
        self.assertEqual(_deduplicate_entities([], []), [])
        primary = [{"text": "a", "label": "OPERATIONAL", "start_char": 0, "end_char": 1}]
        self.assertEqual(len(_deduplicate_entities(primary, [])), 1)
        secondary = [{"text": "b", "label": "THIRD_PARTY", "start_char": 5, "end_char": 6}]
        self.assertEqual(len(_deduplicate_entities([], secondary)), 1)
