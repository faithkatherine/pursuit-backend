from datetime import timedelta

import graphene
from django.utils import timezone

from apps.core.models import Category

# Determine effective location_tag for Editor's Pick matching
from apps.events.locations import location_tag_from_coords
from apps.events.models import EditorsPick, Event, UserEvents
from apps.itinerary.models import Trip
from apps.recommendations.services import get_recommended_events, get_trending_events

from .models import Neighborhood
from .services import fetch_weather_for_city, fetch_weather_for_coordinates

# ---------------------------------------------------------------------------
# Greeting helpers
# ---------------------------------------------------------------------------

_SUBTITLE_SETS = {
    "morning": [
        "What\u2019s on your radar today?",
        "Pick something for later",
        "Make today count",
    ],
    "afternoon": [
        "Got plans tonight?",
        "Find something for the evening",
        "What\u2019s the move?",
    ],
    "evening": [
        "Where to tonight?",
        "Pick your next adventure",
        "Something fun ahead?",
    ],
    "late": [
        "Anything calling you?",
        "Quiet plans for tomorrow?",
    ],
}


def _get_time_bucket():
    """Return a 4-part time bucket: morning / afternoon / evening / late."""

    hour = timezone.localtime().hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late"


def _get_greeting(first_name=None):
    """Build a time-aware greeting string, e.g. 'Good morning, Faith'."""
    bucket = _get_time_bucket()
    name = f", {first_name}" if first_name else ""
    if bucket == "morning":
        return f"Good morning{name}"
    if bucket == "afternoon":
        return f"Good afternoon{name}"
    if bucket == "evening":
        return f"Good evening{name}"
    # late
    return f"Still up, {first_name}?" if first_name else "Still up?"


def _get_greeting_prompt(user_id=None):
    """Deterministic daily subtitle — stable within a day, changes day-to-day."""

    bucket = _get_time_bucket()
    options = _SUBTITLE_SETS[bucket]
    now = timezone.localtime()
    date_str = f"{now.year}-{now.month - 1}-{now.day}"  # month-1 to match JS Date.getMonth()
    seed = f"{date_str}:{user_id or 'anon'}"
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        # keep within 32-bit signed range to match JS `| 0`
        if h >= 0x80000000:
            h -= 0x100000000
    index = abs(h) % len(options)
    return options[index]


class WeatherType(graphene.ObjectType):
    """GraphQL Weather type"""

    city = graphene.String()
    condition = graphene.String()
    temperature = graphene.Float()
    icon = graphene.String()


class NeighborhoodType(graphene.ObjectType):
    """GraphQL Neighborhood type"""

    id = graphene.ID()
    name = graphene.String()
    city = graphene.String()


class HomeDataType(graphene.ObjectType):
    """GraphQL HomeData type"""

    id = graphene.String()
    greeting = graphene.String()
    greeting_prompt = graphene.String()
    time_of_day = graphene.String()
    day_of_week = graphene.String()
    city_name = graphene.String()
    weather = graphene.Field(WeatherType)
    profile_picture = graphene.String()
    user_location = graphene.String()
    allow_location_sharing = graphene.Boolean()
    active_neighborhood = graphene.Field(NeighborhoodType)
    neighborhoods = graphene.List(NeighborhoodType)
    categories = graphene.List("apps.core.schema.CategoryType")
    recommendations = graphene.List("apps.events.types.EventType")
    trending = graphene.List("apps.events.types.EventType")
    upcoming_events = graphene.List("apps.events.types.EventType")
    active_trip = graphene.Field("apps.itinerary.types.TripType")


def _get_weather_for_neighborhood(neighborhood):
    """Fetch weather for a specific neighborhood's coordinates."""
    return fetch_weather_for_coordinates(
        float(neighborhood.latitude),
        float(neighborhood.longitude),
        city_hint=neighborhood.name,
    )


def _get_weather_for_user(user):
    """Resolve weather using coordinates -> city name -> fallback chain."""
    profile = getattr(user, "profile", None)
    if profile and profile.has_location:
        lat, lon = profile.coordinates
        city_hint = profile.location_name or ""
        return fetch_weather_for_coordinates(lat, lon, city_hint)
    if profile and profile.location_name:
        return fetch_weather_for_city(profile.location_name)
    return fetch_weather_for_city("New York")


def _weather_to_type(weather):
    return WeatherType(
        city=weather.city,
        condition=weather.condition,
        temperature=weather.temperature,
        icon=weather.icon,
    )


def _get_time_of_day():
    """Return time of day string based on current hour."""

    hour = timezone.localtime().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    return "evening"


def _get_day_of_week():
    """Return current day of week name."""

    return timezone.localtime().strftime("%A")


def _get_city_name(user, neighborhood=None):
    """Determine city name from neighborhood or user profile."""
    if neighborhood:
        return neighborhood.city
    profile = getattr(user, "profile", None)
    if profile and profile.location_name:
        # location_name is typically "City, Region" — extract city
        return profile.location_name.split(",")[0].strip()
    return ""


