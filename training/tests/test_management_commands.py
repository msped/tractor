import tempfile
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from training.models import Model, TrainingControl
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


class TrainSpancatCommandTests(NetworkBlockerMixin, TestCase):
    """
    Training as a command rather than a queued task: no per-task timeout to
    kill a long run, no broker re-delivering it while it is still going, and
    no worker to restart before a code change takes effect.
    """

    @patch("training.tasks.train_model")
    def test_runs_training_in_this_process(self, train_model):
        call_command("train_spancat")

        train_model.assert_called_once_with(source="training_docs")

    @patch("training.tasks.train_model")
    def test_source_can_be_chosen(self, train_model):
        call_command("train_spancat", source="both")

        train_model.assert_called_once_with(source="both")

    @patch("training.tasks.train_model")
    def test_the_span_ceiling_can_be_overridden_for_one_run(self, train_model):
        call_command("train_spancat", max_span_tokens=48)

        self.assertEqual(settings.SPANCAT_MAX_SPAN_TOKENS, 48)

    @patch("training.tasks.train_model")
    def test_refuses_to_start_alongside_a_running_job(self, train_model):
        control = TrainingControl.get()
        control.started_at = timezone.now()
        control.heartbeat_at = timezone.now()
        control.pid = 1234
        control.save()

        with self.assertRaises(CommandError):
            call_command("train_spancat")

        train_model.assert_not_called()

    @patch("training.tasks.train_model")
    def test_force_overrides_a_run_that_is_known_to_be_dead(self, train_model):
        control = TrainingControl.get()
        control.started_at = timezone.now()
        control.heartbeat_at = timezone.now()
        control.pid = 1234
        control.save()

        call_command("train_spancat", force=True)

        train_model.assert_called_once()

    @patch("training.tasks.train_model")
    def test_an_abandoned_run_does_not_block_a_new_one(self, train_model):
        control = TrainingControl.get()
        control.started_at = timezone.now() - timedelta(hours=3)
        control.heartbeat_at = timezone.now() - timedelta(hours=3)
        control.pid = 1234
        control.save()

        call_command("train_spancat")

        train_model.assert_called_once()
