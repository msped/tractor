import hashlib

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import APIKey

User = get_user_model()


class APIKeyModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.service_user = User.objects.get(username="api_service")

    def test_generate_returns_instance_and_raw_key(self):
        instance, raw_key = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        self.assertIsInstance(instance, APIKey)
        self.assertIsNotNone(raw_key)
        self.assertTrue(len(raw_key) > 0)

    def test_generate_stores_hash_not_plaintext(self):
        instance, raw_key = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self.assertEqual(instance.key_hash, expected_hash)
        self.assertNotEqual(instance.key_hash, raw_key)

    def test_generate_key_is_active_by_default(self):
        instance, _ = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        self.assertTrue(instance.is_active)

    def test_generate_sets_created_by(self):
        instance, _ = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        self.assertEqual(instance.created_by, self.admin)

    def test_generate_sets_user_to_service_account(self):
        instance, _ = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        self.assertEqual(instance.user, self.service_user)

    def test_revoked_key_not_returned_by_active_filter(self):
        instance, _ = APIKey.generate(
            description="Test key",
            created_by=self.admin,
            user=self.service_user,
        )
        instance.is_active = False
        instance.save()
        self.assertFalse(APIKey.objects.filter(is_active=True).exists())

    def test_str_representation(self):
        instance, _ = APIKey.generate(
            description="My integration",
            created_by=self.admin,
            user=self.service_user,
        )
        self.assertIn("My integration", str(instance))

    def test_api_service_user_created_by_migration(self):
        self.assertTrue(User.objects.filter(username="api_service").exists())