def _resolve_time_filter(time_filter):
    """Translate a time_filter string into (date_from, date_to) datetimes."""

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if time_filter == "weekend":
        # Next Saturday 00:00 → Sunday 23:59 (or current Sat/Sun if already weekend)
        days_until_saturday = (5 - today_start.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            sat = today_start
        elif days_until_saturday == 0:
            sat = today_start + timedelta(days=7)
        else:
            sat = today_start + timedelta(days=days_until_saturday)
        sun_end = sat + timedelta(days=2) - timedelta(seconds=1)
        return now if now >= sat else sat, sun_end

    if time_filter == "next_week":
        days_until_monday = (7 - today_start.weekday()) % 7 or 7
        next_monday = today_start + timedelta(days=days_until_monday)
        next_sunday_end = next_monday + timedelta(days=7) - timedelta(seconds=1)
        return next_monday, next_sunday_end

    # Default: "tonight" — from now until end of today
    tonight_end = today_start + timedelta(days=1) - timedelta(seconds=1)
    return now, tonight_end


class InsightsQueries(graphene.ObjectType):
    """Insights GraphQL queries"""

    get_home = graphene.Field(
        HomeDataType,
        offset=graphene.Int(),
        limit=graphene.Int(),
        neighborhood_id=graphene.ID(),
        time_filter=graphene.String(),
    )

    def resolve_get_home(self, info, offset=0, limit=10, neighborhood_id=None, time_filter=None):
        user = info.context.user
        if not user.is_authenticated:
            return None

        # Resolve time filter → date range
        date_from, date_to = (None, None)
        if time_filter:
            date_from, date_to = _resolve_time_filter(time_filter)

        # Resolve neighborhood
        active_neighborhood = None
        if neighborhood_id:
            active_neighborhood = Neighborhood.objects.filter(id=neighborhood_id).first()

        # Weather: use neighborhood coords if selected, else user's location
        if active_neighborhood:
            weather = _get_weather_for_neighborhood(active_neighborhood)
        else:
            weather = _get_weather_for_user(user)
        weather_type = _weather_to_type(weather)

        profile = getattr(user, "profile", None)

        now = timezone.now()
        effective_tag = "nairobi"  # fallback

        if neighborhood_id and active_neighborhood:
            # Manual filter selected → derive from neighborhood coords
            effective_tag = location_tag_from_coords(
                float(active_neighborhood.latitude), float(active_neighborhood.longitude)
            )
        elif profile and profile.has_location:
            # User has GPS coords → derive tag and update profile
            lat, lon = profile.coordinates
            effective_tag = location_tag_from_coords(lat, lon)
            if profile.last_synced_location_tag != effective_tag:
                profile.last_synced_location_tag = effective_tag
                profile.save(update_fields=["last_synced_location_tag"])
        elif profile and profile.last_synced_location_tag:
            # Use stored tag from last sync
            effective_tag = profile.last_synced_location_tag

        # Check for active trip (takes priority over Editor's Pick)
        thirty_days = now + timedelta(days=30)
        active_trip = (
            Trip.objects.filter(
                user=user,
                end_date__gte=now,
                start_date__lte=thirty_days,
            )
            .prefetch_related("events")
            .order_by("start_date")
            .first()
        )

        # Query Editor's Pick only if no active trip
        editors_pick = None
        editors_pick_event_id = None
        if not active_trip:
            editors_pick = (
                EditorsPick.objects.filter(
                    location_tag=effective_tag,
                    active_from__lte=now,
                    active_until__gte=now,
                    position=1,
                )
                .select_related("event")
                .order_by("-active_from")
                .first()
            )
            if editors_pick:
                editors_pick_event_id = editors_pick.event.id

        # Prepare exclusion list for recommendations and trending
        exclude_event_ids = [editors_pick_event_id] if editors_pick_event_id else []

        # Get personalized event recommendations (excluding EditorsPick)
        rec_results = get_recommended_events(
            user,
            offset=offset,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            exclude_event_ids=exclude_event_ids,
        )
        recommendations = []

        # If Editor's Pick exists, prepend it as the first recommendation
        if editors_pick:
            pick_event = editors_pick.event
            pick_event._reason = "Editor's pick"
            pick_event._source = "editorial"
            pick_event._is_saved = False
            pick_event._curator_note = editors_pick.curator_note
            pick_event._curator_name = editors_pick.curator_name
            pick_event._is_editors_pick = True
            recommendations.append(pick_event)

        # Add algorithm recommendations (already excludes the pick event)
        for event, reason, source in rec_results:
            event._reason = reason
            event._source = source
            event._is_saved = False
            event._is_editors_pick = False
            recommendations.append(event)

        # Get trending events (popularity-based, excluding EditorsPick)
        trending_results = get_trending_events(
            user,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
            exclude_event_ids=exclude_event_ids,
        )
        trending = []
        for event, reason, source in trending_results:
            event._reason = reason
            event._source = source
            event._is_saved = False
            event._is_editors_pick = False
            trending.append(event)

        # Get user's upcoming saved events

        now = timezone.now()
        saved_event_ids = UserEvents.objects.filter(user=user).values_list("event_id", flat=True)
        upcoming = list(
            Event.objects.filter(
                id__in=saved_event_ids,
                is_active=True,
                date__gte=now,
            )
            .prefetch_related("category")
            .order_by("date")[:limit]
        )
        for event in upcoming:
            event._is_saved = True

        # All available neighborhoods
        all_neighborhoods = list(Neighborhood.objects.all())

        return HomeDataType(
            id=str(user.id),
            greeting=_get_greeting(user.first_name),
            greeting_prompt=_get_greeting_prompt(str(user.id)),
            time_of_day=_get_time_of_day(),
            day_of_week=_get_day_of_week(),
            city_name=_get_city_name(user, active_neighborhood),
            weather=weather_type,
            profile_picture=user.profile_picture or "",
            user_location=profile.location_name if profile else "",
            allow_location_sharing=profile.allow_location_sharing if profile else False,
            active_neighborhood=active_neighborhood,
            neighborhoods=all_neighborhoods,
            categories=Category.objects.filter(is_active=True)[:6],
            recommendations=recommendations,
            trending=trending,
            upcoming_events=upcoming,
            active_trip=active_trip,
        )
