from unittest.mock import patch

from django.test import TestCase, override_settings

from training.extractors.gemma_extractor import extract_with_gemma
from training.tests.base import NetworkBlockerMixin


class GemmaExtractorTests(NetworkBlockerMixin, TestCase):
    def test_returns_empty_when_ollama_disabled(self):
        with override_settings(OLLAMA_ENABLED=None):
            result = extract_with_gemma("Some text.", "John Doe")
        self.assertEqual(result, [])

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_returns_spans_with_correct_offsets(self, mock_post):
        mock_post.return_value.json.return_value = {
            "message": {
                "content": {
                    "redactions": [
                        {
                            "text": "PC Smith",
                            "reason": "Third-party officer",
                            "redaction_type": "OP_DATA",
                        }
                    ]
                }
            }
        }
        text = "The officer PC Smith attended the scene."
        with override_settings(
            OLLAMA_ENABLED="true",
            OLLAMA_HOST="http://ollama:11434",
            OLLAMA_MODEL="gemma4:e4b",
        ):
            result = extract_with_gemma(text, "Jane Doe")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "PC Smith")
        self.assertEqual(result[0]["start_char"], text.index("PC Smith"))
        self.assertEqual(
            result[0]["end_char"], text.index("PC Smith") + len("PC Smith")
        )
        self.assertEqual(result[0]["label"], "OP_DATA")
        self.assertEqual(result[0]["source"], "LLM")

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_duplicate_phrase_produces_two_spans(self, mock_post):
        mock_post.return_value.json.return_value = {
            "message": {
                "content": {
                    "redactions": [
                        {
                            "text": "PC Smith",
                            "reason": "Third-party officer",
                            "redaction_type": "OP_DATA",
                        }
                    ]
                }
            }
        }
        text = "PC Smith spoke to PC Smith again."
        with override_settings(
            OLLAMA_ENABLED="true",
            OLLAMA_HOST="http://ollama:11434",
            OLLAMA_MODEL="gemma4:e4b",
        ):
            result = extract_with_gemma(text, "Jane Doe")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["start_char"], 0)
        self.assertEqual(result[1]["start_char"], text.index("PC Smith", 1))

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_connection_error_returns_empty_and_logs_warning(self, mock_post):
        mock_post.side_effect = ConnectionError("Ollama unavailable")
        with override_settings(
            OLLAMA_ENABLED="true",
            OLLAMA_HOST="http://ollama:11434",
            OLLAMA_MODEL="gemma4:e4b",
        ):
            with self.assertLogs(
                "training.extractors.gemma_extractor", level="WARNING"
            ) as cm:
                result = extract_with_gemma("Some text.", "Jane Doe")

        self.assertEqual(result, [])
        self.assertTrue(
            any("Gemma extractor failed" in line for line in cm.output)
        )
