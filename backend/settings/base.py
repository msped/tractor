import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")

# Public origin the frontend is served from. Used both for the Microsoft OAuth
# callback URL and (in production) as the sole allowed CORS origin.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

INSTALLED_APPS = [
    "django.contrib.sites",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "auditlog",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "corsheaders",
    "dj_rest_auth",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "django_q",
    "authentication",
    "cases",
    "training",
    "django_cleanup.apps.CleanupConfig",
]

SITE_ID = 1

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


# Database
# Priority 1: DATABASE_URL  (e.g. postgresql://user:pass@host:5432/db)
# Priority 2: Individual POSTGRES_* variables (Docker Compose default)

_database_url = os.environ.get("DATABASE_URL")

if _database_url:
    _db_config = dj_database_url.parse(_database_url)
else:
    _db_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }

DATABASES = {
    "default": {
        **_db_config,
        "CONN_MAX_AGE": 600,
        "TEST": {"NAME": "testdatabase"},
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"

MEDIA_URL = "/media/"

# Media file storage backend — set MEDIA_STORAGE=s3 or MEDIA_STORAGE=azure
# to use cloud storage. Requires django-storages and the relevant extras:
#   S3:    pip install django-storages[s3]
#   Azure: pip install django-storages[azure]
_MEDIA_STORAGE = os.environ.get("MEDIA_STORAGE", "local")

if _MEDIA_STORAGE == "s3":
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME"),
                "region_name": os.environ.get(
                    "AWS_S3_REGION_NAME", "us-east-1"
                ),
                "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
                "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
elif _MEDIA_STORAGE == "azure":
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "account_name": os.environ.get("AZURE_ACCOUNT_NAME"),
                "account_key": os.environ.get("AZURE_ACCOUNT_KEY"),
                "azure_container": os.environ.get("AZURE_CONTAINER"),
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "authentication.authentication.APIKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Rate limits are opt-in per view via `throttle_scope`; only the auth
    # endpoints below are throttled (brute-force / credential-stuffing defence).
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
    },
    "EXCEPTION_HANDLER": "backend.exception_handler.api_exception_handler",
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_HTTPONLY": False,
    "USER_DETAILS_SERIALIZER": "authentication.serializers.UserDetailsSerializer",
}

APPEND_SLASH = False

_JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY")
if not _JWT_SIGNING_KEY:
    raise ValueError("JWT_SIGNING_KEY environment variable must be set")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=24),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": _JWT_SIGNING_KEY,
    "ALGORITHM": "HS512",
}

ACCOUNT_EMAIL_VERIFICATION = "none"

DELETE_ORIGINAL_FILES = False
DELETE_ORIGINAL_FILES_AFTER_DAYS = 30

AUTO_CASE_DELETION_ENABLED = os.environ.get(
    "AUTO_CASE_DELETION_ENABLED", "true"
).lower() in ("true", "1", "yes")
RETENTION_WARNING_DAYS = int(os.environ.get("RETENTION_WARNING_DAYS", 30))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_ENABLED = os.environ.get("OLLAMA_ENABLED", "False").lower() in (
    "true",
    "1",
    "yes",
)
OLLAMA_CHUNK_SIZE = int(os.environ.get("OLLAMA_CHUNK_SIZE", 4000))
OLLAMA_CHUNK_OVERLAP = int(os.environ.get("OLLAMA_CHUNK_OVERLAP", 200))

_retention_schedule = {}
if AUTO_CASE_DELETION_ENABLED:
    _retention_schedule["delete_old_cases_daily"] = {
        "func": "cases.tasks.delete_cases_past_retention_date",
        "schedule_type": "D",
    }

Q_CLUSTER = {
    "name": "DjangORM",
    "workers": 4,
    "timeout": 1800,
    "retry": 2100,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
    "schedule": {
        **_retention_schedule,
        "delete_original_files_daily": {
            "func": "cases.tasks.delete_original_files_past_threshold",
            "schedule_type": "D",
        },
    },
}


# Without an explicit LOGGING config, Django's default only wires the `django`
# logger behind a require_debug_true filter. With DEBUG=False our own loggers
# (cases.*, training.*, authentication.*) fall through to Python's lastResort
# handler: stderr, WARNING and above, no timestamp, no logger name. Every
# logger.info in the export/retention/training paths is dropped, and errors
# arrive with no context. Wire the app loggers explicitly so container logs
# capture them.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "{asctime} {levelname} {name} {module}:{lineno} {message}"
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        # django.request logs 4xx at WARNING and 5xx at ERROR with the request
        # path attached — the trail that was missing during the login outage.
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "authentication": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "cases": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "training": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
