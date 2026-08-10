import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .exception_handler import api_exception_handler
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

    def test_directory_path_returns_404(self):
        # A directory (or empty) path must 404, not 500 on IsADirectoryError.
        for path in ("exports/test-case", "exports/test-case/", ""):
            response = self._get(path, user=self.user)
            self.assertEqual(response.status_code, 404)


class ApiExceptionHandlerTests(TestCase):
    """The handler guarantees a `detail` key so the frontend can always show a
    real reason instead of its generic fallback."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.context = {
            "view": MediaServeView(),
            "request": self.factory.get("/api/thing"),
        }

    def test_unhandled_exception_returns_500_with_reference(self):
        with self.assertLogs("backend.exception_handler", "ERROR") as logs:
            response = api_exception_handler(
                RuntimeError("boom"), self.context
            )

        self.assertEqual(response.status_code, 500)
        reference = response.data["reference"]
        self.assertEqual(len(reference), 8)
        # The reference ties the user-facing message to the logged traceback.
        self.assertIn(reference, response.data["detail"])
        self.assertIn(reference, logs.output[0])
        self.assertIn("RuntimeError: boom", logs.output[0])

    def test_handled_4xx_keeps_detail_and_logs_at_info(self):
        with self.assertLogs("backend.exception_handler", "INFO") as logs:
            response = api_exception_handler(
                NotFound("No such case."), self.context
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "No such case.")
        self.assertIn("404", logs.output[0])

    def test_field_validation_error_gains_detail(self):
        with self.assertLogs("backend.exception_handler", "INFO"):
            response = api_exception_handler(
                ValidationError({"name": ["This field is required."]}),
                self.context,
            )

        self.assertEqual(response.status_code, 400)
        # Per-field data is preserved for forms; `detail` is added alongside.
        self.assertEqual(response.data["name"], ["This field is required."])
        self.assertEqual(response.data["detail"], "This field is required.")

    def test_non_dict_error_body_is_left_alone(self):
        with self.assertLogs("backend.exception_handler", "INFO"):
            response = api_exception_handler(
                ValidationError(["Bad request."]), self.context
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, ["Bad request."])

    def test_handled_5xx_logs_with_traceback(self):
        with self.assertLogs("backend.exception_handler", "ERROR") as logs:
            response = api_exception_handler(
                APIException("Upstream is down."), self.context
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Upstream is down.", logs.output[0])
