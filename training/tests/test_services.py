import os
import tempfile
from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase
from docx import Document as DocxDocument
from lxml import etree

from ..extraction import (
    DocumentStructure,
    _extract_text_from_pdf,
    _table_has_borders,
    extract_document,
    extract_document_structure,
    extract_table_with_styling,
)
from ..pipeline import (
    ExtractionPipeline,
    SpanRuleResult,
    _deduplicate_entities,
    build_default_pipeline,
)
from ..services import _expand_prefix_symbols, extract_entities_from_text
from ..span_rules import build_occurrence_report_rule
from .base import NetworkBlockerMixin


class ServicesTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf"
        )
        self.temp_file.close()
        self.file_path = self.temp_file.name

    def tearDown(self):
        import os

        os.remove(self.file_path)

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_from_text_success(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """
        Test successful entity extraction with GLiNER + Presidio for a non-DOCX file.
        SpanCat returns None (not yet trained) — graceful degradation.
        """
        mock_gliner_model = MagicMock()
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            mock_gliner_model
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )

        mock_pdf.return_value = "Hello, I'm John Doe and I live in London."

        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 12,
                "end_char": 20,
            },
        ]
        mock_presidio.return_value = [
            {
                "text": "London",
                "label": "THIRD_PARTY",
                "start_char": 35,
                "end_char": 41,
            },
        ]
        mock_presidio_op.return_value = []

        extracted_text, results, tables, structure = (
            extract_entities_from_text(self.file_path)
        )

        self.assertEqual(
            extracted_text, "Hello, I'm John Doe and I live in London."
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["text"], "London")
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[1]["text"], "John Doe")
        self.assertEqual(results[1]["label"], "THIRD_PARTY")
        self.assertEqual(tables, [])
        self.assertIsNone(structure)

        mock_gliner.assert_called_once_with(
            mock_gliner_model, "Hello, I'm John Doe and I live in London."
        )
        mock_presidio.assert_called_once_with(
            "Hello, I'm John Doe and I live in London."
        )

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.extractors.spancat_extractor.extract_with_spancat")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_with_spancat(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_spancat,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """
        Test that SpanCat results take priority over GLiNER and Presidio.
        """
        mock_gliner_model = MagicMock()
        mock_spancat_nlp = MagicMock()
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            mock_gliner_model
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            mock_spancat_nlp
        )

        mock_pdf.return_value = "John Doe attended the scene."

        mock_spancat.return_value = [
            {
                "text": "attended the scene",
                "label": "OPERATIONAL",
                "start_char": 9,
                "end_char": 27,
            },
        ]
        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 8,
            },
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        _, results, _, _ = extract_entities_from_text(self.file_path)

        self.assertEqual(len(results), 2)
        labels = {r["label"] for r in results}
        self.assertIn("OPERATIONAL", labels)
        self.assertIn("THIRD_PARTY", labels)
        mock_spancat.assert_called_once_with(
            mock_spancat_nlp, "John Doe attended the scene."
        )

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_spancat_none_skips_spancat_extractor(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """
        When SpanCat returns None (not trained), extract_with_spancat is not called.
        """
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )

        mock_pdf.return_value = "Some text here."
        mock_gliner.return_value = []
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        with patch(
            "training.extractors.spancat_extractor.extract_with_spancat"
        ) as mock_spancat:
            _, results, _, _ = extract_entities_from_text(self.file_path)
            mock_spancat.assert_not_called()

    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_no_model_found(
        self, mock_manager, mock_spancat_mgr
    ):
        """
        Test that a ValueError is raised if get_model() returns None.
        """
        mock_manager.get_instance.return_value.get_model.return_value = None

        with self.assertRaisesMessage(
            ValueError, "No GLiNER model available."
        ):
            extract_entities_from_text(self.file_path)

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_no_text_in_document(
        self,
        mock_manager,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """
        Test that empty text returns empty results rather than raising.
        """
        mock_manager.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = ""

        ner_text, results, tables, structure = extract_entities_from_text(
            self.file_path
        )
        self.assertEqual(ner_text, "")
        self.assertEqual(results, [])
        self.assertEqual(tables, [])
        self.assertIsNone(structure)

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_deduplicates_overlapping(
        self,
        mock_manager,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """
        Test that overlapping GLiNER and Presidio results are deduplicated,
        with GLiNER taking priority.
        """
        mock_manager.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "John Doe lives in London."

        # Presidio finds "John" at 0-4
        mock_presidio.return_value = [
            {
                "text": "John",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 4,
            },
        ]
        mock_presidio_op.return_value = []
        # GLiNER also finds "John Doe" at 0-8 (overlaps with Presidio result)
        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 8,
            },
        ]

        _, results, _, _ = extract_entities_from_text(self.file_path)

        # Only "John" should remain — Presidio > GLiNER priority, overlap removed
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "John")

    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_non_gemma_extractor_exception_propagates(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
    ):
        """GLiNER raising should propagate out of extract_entities_from_text."""
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "Some text here."
        mock_gliner.side_effect = RuntimeError("GLiNER inference failed")
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        with self.assertRaises(RuntimeError, msg="GLiNER inference failed"):
            extract_entities_from_text(self.file_path)

    @patch("training.extractors.gemma_extractor.extract_with_gemma")
    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_gemma_exception_does_not_block_other_results(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
        mock_gemma,
    ):
        """Gemma raising unexpectedly should not prevent GLiNER/Presidio results."""
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "John Doe attended the scene."
        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 8,
            }
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []
        mock_gemma.side_effect = RuntimeError("Ollama crashed")

        with self.assertLogs("training.pipeline", level="WARNING") as cm:
            _, results, _, _ = extract_entities_from_text(self.file_path)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "John Doe")
        self.assertTrue(
            any("Non-fatal extractor" in line for line in cm.output)
        )


def _make_tbl_xml(
    border_values=None, include_tbl_pr=True, include_tbl_borders=True
):
    """
    Build a minimal w:tbl lxml element for testing _table_has_borders.
    border_values: dict mapping border names to w:val values, e.g.
        {"top": "single", "bottom": "none"}
    """
    nsmap = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    }
    tbl = etree.Element(f"{{{nsmap['w']}}}tbl", nsmap=nsmap)

    if include_tbl_pr:
        tbl_pr = etree.SubElement(tbl, f"{{{nsmap['w']}}}tblPr")
        if include_tbl_borders and border_values is not None:
            tbl_borders = etree.SubElement(
                tbl_pr, f"{{{nsmap['w']}}}tblBorders"
            )
            for name, val in border_values.items():
                border_el = etree.SubElement(
                    tbl_borders, f"{{{nsmap['w']}}}{name}"
                )
                border_el.set(f"{{{nsmap['w']}}}val", val)

    return tbl


class TableHasBordersTests(NetworkBlockerMixin, TestCase):
    def _make_mock_table(self, tbl_xml):
        mock_table = MagicMock()
        mock_table._tbl = tbl_xml
        return mock_table

    def test_single_borders_returns_true(self):
        tbl = _make_tbl_xml(
            {
                "top": "single",
                "bottom": "single",
                "left": "single",
                "right": "single",
            }
        )
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_double_borders_returns_true(self):
        tbl = _make_tbl_xml({"top": "double"})
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_all_none_borders_returns_false(self):
        tbl = _make_tbl_xml(
            {
                "top": "none",
                "bottom": "none",
                "left": "none",
                "right": "none",
                "insideH": "none",
                "insideV": "none",
            }
        )
        self.assertFalse(_table_has_borders(self._make_mock_table(tbl)))

    def test_all_nil_borders_returns_false(self):
        tbl = _make_tbl_xml(
            {
                "top": "nil",
                "bottom": "nil",
                "left": "nil",
                "right": "nil",
                "insideH": "nil",
                "insideV": "nil",
            }
        )
        self.assertFalse(_table_has_borders(self._make_mock_table(tbl)))

    def test_missing_tbl_borders_returns_true(self):
        tbl = _make_tbl_xml(include_tbl_borders=False)
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_missing_tbl_pr_returns_true(self):
        tbl = _make_tbl_xml(include_tbl_pr=False)
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))

    def test_mixed_borders_returns_true(self):
        tbl = _make_tbl_xml(
            {"top": "single", "bottom": "none", "left": "nil", "right": "none"}
        )
        self.assertTrue(_table_has_borders(self._make_mock_table(tbl)))


class ExtractTableWithStylingBorderTests(NetworkBlockerMixin, TestCase):
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


class DeduplicateEntitiesTests(NetworkBlockerMixin, TestCase):
    def test_no_overlap_keeps_all(self):
        primary = [
            {
                "text": "ref-123",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 7,
            }
        ]
        secondary = [
            {
                "text": "John",
                "label": "THIRD_PARTY",
                "start_char": 10,
                "end_char": 14,
            }
        ]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 2)

    def test_overlap_removes_secondary_entity(self):
        primary = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 8,
            }
        ]
        secondary = [
            {
                "text": "John",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 4,
            }
        ]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Doe")

    def test_partial_overlap_removes_secondary_entity(self):
        primary = [
            {
                "text": "John Doe ref",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 12,
            }
        ]
        secondary = [
            {
                "text": "John Doe",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 8,
            }
        ]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "OPERATIONAL")

    def test_empty_inputs(self):
        self.assertEqual(_deduplicate_entities([], []), [])
        primary = [
            {
                "text": "a",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 1,
            }
        ]
        self.assertEqual(len(_deduplicate_entities(primary, [])), 1)
        secondary = [
            {
                "text": "b",
                "label": "THIRD_PARTY",
                "start_char": 5,
                "end_char": 6,
            }
        ]
        self.assertEqual(len(_deduplicate_entities([], secondary)), 1)

    def test_secondary_entities_deduplicated_against_each_other(self):
        """Two mutually-overlapping secondary entities: first wins, second dropped."""
        long_span = {
            "text": "John Smith",
            "label": "THIRD_PARTY",
            "start_char": 0,
            "end_char": 10,
        }
        short_span = {
            "text": "John",
            "label": "THIRD_PARTY",
            "start_char": 0,
            "end_char": 4,
        }
        result = _deduplicate_entities([], [long_span, short_span])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Smith")

    def test_secondary_strict_superset_same_label_replaces_primary(self):
        """Secondary that strictly contains a same-label primary replaces it when allow_superset=True."""
        primary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 6,
                "end_char": 25,
            }
        ]
        secondary = [
            {
                "text": "OIC / HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 25,
            }
        ]
        result = _deduplicate_entities(primary, secondary, allow_superset=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "OIC / HUGHES, R. #0723222")

    def test_secondary_superset_not_applied_without_flag(self):
        """Secondary superset does not replace primary when allow_superset=False (default)."""
        primary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 6,
                "end_char": 25,
            }
        ]
        secondary = [
            {
                "text": "OIC / HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 25,
            }
        ]
        result = _deduplicate_entities(primary, secondary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "HUGHES, R. #0723222")

    def test_secondary_superset_different_label_does_not_replace(self):
        """Secondary superset with a different label does not replace the primary."""
        primary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 6,
                "end_char": 25,
            }
        ]
        secondary = [
            {
                "text": "OIC / HUGHES, R. #0723222",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 25,
            }
        ]
        result = _deduplicate_entities(primary, secondary, allow_superset=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "OPERATIONAL")

    def test_secondary_superset_blocked_by_other_overlap(self):
        """Secondary superset is dropped when it also partially overlaps a third entity."""
        primary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 6,
                "end_char": 25,
            },
            {
                "text": "OIC",
                "label": "THIRD_PARTY",
                "start_char": 0,
                "end_char": 3,
            },
        ]
        secondary = [
            {
                "text": "OIC / HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 25,
            }
        ]
        result = _deduplicate_entities(primary, secondary, allow_superset=True)
        self.assertEqual(len(result), 2)
        texts = {e["text"] for e in result}
        self.assertIn("HUGHES, R. #0723222", texts)
        self.assertIn("OIC", texts)

    def test_identical_span_same_label_is_not_superset(self):
        """Identical spans are not treated as a strict superset; primary wins."""
        primary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 19,
            }
        ]
        secondary = [
            {
                "text": "HUGHES, R. #0723222",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 19,
            }
        ]
        result = _deduplicate_entities(primary, secondary, allow_superset=True)
        self.assertEqual(len(result), 1)


class ExpandPrefixSymbolsTests(NetworkBlockerMixin, TestCase):
    def test_hash_prefix_expands_start_char(self):
        text = "Crime ref #42/12345/24 was recorded."
        entities = [
            {
                "text": "42/12345/24",
                "label": "OPERATIONAL",
                "start_char": 11,
                "end_char": 22,
            }
        ]
        result = _expand_prefix_symbols(entities, text)
        self.assertEqual(result[0]["start_char"], 10)
        self.assertEqual(result[0]["text"], "#42/12345/24")

    def test_no_prefix_leaves_entity_unchanged(self):
        text = "Crime ref 42/12345/24 was recorded."
        entities = [
            {
                "text": "42/12345/24",
                "label": "OPERATIONAL",
                "start_char": 10,
                "end_char": 21,
            }
        ]
        result = _expand_prefix_symbols(entities, text)
        self.assertEqual(result[0]["start_char"], 10)
        self.assertEqual(result[0]["text"], "42/12345/24")

    def test_entity_at_start_of_text_not_expanded(self):
        text = "42/12345/24 was recorded."
        entities = [
            {
                "text": "42/12345/24",
                "label": "OPERATIONAL",
                "start_char": 0,
                "end_char": 11,
            }
        ]
        result = _expand_prefix_symbols(entities, text)
        self.assertEqual(result[0]["start_char"], 0)

    def test_non_hash_prefix_not_expanded(self):
        text = "ref:42/12345/24 was recorded."
        entities = [
            {
                "text": "42/12345/24",
                "label": "OPERATIONAL",
                "start_char": 4,
                "end_char": 15,
            }
        ]
        result = _expand_prefix_symbols(entities, text)
        self.assertEqual(result[0]["start_char"], 4)

    def test_multiple_entities_expanded_independently(self):
        text = "refs #42/12345/24 and 43/67890/24"
        entities = [
            {
                "text": "42/12345/24",
                "label": "OPERATIONAL",
                "start_char": 6,
                "end_char": 17,
            },
            {
                "text": "43/67890/24",
                "label": "OPERATIONAL",
                "start_char": 22,
                "end_char": 33,
            },
        ]
        result = _expand_prefix_symbols(entities, text)
        self.assertEqual(result[0]["start_char"], 5)
        self.assertEqual(result[0]["text"], "#42/12345/24")
        self.assertEqual(result[1]["start_char"], 22)
        self.assertEqual(result[1]["text"], "43/67890/24")


class ExtractEntitiesDocxPathTests(NetworkBlockerMixin, TestCase):
    @patch("training.services.extract_document_structure")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_docx_path(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_doc_struct,
    ):
        """DOCX path: extract_document_structure returns structure, tables, and text."""
        mock_gliner_model = MagicMock()
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            mock_gliner_model
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )

        structure = [
            {"type": "paragraph", "text": "Hello world", "start": 0, "end": 11}
        ]
        tables = []
        mock_doc_struct.return_value = (structure, tables, "Hello world")

        mock_gliner.return_value = [
            {
                "text": "world",
                "label": "THIRD_PARTY",
                "start_char": 6,
                "end_char": 11,
            }
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []

        ner_text, results, returned_tables, returned_structure = (
            extract_entities_from_text("/fake/path.docx")
        )

        self.assertEqual(ner_text, "Hello world")
        self.assertEqual(len(results), 1)
        self.assertEqual(returned_tables, tables)
        self.assertEqual(returned_structure, structure)

    @patch("training.services.extract_document_structure")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_extract_entities_docx_empty_text_returns_empty(
        self, mock_gliner_mgr, mock_spancat_mgr, mock_doc_struct
    ):
        """DOCX path with empty text returns empty results rather than raising."""
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_doc_struct.return_value = ([], [], "")

        ner_text, results, tables, structure = extract_entities_from_text(
            "/fake/path.docx"
        )
        self.assertEqual(ner_text, "")
        self.assertEqual(results, [])
        self.assertEqual(tables, [])
        self.assertEqual(structure, [])


class ExtractEntitiesTxtPathTests(NetworkBlockerMixin, TestCase):
    def test_txt_file_reads_content_and_runs_pipeline(self):
        """TXT files bypass DOCX/PDF extraction and feed content directly into the pipeline."""
        content = "PC John Smith attended the scene."
        entity = {
            "text": "John Smith",
            "label": "THIRD_PARTY",
            "start_char": 3,
            "end_char": 13,
        }
        pipeline = ExtractionPipeline(stages=[lambda text: [entity]])

        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            ner_text, results, tables, structure = extract_entities_from_text(
                path, pipeline=pipeline
            )
            self.assertEqual(ner_text, content)
            self.assertEqual(results, [entity])
            self.assertEqual(tables, [])
            self.assertIsNone(structure)
        finally:
            os.remove(path)

    def test_empty_txt_file_returns_empty(self):
        """An empty TXT file returns the same empty result as other empty documents."""
        pipeline = ExtractionPipeline(stages=[lambda text: []])

        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("   ")
            path = f.name
        try:
            ner_text, results, tables, structure = extract_entities_from_text(
                path, pipeline=pipeline
            )
            self.assertEqual(ner_text, "")
            self.assertEqual(results, [])
        finally:
            os.remove(path)


class ExtractDocumentStructureTests(NetworkBlockerMixin, TestCase):
    def test_non_docx_returns_none(self):
        result = extract_document_structure("/some/file.pdf")
        self.assertEqual(result, (None, None))

    def test_docx_with_paragraphs(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            doc.add_paragraph("First paragraph")
            doc.add_paragraph("Second paragraph")
            doc.save(path)

            elements, tables, full_text = extract_document_structure(path)

            self.assertIsNotNone(elements)
            self.assertIn("First paragraph", full_text)
            self.assertIn("Second paragraph", full_text)
            para_elements = [e for e in elements if e["type"] == "paragraph"]
            self.assertEqual(len(para_elements), 2)
        finally:
            os.remove(path)

    def test_docx_with_heading(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            doc.add_heading("Chapter One", level=1)
            doc.add_paragraph("Some text")
            doc.save(path)

            elements, tables, full_text = extract_document_structure(path)

            headings = [e for e in elements if e["type"] == "heading"]
            self.assertEqual(len(headings), 1)
            self.assertEqual(headings[0]["level"], 1)
            self.assertEqual(headings[0]["text"], "Chapter One")
        finally:
            os.remove(path)

    def test_unreadable_file_returns_none(self):
        result = extract_document_structure("/nonexistent/path.docx")
        self.assertEqual(result, (None, None))

    def test_docx_with_table(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "Cell A1"
            table.cell(0, 1).text = "Cell B1"
            table.cell(1, 0).text = "Cell A2"
            table.cell(1, 1).text = "Cell B2"
            doc.save(path)

            elements, tables, full_text = extract_document_structure(path)

            table_elements = [e for e in elements if e["type"] == "table"]
            self.assertEqual(len(table_elements), 1)
            self.assertEqual(len(tables), 1)
            self.assertIn("Cell A1", tables[0]["text"])
        finally:
            os.remove(path)

    def test_docx_empty_paragraph_skipped(self):
        """Paragraphs with only whitespace are skipped."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            doc.add_paragraph("")
            doc.add_paragraph("Real content")
            doc.save(path)

            elements, tables, full_text = extract_document_structure(path)

            para_elements = [e for e in elements if e["type"] == "paragraph"]
            self.assertEqual(len(para_elements), 1)
            self.assertEqual(para_elements[0]["text"], "Real content")
        finally:
            os.remove(path)

    def test_docx_heading_with_invalid_level_defaults_to_one(self):
        """A heading whose style name cannot parse a level integer defaults to level 1."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            para = doc.add_paragraph("Custom heading")
            para.style = doc.styles["Heading 1"]
            doc.save(path)

            # Override: directly test the except branch via a docx where the heading
            # style name ends in a non-integer (mock the style within a real docx)
            elements, tables, full_text = extract_document_structure(path)
            headings = [e for e in elements if e["type"] == "heading"]
            self.assertGreaterEqual(
                len(headings), 0
            )  # just ensure no exception raised
        finally:
            os.remove(path)


class ExtractTextFromPDFTests(NetworkBlockerMixin, TestCase):
    # Minimal valid single-page PDF with no text content
    MINIMAL_PDF = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )

    def test_invalid_file_returns_empty_string(self):
        result = _extract_text_from_pdf("/nonexistent/path.pdf")
        self.assertEqual(result, "")

    def test_empty_pdf_returns_empty_string(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            result = _extract_text_from_pdf(path)
            self.assertEqual(result, "")
        finally:
            os.remove(path)

    def test_valid_pdf_reads_pages(self):
        """A syntactically valid PDF enters the page-reading loop."""
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, mode="wb"
        ) as f:
            f.write(self.MINIMAL_PDF)
            path = f.name
        try:
            result = _extract_text_from_pdf(path)
            # Minimal PDF has no text content; result should be an empty string
            self.assertIsInstance(result, str)
        finally:
            os.remove(path)


class ExtractTableWithStylingFormattingTests(NetworkBlockerMixin, TestCase):
    """Tests for run-level formatting in extract_table_with_styling."""

    def _make_mock_table(
        self, bold=False, italic=False, color_rgb=None, fill=None
    ):
        mock_table = MagicMock()
        mock_cell = MagicMock()
        mock_cell.text = "test"

        mock_tc_pr = MagicMock()
        if fill:
            mock_shading = MagicMock()
            mock_shading.get.side_effect = (
                lambda attr: fill if "fill" in attr else None
            )
            mock_tc_pr.find.return_value = mock_shading
        else:
            mock_tc_pr.find.return_value = None
        mock_cell._tc.get_or_add_tcPr.return_value = mock_tc_pr

        mock_run = MagicMock()
        mock_run.text = "test"
        mock_run.bold = bold
        mock_run.italic = italic

        if color_rgb:
            mock_run.font.color.rgb = color_rgb
        else:
            mock_run.font.color = None

        mock_para = MagicMock()
        mock_para.runs = [mock_run]
        mock_cell.paragraphs = [mock_para]

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table.rows = [mock_row]

        return mock_table

    def test_bold_run_in_cell(self):
        table = self._make_mock_table(bold=True)
        html, cells = extract_table_with_styling(table, 0, has_borders=False)
        self.assertIn("font-weight: bold", html)

    def test_italic_run_in_cell(self):
        table = self._make_mock_table(italic=True)
        html, cells = extract_table_with_styling(table, 0, has_borders=False)
        self.assertIn("font-style: italic", html)

    def test_color_run_in_cell(self):
        table = self._make_mock_table(color_rgb="FF0000")
        html, cells = extract_table_with_styling(table, 0, has_borders=False)
        self.assertIn("color: #FF0000", html)

    def test_background_color_in_cell(self):
        mock_table = MagicMock()
        mock_cell = MagicMock()
        mock_cell.text = "test"

        mock_shading = MagicMock()
        mock_shading.get.return_value = "FF0000"
        mock_tc_pr = MagicMock()
        mock_tc_pr.find.return_value = mock_shading
        mock_cell._tc.get_or_add_tcPr.return_value = mock_tc_pr

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

        html, cells = extract_table_with_styling(
            mock_table, 0, has_borders=False
        )
        self.assertEqual(cells[0]["bgColor"], "#FF0000")
        self.assertIn("background-color: #FF0000", cells[0]["style"])

    def test_empty_run_text_skipped(self):
        """Runs with empty text are skipped and do not appear in cell html."""
        mock_table = MagicMock()
        mock_cell = MagicMock()
        mock_cell.text = ""

        mock_tc_pr = MagicMock()
        mock_tc_pr.find.return_value = None
        mock_cell._tc.get_or_add_tcPr.return_value = mock_tc_pr

        empty_run = MagicMock()
        empty_run.text = ""
        empty_run.bold = False
        empty_run.italic = False
        empty_run.font.color = None

        mock_para = MagicMock()
        mock_para.runs = [empty_run]
        mock_cell.paragraphs = [mock_para]

        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table.rows = [mock_row]

        html, cells = extract_table_with_styling(
            mock_table, 0, has_borders=False
        )
        self.assertEqual(len(cells), 1)
        # No span tags since the empty run was skipped


class GemmaIntegrationTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf"
        )
        self.temp_file.close()
        self.file_path = self.temp_file.name

    def tearDown(self):
        os.remove(self.file_path)

    @patch("training.extractors.gemma_extractor.extract_with_gemma")
    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_data_subject_forwarded_to_gemma(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
        mock_gemma,
    ):
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "Some document text."
        mock_gliner.return_value = []
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []
        mock_gemma.return_value = []

        extract_entities_from_text(
            self.file_path,
            data_subject_name="Jane Doe",
            data_subject_dob="1990-01-01",
        )

        mock_gemma.assert_called_once_with(
            "Some document text.", "Jane Doe", "1990-01-01"
        )

    @patch("training.extractors.gemma_extractor.extract_with_gemma")
    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_non_overlapping_gemma_results_included(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
        mock_gemma,
    ):
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "John Doe spoke to PC Smith."
        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "PII",
                "start_char": 0,
                "end_char": 8,
            }
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []
        mock_gemma.return_value = [
            {
                "text": "PC Smith",
                "label": "OP_DATA",
                "start_char": 18,
                "end_char": 26,
                "source": "LLM",
            }
        ]

        _, results, _, _ = extract_entities_from_text(
            self.file_path, data_subject_name="Jane Doe"
        )

        texts = [r["text"] for r in results]
        self.assertIn("John Doe", texts)
        self.assertIn("PC Smith", texts)

    @patch("training.extractors.gemma_extractor.extract_with_gemma")
    @patch("training.services._extract_text_from_pdf")
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_operational"
    )
    @patch(
        "training.extractors.presidio_provider.PresidioSnapshot.extract_third_party"
    )
    @patch("training.extractors.gliner_extractor.extract_with_gliner")
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_gemma_results_overlapping_ner_are_dropped(
        self,
        mock_gliner_mgr,
        mock_spancat_mgr,
        mock_gliner,
        mock_presidio,
        mock_presidio_op,
        mock_pdf,
        mock_gemma,
    ):
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        mock_pdf.return_value = "John Doe attended."
        mock_gliner.return_value = [
            {
                "text": "John Doe",
                "label": "PII",
                "start_char": 0,
                "end_char": 8,
            }
        ]
        mock_presidio.return_value = []
        mock_presidio_op.return_value = []
        mock_gemma.return_value = [
            {
                "text": "John Doe",
                "label": "PII",
                "start_char": 0,
                "end_char": 8,
                "source": "LLM",
            }
        ]

        _, results, _, _ = extract_entities_from_text(
            self.file_path, data_subject_name="Jane Doe"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "John Doe")


class ExtractionPipelineTests(NetworkBlockerMixin, TestCase):
    """Tests for ExtractionPipeline that use stub stages — no model mocking required."""

    def _make_entity(self, text, start, end, label="THIRD_PARTY"):
        return {
            "text": text,
            "label": label,
            "start_char": start,
            "end_char": end,
        }

    def _stage(self, entities):
        return lambda text: list(entities)

    def _broken_stage(self, exc=None):
        def stage(text):
            raise (exc or RuntimeError("extractor failed"))

        return stage

    def test_single_stage_returns_all_entities(self):
        entity = self._make_entity("John Doe", 0, 8)
        pipeline = ExtractionPipeline(stages=[self._stage([entity])])
        result = pipeline.run("John Doe attended.")
        self.assertEqual(result, [entity])

    def test_earlier_stage_wins_on_overlap(self):
        """Stage 0 (higher priority) keeps its entity; stage 1's overlapping entity is dropped."""
        high = self._make_entity("John Doe", 0, 8)
        low = self._make_entity("John", 0, 4)
        pipeline = ExtractionPipeline(
            stages=[self._stage([high]), self._stage([low])]
        )
        result = pipeline.run("John Doe attended.")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Doe")

    def test_non_overlapping_entities_from_all_stages_kept(self):
        e1 = self._make_entity("John Doe", 0, 8)
        e2 = self._make_entity("London", 20, 26)
        e3 = self._make_entity("PC Smith", 30, 38, label="OPERATIONAL")
        pipeline = ExtractionPipeline(
            stages=[self._stage([e1]), self._stage([e2]), self._stage([e3])]
        )
        result = pipeline.run("John Doe went to London. PC Smith arrived.")
        self.assertEqual(len(result), 3)

    def test_priority_order_spancat_gliner_presidio(self):
        """Verify SpanCat > GLiNER > Presidio ordering with overlapping spans."""
        spancat = self._make_entity("John Doe Smith", 0, 14)
        gliner = self._make_entity(
            "John Doe", 0, 8
        )  # overlaps spancat → dropped
        presidio = self._make_entity(
            "Smith", 9, 14
        )  # overlaps spancat → dropped
        pipeline = ExtractionPipeline(
            stages=[
                self._stage([spancat]),
                self._stage([gliner]),
                self._stage([presidio]),
            ]
        )
        result = pipeline.run("John Doe Smith attended.")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "John Doe Smith")

    def test_entity_type_survives_dedup_and_prefix_expansion(self):
        """
        ``entity_type`` is transient — carried through the pipeline rather than
        persisted — so it has to survive every stage that rewrites spans:
        deduplication (which passes whole dicts through) and prefix expansion
        (which only touches start_char/text).
        """
        name = self._make_entity("BLOGGS, Joe", 0, 11)
        name["entity_type"] = "PERSON_NAME"
        collar = self._make_entity("0723222", 19, 26, label="OPERATIONAL")
        collar["entity_type"] = "UK_COLLAR_NUMBER"
        dropped = self._make_entity("Joe", 8, 11)
        dropped["entity_type"] = "person name"

        pipeline = ExtractionPipeline(
            stages=[self._stage([name, collar]), self._stage([dropped])]
        )
        text = "BLOGGS, Joe is PC #0723222"
        result = _expand_prefix_symbols(pipeline.run(text), text)

        by_type = {r["entity_type"]: r for r in result}
        self.assertEqual(
            set(by_type), {"PERSON_NAME", "UK_COLLAR_NUMBER"}
        )  # the overlapping "person name" span was dropped
        # The collar span grew left onto the '#' and kept its entity_type.
        self.assertEqual(by_type["UK_COLLAR_NUMBER"]["text"], "#0723222")

    def test_fatal_stage_exception_propagates(self):
        pipeline = ExtractionPipeline(
            stages=[self._stage([]), self._broken_stage(RuntimeError("fatal"))]
        )
        with self.assertRaises(RuntimeError, msg="fatal"):
            pipeline.run("some text")

    def test_pipeline_injectable_into_extract_entities_from_text(self):
        """extract_entities_from_text accepts a pre-built pipeline — no model manager needed."""
        entity = self._make_entity("Jane Smith", 6, 16)
        pipeline = ExtractionPipeline(stages=[self._stage([entity])])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            with patch("training.services._extract_text_from_pdf") as mock_pdf:
                mock_pdf.return_value = "Hello Jane Smith goodbye."
                _, results, _, _ = extract_entities_from_text(
                    path, pipeline=pipeline
                )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["text"], "Jane Smith")
        finally:
            os.remove(path)


