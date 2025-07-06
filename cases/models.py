import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


def retention_review_date_default():
    """
    Calculates a date five years from the current time.
    Used as the default for the Case retention_review_date field.
    """
    return timezone.now() + timezone.timedelta(days=365 * 5)


class Case(models.Model):
    """
    Represents a single Subject Access Request case. This is the top-level
    container for all related documents and information.
    """
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CLOSED = 'CLOSED', 'Closed'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="The internal unique identifier for the case (UUID)."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        help_text="The current status of the case."
    )
    case_reference = models.CharField(
        max_length=6,
        unique=True,
        help_text="The human-readable, unique identifier for"
        " this case (e.g., 2025-0114)."
    )

    data_subject_name = models.CharField(
        max_length=255,
        help_text="Full name of the data subject."
    )
    data_subject_dob = models.DateField(
        null=True, blank=True,
        help_text="Date of birth of the data subject."
    )

    # Audit and Ownership fields.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_cases"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cases"
    )

    retention_review_date = models.DateField(
        default=retention_review_date_default,
        help_text="Date when this case should be reviewed for retention."
    )

    def __str__(self):
        return f"Case {self.case_reference} - {self.data_subject_name}"

    class Meta:
        ordering = ['-created_at']


class Document(models.Model):
    """
    Represents a single document/file that has been uploaded to a Case.
    """
    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        READY_FOR_REVIEW = 'READY', 'Ready for Review'
        COMPLETED = 'COMPLETED', 'Completed'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="documents"  # Allows easy access: my_case.documents.all()
    )

    original_file = models.FileField(
        upload_to='originals/%Y/%m/%d/',
        help_text="The original, unmodified uploaded file."
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_type = models.CharField(max_length=10, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING
    )

    extracted_text = models.TextField(blank=True, null=True, editable=False)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.filename = self.original_file.name
            if '.' in self.filename:
                self.file_type = self.filename.split('.')[-1].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.filename} (Case: {self.case.case_reference})"

    class Meta:
        ordering = ['uploaded_at']


class Redaction(models.Model):
    """
    Represents a single, specific redaction within a Document.
    A document can have hundreds of these.
    """
    class RedactionType(models.TextChoices):
        OPERATIONAL_DATA = 'OP_DATA', 'Operational Data'
        THIRD_PARTY_PII = 'PII', 'Third-Party PII'
        DS_INFORMATION = 'DS_INFO', 'Data Subject Information'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Allows easy access: my_document.redactions.all()
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="redactions"
    )

    start_char = models.IntegerField()
    end_char = models.IntegerField()
    text = models.TextField(help_text="The actual text that was redacted.")
    justification = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for a manual redaction or for "
        "rejecting a suggestion."
    )

    redaction_type = models.CharField(
        max_length=10, choices=RedactionType.choices)
    is_suggestion = models.BooleanField(
        default=True,
        help_text="True if this was created by the AI, False if created"
        " manually by a user."
    )
    is_accepted = models.BooleanField(
        default=False,
        help_text="True if the user has confirmed this redaction should"
        " be applied."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Redaction in {self.document.filename}: '{self.text[:30]}...'"

    class Meta:
        ordering = ['start_char']
