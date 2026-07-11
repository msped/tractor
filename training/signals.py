import shutil
from pathlib import Path

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import (
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunTrainingDoc,
)


@receiver(pre_delete, sender=TrainingRun)
def reset_training_docs_on_run_delete(sender, instance, **kwargs):
    """Reset processed flag on TrainingDocuments when their training run is deleted."""
    doc_ids = TrainingRunTrainingDoc.objects.filter(
        training_run=instance
    ).values_list("document_id", flat=True)
    TrainingDocument.objects.filter(id__in=doc_ids).update(processed=False)


@receiver(pre_delete, sender=Model)
def delete_model_folder_on_delete(sender, instance, **kwargs):
    """Delete the model folder from disk when a Model record is deleted."""
    if instance.path:
        model_path = Path(instance.path)
        # The path points to model-best, so get the parent directory
        model_dir = (
            model_path.parent
            if model_path.name == "model-best"
            else model_path
        )
        print("Deleting model directory: ", model_dir)
        if model_dir.exists() and model_dir.is_dir():
            shutil.rmtree(model_dir)
