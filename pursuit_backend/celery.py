import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pursuit_backend.settings.production")

app = Celery("pursuit_backend")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related config keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    "cleanup-expired-tokens-daily": {
        "task": "apps.users.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=2, minute=0),  # Run at 2:00 AM daily
    },
    "refresh-events-cache": {
        "task": "apps.events.tasks.refresh_events_cache",
        "schedule": 300.0,  # Every 5 minutes (matches EVENTS_CACHE_TTL)
    },
    "cleanup-stale-event-caches-hourly": {
        "task": "apps.events.tasks.cleanup_stale_event_caches",
        "schedule": crontab(minute=0),  # Every hour on the hour
    },
}

app.conf.timezone = "UTC"


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
