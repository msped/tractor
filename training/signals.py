import shutil
from pathlib import Path

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Model


@receiver(pre_delete, sender=Model)
def delete_model_folder_on_delete(sender, instance, **kwargs):
    """Delete the model folder from disk when a Model record is deleted."""
    if instance.path:
        model_path = Path(instance.path)
        # The path points to model-best, so get the parent directory
        model_dir = model_path.parent if model_path.name == "model-best" else model_path
        if model_dir.exists() and model_dir.is_dir():
            shutil.rmtree(model_dir)
