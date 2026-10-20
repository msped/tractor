import uuid
from datetime import timedelta

from auditlog.registry import auditlog
from django.db import models
from django.utils import timezone


class SingletonModel(models.Model):
    """Abstract base for settings models that should have exactly one row (pk=1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TrainingControl(SingletonModel):
    """
    What the system knows about a training run: whether one is going, and
    whether it has been asked to stop.

    Training can run for hours in a process nothing else owns. Both facts
    below are kept here, in the database, because that is the only thing
    every participant can see — the web process, the worker, a run started
    from a management command on another machine.

    **The stop signal.** There is no way to reach into a running process and
    ask it to stop, and killing it is destructive: ``train_model`` removes
    its half-written model directory in an ``except`` block, which a killed
    process never reaches, so every force-kill leaves hundreds of megabytes
    behind. So the run asks instead, polling ``cancel_requested`` and
    unwinding cleanly.

    **The heartbeat.** Whether a run is in progress used to be inferred from
    the task queue, which was wrong in a way that mattered: when django-q
    reaped a task at its timeout, the queue entry vanished while the process
    carried on training. The UI then showed nothing running and offered no
    way to stop it, and the "is one already going?" guard let a second run
    start alongside the first. A run now says so itself and keeps saying so,
    which makes a live run visible, stoppable, and impossible to double up
    on — and makes an abandoned one obvious, because its heartbeat goes
    stale rather than disappearing.
    """

    # A run that has not checked in for this long is treated as dead. Well
    # clear of the gap between checkpoints, so a slow batch is not mistaken
    # for a crash.
    STALE_AFTER = timedelta(minutes=15)

    cancel_requested = models.BooleanField(
        default=False,
        help_text=(
            "Set to ask an in-progress training run to stop at its next "
            "checkpoint. Cleared when a run starts."
        ),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current run began. NULL when nothing is running.",
    )
    heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Last time the running process checked in. A stale value means "
            "the run died without clearing up after itself."
        ),
    )
    pid = models.IntegerField(
        null=True,
        blank=True,
        help_text="OS process id of the run, to identify an abandoned one.",
    )

    @property
    def is_running(self):
        """Whether a run is in progress and still checking in."""
        if self.heartbeat_at is None:
            return False
        return timezone.now() - self.heartbeat_at < self.STALE_AFTER

    @property
    def is_stale(self):
        """A run that claimed to start but has stopped checking in."""
        return self.heartbeat_at is not None and not self.is_running

    def __str__(self):
        if self.is_running:
            return f"Training running since {self.started_at} (pid {self.pid})"
        if self.is_stale:
            return f"Training abandoned, last seen {self.heartbeat_at}"
        return "No training running"


class Model(models.Model):
    """
    Represents a trained SpanCat model version.
    GLiNER is zero-shot and system-managed — it is never stored here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="A unique name for the model version (e.g., v2.1-timestamp).",
    )
    path = models.CharField(
        max_length=512,
        unique=True,
        help_text="The absolute file path to the trained model directory.",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Designates if this model is the one currently used for processing.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    precision = models.FloatField(
        null=True, blank=True, help_text="Precision score from evaluation."
    )
    recall = models.FloatField(
        null=True, blank=True, help_text="Recall score from evaluation."
    )
    f1_score = models.FloatField(
        null=True, blank=True, help_text="F1 score from evaluation."
    )

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        # Ensure only one model can be active at a time.
        if self.is_active:
            Model.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]


