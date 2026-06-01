import graphene
from graphene_django import DjangoObjectType

from .models import Event


class EventType(DjangoObjectType):
    """Event GraphQL type"""

    coordinates = graphene.List(graphene.Float)
    is_saved = graphene.Boolean()
    is_editors_pick = graphene.Boolean()
    has_confirmed_ticket = graphene.Boolean()
    reason = graphene.String()
    source = graphene.String()
    curator_note = graphene.String()
    curator_name = graphene.String()

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
            "price",
            "ticketing_enabled",
            "available_tickets",
            "going_count",
            "has_gallery",
            "gallery_images",
            "gallery_description",
            "series_name",
            "created_at",
            "updated_at",
            "is_active",
            "is_free",
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

    def resolve_reason(self, info):
        return getattr(self, "_reason", None)

    def resolve_source(self, info):
        return getattr(self, "_source", None)

    def resolve_is_editors_pick(self, info):
        """Return True if this event is currently shown as an Editor's Pick"""
        return getattr(self, "_is_editors_pick", False)

    def resolve_has_confirmed_ticket(self, info):
        """Return True when the current user has a confirmed booking for this event."""
        return getattr(self, "_has_confirmed_ticket", False)

    def resolve_curator_note(self, info):
        """Return curator note from EditorsPick (set at query time)"""
        return getattr(self, "_curator_note", None)

    def resolve_curator_name(self, info):
        """Return curator name from EditorsPick (set at query time)"""
        return getattr(self, "_curator_name", None)

    def resolve_coordinates(self, info):
        if self.location is None:
            return None
        return [self.location.y, self.location.x]
