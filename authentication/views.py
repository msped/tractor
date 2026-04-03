from allauth.socialaccount.providers.microsoft.views import (
    MicrosoftGraphOAuth2Adapter,
)
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import APIKey
from .serializers import APIKeyCreateSerializer, APIKeySerializer

User = get_user_model()


class MicrosoftLogin(SocialLoginView):
    """Handle Microsoft Entra ID OAuth2 login via the Microsoft Graph adapter."""

    adapter_class = MicrosoftGraphOAuth2Adapter
    callback_url = "http://localhost:3000/api/auth/callback/microsoft-entra-id"
    client_class = OAuth2Client


class APIKeyListCreateView(APIView):
    """
    GET  - list all active API keys (admin only).
    POST - generate a new key and return the raw value once (admin only).
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        keys = APIKey.objects.filter(is_active=True)
        return Response(APIKeySerializer(keys, many=True).data)

    def post(self, request):
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_service_user = User.objects.get(username="api_service")
        instance, raw_key = APIKey.generate(
            description=serializer.validated_data["description"],
            created_by=request.user,
            user=api_service_user,
        )
        return Response(
            {
                **APIKeySerializer(instance).data,
                "key": raw_key,
            },
            status=status.HTTP_201_CREATED,
        )


class APIKeyRevokeView(APIView):
    """
    DELETE - revoke (soft-delete) an API key by ID (admin only).
    """

    permission_classes = [IsAdminUser]

    def delete(self, request, key_id):
        try:
            key = APIKey.objects.get(id=key_id, is_active=True)
        except APIKey.DoesNotExist:
            return Response(
                {"detail": "API key not found or already revoked."},
                status=status.HTTP_404_NOT_FOUND,
            )
        key.is_active = False
        key.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
