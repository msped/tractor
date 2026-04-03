from django.contrib import admin

from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["description", "created_by", "created_at", "is_active"]
    list_filter = ["is_active"]
    readonly_fields = ["key_hash", "created_at", "created_by"]
    fields = [
        "description",
        "user",
        "is_active",
        "key_hash",
        "created_at",
        "created_by",
    ]

    def has_add_permission(self, request):
        # Key creation must go through the API so the raw key is returned once.
        return False
