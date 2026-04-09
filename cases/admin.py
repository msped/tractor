from auditlog.models import LogEntry
from django.contrib import admin

from .models import Case, Document, ExemptionTemplate, Redaction


class SuperuserDeleteMixin:
    """Restricts deletion of records to superusers only."""

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Case)
class CaseAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ("case_reference", "status", "created_at")
    search_fields = ("case_reference", "data_subject_name")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)


@admin.register(Document)
class DocumentAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ("filename", "case", "status", "uploaded_at")
    search_fields = ("filename", "case__case_reference")
    list_filter = ("status", "uploaded_at")
    ordering = ("-uploaded_at",)


@admin.register(Redaction)
class RedactionAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ("document", "redaction_type", "created_at")
    search_fields = ("document__filename", "redaction_type")
    list_filter = ("redaction_type", "created_at")
    ordering = ("-created_at",)


@admin.register(ExemptionTemplate)
class ExemptionTemplateAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    ordering = ("name",)


try:
    admin.site.unregister(LogEntry)
except admin.sites.NotRegistered:
    pass


@admin.register(LogEntry)
class AuditLogEntryAdmin(SuperuserDeleteMixin, admin.ModelAdmin):
    """Read-only audit log. Deletion restricted to superusers only."""

    list_display = (
        "timestamp",
        "content_type",
        "object_repr",
        "action",
        "actor",
    )
    list_filter = ("action", "content_type")
    readonly_fields = (
        "timestamp",
        "content_type",
        "object_pk",
        "object_id",
        "object_repr",
        "action",
        "changes",
        "actor",
        "remote_addr",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
