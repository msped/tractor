import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .views import MediaServeView

User = get_user_model()

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MediaServeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="mediauser", password="password"
        )

    def setUp(self):
        self.factory = APIRequestFactory()
        with override_settings(MEDIA_ROOT=MEDIA_ROOT):
            self.file_path = default_storage.save(
                "exports/test-case/package.zip", ContentFile(b"zip-bytes")
            )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _get(self, path, user=None):
        request = self.factory.get(f"/media/{path}")
        if user:
            force_authenticate(request, user=user)
        return MediaServeView.as_view()(request, path=path)

    def test_unauthenticated_request_is_rejected(self):
        response = self._get(self.file_path)
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_returns_file(self):
        response = self._get(self.file_path, user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"zip-bytes")
        self.assertIn("package.zip", response.headers["Content-Disposition"])

    def test_missing_file_returns_404(self):
        response = self._get("exports/nope/missing.zip", user=self.user)
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_returns_404(self):
        response = self._get("../../etc/passwd", user=self.user)
        self.assertEqual(response.status_code, 404)
