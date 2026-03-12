from unittest.mock import MagicMock

from django.test import TestCase

from ..extractors.gliner_extractor import _MAX_CHUNK_CHARS, GLINER_LABELS, _chunk_text, extract_with_gliner
from .base import NetworkBlockerMixin


class ExtractWithGLiNERTests(NetworkBlockerMixin, TestCase):
    def _make_model(self, raw_results):
        model = MagicMock()
        model.predict_entities.return_value = raw_results
        return model

    def test_person_name_maps_to_third_party(self):
        model = self._make_model([{"text": "John Smith", "label": "person name", "start": 0, "end": 10, "score": 0.9}])
        results = extract_with_gliner(model, "John Smith was here.")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[0]["text"], "John Smith")
        self.assertEqual(results[0]["start_char"], 0)
        self.assertEqual(results[0]["end_char"], 10)

    def test_police_collar_number_is_skipped(self):
        """Collar numbers are no longer in GLINER_LABELS — SpanCat/Presidio owns OPERATIONAL."""
        model = self._make_model(
            [{"text": "PC 1234", "label": "police collar number", "start": 0, "end": 7, "score": 0.85}]
        )
        results = extract_with_gliner(model, "PC 1234 attended the scene.")
        self.assertEqual(results, [])

    def test_case_reference_is_skipped(self):
        """Case refs are no longer in GLINER_LABELS — SpanCat/Presidio owns OPERATIONAL."""
        model = self._make_model(
            [{"text": "42/12345/24", "label": "case reference number", "start": 12, "end": 23, "score": 0.88}]
        )
        results = extract_with_gliner(model, "Crime Ref No: 42/12345/24")
        self.assertEqual(results, [])

    def test_multiple_entities_all_third_party(self):
        model = self._make_model(
            [
                {"text": "SMITH, John", "label": "person name", "start": 0, "end": 11, "score": 0.92},
                {"text": "Manchester", "label": "location", "start": 20, "end": 30, "score": 0.80},
            ]
        )
        results = extract_with_gliner(model, "SMITH, John lives in Manchester.")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["label"] == "THIRD_PARTY" for r in results))

    def test_unknown_label_is_skipped(self):
        model = self._make_model([{"text": "something", "label": "unknown_label", "start": 0, "end": 9, "score": 0.95}])
        results = extract_with_gliner(model, "something here")
        self.assertEqual(results, [])

    def test_empty_results(self):
        model = self._make_model([])
        results = extract_with_gliner(model, "no entities here")
        self.assertEqual(results, [])

    def test_calls_predict_entities_with_correct_labels(self):
        model = self._make_model([])
        extract_with_gliner(model, "test text")
        model.predict_entities.assert_called_once_with("test text", GLINER_LABELS, flat_ner=True, threshold=0.35)

    def test_all_third_party_labels(self):
        """Test that all expected THIRD_PARTY labels map correctly."""
        third_party_labels = ["person name", "organisation", "location", "date of birth", "address"]
        for label in third_party_labels:
            model = self._make_model([{"text": "test", "label": label, "start": 0, "end": 4, "score": 0.8}])
            results = extract_with_gliner(model, "test")
            self.assertEqual(results[0]["label"], "THIRD_PARTY", f"Label '{label}' should map to THIRD_PARTY")

    def test_no_operational_labels_in_gliner(self):
        """Confirm OPERATIONAL labels are not present in GLINER_LABELS."""
        operational_labels = ["police collar number", "case reference number", "reference number"]
        for label in operational_labels:
            self.assertNotIn(label, GLINER_LABELS, f"'{label}' should not be in GLINER_LABELS")

    def test_long_text_is_chunked_and_offsets_applied(self):
        """Entities found in later chunks have offsets adjusted to full-text positions."""
        # Force a second chunk by using _MAX_CHUNK_CHARS 'x' chars with no spaces/newlines
        prefix = "x" * _MAX_CHUNK_CHARS
        entity_text = "John Smith"
        text = prefix + entity_text + " was here."

        def fake_predict(chunk_text, labels, **kwargs):
            if entity_text in chunk_text:
                idx = chunk_text.index(entity_text)
                return [
                    {
                        "text": entity_text,
                        "label": "person name",
                        "start": idx,
                        "end": idx + len(entity_text),
                        "score": 0.9,
                    }
                ]
            return []

        model = MagicMock()
        model.predict_entities.side_effect = fake_predict

        results = extract_with_gliner(model, text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["start_char"], _MAX_CHUNK_CHARS)
        self.assertEqual(results[0]["end_char"], _MAX_CHUNK_CHARS + len(entity_text))

    def test_chunk_text_short_text_is_single_chunk(self):
        """Short text is returned as a single chunk with offset 0."""
        chunks = _chunk_text("short text")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], ("short text", 0))

    def test_chunk_text_prefers_newline_boundary(self):
        """_chunk_text splits at newline boundaries when available."""
        line = "word " * 200  # 1000 chars
        text = line + "\n" + line  # 2001 chars — over the limit
        chunks = _chunk_text(text)
        self.assertGreater(len(chunks), 1)
        # First chunk should end just after the newline
        first_chunk, first_offset = chunks[0]
        self.assertTrue(first_chunk.endswith("\n"))
