from pathlib import Path

from .base import *  # noqa: F401, F403

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = True

ALLOWED_HOSTS = ["*"]

MEDIA_ROOT = BASE_DIR / "media"
