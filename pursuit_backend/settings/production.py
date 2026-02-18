"""
Django production settings for pursuit_backend project.

Strict security, required secrets validation. This is the default
for wsgi.py and asgi.py (i.e., gunicorn deployments).
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('ALLOWED_HOSTS', '').split(',')
    if h.strip()
]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if o.strip()
]

# Strict security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static files served by WhiteNoise
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Startup validation: fail fast if required secrets are missing
# ---------------------------------------------------------------------------
_errors = []

if SECRET_KEY == 'django-insecure-change-me-in-production':
    _errors.append(
        "SECRET_KEY is still the insecure default. "
        "Set a strong SECRET_KEY env var for production."
    )

if not JWT_SECRET_KEY:
    _errors.append(
        "JWT_SECRET_KEY must be set in production. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )

if not ALLOWED_HOSTS:
    _errors.append(
        "ALLOWED_HOSTS must be set in production (comma-separated)."
    )

if os.environ.get('DB_PASSWORD', 'pursuit_password') == 'pursuit_password':
    _errors.append(
        "DB_PASSWORD is still the insecure default. "
        "Set a strong DB_PASSWORD env var for production."
    )

if _errors:
    raise ValueError(
        "Production settings validation failed:\n  - " + "\n  - ".join(_errors)
    )
