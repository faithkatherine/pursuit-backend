import graphene
from graphene_django import DjangoObjectType

from .models import Event, TicketTier


class UserTicketType(graphene.ObjectType):
    """User's ticket information for an event"""
    order_id = graphene.ID(required=True)
    ticket_count = graphene.Int(required=True)
    total_paid = graphene.String(required=True)
    tier_name = graphene.String()
    purchase_date = graphene.DateTime(required=True)


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
    is_going = graphene.Boolean()
    is_editors_pick = graphene.Boolean()
    has_confirmed_ticket = graphene.Boolean()
    user_ticket = graphene.Field(UserTicketType)
    is_external = graphene.Boolean()
    is_internal = graphene.Boolean()
    reason = graphene.String()
    source = graphene.String()
    curator_note = graphene.String()
    curator_name = graphene.String()
    ticket_tiers = graphene.List(graphene.NonNull(TicketTierType))
    user_status = graphene.String()

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
            "status",
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

    def resolve_is_going(self, info):
        # Use annotation from queryset if available (no extra query)
        if hasattr(self, "_is_going"):
            return self._is_going
        # Fallback for single-event lookups
        user = info.context.user
        if not user.is_authenticated:
            return False
        from .models import EventGoing
        return EventGoing.objects.filter(user=user, event=self).exists()

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

    def resolve_ticket_tiers(self, info):
        """Return active ticket tiers for this event, ordered by sort_order and price"""
        return self.ticket_tiers.filter(is_active=True)

    def resolve_user_ticket(self, info):
        """Return user's ticket info if they have purchased a ticket for this event"""
        user = info.context.user
        if not user.is_authenticated:
            return None

        # Use cached ticket info if available (set by resolver)
        if hasattr(self, "_user_ticket_info"):
            return self._user_ticket_info

        # Fallback: query for user's paid order for this event
        from apps.payments.models import Order

        order = Order.objects.filter(
            user=user,
            event=self,
            status='paid'
        ).select_related('mpesa_transaction').prefetch_related('items__tickets').first()

        if not order:
            return None

        # Count total tickets across all order items
        ticket_count = sum(item.tickets.count() for item in order.items.all())

        # Get primary tier name (from first order item)
        tier_name = None
        if order.items.exists():
            tier_name = order.items.first().tier.name

        return UserTicketType(
            order_id=str(order.id),
            ticket_count=ticket_count,
            total_paid=str(order.total),
            tier_name=tier_name,
            purchase_date=order.paid_at or order.created_at
        )

    def resolve_is_external(self, info):
        """Return True if event has external ticketing (more_details_url exists)"""
        return bool(self.more_details_url)

    def resolve_is_internal(self, info):
        """Return True if event uses internal ticketing (no more_details_url)"""
        return not bool(self.more_details_url)

    def resolve_user_status(self, info):
        """Return user's status for this event: 'WENT', 'SAVED', or None"""
        return getattr(self, "_user_status", None)
