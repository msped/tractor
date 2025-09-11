from django.db import migrations
import uuid


def create_default_model(apps, schema_editor):
    Model = apps.get_model("training", "Model")

    # Deactivate any currently active models
    Model.objects.filter(is_active=True).update(is_active=False)

    # Insert or update the default spaCy model
    Model.objects.update_or_create(
        name="default-en_core_web_lg",
        defaults={
            "id": uuid.uuid4(),
            "path": "en_core_web_lg",  # pip-installed model, not a directory
            "is_active": True,
        },
    )


def remove_default_model(apps, schema_editor):
    Model = apps.get_model("training", "Model")
    Model.objects.filter(name="default-en_core_web_lg").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0002_model_f1_score_model_precision_model_recall"),
    ]

    operations = [
        migrations.RunPython(create_default_model, remove_default_model),
    ]
