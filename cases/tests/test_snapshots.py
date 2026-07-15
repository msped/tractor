import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from training.tests.base import NetworkBlockerMixin

from ..models import (
    Case,
    Document,
    Redaction,
    RedactionContext,
    RedactionSnapshot,
)
from ..snapshots import restore_redactions, snapshot_redactions

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SnapshotTests(NetworkBlockerMixin, TestCase):
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

    def _live_fingerprint(self):
        """
        A comparable, order-independent representation of the live redaction
        set for the case, including RedactionContext.
        """
        rows = []
        for r in Redaction.objects.filter(document__case=self.case):
            context = getattr(r, "context", None)
            rows.append(
                (
                    str(r.id),
                    str(r.document_id),
                    r.start_char,
                    r.end_char,
                    r.text,
                    r.justification,
                    r.redaction_type,
                    r.is_suggestion,
                    r.is_accepted,
                    r.decided_by,
                    r.source,
                    r.created_at.isoformat(),
                    context.text if context is not None else None,
                )
            )
        return sorted(rows)

    # ---- snapshot ----

    def test_snapshot_creates_frozen_row(self):
        self._make_redaction()
        snapshot = snapshot_redactions(self.case)

        self.assertIsInstance(snapshot, RedactionSnapshot)
        self.assertEqual(snapshot.case, self.case)
        self.assertEqual(len(snapshot.payload), 1)
        self.assertEqual(RedactionSnapshot.objects.count(), 1)

    def test_snapshot_captures_all_fields_and_context(self):
        redaction = self._make_redaction(
            justification="manual note",
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
            is_suggestion=False,
            source=Redaction.Source.LLM,
        )
        RedactionContext.objects.create(
            redaction=redaction, text="context blurb"
        )

        snapshot = snapshot_redactions(self.case)
        row = snapshot.payload[0]

        self.assertEqual(row["id"], str(redaction.id))
        self.assertEqual(row["document_id"], str(self.document.id))
        self.assertEqual(row["start_char"], 0)
        self.assertEqual(row["end_char"], 5)
        self.assertEqual(row["text"], "Alice")
        self.assertEqual(row["justification"], "manual note")
        self.assertEqual(
            row["redaction_type"], Redaction.RedactionType.OPERATIONAL_DATA
        )
        self.assertFalse(row["is_suggestion"])
        self.assertTrue(row["is_accepted"])
        self.assertEqual(row["decided_by"], Redaction.DecidedBy.HUMAN)
        self.assertEqual(row["source"], Redaction.Source.LLM)
        self.assertEqual(row["context"], "context blurb")
        self.assertIn("created_at", row)

    def test_snapshot_only_captures_this_case(self):
        self._make_redaction()
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

        snapshot = snapshot_redactions(self.case)
        self.assertEqual(len(snapshot.payload), 1)

    # ---- restore round trip ----

    def test_round_trip_after_arbitrary_edits(self):
        r_flip = self._make_redaction(text="Alice", start_char=0, end_char=5)
        r_rebound = self._make_redaction(
            text="Bob",
            start_char=10,
            end_char=13,
            redaction_type=Redaction.RedactionType.OPERATIONAL_DATA,
        )
        r_deleted = self._make_redaction(
            text="London",
            start_char=17,
            end_char=23,
            is_accepted=False,
            decided_by=None,
        )
        RedactionContext.objects.create(
            redaction=r_rebound, text="the suspect"
        )

        deleted_pk = r_deleted.pk
        original = self._live_fingerprint()
        snapshot = snapshot_redactions(self.case)

        # Mutate the live set every which way.
        Redaction.objects.filter(pk=r_flip.pk).reject(
            "not needed", by=Redaction.DecidedBy.HUMAN
        )
        r_rebound.start_char = 99
        r_rebound.end_char = 102
        r_rebound.redaction_type = Redaction.RedactionType.THIRD_PARTY_PII
        r_rebound.save()
        r_rebound.context.delete()
        r_deleted.delete()
        added = self._make_redaction(
            text="2020-01-01",
            start_char=27,
            end_char=37,
            redaction_type=Redaction.RedactionType.DS_INFORMATION,
        )

        self.assertNotEqual(self._live_fingerprint(), original)

        restore_redactions(self.case, snapshot)

        self.assertEqual(self._live_fingerprint(), original)
        # The row added after the snapshot is gone.
        self.assertFalse(Redaction.objects.filter(pk=added.pk).exists())
        # The deleted row is back with its original identity.
        self.assertTrue(Redaction.objects.filter(pk=deleted_pk).exists())
        # Context is reconstructed exactly.
        self.assertEqual(
            RedactionContext.objects.get(redaction_id=r_rebound.pk).text,
            "the suspect",
        )

    def test_restore_preserves_ids_and_created_at(self):
        redaction = self._make_redaction()
        original_id = redaction.id
        original_created = redaction.created_at
        snapshot = snapshot_redactions(self.case)

        redaction.delete()
        restore_redactions(self.case, snapshot)

        restored = Redaction.objects.get(document__case=self.case)
        self.assertEqual(restored.id, original_id)
        self.assertEqual(restored.created_at, original_created)

    def test_restore_to_empty_snapshot_clears_live_set(self):
        empty = snapshot_redactions(self.case)
        self.assertEqual(empty.payload, [])

        self._make_redaction()
        restore_redactions(self.case, empty)

        self.assertEqual(
            Redaction.objects.filter(document__case=self.case).count(), 0
        )

    def test_restore_leaves_other_cases_untouched(self):
        self._make_redaction()
        snapshot = snapshot_redactions(self.case)

        other_case = Case.objects.create(
            case_reference="250003", data_subject_name="Jane Roe"
        )
        other_doc = Document.objects.create(
            case=other_case,
            original_file=SimpleUploadedFile("o.txt", b"x"),
            filename="o.txt",
            file_type=".txt",
        )
        other_redaction = Redaction.objects.create(
            document=other_doc,
            start_char=0,
            end_char=1,
            text="x",
            redaction_type=Redaction.RedactionType.THIRD_PARTY_PII,
            is_accepted=False,
        )

        restore_redactions(self.case, snapshot)

        self.assertTrue(
            Redaction.objects.filter(pk=other_redaction.pk).exists()
        )
