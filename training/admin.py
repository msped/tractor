from django.contrib import admin

from .models import Model, TrainingDocument, TrainingRun, TrainingRunCaseDoc, TrainingRunTrainingDoc


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
