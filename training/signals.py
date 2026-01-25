from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import TrainingRun


@receiver(pre_delete, sender=TrainingRun)
def reset_training_docs_on_run_delete(sender, instance, **kwargs):
    """Reset TrainingDocument.processed when a TrainingRun is deleted.

    When a Model is deleted, the associated TrainingRun is cascade deleted.
    This signal ensures that any TrainingDocuments used in that run are
    reset to unprocessed state so they can be used in future training runs.
    """
    for link in instance.trainingruntrainingdoc_set.all():
        link.document.processed = False
        link.document.save(update_fields=["processed"])
