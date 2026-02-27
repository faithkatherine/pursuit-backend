import graphene
from graphene_django import DjangoObjectType

from .models import Event


class EventType(DjangoObjectType):
    """Event GraphQL type"""

    coordinates = graphene.List(graphene.Float)
    is_saved = graphene.Boolean()

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

    def resolve_is_saved(self, info):
        # Use annotation from queryset if available (no extra query)
        if hasattr(self, "_is_saved"):
            return self._is_saved
        # Fallback for single-event lookups
        user = info.context.user
        if not user.is_authenticated:
            return False
        return self.user_interactions.filter(user=user).exists()

    def resolve_coordinates(self, info):
        if self.location is None:
            return None
        return [self.location.y, self.location.x]
