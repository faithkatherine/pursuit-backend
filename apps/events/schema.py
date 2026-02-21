import graphene
from django.core.cache import cache

from .models import Event
from .signals import EVENTS_CACHE_VERSION_KEY
from .types import EventType

MAX_LIMIT = 100
EVENTS_CACHE_TTL = 300  # 5 minutes


def _get_events_cache_version():
    version = cache.get(EVENTS_CACHE_VERSION_KEY)
    if version is None:
        cache.set(EVENTS_CACHE_VERSION_KEY, 1)
        version = 1
    return version


class EventsListPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    events = graphene.List(graphene.NonNull(EventType), required=True)


class EventsQueries(graphene.ObjectType):
    get_events = graphene.Field(
        EventsListPayload,
        category=graphene.String(),
        offset=graphene.Int(),
        limit=graphene.Int(),
    )

    def resolve_get_events(self, info, category=None, offset=0, limit=20):
        offset = max(0, offset)
        limit = max(1, min(limit, MAX_LIMIT))

        version = _get_events_cache_version()
        cache_key = f"events:v{version}:{category or 'all'}:{offset}:{limit}"
        event_ids = cache.get(cache_key)

        if event_ids is None:
            qs = Event.objects.filter(is_active=True)
            if category:
                qs = qs.filter(category__name__iexact=category)
            events = list(qs[offset : offset + limit])
            event_ids = [e.pk for e in events]
            cache.set(cache_key, event_ids, EVENTS_CACHE_TTL)
        else:
            events = list(Event.objects.filter(pk__in=event_ids))
            # Preserve original ordering
            id_order = {pk: i for i, pk in enumerate(event_ids)}
            events.sort(key=lambda e: id_order[e.pk])

        return EventsListPayload(ok=True, events=events)
