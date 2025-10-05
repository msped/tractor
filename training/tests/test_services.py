import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase

from ..services import extract_entities_from_text
from .base import NetworkBlockerMixin


class MockSpan:
    """A simple mock for a spaCy Span object."""

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
    def test_extract_entities_from_text_success(
        self, mock_model_manager, mock_spacy_layout
    ):
        """
        Test successful entity extraction.
        """
        mock_nlp = MagicMock()
        mock_doc_with_ents = MagicMock()
        mock_doc_with_ents.ents = [
            MockSpan("John Doe", "PERSON", 12, 20),
            MockSpan("London", "GPE", 35, 41),
        ]
        mock_nlp.return_value = mock_doc_with_ents

        mock_manager_instance = mock_model_manager.get_instance.return_value
        mock_manager_instance.get_model.return_value = mock_nlp

        mock_layout_instance = MagicMock()
        mock_layout_doc = MagicMock()
        mock_layout_doc.text = "Hello, I'm John Doe and I live in London."
        mock_layout_instance.return_value = mock_layout_doc
        mock_spacy_layout.return_value = mock_layout_instance

        extracted_text, results = extract_entities_from_text(self.file_path)

        self.assertEqual(
            extracted_text, "Hello, I'm John Doe and I live in London."
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["text"], "John Doe")
        self.assertEqual(results[0]["label"], "PERSON")
        self.assertEqual(results[1]["text"], "London")
        self.assertEqual(results[1]["label"], "GPE")

        mock_model_manager.get_instance.assert_called_once()
        mock_manager_instance.get_model.assert_called_once()
        mock_spacy_layout.assert_called_once_with(mock_nlp)
        mock_layout_instance.assert_called_once_with(self.file_path)
        mock_nlp.assert_called_once_with(
            "Hello, I'm John Doe and I live in London.")

    @patch("training.services.SpacyModelManager")
    def test_extract_entities_no_model_found(self, mock_model_manager):
        """
        Test that a ValueError is raised if no active model is found.
        """
        mock_model_manager.get_instance.return_value.get_model.return_value = \
            None

        with self.assertRaisesMessage(ValueError,
                                      "No active spaCy model found."):
            extract_entities_from_text(self.file_path)

    @patch("training.services.spaCyLayout")
    @patch("training.services.SpacyModelManager")
    def test_extract_entities_no_text_in_document(
        self, mock_model_manager, mock_spacy_layout
    ):
        """
        Test that a ValueError is raised if the document contains no text.
        """
        mock_nlp = MagicMock()
        mock_model_manager.get_instance.return_value.get_model.return_value = \
            mock_nlp

        mock_layout_instance = MagicMock()
        mock_layout_doc = MagicMock()
        mock_layout_doc.text = ""
        mock_layout_instance.return_value = mock_layout_doc
        mock_spacy_layout.return_value = mock_layout_instance

        with self.assertRaisesMessage(ValueError,
                                      "No text found in the document."):
            extract_entities_from_text(self.file_path)
