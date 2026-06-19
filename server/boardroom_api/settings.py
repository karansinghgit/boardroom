"""Minimal Django settings for the BoardRoom API.

This is an API-only service with no database, templates, sessions, or admin: it
exists solely to expose the debate engine over HTTP for the frontend. Keeping
the installed apps and middleware minimal makes it easy to read and quick to
boot.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-do-not-use-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = ["api"]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "boardroom_api.urls"
WSGI_APPLICATION = "boardroom_api.wsgi.application"
ASGI_APPLICATION = "boardroom_api.asgi.application"

# No database is used; the service is stateless.
DATABASES: dict = {}

TEMPLATES: list = []

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
