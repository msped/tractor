"""
Management command to download a GLiNER model from HuggingFace Hub, save it
to nlp_models/, and register it as the active model in the database.

Run once during initial project setup, or whenever a maintainer decides
to update the base model. After this, the application loads the model
entirely from the local nlp_models/ directory — no network requests are made
during normal operation.

Usage:
    python manage.py download_model
    python manage.py download_model --name urchade/gliner_large-v2.1
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from training.models import Model

NLP_MODELS_DIR = os.path.join(settings.BASE_DIR, "nlp_models")


class Command(BaseCommand):
    help = "Download a GLiNER model from HuggingFace, save it locally, and register it as active."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="urchade/gliner_medium-v2.1",
            help="HuggingFace model ID to download (default: urchade/gliner_medium-v2.1)",
        )

    def handle(self, *args, **options):
        from gliner import GLiNER

        model_id = options["name"]
        db_name = model_id.replace("/", "_").replace("-", "_").replace(".", "_")
        local_path = os.path.join(NLP_MODELS_DIR, db_name)

        self.stdout.write(f"Downloading GLiNER model: {model_id}")
        self.stdout.write("This may take a few minutes on first run...")

        os.makedirs(NLP_MODELS_DIR, exist_ok=True)
        model = GLiNER.from_pretrained(model_id)
        model.save_pretrained(local_path)

        self.stdout.write(self.style.SUCCESS(f"Saved to {local_path}"))
        self.stdout.write("Registering as active model...")

        Model.objects.filter(is_active=True).update(is_active=False)
        Model.objects.update_or_create(
            name=db_name,
            defaults={
                "path": local_path,
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS(f"Model '{db_name}' is now active."))