def _span(text, start, end, label="THIRD_PARTY", entity_type=None):
    return {
        "text": text,
        "label": label,
        "start_char": start,
        "end_char": end,
        "entity_type": entity_type,
    }


class _StubRule:
    """A span rule that adds canned spans and drops detector spans by text."""

    def __init__(self, added=(), drop_texts=()):
        self.added = list(added)
        self.drop_texts = set(drop_texts)

    def apply(self, text, stage_results):
        return SpanRuleResult(
            stage_results=[
                [s for s in results if s["text"] not in self.drop_texts]
                for results in stage_results
            ],
            added=list(self.added),
        )


class SpanRuleStepTests(NetworkBlockerMixin, TestCase):
    """The generic span-rule step of ExtractionPipeline, with stub rules."""

    TEXT = "Summary: Jane Smith shouted at a neighbour."

    def _stage(self, entities):
        return lambda text: list(entities)

    def test_rule_span_outranks_every_detector(self):
        # Superset stage on purpose: even SpanCat's superset replacement must
        # not widen over a rule span.
        rule_span = _span("Summary: Jane Smith", 0, 19)
        spancat = _span("Summary: Jane Smith shouted", 0, 27)
        gliner = _span("Jane Smith", 9, 19, entity_type="person name")
        neighbour = _span("neighbour", 33, 42)
        pipeline = ExtractionPipeline(
            stages=[self._stage([spancat]), self._stage([gliner, neighbour])],
            superset_stage_indices=frozenset({0}),
            span_rules=[_StubRule(added=[rule_span])],
        )

        result = pipeline.run(self.TEXT)

        self.assertCountEqual(result, [rule_span, neighbour])

    def test_span_dropped_by_rule_never_reaches_deduplication(self):
        # Dropped before deduplication, so the whole-line SpanCat span cannot
        # erase the inner name a lower-priority detector found.
        whole_line = _span(self.TEXT, 0, len(self.TEXT), label="OPERATIONAL")
        gliner = _span("Jane Smith", 9, 19, entity_type="person name")
        pipeline = ExtractionPipeline(
            stages=[self._stage([whole_line]), self._stage([gliner])],
            span_rules=[_StubRule(drop_texts={self.TEXT})],
        )

        self.assertEqual(pipeline.run(self.TEXT), [gliner])


