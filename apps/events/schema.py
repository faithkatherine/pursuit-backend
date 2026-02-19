from .types import EventType
from .models import Event
import graphene

MAX_LIMIT = 100


class EventsQueries(graphene.ObjectType):
    events = graphene.List(EventType, offset=graphene.Int(), limit=graphene.Int())

    def resolve_events(self, info, offset=0, limit=10):
        offset = max(0, offset)
        limit = max(1, min(limit, MAX_LIMIT))
        return Event.objects.filter(is_active=True)[offset:offset + limit]