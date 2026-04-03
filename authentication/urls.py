from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import LoginView, LogoutView, UserDetailsView
from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import APIKeyListCreateView, APIKeyRevokeView, MicrosoftLogin

urlpatterns = [
    path("login", LoginView.as_view(), name="rest_login"),
    path("logout", LogoutView.as_view(), name="rest_logout"),
    path("user", UserDetailsView.as_view(), name="rest_user_details"),
    path("token/verify", TokenVerifyView.as_view(), name="token_verify"),
    path("token/refresh", get_refresh_view().as_view(), name="token_refresh"),
    path("microsoft", MicrosoftLogin.as_view(), name="microsoft_login"),
    path(
        "api-keys", APIKeyListCreateView.as_view(), name="api-key-list-create"
    ),
    path(
        "api-keys/<int:key_id>",
        APIKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
]
