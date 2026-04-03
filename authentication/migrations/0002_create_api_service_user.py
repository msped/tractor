from django.db import migrations


def create_api_service_user(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.get_or_create(
        username="api_service",
        defaults={
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        },
    )


def delete_api_service_user(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(username="api_service").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_api_service_user, delete_api_service_user),
    ]
