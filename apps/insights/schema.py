import graphene

from apps.core.models import Category
from apps.recommendations.services import get_recommended_events, get_trending_events

from .services import fetch_weather_for_city, fetch_weather_for_coordinates


class WeatherType(graphene.ObjectType):
    """GraphQL Weather type"""

    city = graphene.String()
    condition = graphene.String()
    temperature = graphene.Float()
    icon = graphene.String()


class HomeDataType(graphene.ObjectType):
    """GraphQL HomeData type"""

    id = graphene.String()
    greeting = graphene.String()
    time_of_day = graphene.String()
    weather = graphene.Field(WeatherType)
    profile_picture = graphene.String()
    user_location = graphene.String()
    categories = graphene.List("apps.core.schema.CategoryType")
    recommendations = graphene.List("apps.events.types.EventType")
    trending = graphene.List("apps.events.types.EventType")
    upcoming_events = graphene.List("apps.events.types.EventType")
    active_trip = graphene.Field("apps.itinerary.types.TripType")


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
    from django.utils import timezone

    hour = timezone.localtime().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    return "evening"


class InsightsQueries(graphene.ObjectType):
    """Insights GraphQL queries"""

    get_home = graphene.Field(HomeDataType, offset=graphene.Int(), limit=graphene.Int())

    def resolve_get_home(self, info, offset=0, limit=10):
        user = info.context.user
        if not user.is_authenticated:
            return None

        weather = _get_weather_for_user(user)
        weather_type = _weather_to_type(weather)

        profile = getattr(user, "profile", None)

        # Get personalized event recommendations
        rec_results = get_recommended_events(user, offset=0, limit=5)
        recommendations = []
        for event, reason, source in rec_results:
            event._reason = reason
            event._source = source
            event._is_saved = False
            recommendations.append(event)

        # Get trending events (popularity-based, not personalized)
        trending_results = get_trending_events(user, limit=5)
        trending = []
        for event, reason, source in trending_results:
            event._reason = reason
            event._source = source
            event._is_saved = False
            trending.append(event)

        # Get user's upcoming saved events (soonest 3 future events)
        from django.utils import timezone
        from apps.events.models import Event, UserEvents
        from apps.itinerary.models import Trip

        now = timezone.now()
        saved_event_ids = UserEvents.objects.filter(user=user).values_list(
            "event_id", flat=True
        )
        upcoming = list(
            Event.objects.filter(
                id__in=saved_event_ids,
                is_active=True,
                date__gte=now,
            )
            .prefetch_related("category")
            .order_by("date")[:3]
        )
        for event in upcoming:
            event._is_saved = True

        # Get user's next upcoming trip
        active_trip = (
            Trip.objects.filter(user=user, end_date__gte=now)
            .prefetch_related("events")
            .order_by("start_date")
            .first()
        )

        return HomeDataType(
            id=str(user.id),
            greeting=f"Hello, {user.first_name}",
            time_of_day=_get_time_of_day(),
            weather=weather_type,
            profile_picture=user.profile_picture or "",
            user_location=profile.location_name if profile else "",
            categories=Category.objects.filter(is_active=True)[:6],
            recommendations=recommendations,
            trending=trending,
            upcoming_events=upcoming,
            active_trip=active_trip,
        )
