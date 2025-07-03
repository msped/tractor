from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document
from django_q.tasks import async_task


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    Fires when a Document object is saved.
    """
    if created and instance.status == Document.Status.PROCESSING:
        async_task(
            'cases.services.process_document_and_create_redactions',
            instance.id
        )
