from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..loader import (
    DEFAULT_GLINER_MODEL,
    GLiNERModelManager,
    SpanCatModelManager,
    _get_device,
)
from ..models import Model
from .base import NetworkBlockerMixin


class GetDeviceTests(TestCase):
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.backends.mps.is_available", return_value=False)
    def test_returns_cuda_when_available(self, mock_mps, mock_cuda):
        self.assertEqual(_get_device(), "cuda")

    @patch("torch.cuda.is_available", return_value=False)
    @patch("torch.backends.mps.is_available", return_value=True)
    def test_returns_mps_when_cuda_unavailable(self, mock_mps, mock_cuda):
        self.assertEqual(_get_device(), "mps")

    @patch("torch.cuda.is_available", return_value=False)
    @patch("torch.backends.mps.is_available", return_value=False)
    def test_returns_cpu_as_fallback(self, mock_mps, mock_cuda):
        self.assertEqual(_get_device(), "cpu")

    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.backends.mps.is_available", return_value=True)
    def test_cuda_takes_priority_over_mps(self, mock_mps, mock_cuda):
        self.assertEqual(_get_device(), "cuda")



class GLiNERModelManagerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        GLiNERModelManager._instance = None

    @patch("training.loader._load_gliner_model")
    def test_get_instance_is_singleton(self, mock_load):
        instance1 = GLiNERModelManager.get_instance()
        instance2 = GLiNERModelManager.get_instance()
        self.assertIs(instance1, instance2)

    @patch("training.loader._load_gliner_model")
    def test_initialization_does_not_load_from_db(self, mock_load):
        """GLiNER is not tracked in the DB — init never calls _load_gliner_model."""
        GLiNERModelManager.get_instance()
        mock_load.assert_not_called()

    @patch("training.loader.os.path.isdir", return_value=False)
    @patch("training.loader._load_gliner_model")
    def test_get_model_loads_default(self, mock_load, mock_isdir):
        """get_model() falls back to DEFAULT_GLINER_MODEL when local path is absent."""
        mock_model = MagicMock()
        mock_load.return_value = mock_model

        manager = GLiNERModelManager.get_instance()
        result = manager.get_model()

        mock_load.assert_called_once_with(DEFAULT_GLINER_MODEL)
        self.assertIs(result, mock_model)
        self.assertEqual(manager.model_name, DEFAULT_GLINER_MODEL)

    @patch("training.loader._load_gliner_model")
    def test_get_model_returns_cached_model(self, mock_load):
        """get_model() returns the cached model without reloading."""
        mock_load.return_value = MagicMock()

        manager = GLiNERModelManager.get_instance()
        manager.get_model()
        manager.get_model()

        mock_load.assert_called_once()

    @patch("training.loader._load_gliner_model")
    def test_switch_model(self, mock_load):
        """switch_model() loads the named model from its DB path."""
        model_entry = Model.objects.create(
            name="custom_gliner", path="/path/to/custom"
        )

        manager = GLiNERModelManager.get_instance()
        manager.switch_model("custom_gliner")

        mock_load.assert_called_with("/path/to/custom")
        self.assertEqual(manager.model_name, "custom_gliner")
        model_entry.refresh_from_db()
        self.assertTrue(model_entry.is_active)


class SpanCatModelManagerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        SpanCatModelManager._instance = None

    @patch("training.loader._load_spancat_model")
    def test_get_instance_is_singleton(self, mock_load):
        instance1 = SpanCatModelManager.get_instance()
        instance2 = SpanCatModelManager.get_instance()
        self.assertIs(instance1, instance2)

    @patch("training.loader._load_spancat_model")
    def test_initialization_loads_active_model(self, mock_load):
        """Manager loads the active SpanCat model on init."""
        mock_nlp = MagicMock()
        mock_load.return_value = mock_nlp

        active_model = Model.objects.create(
            name="spancat_v1", path="/path/to/spancat_v1", is_active=True
        )

        manager = SpanCatModelManager.get_instance()

        mock_load.assert_called_once_with(active_model.path)
        self.assertEqual(manager.model_name, active_model.name)
        self.assertIs(manager.model, mock_nlp)

    @patch("training.loader._load_spancat_model")
    def test_get_model_returns_none_when_no_model_trained(self, mock_load):
        """get_model() returns None gracefully if no SpanCat model exists."""
        Model.objects.all().delete()

        manager = SpanCatModelManager.get_instance()
        result = manager.get_model()

        self.assertIsNone(result)
        mock_load.assert_not_called()

    @patch("training.loader._load_spancat_model")
    def test_get_model_returns_cached_model(self, mock_load):
        """get_model() returns cached model without reloading."""
        Model.objects.create(
            name="spancat_v1", path="/path/to/spancat_v1", is_active=True
        )

        manager = SpanCatModelManager.get_instance()
        self.assertEqual(mock_load.call_count, 1)

        manager.get_model()
        self.assertEqual(mock_load.call_count, 1)

    @patch("training.loader._load_spancat_model")
    def test_switch_model(self, mock_load):
        """Test switching to a different SpanCat model."""
        active_model = Model.objects.create(
            name="spancat_v1", path="/path/to/spancat_v1", is_active=True
        )
        inactive_model = Model.objects.create(
            name="spancat_v2", path="/path/to/spancat_v2", is_active=False
        )

        manager = SpanCatModelManager.get_instance()
        mock_load.assert_called_once_with(active_model.path)

        manager.switch_model("spancat_v2")

        mock_load.assert_called_with(inactive_model.path)
        self.assertEqual(mock_load.call_count, 2)
        self.assertEqual(manager.model_name, "spancat_v2")

        active_model.refresh_from_db()
        inactive_model.refresh_from_db()
        self.assertFalse(active_model.is_active)
        self.assertTrue(inactive_model.is_active)

    @patch("training.loader._load_spancat_model")
    def test_no_active_model_on_init(self, mock_load):
        """No model loaded during init if no active SpanCat model."""
        Model.objects.all().delete()

        manager = SpanCatModelManager.get_instance()

        self.assertIsNone(manager.model)
        self.assertIsNone(manager.model_name)
        self.assertIsNone(manager.model_entry)
        mock_load.assert_not_called()
