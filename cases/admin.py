from django.contrib import admin

from .models import Case, Document, Redaction


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_reference", "status", "created_at")
    search_fields = ("case_reference", "data_subject_name")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("filename", "case", "status", "uploaded_at")
    search_fields = ("filename", "case__case_reference")
    list_filter = ("status", "uploaded_at")
    ordering = ("-uploaded_at",)


@admin.register(Redaction)
class RedactionAdmin(admin.ModelAdmin):
    list_display = ("document", "redaction_type", "created_at")
    search_fields = ("document__filename", "redaction_type")
    list_filter = ("redaction_type", "created_at")
    ordering = ("-created_at",)
