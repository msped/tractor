from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Document, InternalReview, Redaction


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    When a document is first created, trigger the AI processing task.
    """
    if created and instance.status == Document.Status.PROCESSING:
        instance.start_processing()


@receiver(pre_save, sender=Redaction)
def redaction_pre_save(sender, instance, **kwargs):
    """Store the pre-save redaction_type so post_save can detect type changes."""
    if instance.pk:
        try:
            instance._original_redaction_type = Redaction.objects.get(
                pk=instance.pk
            ).redaction_type
        except Redaction.DoesNotExist:
            instance._original_redaction_type = None
    else:
        instance._original_redaction_type = None


@receiver(post_save, sender=Redaction)
def redaction_post_save(sender, instance, created, **kwargs):
    """
    When a redaction is created as or updated to be DS_INFO, trigger a
    task to find that same text in all other documents in the case.
    """
    if instance.redaction_type != Redaction.RedactionType.DS_INFORMATION:
        return

    original_type = getattr(instance, "_original_redaction_type", None)
    type_changed_to_ds_info = (
        created or original_type != Redaction.RedactionType.DS_INFORMATION
    )

    if not type_changed_to_ds_info:
        return

    # During an Internal Review, propagation is no longer fire-and-forget: the
    # reviewer previews the affected documents and confirms before it applies
    # (see cases.views.RedactionPropagationView). Suppress the automatic task
    # so no case-wide write happens without that confirmation.
    review_open = InternalReview.objects.filter(
        case=instance.document.case_id,
        status=InternalReview.Status.OPEN,
    ).exists()
    if review_open:
        return

    from django_q.tasks import async_task

    async_task(
        "cases.tasks.find_and_flag_matching_text_in_case",
        instance.id,
    )
