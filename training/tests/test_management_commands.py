from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from training.models import Model
from training.tests.base import NetworkBlockerMixin


class DownloadModelCommandTests(NetworkBlockerMixin, TestCase):
    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_default_model_registered_as_active(self, mock_gliner_cls, mock_makedirs):
        """Running download_model with defaults creates and activates the medium model."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        call_command("download_model")

        model = Model.objects.get(name="urchade_gliner_medium_v2_1")
        self.assertTrue(model.is_active)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_custom_name_argument(self, mock_gliner_cls, mock_makedirs):
        """--name argument is slugified and stored as the model name."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        call_command("download_model", name="urchade/gliner_large-v2.1")

        model = Model.objects.get(name="urchade_gliner_large_v2_1")
        self.assertTrue(model.is_active)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_previous_active_model_deactivated(self, mock_gliner_cls, mock_makedirs):
        """An existing active model is deactivated before registering the new one."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        old_model = Model.objects.create(name="old_model", path="/old/path", is_active=True)

        call_command("download_model")

        old_model.refresh_from_db()
        self.assertFalse(old_model.is_active)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_update_or_create_for_existing_name(self, mock_gliner_cls, mock_makedirs):
        """Re-running with the same name updates the existing record instead of creating a duplicate."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        Model.objects.create(name="urchade_gliner_medium_v2_1", path="/some/old/path")

        call_command("download_model")

        self.assertEqual(Model.objects.filter(name="urchade_gliner_medium_v2_1").count(), 1)
        self.assertTrue(Model.objects.get(name="urchade_gliner_medium_v2_1").is_active)

    @patch("training.management.commands.download_model.os.makedirs")
    @patch("gliner.GLiNER")
    def test_output_messages_written(self, mock_gliner_cls, mock_makedirs):
        """Success messages are written to stdout."""
        mock_gliner_cls.from_pretrained.return_value = MagicMock()

        stdout = StringIO()
        call_command("download_model", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Downloading GLiNER model", output)
        self.assertIn("Registering as active model", output)
