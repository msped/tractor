import hashlib

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticates requests carrying an 'Authorization: Api-Key <key>' header.
    Returns (api_key.user, api_key) on success; None if the header is absent
    so the next authenticator (JWT) gets a chance.
    """

    PREFIX = "Api-Key "

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.PREFIX):
            return None

        raw_key = auth_header[len(self.PREFIX) :]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            api_key = APIKey.objects.select_related("user").get(
                key_hash=key_hash, is_active=True
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or revoked API key.")

        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return 'Api-Key realm="api"'
