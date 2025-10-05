from unittest.mock import patch, MagicMock
from django.test import TestCase
from ..models import Model
from ..loader import SpacyModelManager
from .base import NetworkBlockerMixin


class SpacyModelManagerTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        """
        Reset the singleton instance before each test to ensure isolation.
        """
        SpacyModelManager._instance = None

    @patch("training.loader.spacy.load")
    def test_get_instance_is_singleton(self, mock_spacy_load):
        """Test that get_instance() always returns the same object."""
        instance1 = SpacyModelManager.get_instance()
        instance2 = SpacyModelManager.get_instance()
        self.assertIs(instance1, instance2)

    @patch("training.loader.spacy.load")
    def test_initialization_loads_active_model(self, mock_spacy_load):
        """
        Test that the manager loads the active model from the DB on init.
        """
        mock_model_object = MagicMock()
        mock_spacy_load.return_value = mock_model_object

        active_model = Model.objects.create(
            name="active_model", path="/path/to/active", is_active=True
        )
        Model.objects.create(
            name="inactive_model", path="/path/to/inactive", is_active=False
        )

        manager = SpacyModelManager.get_instance()

        mock_spacy_load.assert_called_once_with(active_model.path)
        self.assertEqual(manager.model_name, active_model.name)
        self.assertEqual(manager.model_entry, active_model)
        self.assertIs(manager.model, mock_model_object)

    @patch("training.loader.spacy.load")
    def test_get_model_returns_loaded_model(self, mock_spacy_load):
        """
        Test that get_model() returns the already loaded
        model without reloading.
        """
        Model.objects.create(
            name="active_model", path="/path/to/active", is_active=True
        )

        manager = SpacyModelManager.get_instance()
        self.assertEqual(mock_spacy_load.call_count, 1)

        # Call get_model again and assert spacy.load was not called again
        manager.get_model()
        self.assertEqual(mock_spacy_load.call_count, 1)

    @patch("training.loader.spacy.load")
    def test_switch_model(self, mock_spacy_load):
        """Test switching to a different model."""
        active_model = Model.objects.create(
            name="active_model", path="/path/to/active", is_active=True
        )
        inactive_model = Model.objects.create(
            name="inactive_model", path="/path/to/inactive", is_active=False
        )

        manager = SpacyModelManager.get_instance()

        # Initial load
        mock_spacy_load.assert_called_once_with(active_model.path)
        self.assertEqual(manager.model_name, "active_model")

        # Switch to the inactive model
        manager.switch_model("inactive_model")

        # Check that the new model was loaded
        mock_spacy_load.assert_called_with(inactive_model.path)
        self.assertEqual(mock_spacy_load.call_count, 2)
        self.assertEqual(manager.model_name, "inactive_model")

        # Check that the DB state was updated
        active_model.refresh_from_db()
        inactive_model.refresh_from_db()
        self.assertFalse(active_model.is_active)
        self.assertTrue(inactive_model.is_active)

    @patch("training.loader.spacy.load")
    def test_no_active_model_on_init(self, mock_spacy_load):
        """
        Test that no model is loaded if no active model exists in the DB.
        """

        Model.objects.all().delete()

        manager = SpacyModelManager.get_instance()

        self.assertIsNone(manager.model)
        self.assertIsNone(manager.model_name)
        self.assertIsNone(manager.model_entry)
