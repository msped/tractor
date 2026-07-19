import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..diff import diff_disclosure
from ..models import (
    Case,
    Document,
    Export,
    Redaction,
    RedactionContext,
)
from ..snapshots import snapshot_redactions

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DiffDisclosureTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.case = Case.objects.create(
            case_reference="250001",
            data_subject_name="John Doe",
            data_subject_dob=date(1990, 1, 1),
            created_by=self.user,
        )
        self.document = Document.objects.create(
            case=self.case,
            original_file=SimpleUploadedFile("doc.txt", b"hello world"),
            filename="doc.txt",
            file_type=".txt",
            status=Document.Status.COMPLETED,
            extracted_text="Alice met Bob in London on 2020-01-01.",
        )

    def _make_redaction(self, **overrides):
        defaults = {
            "document": self.document,
            "start_char": 0,
            "end_char": 5,
            "text": "Alice",
            "redaction_type": Redaction.RedactionType.THIRD_PARTY_PII,
            "is_suggestion": True,
            "is_accepted": True,
            "decided_by": Redaction.DecidedBy.HUMAN,
            "source": Redaction.Source.NER,
        }
        defaults.update(overrides)
        return Redaction.objects.create(**defaults)

    # ---- no baseline ----

    def test_no_snapshot_returns_none(self):
        self._make_redaction()
        self.assertIsNone(diff_disclosure(self.case))

    def test_no_changes_since_snapshot(self):
        self._make_redaction()
        snapshot_redactions(self.case)

        diff = diff_disclosure(self.case)
        self.assertEqual(
            diff["counts"], {"added": 0, "removed": 0, "modified": 0}
        )
        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])
        self.assertEqual(diff["modified"], [])

    # ---- edit types ----

    def test_added_redaction(self):
        snapshot_redactions(self.case)
        added = self._make_redaction(
            text="Bob",
            start_char=10,
            end_char=13,
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )

        diff = diff_disclosure(self.case)
        self.assertEqual(diff["counts"]["added"], 1)
        entry = diff["added"][0]
        self.assertEqual(entry["id"], str(added.id))
        self.assertEqual(entry["text"], "Bob")
        self.assertEqual(entry["filename"], "doc.txt")
        self.assertEqual(diff["removed"], [])
        self.assertEqual(diff["modified"], [])

    def test_removed_redaction(self):
        redaction = self._make_redaction()
        snapshot_redactions(self.case)
        redaction_id = str(redaction.id)
        redaction.delete()

        diff = diff_disclosure(self.case)
        self.assertEqual(diff["counts"]["removed"], 1)
        entry = diff["removed"][0]
        self.assertEqual(entry["id"], redaction_id)
        self.assertEqual(entry["text"], "Alice")
        self.assertEqual(entry["filename"], "doc.txt")

    def test_modified_flip_reports_decision_change(self):
        redaction = self._make_redaction(is_accepted=True)
        snapshot_redactions(self.case)
        Redaction.objects.filter(pk=redaction.pk).reject(
            "not needed", by=Redaction.DecidedBy.HUMAN
        )

        diff = diff_disclosure(self.case)
        self.assertEqual(diff["counts"]["modified"], 1)
        entry = diff["modified"][0]
        self.assertEqual(entry["id"], str(redaction.id))
        self.assertEqual(
            entry["changes"]["is_accepted"], {"from": True, "to": False}
        )
        self.assertEqual(
            entry["changes"]["justification"],
            {"from": None, "to": "not needed"},
        )

    def test_modified_rebound_and_retype(self):
        redaction = self._make_redaction(start_char=0, end_char=5)
        snapshot_redactions(self.case)
        redaction.start_char = 10
        redaction.end_char = 13
        redaction.redaction_type = Redaction.RedactionType.OPERATIONAL_DATA
        redaction.save()

        diff = diff_disclosure(self.case)
        changes = diff["modified"][0]["changes"]
        self.assertEqual(changes["start_char"], {"from": 0, "to": 10})
        self.assertEqual(changes["end_char"], {"from": 5, "to": 13})
        self.assertEqual(
            changes["redaction_type"],
            {
                "from": Redaction.RedactionType.THIRD_PARTY_PII,
                "to": Redaction.RedactionType.OPERATIONAL_DATA,
            },
        )

    def test_modified_context_change(self):
        redaction = self._make_redaction()
        RedactionContext.objects.create(
            redaction=redaction, text="the suspect"
        )
        snapshot_redactions(self.case)
        redaction.context.text = "a witness"
        redaction.context.save()

        diff = diff_disclosure(self.case)
        self.assertEqual(
            diff["modified"][0]["changes"]["context"],
            {"from": "the suspect", "to": "a witness"},
        )

    # ---- baseline metadata / scoping ----

    def test_diffs_against_latest_snapshot(self):
        self._make_redaction(text="Alice")
        snapshot_redactions(self.case)
        # A second, later snapshot becomes the baseline.
        second = self._make_redaction(text="Bob", start_char=10, end_char=13)
        latest = snapshot_redactions(self.case)
        # Now delete Bob after the latest snapshot.
        second.delete()

        diff = diff_disclosure(self.case)
        self.assertEqual(diff["snapshot"]["id"], str(latest.id))
        # Only the change since the latest snapshot is reported.
        self.assertEqual(diff["counts"]["removed"], 1)
        self.assertEqual(diff["counts"]["added"], 0)

    def test_snapshot_metadata_includes_export(self):
        export = Export.objects.create(
            case=self.case,
            export_file=SimpleUploadedFile("d.zip", b"zip"),
            sequence=1,
            label="Original disclosure",
        )
        self._make_redaction()
        snapshot = snapshot_redactions(self.case)
        snapshot.export = export
        snapshot.save(update_fields=["export"])

        diff = diff_disclosure(self.case)
        self.assertEqual(
            diff["snapshot"]["export"],
            {"sequence": 1, "label": "Original disclosure"},
        )

    def test_snapshot_metadata_export_none_when_unlinked(self):
        self._make_redaction()
        snapshot_redactions(self.case)

        diff = diff_disclosure(self.case)
        self.assertIsNone(diff["snapshot"]["export"])

    def test_ignores_other_cases(self):
        self._make_redaction()
        snapshot_redactions(self.case)

        other_case = Case.objects.create(
            case_reference="250002", data_subject_name="Jane Roe"
        )
        other_doc = Document.objects.create(
            case=other_case,
            original_file=SimpleUploadedFile("o.txt", b"x"),
            filename="o.txt",
            file_type=".txt",
        )
        Redaction.objects.create(
            document=other_doc,
            start_char=0,
            end_char=1,
            text="x",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=False,
        )

        diff = diff_disclosure(self.case)
        self.assertEqual(
            diff["counts"], {"added": 0, "removed": 0, "modified": 0}
        )
