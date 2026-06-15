# Test settings for Django
import os

from .settings.development import *  # noqa: F401,F403

# Use PostGIS for tests (matches CI service container)
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "pursuit_db"),
        "USER": os.environ.get("DB_USER", "pursuit_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "pursuit_password"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Disable migrations for faster tests


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Use simple static file storage for tests (no manifest required)
STORAGES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Disable cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Disable celery
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable logging in tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
    },
}
