import os
from pathlib import Path

from .base import *  # noqa: F401, F403

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = False

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN]  # noqa: F405 (from base import *)

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = BASE_DIR / "mediafiles"

# Set USE_HTTPS=false for HTTP-only deployments (e.g. local prod testing).
# When TLS is terminated at a proxy (nginx), keep it true and let the proxy
# forward X-Forwarded-Proto so Django recognises the original scheme instead
# of redirecting internal plain-HTTP service-to-service calls.
USE_HTTPS = os.environ.get("USE_HTTPS", "true").lower() != "false"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
