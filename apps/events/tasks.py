"""
Celery tasks for the events app.
"""

from celery import shared_task
from django.core.cache import cache

from .signals import EVENTS_CACHE_VERSION_KEY


@shared_task(ignore_result=True)
def refresh_events_cache():
    """
    Periodically increment the events cache version to ensure fresh data.

    This runs every 5 minutes as a safety net in case signals fail to fire.
    The actual cache has a 5-minute TTL, so this ensures even if a signal
    is missed, the cache will be refreshed.
    """
    try:
        cache.incr(EVENTS_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(EVENTS_CACHE_VERSION_KEY, 1)

    return "Events cache version incremented"


@shared_task(ignore_result=True)
def cleanup_stale_event_caches():
    """
    Remove old event cache entries.

    The cache version system makes old entries stale but doesn't delete them.
    This task periodically cleans them up to free Redis memory.
    """
    try:
        # Pattern match all event cache keys
        pattern = "events:v*"
        deleted_count = 0

        # Note: This requires Redis. If using different cache backend,
        # this task will silently pass.
        if hasattr(cache, '_cache') and hasattr(cache._cache, 'scan_iter'):
            for key in cache._cache.scan_iter(match=pattern):
                # Keep keys with current version, delete old ones
                current_version = cache.get(EVENTS_CACHE_VERSION_KEY, 1)
                if f":v{current_version}:" not in key.decode() if isinstance(key, bytes) else key:
                    cache.delete(key.decode() if isinstance(key, bytes) else key)
                    deleted_count += 1

        return f"Cleaned up {deleted_count} stale cache entries"
    except Exception as e:
        # Fail silently - cache cleanup is non-critical
        return f"Cache cleanup failed: {str(e)}"
