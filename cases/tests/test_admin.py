import shutil
import tempfile
from datetime import date

from auditlog.models import LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..admin import (
    AuditLogEntryAdmin,
    CaseAdmin,
    DocumentAdmin,
    ExemptionTemplateAdmin,
    RedactionAdmin,
)
from ..models import Case, Document, ExemptionTemplate, Redaction

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SuperuserDeleteMixinTests(NetworkBlockerMixin, TestCase):
    """
    Tests that deletion is restricted to superusers across all admin classes.
    """

    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

        self.staff_user = User.objects.create_user(
            username="staff", password="password", is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username="super", password="password"
        )

        self.case = Case.objects.create(
            case_reference="ADM001",
            data_subject_name="Test Subject",
            data_subject_dob=date(1990, 1, 1),
            created_by=self.staff_user,
        )

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _make_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_staff_cannot_delete_case(self):
        admin = CaseAdmin(Case, self.site)
        request = self._make_request(self.staff_user)
        self.assertFalse(admin.has_delete_permission(request, self.case))

    def test_superuser_can_delete_case(self):
        admin = CaseAdmin(Case, self.site)
        request = self._make_request(self.superuser)
        self.assertTrue(admin.has_delete_permission(request, self.case))

    def test_staff_cannot_delete_document(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("f.pdf", b"content"),
        )
        admin = DocumentAdmin(Document, self.site)
        request = self._make_request(self.staff_user)
        self.assertFalse(admin.has_delete_permission(request, doc))

    def test_superuser_can_delete_document(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("f.pdf", b"content"),
        )
        admin = DocumentAdmin(Document, self.site)
        request = self._make_request(self.superuser)
        self.assertTrue(admin.has_delete_permission(request, doc))

    def test_staff_cannot_delete_redaction(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("f.pdf", b"content"),
        )
        redaction = Redaction.objects.create(
            document=doc,
            start_char=0,
            end_char=3,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        admin = RedactionAdmin(Redaction, self.site)
        request = self._make_request(self.staff_user)
        self.assertFalse(admin.has_delete_permission(request, redaction))

    def test_superuser_can_delete_redaction(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("f.pdf", b"content"),
        )
        redaction = Redaction.objects.create(
            document=doc,
            start_char=0,
            end_char=3,
            text="PII",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
        )
        admin = RedactionAdmin(Redaction, self.site)
        request = self._make_request(self.superuser)
        self.assertTrue(admin.has_delete_permission(request, redaction))

    def test_staff_cannot_delete_exemption_template(self):
        template = ExemptionTemplate.objects.create(name="S.40")
        admin = ExemptionTemplateAdmin(ExemptionTemplate, self.site)
        request = self._make_request(self.staff_user)
        self.assertFalse(admin.has_delete_permission(request, template))

    def test_superuser_can_delete_exemption_template(self):
        template = ExemptionTemplate.objects.create(name="S.40")
        admin = ExemptionTemplateAdmin(ExemptionTemplate, self.site)
        request = self._make_request(self.superuser)
        self.assertTrue(admin.has_delete_permission(request, template))


class AuditLogEntryAdminTests(NetworkBlockerMixin, TestCase):
    """
    Tests that the audit log is read-only and deletion is superuser-only.
    """

    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()

        self.staff_user = User.objects.create_user(
            username="staff", password="password", is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username="super", password="password"
        )
        self.admin = AuditLogEntryAdmin(LogEntry, self.site)

    def _make_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_staff_cannot_delete_log_entry(self):
        request = self._make_request(self.staff_user)
        self.assertFalse(self.admin.has_delete_permission(request))

    def test_superuser_can_delete_log_entry(self):
        request = self._make_request(self.superuser)
        self.assertTrue(self.admin.has_delete_permission(request))

    def test_nobody_can_add_log_entry(self):
        for user in (self.staff_user, self.superuser):
            request = self._make_request(user)
            self.assertFalse(self.admin.has_add_permission(request))

    def test_nobody_can_change_log_entry(self):
        for user in (self.staff_user, self.superuser):
            request = self._make_request(user)
            self.assertFalse(self.admin.has_change_permission(request))
