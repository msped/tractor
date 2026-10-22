import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from training.models import Model
from training.tests.base import NetworkBlockerMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_collect"))
class DownloadModelCommandTests(NetworkBlockerMixin, TestCase):
    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_default_model_downloaded_and_saved(
        self, mock_gliner_cls, mock_makedirs
    ):
        """Running download_model with defaults downloads and saves the medium model locally."""
        mock_instance = MagicMock()
        mock_gliner_cls.from_pretrained.return_value = mock_instance

        call_command("download_model")

        mock_gliner_cls.from_pretrained.assert_called_once_with(
            "urchade/gliner_medium-v2.1"
        )
        mock_instance.save_pretrained.assert_called_once()
        saved_path = mock_instance.save_pretrained.call_args[0][0]
        self.assertIn("urchade_gliner_medium_v2_1", saved_path)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_custom_name_argument(self, mock_gliner_cls, mock_makedirs):
        """--name argument downloads the specified model and saves to a matching local path."""
        mock_instance = MagicMock()
        mock_gliner_cls.from_pretrained.return_value = mock_instance

        call_command("download_model", name="urchade/gliner_large-v2.1")

        mock_gliner_cls.from_pretrained.assert_called_once_with(
            "urchade/gliner_large-v2.1"
        )
        saved_path = mock_instance.save_pretrained.call_args[0][0]
        self.assertIn("urchade_gliner_large_v2_1", saved_path)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_does_not_register_in_db(self, mock_gliner_cls, mock_makedirs):
        """download_model does not create or modify any Model DB entries."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        call_command("download_model")

        self.assertEqual(Model.objects.count(), 0)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_output_messages_written(self, mock_gliner_cls, mock_makedirs):
        """Success messages are written to stdout."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        stdout = StringIO()
        call_command("download_model", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Downloading GLiNER model", output)
        self.assertIn("Saved to", output)