class TrainingDocument(models.Model):
    """
    Represents a manually uploaded training document with highlights
    used to bootstrap or retrain models.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    original_file = models.FileField(upload_to="training_docs/")
    extracted_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", related_name="training_docs", on_delete=models.CASCADE
    )
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"TrainingDoc: {self.name}"


class TrainingEntity(models.Model):
    """
    Entity annotations extracted from highlights in a TrainingDocument.
    """

    class EntityType(models.TextChoices):
        DS_INFORMATION = "DS_INFORMATION", "Data Subject Information"
        THIRD_PARTY = "THIRD_PARTY", "Third Party Information"
        OPERATIONAL = "OPERATIONAL", "Operational Information"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        TrainingDocument, related_name="entities", on_delete=models.CASCADE
    )
    start_char = models.IntegerField()
    end_char = models.IntegerField()
    label = models.CharField(max_length=50, choices=EntityType.choices)

    def __str__(self):
        return f"{self.label}: {self.start_char}-{self.end_char} \
            ({self.document.name})"


class TrainingRun(models.Model):
    """Record of a single SpanCat model training run, including its outcome and source data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.OneToOneField("Model", on_delete=models.CASCADE)
    source = models.CharField(
        max_length=20,
        choices=[
            ("training_docs", "Training Documents"),
            ("redactions", "Redactions"),
            ("both", "Both"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TrainingRun {self.id} -> {self.model.name}"


class TrainingRunTrainingDoc(models.Model):
    """Join table linking a TrainingRun to the TrainingDocuments used as its source."""

    training_run = models.ForeignKey(TrainingRun, on_delete=models.CASCADE)
    document = models.ForeignKey("TrainingDocument", on_delete=models.CASCADE)


class TrainingRunCaseDoc(models.Model):
    """Join table linking a TrainingRun to the case Documents used as its source."""

    training_run = models.ForeignKey(TrainingRun, on_delete=models.CASCADE)
    document = models.ForeignKey("cases.Document", on_delete=models.CASCADE)


auditlog.register(TrainingDocument)
auditlog.register(TrainingRun)
auditlog.register(Model)
auditlog.register(TrainingEntity)
auditlog.register(TrainingRunTrainingDoc)
auditlog.register(TrainingRunCaseDoc)


class CustomRecognizer(models.Model):
    """A user-defined Presidio recognizer consisting of regex patterns and/or deny-list terms."""

    class EntityType(models.TextChoices):
        THIRD_PARTY = "THIRD_PARTY", "Third-Party PII"
        OPERATIONAL = "OPERATIONAL", "Operational Data"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class CustomPattern(models.Model):
    """A regex pattern belonging to a CustomRecognizer."""

    recognizer = models.ForeignKey(
        CustomRecognizer, related_name="patterns", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, blank=True, default="")
    regex = models.TextField()
    score = models.FloatField(default=0.85)

    def __str__(self):
        return f"Pattern for {self.recognizer.name}"


class CustomDenyListItem(models.Model):
    """A literal deny-list term belonging to a CustomRecognizer."""

    recognizer = models.ForeignKey(
        CustomRecognizer, related_name="deny_list", on_delete=models.CASCADE
    )
    value = models.CharField(max_length=500)

    def __str__(self):
        return f"'{self.value}' for {self.recognizer.name}"


DEFAULT_SYSTEM_PROMPT = """You are a data protection specialist reviewing documents for Subject
Access Requests (SARs) under UK GDPR and the Data Protection Act 2018.

Your task: identify passages of text where the CONTENT — not just the presence of a name \
— contextually discloses information about a third party that should not be released.

Focus on:
- Sentences or passages that reveal what a third party said, did, witnessed, or experienced
- Text that discloses a third party's personal circumstances, health, behaviour, or involvement
- Passages where releasing the content would identify or harm someone other than the data subject

Do NOT flag:
- Text that is solely about the data subject themselves
- Isolated names or identifiers — these are handled separately by other tools
- Text where no third-party disclosure is made in context

Return verbatim passages from the document. Prefer longer spans that capture the full \
context of the disclosure rather than isolated words."""


class LLMPromptSettings(SingletonModel):
    system_prompt = models.TextField(default=DEFAULT_SYSTEM_PROMPT)

    class Meta(SingletonModel.Meta):
        verbose_name = "LLM Prompt Settings"
        verbose_name_plural = "LLM Prompt Settings"
