import hashlib
import secrets

from django.conf import settings
from django.db import models


class APIKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="The service account this key authenticates as.",
    )
    description = models.CharField(
        max_length=255,
        help_text="Human-readable label for this key (e.g. 'Case management integration').",
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hex digest of the raw key. Never stored in plaintext.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_api_keys",
        help_text="Admin who created this key.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.description} (created {self.created_at:%Y-%m-%d})"

    @classmethod
    def generate(cls, description, created_by, user):
        """
        Creates and saves a new APIKey. Returns (instance, raw_key).
        raw_key is shown once and never stored.
        """
        raw = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        instance = cls.objects.create(
            user=user,
            description=description,
            key_hash=key_hash,
            created_by=created_by,
        )
        return instance, raw
