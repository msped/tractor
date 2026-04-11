from unittest.mock import call, patch

from django.test import TestCase, override_settings

from training.extractors.gemma_extractor import _chunk_text, extract_with_gemma
from training.models import LLMPromptSettings
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

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_custom_prompt_is_sent_to_ollama(self, mock_post):
        mock_post.return_value.json.return_value = {
            "message": {"content": {"redactions": []}}
        }
        LLMPromptSettings.objects.create(
            pk=1, system_prompt="custom instructions"
        )
        with override_settings(
            OLLAMA_ENABLED="true",
            OLLAMA_HOST="http://ollama:11434",
            OLLAMA_MODEL="gemma4:e4b",
        ):
            extract_with_gemma("Some text.", "Jane Doe")

        call_body = mock_post.call_args[1]["json"]
        system_message = next(
            m for m in call_body["messages"] if m["role"] == "system"
        )
        self.assertEqual(system_message["content"], "custom instructions")


class ChunkTextTests(TestCase):
    def test_short_text_returned_as_single_chunk(self):
        text = "Short text."
        chunks = _chunk_text(text, chunk_size=100, overlap=10)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], (text, 0))

    def test_long_text_splits_into_multiple_chunks(self):
        text = "a" * 500
        chunks = _chunk_text(text, chunk_size=200, overlap=50)
        self.assertGreater(len(chunks), 1)

    def test_chunk_offsets_are_correct(self):
        text = "a" * 500
        chunks = _chunk_text(text, chunk_size=200, overlap=50)
        step = 200 - 50
        for i, (chunk, offset) in enumerate(chunks):
            self.assertEqual(offset, i * step)

    def test_overlap_region_present_in_consecutive_chunks(self):
        text = "abcdefghij"  # 10 chars
        chunks = _chunk_text(text, chunk_size=6, overlap=2)
        # chunk 0: text[0:6], chunk 1: text[4:10]
        self.assertEqual(chunks[0][0], "abcdef")
        self.assertEqual(chunks[1][0], "efghij")
        self.assertEqual(chunks[1][1], 4)


class GemmaChunkingTests(NetworkBlockerMixin, TestCase):
    OLLAMA_SETTINGS = dict(
        OLLAMA_ENABLED="true",
        OLLAMA_HOST="http://ollama:11434",
        OLLAMA_MODEL="gemma4:e4b",
    )

    def _ollama_response(self, redactions):
        mock = type("R", (), {})()
        mock.json = lambda: {
            "message": {"content": {"redactions": redactions}}
        }
        mock.raise_for_status = lambda: None
        return mock

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_large_document_sends_multiple_requests(self, mock_post):
        mock_post.return_value = self._ollama_response([])
        text = "x" * 5000
        with override_settings(
            **self.OLLAMA_SETTINGS,
            OLLAMA_CHUNK_SIZE=2000,
            OLLAMA_CHUNK_OVERLAP=100,
        ):
            extract_with_gemma(text, "Jane Doe")
        self.assertGreater(mock_post.call_count, 1)

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_spans_from_all_chunks_are_returned(self, mock_post):
        # First chunk returns entity at position 10; second chunk returns entity at position 10
        # within that chunk (which maps to a later absolute position).
        chunk_size = 50
        overlap = 10
        # Build text: 'A' * 50 + 'B' * 50 = 100 chars; two chunks with overlap
        text = "A" * chunk_size + "B" * chunk_size

        def side_effect(*args, **kwargs):
            user_msg = kwargs["json"]["messages"][1]["content"]
            if "AAAAAAAAAA" in user_msg:
                return self._ollama_response(
                    [
                        {
                            "text": "AAAAAAAAAA",
                            "reason": "r",
                            "redaction_type": "PII",
                        }
                    ]
                )
            return self._ollama_response(
                [
                    {
                        "text": "BBBBBBBBBB",
                        "reason": "r",
                        "redaction_type": "PII",
                    }
                ]
            )

        mock_post.side_effect = side_effect
        with override_settings(
            **self.OLLAMA_SETTINGS,
            OLLAMA_CHUNK_SIZE=chunk_size,
            OLLAMA_CHUNK_OVERLAP=overlap,
        ):
            results = extract_with_gemma(text, "Jane Doe")

        labels = {r["text"][:1] for r in results}
        self.assertIn("A", labels)
        self.assertIn("B", labels)

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_overlap_does_not_produce_duplicate_spans(self, mock_post):
        # Entity sits in the overlap region — both chunks return it but result should appear once.
        chunk_size = 20
        overlap = 10
        text = "x" * 10 + "ENTITY" + "x" * 10  # ENTITY at position 10–16

        mock_post.return_value = self._ollama_response(
            [{"text": "ENTITY", "reason": "r", "redaction_type": "PII"}]
        )
        with override_settings(
            **self.OLLAMA_SETTINGS,
            OLLAMA_CHUNK_SIZE=chunk_size,
            OLLAMA_CHUNK_OVERLAP=overlap,
        ):
            results = extract_with_gemma(text, "Jane Doe")

        entity_spans = [r for r in results if r["text"] == "ENTITY"]
        positions = {(r["start_char"], r["end_char"]) for r in entity_spans}
        self.assertEqual(len(positions), 1)

    @patch("training.extractors.gemma_extractor.requests.post")
    def test_single_chunk_document_unaffected(self, mock_post):
        mock_post.return_value = self._ollama_response(
            [{"text": "PC Smith", "reason": "r", "redaction_type": "OP_DATA"}]
        )
        text = "The officer PC Smith attended."
        with override_settings(
            **self.OLLAMA_SETTINGS,
            OLLAMA_CHUNK_SIZE=4000,
            OLLAMA_CHUNK_OVERLAP=200,
        ):
            results = extract_with_gemma(text, "Jane Doe")

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["start_char"], text.index("PC Smith"))
