import os
import uuid

from auditlog.registry import auditlog
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django_q.tasks import async_task

from training.models import Model, SingletonModel


def case_export_upload_to(instance, filename):
    return f"exports/{instance.id}/{filename}"


def export_upload_to(instance, filename):
    return f"exports/{instance.case_id}/{instance.id}/{filename}"


def retention_review_date_default():
    """
    Calculates a date six years from the current time.
    Used as the default for the Case retention_review_date field.
    """
    retention_years = getattr(settings, "CASE_RETENTION_YEARS", 6)
    return (timezone.now() + relativedelta(years=retention_years)).date()


class Case(models.Model):
    """
    Represents a single case. This is the top-level
    container for all related documents and information.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CLOSED = "CLOSED", "Closed"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        ERROR = "ERROR", "Error"

    class ExportStatus(models.TextChoices):
        NONE = "NONE", "Not Generated"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        ERROR = "ERROR", "Error"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="The internal unique identifier for the case (UUID).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        help_text="The current status of the case.",
    )
    case_reference = models.CharField(
        max_length=6,
        unique=True,
        help_text="The human-readable, unique identifier for this case, max 6 characters (e.g., 202501).",
    )

    data_subject_name = models.CharField(
        max_length=255, help_text="Full name of the data subject."
    )
    data_subject_dob = models.DateField(
        null=True, blank=True, help_text="Date of birth of the data subject."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cases",
    )

    retention_review_date = models.DateField(
        default=retention_review_date_default,
        help_text="Date when this case should be reviewed for retention.",
    )

    # Export-related fields
    export_status = models.CharField(
        max_length=20, choices=ExportStatus.choices, default=ExportStatus.NONE
    )
    export_file = models.FileField(
        upload_to=case_export_upload_to,
        null=True,
        blank=True,
        help_text="The path to the generated ZIP export file.",
    )
    export_task_id = models.CharField(max_length=255, null=True, blank=True)

    def start_export(self):
        """
        Sets the case status to PROCESSING and triggers the background
        task to generate the export package.
        Returns the task_id.
        """
        self.export_status = self.ExportStatus.PROCESSING
        task_id = async_task("cases.tasks.export_case_documents", self.id)
        self.export_task_id = task_id
        self.save(update_fields=["export_status", "export_task_id"])
        return task_id

    def __str__(self):
        return f"Case {self.case_reference} - {self.data_subject_name}"

    def _calculate_retention_date(self, today=None):
        """
        Calculates the retention date based on the data subject's age.
        - For adults (or if DOB is unknown), it's 6 years from now.
        - For minors, it's 6 years after they turn 18.
        :param today: The date to calculate from. Defaults to timezone.now().
        """
        today = today or timezone.now().date()
        retention_years = getattr(settings, "CASE_RETENTION_YEARS", 6)
        if self.data_subject_dob:
            age = relativedelta(today, self.data_subject_dob).years
            eighteenth_birthday = self.data_subject_dob + relativedelta(
                years=18
            )

            if age < 18:
                return eighteenth_birthday + relativedelta(
                    years=retention_years
                )
            else:
                return today + relativedelta(years=retention_years)

        return today + relativedelta(years=retention_years)

    def save(self, *args, **kwargs):
        # UUID pks are assigned at instantiation, so check _state.adding
        # rather than pk to detect creation. Only derive the DOB-aware
        # retention date when the caller left the field at its default —
        # an explicitly provided date must be preserved.
        if (
            self._state.adding
            and self.retention_review_date == retention_review_date_default()
        ):
            self.retention_review_date = self._calculate_retention_date()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]


class Document(models.Model):
    """
    Represents a single document/file that has been uploaded to a Case.
    """

    class Status(models.TextChoices):
        UNPROCESSED = "UNPROCESSED", "Unprocessed"
        PROCESSING = "PROCESSING", "Processing"
        READY_FOR_REVIEW = "READY", "Ready for Review"
        COMPLETED = "COMPLETED", "Completed"
        ERROR = "ERROR", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="documents",  # Allows easy access: my_case.documents.all()
    )

    original_file = models.FileField(
        upload_to="originals/%Y/%m/%d/",
        help_text="The original, unmodified uploaded file.",
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_type = models.CharField(max_length=10, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING
    )

    extracted_text = models.TextField(blank=True, null=True, editable=False)
    extracted_tables = models.JSONField(default=list, blank=True)
    extracted_structure = models.JSONField(null=True, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    processing_task_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    spacy_model = models.ForeignKey(
        Model,
        on_delete=models.SET_NULL,  # Important for data retention
        null=True,
        blank=True,
        help_text="A link to the spaCy model used for processing.",
    )

    def save(self, *args, **kwargs):
        # Derive filename/file_type on creation only when the caller hasn't
        # set them, using the same format as DocumentSerializer.create
        # (extension with leading dot, e.g. ".pdf") — the frontend matches
        # on that form.
        if self._state.adding:
            if not self.filename:
                self.filename = self.original_file.name
            if not self.file_type and self.filename:
                self.file_type = os.path.splitext(self.filename)[1]
        super().save(*args, **kwargs)

    def start_processing(self):
        """
        Transition this document to PROCESSING, enqueue the NLP task, and
        persist the task ID.  Both initial upload (via signal) and resubmit
        (via view) use this method — it is the single place that knows the
        task routing string.  Returns the task_id.
        """
        task_id = async_task(
            "cases.tasks.process_document_and_create_redactions", self.id
        )
        Document.objects.filter(pk=self.pk).update(
            status=self.Status.PROCESSING,
            processing_task_id=task_id,
        )
        return task_id

    def __str__(self):
        return f"{self.filename} (Case: {self.case.case_reference})"

    class Meta:
        ordering = ["uploaded_at"]
        indexes = [
            models.Index(fields=["status"], name="document_status_idx"),
        ]


class ProvenanceError(TypeError):
    """A decision-state write was attempted without provenance."""


# Fields that together encode an accept/reject decision.  They may only be
# written through the decision methods below, never via a generic update().
_DECISION_FIELDS = frozenset({"is_accepted", "justification", "decided_by"})


class RedactionQuerySet(models.QuerySet):
    # ---- writes: provenance is keyword-only with no default ----
    def accept(self, *, by):
        """
        Accept everything in the queryset as decided by `by`.

        Overwrites prior provenance — a HUMAN accept over a machine-accepted
        row flips it to human-decided — and clears any stale rejection
        justification.  Scope with .pending() first if prior decisions must
        be preserved.  Single UPDATE.
        """
        return super().update(
            is_accepted=True, justification=None, decided_by=by
        )

    def reject(self, justification="", *, by):
        """Reject everything in the queryset as decided by `by`."""
        return super().update(
            is_accepted=False, justification=justification, decided_by=by
        )

    def reset(self):
        """Return all redactions in the queryset to pending (no decision)."""
        return super().update(
            is_accepted=False, justification=None, decided_by=None
        )

    # ---- reads: pending/decided derived from provenance ----
    def pending(self):
        """Redactions that have not yet been accepted or explicitly rejected."""
        return self.filter(decided_by__isnull=True)

    def decided(self):
        """Redactions that have been accepted or explicitly rejected."""
        return self.filter(decided_by__isnull=False)

    def trainable(self):
        """
        The canonical SpanCat training selection: human-accepted redactions,
        excluding data-subject information.
        """
        return self.filter(
            is_accepted=True, decided_by=Redaction.DecidedBy.HUMAN
        ).exclude(redaction_type=Redaction.RedactionType.DS_INFORMATION)

    # ---- enforcement: no naked writes to decision state ----
    def update(self, **kwargs):
        if _DECISION_FIELDS & kwargs.keys():
            raise ProvenanceError(
                "Decision fields may not be written directly — use "
                ".accept(by=)/.reject(by=)/.reset()."
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        if _DECISION_FIELDS & set(fields):
            raise ProvenanceError(
                "Decision fields may not be written directly — use "
                ".accept(by=)/.reject(by=)/.reset()."
            )
        return super().bulk_update(objs, fields, **kwargs)


class Redaction(models.Model):
    """
    Represents a single, specific redaction within a Document.
    A document can have hundreds of these.
    """

    class RedactionType(models.TextChoices):
        OPERATIONAL_DATA = "OP_DATA", "Operational Data"
        THIRD_PARTY_PII = "PII", "Third-Party PII"
        DS_INFORMATION = "DS_INFO", "Data Subject Information"

    class Source(models.TextChoices):
        NER = "NER", "NER"
        LLM = "LLM", "LLM"

    class DecidedBy(models.TextChoices):
        HUMAN = "HUMAN", "Human reviewer"
        AUTO_ACCEPT = "AUTO", "Auto-accept review mode"
        CASE_PROPAGATION = "CASE_PROP", "Unanimous case-decision propagation"
        DS_INFO_PROPAGATION = "DS_PROP", "DS information propagation"

    objects = RedactionQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Allows easy access: my_document.redactions.all()
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="redactions"
    )

    start_char = models.IntegerField()
    end_char = models.IntegerField()
    text = models.TextField(help_text="The actual text that was redacted.")
    justification = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for a manual redaction or for rejecting a suggestion.",
    )

    redaction_type = models.CharField(
        max_length=10, choices=RedactionType.choices
    )
    is_suggestion = models.BooleanField(
        default=True,
        help_text="True if this was created by the AI, False if created manually by a user.",
    )
    is_accepted = models.BooleanField(
        default=False,
        help_text="True if the user has confirmed this redaction should be applied.",
    )
    decided_by = models.CharField(
        max_length=9,
        choices=DecidedBy.choices,
        null=True,
        blank=True,
        help_text="Who/what made the accept/reject decision. NULL = pending.",
    )
    source = models.CharField(
        max_length=3,
        choices=Source.choices,
        default=Source.NER,
        help_text="Whether this redaction was produced by an NER model or an LLM.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def auto_accepted(self):
        """True if accepted by a system mechanism rather than a human reviewer."""
        return bool(
            self.is_accepted
            and self.decided_by
            and self.decided_by != self.DecidedBy.HUMAN
        )

    def __str__(self):
        return f"Redaction in {self.document.filename}: '{self.text[:30]}...'"

    class Meta:
        ordering = ["start_char"]
        constraints = [
            # Impossible to accept without provenance, from any code path
            # (ORM, bulk_create, raw SQL, admin).
            models.CheckConstraint(
                name="redaction_accept_requires_decided_by",
                check=Q(is_accepted=False) | Q(decided_by__isnull=False),
            ),
        ]
        indexes = [
            models.Index(
                fields=["text", "redaction_type"],
                name="redaction_text_type_idx",
            ),
            models.Index(
                fields=["document", "start_char", "end_char"],
                name="redaction_doc_pos_idx",
            ),
        ]


class RedactionContext(models.Model):
    """
    Stores optional, user-provided context for a specific redaction.
    This context is displayed in place of a black-box redaction in the
    final exported document to provide more clarity.
    """

    redaction = models.OneToOneField(
        Redaction,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="context",
    )
    text = models.TextField(
        help_text="User-provided context for the redaction."
    )


class InternalReview(models.Model):
    """
    A single post-disclosure re-review episode on a case (opened when a data
    subject challenges a disclosure).

    This slice defines the record only; the open/complete/abandon lifecycle
    service and the provenance lock that guard it are added in a later slice.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        COMPLETED = "COMPLETED", "Completed"
        ABANDONED = "ABANDONED", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="reviews"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_reviews",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_reviews",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.TextField(
        blank=True,
        default="",
        help_text="Required written outcome recorded when the review is closed.",
    )

    def __str__(self):
        return f"Review of {self.case.case_reference} ({self.status})"

    class Meta:
        ordering = ["-opened_at"]


