import graphene
from graphene_django import DjangoObjectType

from .models import Event


class EventType(DjangoObjectType):
    """Event GraphQL type"""

    coordinates = graphene.List(graphene.Float)

    class Meta:
        model = Event
        fields = (
            "id",
            "name",
            "description",
            "category",
            "date",
            "end_date",
            "image",
            "timezone",
            "location_name",
            "more_details_url",
            "created_at",
            "updated_at",
            "is_active",
        )

    def resolve_coordinates(self, info):
        if self.location is None:
            return None
        return [self.location.y, self.location.x]
