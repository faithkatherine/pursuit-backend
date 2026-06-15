import graphene
from graphene_django import DjangoObjectType

from .models import Event, TicketTier


class TicketTierType(DjangoObjectType):
    """Ticket tier GraphQL type"""

    class Meta:
        model = TicketTier
        fields = (
            "id",
            "name",
            "description",
            "price",
            "available",
            "capacity",
            "is_active",
            "sort_order",
        )


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
    ticket_tiers = graphene.List(graphene.NonNull(TicketTierType))

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'description', 'category', 'date', 'end_date',
            'image', 'timezone', 'location_name', 'more_details_url',
            'created_at', 'updated_at',
        )

    def resolve_coordinates(self, info):
        if self.location is None:
            return None
        return [self.location.y, self.location.x]

    def resolve_ticket_tiers(self, info):
        """Return active ticket tiers for this event, ordered by sort_order and price"""
        return self.ticket_tiers.filter(is_active=True)
