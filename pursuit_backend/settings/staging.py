"""
Django staging settings for pursuit_backend project.

Production-like but with staging-specific configuration.
"""

import os

import dj_database_url

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

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Database — prefer DATABASE_URL (provided by Render) over individual vars
_db_url = os.environ.get('DATABASE_URL')
if _db_url:
    DATABASES['default'] = dj_database_url.config(  # noqa: F405
        default=_db_url,
        engine='django.contrib.gis.db.backends.postgis',
    )

# Static files served by WhiteNoise
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
