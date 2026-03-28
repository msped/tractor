from unittest.mock import MagicMock

from django.test import TestCase

from ..extractors.spancat_extractor import extract_with_spancat
from .base import NetworkBlockerMixin


def _make_span(text, label, start_char, end_char):
    span = MagicMock()
    span.text = text
    span.label_ = label
    span.start_char = start_char
    span.end_char = end_char
    return span


def _make_nlp(spans):
    """Return a mock spaCy nlp pipeline whose doc.spans["sc"] yields *spans*."""
    doc = MagicMock()
    doc.spans.get.return_value = spans
    nlp = MagicMock()
    nlp.return_value = doc
    return nlp


class ExtractWithSpanCatTests(NetworkBlockerMixin, TestCase):
    def test_third_party_span_returned(self):
        span = _make_span("John Smith", "THIRD_PARTY", 0, 10)
        nlp = _make_nlp([span])
        results = extract_with_spancat(nlp, "John Smith was here.")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[0]["text"], "John Smith")
        self.assertEqual(results[0]["start_char"], 0)
        self.assertEqual(results[0]["end_char"], 10)

    def test_operational_span_returned(self):
        span = _make_span("attended the scene at night", "OPERATIONAL", 10, 37)
        nlp = _make_nlp([span])
        results = extract_with_spancat(
            nlp, "Officers attended the scene at night."
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "OPERATIONAL")

    def test_mixed_labels_both_returned(self):
        spans = [
            _make_span("John Doe", "THIRD_PARTY", 0, 8),
            _make_span("attended the scene", "OPERATIONAL", 15, 33),
        ]
        nlp = _make_nlp(spans)
        results = extract_with_spancat(
            nlp, "John Doe was seen attending the scene."
        )
        self.assertEqual(len(results), 2)
        labels = {r["label"] for r in results}
        self.assertIn("THIRD_PARTY", labels)
        self.assertIn("OPERATIONAL", labels)

    def test_unknown_label_is_skipped(self):
        span = _make_span("something", "UNKNOWN_LABEL", 0, 9)
        nlp = _make_nlp([span])
        results = extract_with_spancat(nlp, "something here")
        self.assertEqual(results, [])

    def test_empty_spans(self):
        nlp = _make_nlp([])
        results = extract_with_spancat(nlp, "no entities here")
        self.assertEqual(results, [])

    def test_no_sc_key_returns_empty(self):
        """If doc.spans has no 'sc' key, get() returns None-like; handle gracefully."""
        doc = MagicMock()
        doc.spans.get.return_value = []
        nlp = MagicMock()
        nlp.return_value = doc
        results = extract_with_spancat(nlp, "some text")
        self.assertEqual(results, [])

    def test_calls_nlp_with_text(self):
        nlp = _make_nlp([])
        extract_with_spancat(nlp, "test document text")
        nlp.assert_called_once_with("test document text")

    def test_result_keys_present(self):
        span = _make_span("Jane Doe", "THIRD_PARTY", 5, 13)
        nlp = _make_nlp([span])
        results = extract_with_spancat(nlp, "Name: Jane Doe")
        self.assertIn("text", results[0])
        self.assertIn("label", results[0])
        self.assertIn("start_char", results[0])
        self.assertIn("end_char", results[0])