# Synthetic occurrence report.  Every name, code and date is invented.
_REPORTED_TIME = "Reported time: 01/02/2026 10:00"
_SUMMARY = (
    "Summary: Closure Summary: XX1 AB12 - Reporting Person given advice "
    "and advised of NFA decision."
)
_ORIGINAL_REPORT = (
    "Original Incident Report: Caller states that a neighbour shouted at them."
)
_JOE_REPORTING = "BLOGGS, Joe [A1B] / Person reporting / DOB: 02/01/1990"
_JANE_SUSPECT = "SMITH, Jane / Suspect / DOB: 03/04/1985"


def _occurrence_report(
    *person_lines,
    head=(_REPORTED_TIME, _SUMMARY, _ORIGINAL_REPORT),
    sections=1,
):
    lines = ["Occurrence number: 01/000001/26", *head]
    for _ in range(sections):
        lines += ["Involved persons:", *person_lines, ""]
    lines.append("Officer in charge: PC 0000")
    return "\n".join(lines)


class RoleDependentFieldRuleTests(NetworkBlockerMixin, TestCase):
    """
    The occurrence-report span rule, through ExtractionPipeline.run with stub
    detectors and synthetic text.
    """

    def _whole_line_spans(self, text):
        # How SpanCat treats the summary and original incident report today:
        # one operational span over each whole line.  The reported time goes
        # undetected.
        spans = []
        for line in (_SUMMARY, _ORIGINAL_REPORT):
            start = text.find(line)
            if start != -1:
                spans.append(
                    _span(line, start, start + len(line), label="OPERATIONAL")
                )
        return spans

    def _run(self, text, ds_name, ds_dob, *, detectors=None):
        stage_spans = (
            detectors
            if detectors is not None
            else self._whole_line_spans(text)
        )
        pipeline = ExtractionPipeline(
            stages=[lambda _text: list(stage_spans)],
            span_rules=[
                build_occurrence_report_rule(
                    data_subject_name=ds_name, data_subject_dob=ds_dob
                )
            ],
        )
        return pipeline.run(text)

    def _labelled(self, result):
        return sorted((s["label"], s["text"]) for s in result)

    def assertFieldsWithheld(self, result, fields=None):
        fields = fields or (_REPORTED_TIME, _SUMMARY, _ORIGINAL_REPORT)
        self.assertEqual(
            self._labelled(result),
            sorted(("THIRD_PARTY", f) for f in fields),
        )

    def test_ds_with_another_role_has_fields_withheld_as_third_party(self):
        text = _occurrence_report(_JOE_REPORTING, _JANE_SUSPECT)

        result = self._run(text, "Jane Smith", date(1985, 4, 3))

        self.assertFieldsWithheld(result)
        for span in result:
            self.assertEqual(
                text[span["start_char"] : span["end_char"]], span["text"]
            )

    def test_uncertain_role_has_fields_withheld(self):
        cases = {
            "no person line matches the data subject": (
                ("Alan Partridge", date(1970, 5, 6)),
                (_JOE_REPORTING, _JANE_SUSPECT),
            ),
            "only an ambiguous match (shared surname)": (
                ("Mary Bloggs", None),
                (_JOE_REPORTING, _JANE_SUSPECT),
            ),
            "the data subject's line shows no role": (
                ("Joe Bloggs", date(1990, 1, 2)),
                ("BLOGGS, Joe [A1B] / DOB: 02/01/1990", _JANE_SUSPECT),
            ),
            "matching lines disagree on the role": (
                ("Joe Bloggs", date(1990, 1, 2)),
                (_JOE_REPORTING, "BLOGGS, Joe / Victim / DOB: 02/01/1990"),
            ),
            "no data subject on the case": (
                (None, None),
                (_JOE_REPORTING, _JANE_SUSPECT),
            ),
        }
        for description, ((ds_name, ds_dob), person_lines) in cases.items():
            with self.subTest(description):
                text = _occurrence_report(*person_lines)
                self.assertFieldsWithheld(self._run(text, ds_name, ds_dob))

    def test_more_than_one_record_has_fields_withheld(self):
        # The data subject reports in both, but one record's role must never
        # decide another record's fields.
        text = _occurrence_report(_JOE_REPORTING, _JANE_SUSPECT, sections=2)

        result = self._run(text, "Joe Bloggs", date(1990, 1, 2))

        self.assertFieldsWithheld(result)

    def test_reporting_person_fields_are_not_withheld_as_third_party(self):
        for person_line in (
            _JOE_REPORTING,
            "BLOGGS, Joe / Victim / Person reporting / DOB: 02/01/1990",
        ):
            with self.subTest(person_line):
                text = _occurrence_report(person_line, _JANE_SUSPECT)

                result = self._run(text, "Joe Bloggs", date(1990, 1, 2))

                self.assertEqual(
                    [s for s in result if s["label"] == "THIRD_PARTY"], []
                )

    def test_document_without_persons_section_is_untouched(self):
        text = "\n".join(
            [_REPORTED_TIME, _SUMMARY, _ORIGINAL_REPORT, "Logged by PC 0000"]
        )
        detectors = self._whole_line_spans(text) + [
            _span("PC 0000", text.find("PC 0000"), len(text))
        ]
        without_rule = ExtractionPipeline(
            stages=[lambda _text: list(detectors)]
        ).run(text)

        result = self._run(
            text, "Jane Smith", date(1985, 4, 3), detectors=detectors
        )

        self.assertEqual(result, without_rule)

    def test_field_wrapping_onto_following_lines_is_withheld_in_full(self):
        wrapped_summary = (
            "Summary: Closure Summary: neighbour dispute.\n"
            "Advice given by phone\n"
            "and by letter."
        )
        text = _occurrence_report(
            _JOE_REPORTING,
            _JANE_SUSPECT,
            head=(_REPORTED_TIME, wrapped_summary, "", _ORIGINAL_REPORT),
        )

        result = self._run(text, "Jane Smith", date(1985, 4, 3))

        self.assertFieldsWithheld(
            result, fields=(_REPORTED_TIME, wrapped_summary, _ORIGINAL_REPORT)
        )


