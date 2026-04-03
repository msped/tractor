from dj_rest_auth.serializers import (
    UserDetailsSerializer as BaseUserDetailsSerializer,
)
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import APIKey

User = get_user_model()


class UserDetailsSerializer(BaseUserDetailsSerializer):
    class Meta(BaseUserDetailsSerializer.Meta):
        model = User
        fields = BaseUserDetailsSerializer.Meta.fields + (
            "is_staff",
            "is_superuser",
        )
        read_only_fields = BaseUserDetailsSerializer.Meta.read_only_fields + (
            "is_staff",
            "is_superuser",
        )


class APIKeySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = APIKey
        fields = ["id", "description", "created_at", "created_by_username"]
        read_only_fields = ["id", "created_at", "created_by_username"]


class APIKeyCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
