import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY")

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
    )
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_HTTPONLY": False,
    "USER_DETAILS_SERIALIZER": "authentication.serializers.UserDetailsSerializer",
}

APPEND_SLASH = False

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=24),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY"),
    "ALGORITHM": "HS512",
}

ACCOUNT_EMAIL_VERIFICATION = "none"

DELETE_ORIGINAL_FILES = False
DELETE_ORIGINAL_FILES_AFTER_DAYS = 30

Q_CLUSTER = {
    "name": "DjangORM",
    "workers": 4,
    "timeout": 1800,
    "retry": 2100,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
    "schedule": {
        "delete_old_cases_daily": {
            "func": "cases.services.delete_cases_past_retention_date",
            "schedule_type": "D",
        },
        "delete_original_files_daily": {
            "func": "cases.services.delete_original_files_past_threshold",
            "schedule_type": "D",
        },
    },
}
