from django.contrib import admin
from django.db import models as db_models
from django.forms import Textarea

from .models import (
    LLMPromptSettings,
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)


class TrainingRunTrainingDocInline(admin.TabularInline):
    model = TrainingRunTrainingDoc
    extra = 0
    readonly_fields = ["document"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class TrainingRunCaseDocInline(admin.TabularInline):
    model = TrainingRunCaseDoc
    extra = 0
    readonly_fields = ["document"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TrainingRun)
class TrainingRunAdmin(admin.ModelAdmin):
    list_display = ["id", "model", "source", "created_at"]
    list_filter = ["source", "created_at"]
    readonly_fields = ["id", "model", "source", "created_at"]
    inlines = [TrainingRunTrainingDocInline, TrainingRunCaseDocInline]


admin.site.register(Model)
admin.site.register(TrainingDocument)


@admin.register(LLMPromptSettings)
class LLMPromptSettingsAdmin(admin.ModelAdmin):
    formfield_overrides = {
        db_models.TextField: {
            "widget": Textarea(attrs={"rows": 20, "cols": 80})
        },
    }

    def has_add_permission(self, request):
        return not LLMPromptSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
