from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Document, Redaction


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    When a document is first created, trigger the AI processing task.
    """
    if created and instance.status == Document.Status.PROCESSING:
        instance.start_processing()


@receiver(post_save, sender=Redaction)
def redaction_post_save(sender, instance, created, **kwargs):
    """
    When a redaction is created as or updated to be DS_INFO, trigger a
    task to find that same text in all other documents in the case.
    """
    if instance.redaction_type == Redaction.RedactionType.DS_INFORMATION:
        if created:
            from django_q.tasks import async_task

            async_task(
                "cases.tasks.find_and_flag_matching_text_in_case",
                instance.id,
            )
        else:
            update_fields = kwargs.get("update_fields") or set()
            if "redaction_type" in update_fields:
                from django_q.tasks import async_task

                async_task(
                    "cases.tasks.find_and_flag_matching_text_in_case",
                    instance.id,
                )
