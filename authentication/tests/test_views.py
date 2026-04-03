import hashlib

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from training.tests.base import NetworkBlockerMixin

from ..models import APIKey

User = get_user_model()


class APIKeyListCreateViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.superuser = User.objects.create_user(
            username="superuser", password="password", is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="password", is_staff=False
        )
        self.service_user = User.objects.get(username="api_service")
        self.url = reverse("api-key-list-create")

    def test_list_returns_active_keys_for_admin(self):
        self.client.force_authenticate(user=self.admin)
        APIKey.generate(
            description="Key 1", created_by=self.admin, user=self.service_user
        )
        APIKey.generate(
            description="Key 2", created_by=self.admin, user=self.service_user
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_excludes_revoked_keys(self):
        self.client.force_authenticate(user=self.admin)
        instance, _ = APIKey.generate(
            description="Revoked key",
            created_by=self.admin,
            user=self.service_user,
        )
        instance.is_active = False
        instance.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_allowed_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_allowed_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(self.url, {"description": "Superuser key"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("key", response.data)

    def test_list_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_returns_201_with_key_for_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.url, {"description": "My integration"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("key", response.data)
        self.assertIn("id", response.data)
        self.assertIn("description", response.data)
        self.assertEqual(response.data["description"], "My integration")

    def test_create_key_not_stored_in_plaintext(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"description": "Test"})
        raw_key = response.data["key"]
        api_key = APIKey.objects.get(id=response.data["id"])
        self.assertNotEqual(api_key.key_hash, raw_key)
        self.assertEqual(
            api_key.key_hash, hashlib.sha256(raw_key.encode()).hexdigest()
        )

    def test_create_sets_created_by_to_requesting_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"description": "Test"})
        api_key = APIKey.objects.get(id=response.data["id"])
        self.assertEqual(api_key.created_by, self.admin)

    def test_create_sets_user_to_service_account(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"description": "Test"})
        api_key = APIKey.objects.get(id=response.data["id"])
        self.assertEqual(api_key.user, self.service_user)

    def test_create_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.url, {"description": "Test"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_requires_description(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class APIKeyRevokeViewTests(NetworkBlockerMixin, APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="password", is_staff=False
        )
        self.service_user = User.objects.get(username="api_service")
        self.instance, _ = APIKey.generate(
            description="Revoke me",
            created_by=self.admin,
            user=self.service_user,
        )

    def _url(self, key_id):
        return reverse("api-key-revoke", kwargs={"key_id": key_id})

    def test_revoke_sets_is_active_false(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self._url(self.instance.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.instance.refresh_from_db()
        self.assertFalse(self.instance.is_active)

    def test_revoke_already_revoked_returns_404(self):
        self.instance.is_active = False
        self.instance.save()
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self._url(self.instance.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_revoke_nonexistent_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self._url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_revoke_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(self._url(self.instance.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class APIKeyAuthenticationTests(NetworkBlockerMixin, APITestCase):
    """Tests that the APIKeyAuthentication class works end-to-end."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.service_user = User.objects.get(username="api_service")
        self.instance, self.raw_key = APIKey.generate(
            description="Test auth key",
            created_by=self.admin,
            user=self.service_user,
        )
        # Use the cases list endpoint to test end-to-end authentication
        self.cases_url = reverse("case-list-create")

    def test_valid_api_key_authenticates_request(self):
        response = self.client.get(
            self.cases_url,
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_api_key_returns_401(self):
        response = self.client.get(
            self.cases_url,
            HTTP_AUTHORIZATION="Api-Key invalidkeyvalue",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_revoked_api_key_returns_401(self):
        self.instance.is_active = False
        self.instance.save()
        response = self.client.get(
            self.cases_url,
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_key_creates_case_attributed_to_service_user(self):
        response = self.client.post(
            self.cases_url,
            {
                "case_reference": "TEST01",
                "data_subject_name": "Jane Smith",
            },
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        from cases.models import Case

        case = Case.objects.get(case_reference="TEST01")
        self.assertEqual(case.created_by, self.service_user)

    def test_jwt_still_works_when_api_key_auth_class_is_present(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.cases_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_key_cannot_manage_api_keys(self):
        """API keys auth as api_service (non-staff) so cannot create/list keys."""
        url = reverse("api-key-list-create")
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
