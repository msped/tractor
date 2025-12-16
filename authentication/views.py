from allauth.socialaccount.providers.microsoft.views import MicrosoftGraphOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.oauth2.client import OAuth2Client


class MicrosoftLogin(SocialLoginView):
    adapter_class = MicrosoftGraphOAuth2Adapter
    callback_url = "http://localhost:3000/api/auth/callback/microsoft-entra-id"
    client_class = OAuth2Client
