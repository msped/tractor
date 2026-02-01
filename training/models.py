import uuid

from auditlog.registry import auditlog
from django.db import models


class Model(models.Model):
    """
    Represents a trained spaCy model version.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, unique=True, help_text="A unique name for the model version (e.g., v2.1-timestamp)."
    )
    path = models.CharField(
        max_length=512, unique=True, help_text="The absolute file path to the trained model directory."
    )
    is_active = models.BooleanField(
        default=False, help_text="Designates if this model is the one currently used for processing."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    precision = models.FloatField(null=True, blank=True, help_text="Precision score from evaluation.")
    recall = models.FloatField(null=True, blank=True, help_text="Recall score from evaluation.")
    f1_score = models.FloatField(null=True, blank=True, help_text="F1 score from evaluation.")

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        # Ensure only one model can be active at a time.
        if self.is_active:
            Model.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
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
    created_by = models.ForeignKey("auth.User", related_name="training_docs", on_delete=models.CASCADE)
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
    document = models.ForeignKey(TrainingDocument, related_name="entities", on_delete=models.CASCADE)
    start_char = models.IntegerField()
    end_char = models.IntegerField()
    label = models.CharField(max_length=50, choices=EntityType.choices)

    def __str__(self):
        return f"{self.label}: {self.start_char}-{self.end_char} \
            ({self.document.name})"


class TrainingRun(models.Model):
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
    training_run = models.ForeignKey(TrainingRun, on_delete=models.CASCADE)
    document = models.ForeignKey("TrainingDocument", on_delete=models.CASCADE)


class TrainingRunCaseDoc(models.Model):
    training_run = models.ForeignKey(TrainingRun, on_delete=models.CASCADE)
    document = models.ForeignKey("cases.Document", on_delete=models.CASCADE)


auditlog.register(TrainingDocument)
auditlog.register(TrainingRun)
auditlog.register(Model)
auditlog.register(TrainingEntity)
auditlog.register(TrainingRunTrainingDoc)
auditlog.register(TrainingRunCaseDoc)