class Export(models.Model):
    """
    One preserved disclosure package for a case. A case has many; each export
    keeps its own ZIP and is never overwritten by a later re-export.
    `Case.export_file` is a pointer to the most recent export's file.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="exports"
    )
    export_file = models.FileField(
        upload_to=export_upload_to,
        help_text="The preserved ZIP package for this disclosure.",
    )
    sequence = models.PositiveIntegerField(
        help_text="1-based order of this export within the case."
    )
    label = models.CharField(
        max_length=100,
        help_text='Human label, e.g. "Original disclosure" or "Disclosure 2".',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exports",
    )
    review = models.ForeignKey(
        InternalReview,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exports",
        help_text="The review that produced this export; null for the original disclosure.",
    )

    def __str__(self):
        return f"{self.label} for {self.case.case_reference}"

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["case", "sequence"],
                name="export_unique_case_sequence",
            ),
        ]


class RedactionSnapshot(models.Model):
    """
    An immutable, complete, restorable capture of the entire redaction set
    for a case's documents at a single point in time.

    Taken on every export completion, this is the "as-disclosed" record: the
    source for disclosed-vs-current diffing and for rolling the live set back
    when an Internal Review is abandoned. The capture is *complete* (every
    field of every redaction plus any RedactionContext), not decision-only,
    because a review may add, delete, or re-bound redactions and restore must
    reconstruct the live set exactly.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="redaction_snapshots",
    )
    export = models.OneToOneField(
        "Export",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="snapshot",
        help_text="The export this snapshot froze the redaction set for.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(
        default=list,
        editable=False,
        help_text=(
            "Frozen list of every redaction (all fields) plus associated "
            "RedactionContext for the case's documents at capture time."
        ),
    )

    def __str__(self):
        return f"Snapshot of {self.case.case_reference} at {self.created_at}"

    class Meta:
        ordering = ["-created_at"]


