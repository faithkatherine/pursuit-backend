import graphene

from apps.events.models import Event

from .models import Trip
from .types import TripType


class TripPayload(graphene.ObjectType):
    """Response payload for trip mutations."""

    ok = graphene.Boolean(required=True)
    trip = graphene.Field(TripType)
    errors = graphene.List(graphene.NonNull(graphene.String))


class CreateTripMutation(graphene.Mutation):
    """Create a new trip."""

    class Arguments:
        name = graphene.String(required=True)
        destination = graphene.String(required=True)
        start_date = graphene.DateTime(required=True)
        end_date = graphene.DateTime(required=True)
        image = graphene.String()
        event_ids = graphene.List(graphene.ID)

    Output = TripPayload

    def mutate(self, info, name, destination, start_date, end_date, image=None, event_ids=None):
        user = info.context.user
        if not user.is_authenticated:
            return TripPayload(ok=False, trip=None, errors=["Authentication required."])

        if end_date < start_date:
            return TripPayload(ok=False, trip=None, errors=["End date cannot be before start date."])

        trip = Trip.objects.create(
            user=user,
            name=name,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            image=image or "",
        )

        if event_ids:
            events = Event.objects.filter(pk__in=event_ids, is_active=True)
            trip.events.set(events)

        return TripPayload(ok=True, trip=trip, errors=[])


class AddEventToTripMutation(graphene.Mutation):
    """Add an event to an existing trip."""

    class Arguments:
        trip_id = graphene.ID(required=True)
        event_id = graphene.ID(required=True)

    Output = TripPayload

    def mutate(self, info, trip_id, event_id):
        user = info.context.user
        if not user.is_authenticated:
            return TripPayload(ok=False, trip=None, errors=["Authentication required."])

        try:
            trip = Trip.objects.get(pk=trip_id, user=user)
        except Trip.DoesNotExist:
            return TripPayload(ok=False, trip=None, errors=["Trip not found."])

        try:
            event = Event.objects.get(pk=event_id, is_active=True)
        except Event.DoesNotExist:
            return TripPayload(ok=False, trip=None, errors=["Event not found."])

        trip.events.add(event)
        return TripPayload(ok=True, trip=trip, errors=[])


class RemoveEventFromTripMutation(graphene.Mutation):
    """Remove an event from a trip."""

    class Arguments:
        trip_id = graphene.ID(required=True)
        event_id = graphene.ID(required=True)

    Output = TripPayload

    def mutate(self, info, trip_id, event_id):
        user = info.context.user
        if not user.is_authenticated:
            return TripPayload(ok=False, trip=None, errors=["Authentication required."])

        try:
            trip = Trip.objects.get(pk=trip_id, user=user)
        except Trip.DoesNotExist:
            return TripPayload(ok=False, trip=None, errors=["Trip not found."])

        trip.events.remove(event_id)
        return TripPayload(ok=True, trip=trip, errors=[])


class ItineraryQueries(graphene.ObjectType):
    """Itinerary GraphQL queries"""

    pass


class ItineraryMutations(graphene.ObjectType):
    """Itinerary GraphQL mutations"""

    create_trip = CreateTripMutation.Field()
    add_event_to_trip = AddEventToTripMutation.Field()
    remove_event_from_trip = RemoveEventFromTripMutation.Field()
