from .types import EventType
from .models import  Event
import graphene

    
class GetEvents(graphene.ObjectType):
    events = graphene.List(EventType, offset=graphene.Int(), limit=graphene.Int())

    def resolve_events(self, info, offset=0, limit=10):
        return Event.objects.all()[offset:offset + limit]