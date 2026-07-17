from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from training.tests.base import NetworkBlockerMixin


class BackfillExportsMigrationTests(NetworkBlockerMixin, TransactionTestCase):
    """
    0027_backfill_exports wraps each legacy Case.export_file in a first-class
    Export row plus a baseline RedactionSnapshot built from live redactions.
    """

    migrate_from = [
        (
            "cases",
            "0026_export_redactionsnapshot_export_internalreview_and_more",
        )
    ]
    migrate_to = [("cases", "0027_backfill_exports")]

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor

    def setUp(self):
        # Rewind to the state just before the backfill runs.
        self._migrate(self.migrate_from)
        old_apps = (
            MigrationExecutor(connection)
            .loader.project_state(self.migrate_from)
            .apps
        )

        Case = old_apps.get_model("cases", "Case")
        Document = old_apps.get_model("cases", "Document")
        Redaction = old_apps.get_model("cases", "Redaction")
        RedactionContext = old_apps.get_model("cases", "RedactionContext")

        self.legacy_case = Case.objects.create(
            case_reference="LEGACY",
            data_subject_name="Legacy Subject",
            data_subject_dob=date(1980, 5, 1),
            export_file="exports/legacy/package.zip",
        )
        self.document = Document.objects.create(
            case=self.legacy_case,
            extracted_text="Some operational text here",
        )
        self.redaction = Redaction.objects.create(
            document=self.document,
            start_char=5,
            end_char=16,
            text="operational",
            redaction_type="OP_DATA",
        )
        RedactionContext.objects.create(
            redaction=self.redaction, text="Some operational text"
        )

        # A case with no export_file must be left untouched.
        self.no_export_case = Case.objects.create(
            case_reference="NOEXP1",
            data_subject_name="No Export",
        )

    def test_backfill_creates_export_and_baseline_snapshot(self):
        self._migrate(self.migrate_to)
        new_apps = (
            MigrationExecutor(connection)
            .loader.project_state(self.migrate_to)
            .apps
        )

        Export = new_apps.get_model("cases", "Export")
        RedactionSnapshot = new_apps.get_model("cases", "RedactionSnapshot")

        exports = Export.objects.filter(case_id=self.legacy_case.id)
        self.assertEqual(exports.count(), 1)
        export = exports.first()
        self.assertEqual(export.sequence, 1)
        self.assertEqual(export.label, "Original disclosure")
        self.assertEqual(export.export_file, "exports/legacy/package.zip")
        self.assertIsNone(export.review_id)
        self.assertIsNone(export.created_by_id)

        snapshot = RedactionSnapshot.objects.get(export=export)
        self.assertEqual(snapshot.case_id, self.legacy_case.id)
        self.assertEqual(len(snapshot.payload), 1)
        row = snapshot.payload[0]
        self.assertEqual(row["id"], str(self.redaction.id))
        self.assertEqual(row["text"], "operational")
        self.assertEqual(row["context"], "Some operational text")

        # The case without an export produced nothing.
        self.assertFalse(
            Export.objects.filter(case_id=self.no_export_case.id).exists()
        )

    def test_backfill_skips_cases_that_already_have_an_export(self):
        import importlib

        self._migrate(self.migrate_to)
        new_apps = (
            MigrationExecutor(connection)
            .loader.project_state(self.migrate_to)
            .apps
        )
        Export = new_apps.get_model("cases", "Export")

        # Re-invoking the data function must be a no-op for backfilled cases.
        migration = importlib.import_module(
            "cases.migrations.0027_backfill_exports"
        )
        migration.backfill_exports(new_apps, connection.schema_editor())
        self.assertEqual(
            Export.objects.filter(case_id=self.legacy_case.id).count(), 1
        )

    def tearDown(self):
        # Leave the schema at the latest migration for the rest of the suite.
        self._migrate([("cases", "0027_backfill_exports")])
