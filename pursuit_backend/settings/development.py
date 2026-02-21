"""
Django development settings for pursuit_backend project.

Used for local development. This is the default for manage.py.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ['*']

CORS_ALLOW_ALL_ORIGINS = True

# Security relaxed for local dev
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False

# Console email for local dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# JWT: fall back to SECRET_KEY in development if JWT_SECRET_KEY not set
if not JWT_SECRET_KEY:  # noqa: F405
    JWT_SECRET_KEY = SECRET_KEY  # noqa: F405
