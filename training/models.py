import uuid
from django.db import models


class Model(models.Model):
    """
    Represents a trained spaCy model version.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="A unique name for the model version (e.g., v2.1-timestamp)."
    )
    path = models.CharField(
        max_length=512,
        unique=True,
        help_text="The absolute file path to the trained model directory."
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Designates if this model is the one currently used for "
        "processing."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        # Ensure only one model can be active at a time.
        if self.is_active:
            Model.objects.filter(is_active=True).exclude(
                pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