class ExemptionTemplate(models.Model):
    """
    A reusable rejection reason (e.g. "S.40 - Personal Information") that
    admins configure and users select when rejecting redaction suggestions.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="The exemption label shown to users.",
    )
    description = models.TextField(
        blank=True, help_text="Optional longer description of this exemption."
    )
    is_active = models.BooleanField(
        default=True, help_text="Inactive templates are hidden from the UI."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class DocumentExportSettings(SingletonModel):
    class FontFamily(models.TextChoices):
        ARIAL = "arial", "Arial"
        TIMES_NEW_ROMAN = "times_new_roman", "Times New Roman"
        COURIER_NEW = "courier_new", "Courier New"
        GEORGIA = "georgia", "Georgia"
        VERDANA = "verdana", "Verdana"

    _FONT_CSS = {
        "arial": "Arial, sans-serif",
        "times_new_roman": '"Times New Roman", serif',
        "courier_new": '"Courier New", monospace',
        "georgia": "Georgia, serif",
        "verdana": "Verdana, sans-serif",
    }

    class DisclosureStyle(models.TextChoices):
        BARS = "bars", "Black Bars"
        REMOVAL = "removal", "Remove Text"

    header_text = models.CharField(max_length=500, blank=True, default="")
    footer_text = models.CharField(max_length=500, blank=True, default="")
    watermark_text = models.CharField(max_length=200, blank=True, default="")
    watermark_include_case_ref = models.BooleanField(default=False)
    page_numbers_enabled = models.BooleanField(default=False)
    font_family = models.CharField(
        max_length=50, choices=FontFamily, default=FontFamily.ARIAL
    )
    disclosure_style = models.CharField(
        max_length=20,
        choices=DisclosureStyle.choices,
        default=DisclosureStyle.BARS,
    )

    @property
    def font_family_css(self):
        return self._FONT_CSS.get(self.font_family, "Arial, sans-serif")

    class Meta(SingletonModel.Meta):
        verbose_name = "Document Export Settings"
        verbose_name_plural = "Document Export Settings"


class ReviewWorkflowSettings(SingletonModel):
    auto_accept_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, all NER redaction suggestions are automatically accepted on processing.",
    )

    class Meta(SingletonModel.Meta):
        verbose_name = "Review Workflow Settings"
        verbose_name_plural = "Review Workflow Settings"


auditlog.register(Case)
auditlog.register(Document)
auditlog.register(Redaction)
auditlog.register(ExemptionTemplate)
auditlog.register(InternalReview)
auditlog.register(Export)
