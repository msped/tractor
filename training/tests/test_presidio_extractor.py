from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..extractors.presidio_extractor import (
    _build_analyzer,
    _build_operational_analyzer,
    extract_operational_with_presidio,
    extract_with_presidio,
)
from .base import NetworkBlockerMixin


class ExtractWithPresidioTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        # Reset cached analyzers between tests to avoid state bleed
        import training.extractors.presidio_extractor as mod

        mod._analyzer = None
        mod._operational_analyzer = None

    @patch("training.extractors.presidio_extractor._get_analyzer")
    def test_email_detection(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "EMAIL_ADDRESS"
        mock_result.start = 10
        mock_result.end = 28
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        text = "Contact: john@example.com today"
        results = extract_with_presidio(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[0]["start_char"], 10)
        self.assertEqual(results[0]["end_char"], 28)
        self.assertEqual(results[0]["text"], text[10:28])

    @patch("training.extractors.presidio_extractor._get_analyzer")
    def test_phone_number_detection(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "PHONE_NUMBER"
        mock_result.start = 11
        mock_result.end = 25
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        text = "Call me on 07700 900000"
        results = extract_with_presidio(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "THIRD_PARTY")
        self.assertEqual(results[0]["start_char"], 11)
        self.assertEqual(results[0]["end_char"], 25)

    @patch("training.extractors.presidio_extractor._get_analyzer")
    def test_nhs_number_detection(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "UK_NHS"
        mock_result.start = 13
        mock_result.end = 23
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        text = "NHS Number: 485 777 3456"
        results = extract_with_presidio(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "THIRD_PARTY")

    @patch("training.extractors.presidio_extractor._get_analyzer")
    def test_multiple_entities(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result_1 = MagicMock()
        mock_result_1.entity_type = "EMAIL_ADDRESS"
        mock_result_1.start = 0
        mock_result_1.end = 16

        mock_result_2 = MagicMock()
        mock_result_2.entity_type = "PHONE_NUMBER"
        mock_result_2.start = 21
        mock_result_2.end = 35

        mock_analyzer.analyze.return_value = [mock_result_1, mock_result_2]
        mock_get_analyzer.return_value = mock_analyzer

        text = "john@example.com and 07700 900000"
        results = extract_with_presidio(text)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["label"] == "THIRD_PARTY" for r in results))

    @patch("training.extractors.presidio_extractor._get_analyzer")
    def test_empty_result(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_get_analyzer.return_value = mock_analyzer

        results = extract_with_presidio("No PII here at all.")
        self.assertEqual(results, [])

    def test_analyzer_is_cached(self):
        """The analyzer instance should be cached after first creation."""
        import training.extractors.presidio_extractor as mod

        mod._analyzer = None

        with patch("training.extractors.presidio_extractor._build_analyzer") as mock_build:
            mock_build.return_value = MagicMock()
            mock_build.return_value.analyze.return_value = []

            extract_with_presidio("test")
            extract_with_presidio("test again")

            # _build_analyzer should only be called once
            mock_build.assert_called_once()


class ExtractOperationalWithPresidioTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        import training.extractors.presidio_extractor as mod

        mod._operational_analyzer = None

    @patch("training.extractors.presidio_extractor._get_operational_analyzer")
    def test_crime_ref_detection(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "UK_CRIME_REF"
        mock_result.start = 13
        mock_result.end = 24
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        text = "Crime Ref No: 42/12345/24"
        results = extract_operational_with_presidio(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "OPERATIONAL")
        self.assertEqual(results[0]["start_char"], 13)
        self.assertEqual(results[0]["end_char"], 24)
        self.assertEqual(results[0]["text"], text[13:24])

    @patch("training.extractors.presidio_extractor._get_operational_analyzer")
    def test_collar_number_detection(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "UK_COLLAR_NUMBER"
        mock_result.start = 0
        mock_result.end = 7
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        text = "PC 1234 attended the scene."
        results = extract_operational_with_presidio(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["label"], "OPERATIONAL")
        self.assertEqual(results[0]["start_char"], 0)
        self.assertEqual(results[0]["end_char"], 7)

    @patch("training.extractors.presidio_extractor._get_operational_analyzer")
    def test_multiple_operational_entities(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        r1 = MagicMock()
        r1.entity_type = "UK_CRIME_REF"
        r1.start = 0
        r1.end = 11

        r2 = MagicMock()
        r2.entity_type = "UK_COLLAR_NUMBER"
        r2.start = 20
        r2.end = 27

        mock_analyzer.analyze.return_value = [r1, r2]
        mock_get_analyzer.return_value = mock_analyzer

        text = "42/12345/24 attended by PC 1234"
        results = extract_operational_with_presidio(text)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["label"] == "OPERATIONAL" for r in results))

    @patch("training.extractors.presidio_extractor._get_operational_analyzer")
    def test_empty_result(self, mock_get_analyzer):
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_get_analyzer.return_value = mock_analyzer

        results = extract_operational_with_presidio("No refs here.")
        self.assertEqual(results, [])

    def test_operational_analyzer_is_cached(self):
        """The operational analyzer should be cached after first creation."""
        import training.extractors.presidio_extractor as mod

        mod._operational_analyzer = None

        with patch("training.extractors.presidio_extractor._build_operational_analyzer") as mock_build:
            mock_build.return_value = MagicMock()
            mock_build.return_value.analyze.return_value = []

            extract_operational_with_presidio("test")
            extract_operational_with_presidio("test again")

            mock_build.assert_called_once()


class BuildAnalyzerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        import training.extractors.presidio_extractor as mod

        mod._analyzer = None
        mod._operational_analyzer = None

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    @patch("presidio_analyzer.PatternRecognizer")
    @patch("presidio_analyzer.Pattern")
    def test_build_analyzer_returns_engine(self, mock_pattern, mock_recognizer, mock_engine, mock_provider):
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        result = _build_analyzer()

        mock_engine.assert_called_once()
        self.assertEqual(mock_engine_instance.registry.add_recognizer.call_count, 2)
        self.assertEqual(result, mock_engine_instance)

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    @patch("presidio_analyzer.PatternRecognizer")
    @patch("presidio_analyzer.Pattern")
    def test_build_operational_analyzer_returns_engine(self, mock_pattern, mock_recognizer, mock_engine, mock_provider):
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        result = _build_operational_analyzer()

        mock_engine.assert_called_once()
        self.assertEqual(mock_engine_instance.registry.add_recognizer.call_count, 2)
        self.assertEqual(result, mock_engine_instance)
