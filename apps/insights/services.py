import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .models import WeatherData

logger = logging.getLogger(__name__)

CACHE_DURATION = timedelta(minutes=30)
OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def _parse_owm_response(data: dict) -> dict:
    """Parse OpenWeatherMap API response into our model fields."""
    weather_main = data.get("weather", [{}])[0]
    main = data.get("main", {})
    return {
        "city": data.get("name", "Unknown"),
        "condition": weather_main.get("main", "Clear"),
        "temperature": round(main.get("temp", 72)),
        "icon": weather_main.get("icon", "01d"),
        "latitude": data.get("coord", {}).get("lat"),
        "longitude": data.get("coord", {}).get("lon"),
    }


def _get_cached_weather(city: str) -> WeatherData | None:
    """Return cached weather if still fresh (within CACHE_DURATION)."""
    cutoff = timezone.now() - CACHE_DURATION
    return WeatherData.objects.filter(city__iexact=city, updated_at__gte=cutoff).first()


def _save_weather(parsed: dict) -> WeatherData:
    """Upsert weather data for a city."""
    weather, _ = WeatherData.objects.update_or_create(
        city__iexact=parsed["city"],
        defaults=parsed,
    )
    return weather


def _mock_weather(city: str = "New York") -> WeatherData:
    """Return mock weather as a fallback."""
    return WeatherData(city=city, condition="Sunny", temperature=72, icon="01d")


def fetch_weather_for_city(city: str) -> WeatherData:
    """Fetch weather for a city name, with caching and fallback."""
    # Check cache first
    cached = _get_cached_weather(city)
    if cached:
        return cached

    api_key = getattr(settings, "OPENWEATHERMAP_API_KEY", "")
    if not api_key:
        logger.debug("No OpenWeatherMap API key configured, returning mock data")
        return _mock_weather(city)

    try:
        resp = requests.get(
            OWM_BASE_URL,
            params={"q": city, "appid": api_key, "units": "imperial"},
            timeout=5,
        )
        resp.raise_for_status()
        parsed = _parse_owm_response(resp.json())
        return _save_weather(parsed)
    except Exception:
        logger.exception("Failed to fetch weather for city=%s", city)
        # Fall back to any cached data (even stale)
        stale = WeatherData.objects.filter(city__iexact=city).first()
        return stale or _mock_weather(city)


def fetch_weather_for_coordinates(lat: float, lon: float, city_hint: str = "") -> WeatherData:
    """Fetch weather by coordinates, with caching and fallback."""
    # If we have a city hint, check cache by city name first
    if city_hint:
        cached = _get_cached_weather(city_hint)
        if cached:
            return cached

    api_key = getattr(settings, "OPENWEATHERMAP_API_KEY", "")
    if not api_key:
        logger.debug("No OpenWeatherMap API key configured, returning mock data")
        return _mock_weather(city_hint or "New York")

    try:
        resp = requests.get(
            OWM_BASE_URL,
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "imperial"},
            timeout=5,
        )
        resp.raise_for_status()
        parsed = _parse_owm_response(resp.json())
        return _save_weather(parsed)
    except Exception:
        logger.exception("Failed to fetch weather for lat=%s, lon=%s", lat, lon)
        # Fall back to cached or mock
        if city_hint:
            stale = WeatherData.objects.filter(city__iexact=city_hint).first()
            if stale:
                return stale
        return _mock_weather(city_hint or "New York")
