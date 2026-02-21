import graphene

from .models import Event
from .types import EventType

MAX_LIMIT = 100


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

        events = Event.objects.filter(is_active=True)

        if category:
            events = events.filter(category__name__iexact=category)

        return EventsListPayload(ok=True, events=events[offset : offset + limit])
