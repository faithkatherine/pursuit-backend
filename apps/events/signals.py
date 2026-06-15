from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Event

EVENTS_CACHE_VERSION_KEY = "events:version"


@receiver([post_save, post_delete], sender=Event)
def invalidate_events_cache(sender, **kwargs):
    """Bump the events cache version so all existing event cache keys become stale."""
    try:
        cache.incr(EVENTS_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(EVENTS_CACHE_VERSION_KEY, 1)
