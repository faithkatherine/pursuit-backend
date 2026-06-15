import hashlib
import json

import graphene
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.cache import cache
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from graphql import GraphQLError

from .locations import location_tag_from_coords
from .models import EditorsPick, Event, UserEvents
from .signals import EVENTS_CACHE_VERSION_KEY
from .types import EventType

MAX_LIMIT = 100
EVENTS_CACHE_TTL = 300  # 5 minutes


def _annotate_is_saved(queryset, user):
    """Annotate each event with _is_saved for the given user (single query, no N+1)."""
    if not user.is_authenticated:
        return queryset
    return queryset.annotate(
        _is_saved=Exists(
            UserEvents.objects.filter(user=user, event=OuterRef("pk"))
        )
    )


def _get_events_cache_version():
    """Return the current cache version, initializing to 1 if unset."""
    version = cache.get(EVENTS_CACHE_VERSION_KEY)
    if version is None:
        cache.set(EVENTS_CACHE_VERSION_KEY, 1)
        version = 1
    return version


def _get_user_location_tag(user):
    if not user.is_authenticated:
        return "nairobi"

    profile = getattr(user, "profile", None)
    if not profile:
        return "nairobi"

    if profile.allow_location_sharing and profile.coordinates:
        lat, lon = profile.coordinates
        effective_tag = location_tag_from_coords(lat, lon)
        if profile.last_synced_location_tag != effective_tag:
            profile.last_synced_location_tag = effective_tag
            profile.save(update_fields=["last_synced_location_tag"])
        return effective_tag

    return profile.last_synced_location_tag or "nairobi"


def _attach_active_editors_pick(event, user):
    effective_tag = _get_user_location_tag(user)
    editors_pick = (
        EditorsPick.objects.filter(
            event=event,
            location_tag=effective_tag,
            active_from__lte=timezone.now(),
            active_until__gte=timezone.now(),
            position=1,
        )
        .order_by("-active_from")
        .first()
    )

    event._is_editors_pick = bool(editors_pick)
    if editors_pick:
        event._reason = "Editor's pick"
        event._source = "editorial"
        event._curator_note = editors_pick.curator_note
        event._curator_name = editors_pick.curator_name

    return event


class EventsListPayload(graphene.ObjectType):
    """Response payload for paginated event list queries."""

    ok = graphene.Boolean(required=True)
    events = graphene.List(graphene.NonNull(EventType), required=True)


class EventPayload(graphene.ObjectType):
    """Response payload for single event queries."""

    ok = graphene.Boolean(required=True)
    event = graphene.Field(EventType)


class SaveEventPayload(graphene.ObjectType):
    """Response payload for save/unsave event mutations."""

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
    """Mutations for saving and unsaving events."""

    save_event = SaveEventMutation.Field()
    unsave_event = UnsaveEventMutation.Field()


class EventsQueries(graphene.ObjectType):
    """Queries for listing, searching, and retrieving events."""

    events = graphene.Field(
        EventsListPayload,
        search=graphene.String(),
        category=graphene.List(graphene.ID),
        date_from=graphene.DateTime(),
        date_to=graphene.DateTime(),
        latitude=graphene.Float(),
        longitude=graphene.Float(),
        radius_km=graphene.Float(),
        is_free=graphene.Boolean(),
        offset=graphene.Int(),
        limit=graphene.Int(),
    )
    event = graphene.Field(
        EventPayload,
        id=graphene.ID(required=True),
    )
    saved_events = graphene.Field(
        EventsListPayload,
        offset=graphene.Int(),
        limit=graphene.Int(),
    )

    def resolve_events(
        self,
        info,
        search=None,
        category=None,
        date_from=None,
        date_to=None,
        latitude=None,
        longitude=None,
        radius_km=None,
        is_free=None,
        offset=0,
        limit=20,
    ):
        """Return a paginated list of active events with optional filters.

        All filters combine with AND logic. Results are cached by a hash of
        the filter parameters and invalidated when the cache version increments.
        """
        user = info.context.user
        offset = max(0, offset)
        limit = max(1, min(limit, MAX_LIMIT))

        version = _get_events_cache_version()
        filter_params = {
            "search": search,
            "category": sorted(category) if category else [],
            "dateFrom": str(date_from),
            "dateTo": str(date_to),
            "latitude": latitude,
            "longitude": longitude,
            "radiusKm": radius_km,
            "isFree": is_free,
        }
        params_hash = hashlib.md5(
            json.dumps(filter_params, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]
        cache_key = f"events:v{version}:{params_hash}:{offset}:{limit}"
        event_ids = cache.get(cache_key)

        if event_ids is None:
            qs = Event.objects.filter(is_active=True)

            if search:
                qs = qs.filter(
                    Q(name__icontains=search) | Q(description__icontains=search)
                )
            if category:
                qs = qs.filter(category__id__in=category).distinct()
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
            if latitude is not None and longitude is not None:
                radius = radius_km if radius_km is not None else 50
                point = Point(longitude, latitude, srid=4326)
                qs = qs.filter(location__dwithin=(point, D(km=radius)))
            if is_free is not None:
                qs = qs.filter(is_free=is_free)

            events = list(qs[offset : offset + limit])
            event_ids = [e.pk for e in events]
            cache.set(cache_key, event_ids, EVENTS_CACHE_TTL)
        else:
            events = list(Event.objects.filter(pk__in=event_ids))
            # Preserve original ordering
            id_order = {pk: i for i, pk in enumerate(event_ids)}
            events.sort(key=lambda e: id_order[e.pk])

        # Annotate is_saved in a single query instead of N+1
        if user.is_authenticated and events:
            saved_ids = set(
                UserEvents.objects.filter(
                    user=user, event_id__in=[e.pk for e in events]
                ).values_list("event_id", flat=True)
            )
            for event in events:
                event._is_saved = event.pk in saved_ids

        return EventsListPayload(ok=True, events=events)

    def resolve_saved_events(self, info, offset=0, limit=20):
        """Return the authenticated user's saved events, ordered by most recently saved."""
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required.")

        offset = max(0, offset)
        limit = max(1, min(limit, MAX_LIMIT))

        qs = (
            _annotate_is_saved(
                Event.objects.filter(
                    user_interactions__user=user,
                    is_active=True,
                ),
                user,
            )
            .prefetch_related("category")
            .order_by("-user_interactions__created_at")
        )
        return EventsListPayload(ok=True, events=list(qs[offset : offset + limit]))

    def resolve_event(self, info, id):
        """Return a single active event by ID. Raises GraphQLError if not found or inactive."""
        try:
            event = Event.objects.prefetch_related("category").get(pk=id)
        except Event.DoesNotExist:
            raise GraphQLError("Event not found.")

        if not event.is_active:
            raise GraphQLError("Event not found.")

        if info.context.user.is_authenticated:
            event._is_saved = UserEvents.objects.filter(
                user=info.context.user, event=event
            ).exists()

        _attach_active_editors_pick(event, info.context.user)

        return EventPayload(ok=True, event=event)
