import graphene
from django.core.cache import cache
from graphql import GraphQLError

from .models import Event, UserEvents
from .signals import EVENTS_CACHE_VERSION_KEY
from .types import EventType

MAX_LIMIT = 100
EVENTS_CACHE_TTL = 300  # 5 minutes


def _get_events_cache_version():
    version = cache.get(EVENTS_CACHE_VERSION_KEY)
    if version is None:
        cache.set(EVENTS_CACHE_VERSION_KEY, 1)
        version = 1
    return version


class EventsListPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    events = graphene.List(graphene.NonNull(EventType), required=True)


class EventPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    event = graphene.Field(EventType)


class SaveEventPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    event = graphene.Field(EventType)
    errors = graphene.List(graphene.NonNull(graphene.String))


class SaveEventMutation(graphene.Mutation):
    """Allow a user to save an event to their profile for later reference."""

    class Arguments:
        id = graphene.ID(required=True)

    Output = SaveEventPayload

    def mutate(self, info, id):
        if not info.context.user.is_authenticated:
            return SaveEventPayload(
                ok=False, event=None, errors=["Authentication required."]
            )

        try:
            event = Event.objects.get(pk=id, is_active=True)
            UserEvents.objects.get_or_create(user=info.context.user, event=event)
            return SaveEventPayload(ok=True, event=event, errors=[])

        except Event.DoesNotExist:
            return SaveEventPayload(ok=False, event=None, errors=["Event not found."])


class UnsaveEventMutation(graphene.Mutation):
    """Remove an event from the user's saved list."""

    class Arguments:
        id = graphene.ID(required=True)

    Output = SaveEventPayload

    def mutate(self, info, id):
        if not info.context.user.is_authenticated:
            return SaveEventPayload(
                ok=False, event=None, errors=["Authentication required."]
            )

        try:
            event = Event.objects.get(pk=id, is_active=True)
        except Event.DoesNotExist:
            return SaveEventPayload(ok=False, event=None, errors=["Event not found."])

        deleted_count, _ = UserEvents.objects.filter(user=info.context.user, event=event).delete()
        if deleted_count == 0:
            return SaveEventPayload(ok=False, event=None, errors=["Event is not in your saved list."])

        return SaveEventPayload(ok=True, event=event, errors=[])


class EventsMutations(graphene.ObjectType):
    save_event = SaveEventMutation.Field()
    unsave_event = UnsaveEventMutation.Field()


class EventsQueries(graphene.ObjectType):
    events = graphene.Field(
        EventsListPayload,
        category=graphene.String(),
        offset=graphene.Int(),
        limit=graphene.Int(),
    )
    event = graphene.Field(
        EventPayload,
        id=graphene.ID(required=True),
    )
    saved_events = graphene.Field(EventsListPayload)

    def resolve_events(self, info, category=None, offset=0, limit=20):
        offset = max(0, offset)
        limit = max(1, min(limit, MAX_LIMIT))

        version = _get_events_cache_version()
        cache_key = f"events:v{version}:{category or 'all'}:{offset}:{limit}"
        event_ids = cache.get(cache_key)

        if event_ids is None:
            qs = Event.objects.filter(is_active=True)
            if category:
                qs = qs.filter(category__name__iexact=category)
            events = list(qs[offset : offset + limit])
            event_ids = [e.pk for e in events]
            cache.set(cache_key, event_ids, EVENTS_CACHE_TTL)
        else:
            events = list(Event.objects.filter(pk__in=event_ids))
            # Preserve original ordering
            id_order = {pk: i for i, pk in enumerate(event_ids)}
            events.sort(key=lambda e: id_order[e.pk])

        return EventsListPayload(ok=True, events=events)

    def resolve_saved_events(self, info):
        if not info.context.user.is_authenticated:
            raise GraphQLError("Authentication required.")

        saved = (
            Event.objects.filter(
                user_interactions__user=info.context.user,
                is_active=True,
            )
            .prefetch_related("category")
            .order_by("-user_interactions__created_at")
        )
        return EventsListPayload(ok=True, events=list(saved))

    def resolve_event(self, info, id):
        try:
            event = Event.objects.prefetch_related("category").get(pk=id)
        except Event.DoesNotExist:
            raise GraphQLError("Event not found.")

        if not event.is_active:
            raise GraphQLError("Event not found.")

        return EventPayload(ok=True, event=event)