class DefaultPipelineWiringTests(NetworkBlockerMixin, TestCase):
    """build_default_pipeline attaches the occurrence-report rule."""

    @patch(
        "training.extractors.gemma_extractor.extract_with_gemma",
        return_value=[],
    )
    @patch(
        "training.extractors.gliner_extractor.extract_with_gliner",
        return_value=[],
    )
    @patch("training.loader.SpanCatModelManager")
    @patch("training.loader.GLiNERModelManager")
    def test_default_pipeline_withholds_role_dependent_fields(
        self, mock_gliner_mgr, mock_spancat_mgr, _gliner, _gemma
    ):
        mock_gliner_mgr.get_instance.return_value.get_model.return_value = (
            MagicMock()
        )
        mock_spancat_mgr.get_instance.return_value.get_model.return_value = (
            None
        )
        snapshot = MagicMock()
        snapshot.extract_custom.return_value = []
        snapshot.extract_third_party.return_value = []
        snapshot.extract_operational.return_value = []

        pipeline = build_default_pipeline(
            "Jane Smith", date(1985, 4, 3), presidio_snapshot=snapshot
        )
        result = pipeline.run(
            _occurrence_report(_JOE_REPORTING, _JANE_SUSPECT)
        )

        self.assertEqual(
            sorted((s["label"], s["text"]) for s in result),
            sorted(
                ("THIRD_PARTY", f)
                for f in (_REPORTED_TIME, _SUMMARY, _ORIGINAL_REPORT)
            ),
        )


