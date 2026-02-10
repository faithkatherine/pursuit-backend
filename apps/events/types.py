from graphene_django import DjangoObjectType
from .models import EventCategory, Event



class EventType(DjangoObjectType):
    """Event GraphQL type"""

    class Meta:
        model = Event
        fields = '__all__'