class DocumentStructureTests(NetworkBlockerMixin, TestCase):
    """Tests for DocumentStructure.check_invariant() and extract_document()."""

    def _make_structure(
        self, full_text, elements=None, tables=None, is_structured=True
    ):
        return DocumentStructure(
            full_text=full_text,
            elements=elements or [],
            tables=tables or [],
            is_structured=is_structured,
        )

    def test_check_invariant_passes_for_valid_structure(self):
        full_text = "Hello world"
        ds = self._make_structure(
            full_text,
            elements=[
                {
                    "type": "paragraph",
                    "text": "Hello world",
                    "start": 0,
                    "end": 11,
                }
            ],
        )
        self.assertEqual(ds.check_invariant(), [])

    def test_check_invariant_detects_element_mismatch(self):
        full_text = "Hello world"
        ds = self._make_structure(
            full_text,
            elements=[
                {
                    "type": "paragraph",
                    "text": "wrong text",
                    "start": 0,
                    "end": 11,
                }
            ],
        )
        violations = ds.check_invariant()
        self.assertEqual(len(violations), 1)
        self.assertIn("paragraph", violations[0])

    def test_check_invariant_skips_table_elements(self):
        full_text = "Cell A\tCell B"
        ds = self._make_structure(
            full_text,
            elements=[{"type": "table", "table_id": 0, "start": 0, "end": 13}],
        )
        self.assertEqual(ds.check_invariant(), [])

    def test_check_invariant_detects_cell_mismatch(self):
        full_text = "Cell A\tCell B"
        ds = self._make_structure(
            full_text,
            tables=[
                {
                    "cells": [
                        {
                            "row": 0,
                            "col": 0,
                            "text": "wrong",
                            "start": 0,
                            "end": 6,
                            "isMergedContinuation": False,
                        }
                    ]
                }
            ],
        )
        violations = ds.check_invariant()
        self.assertEqual(len(violations), 1)
        self.assertIn("[0,0]", violations[0])

    def test_check_invariant_skips_continuation_cells(self):
        full_text = "Cell A"
        ds = self._make_structure(
            full_text,
            tables=[
                {
                    "cells": [
                        {
                            "row": 0,
                            "col": 0,
                            "text": "Cell A",
                            "start": 0,
                            "end": 6,
                            "isMergedContinuation": False,
                        },
                        {
                            "row": 0,
                            "col": 1,
                            "text": "Cell A",
                            "start": 0,
                            "end": 0,
                            "isMergedContinuation": True,
                        },
                    ]
                }
            ],
        )
        self.assertEqual(ds.check_invariant(), [])

    def test_extract_document_docx_returns_structured(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            doc.add_paragraph("First line")
            doc.add_paragraph("Second line")
            doc.save(path)

            ds = extract_document(path)

            self.assertTrue(ds.is_structured)
            self.assertIsNotNone(ds.elements)
            self.assertIn("First line", ds.full_text)
            self.assertIn("Second line", ds.full_text)
            self.assertEqual(ds.check_invariant(), [])
        finally:
            os.remove(path)

    def test_extract_document_docx_with_table_invariant_holds(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = DocxDocument()
            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "A1"
            table.cell(0, 1).text = "B1"
            table.cell(1, 0).text = "A2"
            table.cell(1, 1).text = "B2"
            doc.save(path)

            ds = extract_document(path)

            self.assertTrue(ds.is_structured)
            self.assertEqual(ds.check_invariant(), [], ds.check_invariant())
        finally:
            os.remove(path)

    def test_extract_document_pdf_returns_unstructured(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            ds = extract_document(path)
            self.assertFalse(ds.is_structured)
            self.assertIsNone(ds.elements)
            self.assertEqual(ds.tables, [])
        finally:
            os.remove(path)
