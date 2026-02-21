import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import Event

# ─── FIXTURES ─────────────────────────────────────────────


@pytest.fixture
def category(db):
    return Category.objects.create(name="Music", icon="🎵")


@pytest.fixture
def another_category(db):
    return Category.objects.create(name="Sports", icon="⚽")


@pytest.fixture
def active_event(db, category):
    event = Event.objects.create(
        name="Jazz Festival",
        description="A night of jazz",
        date=timezone.now() + timedelta(days=7),
        location_name="Central Park",
        is_active=True,
    )
    event.category.add(category)
    return event


@pytest.fixture
def inactive_event(db, category):
    event = Event.objects.create(
        name="Cancelled Show",
        date=timezone.now() + timedelta(days=14),
        is_active=False,
    )
    event.category.add(category)
    return event


@pytest.fixture
def future_event(db, another_category):
    event = Event.objects.create(
        name="Football Match",
        date=timezone.now() + timedelta(days=30),
        is_active=True,
    )
    event.category.add(another_category)
    return event


# ─── MODEL TESTS ──────────────────────────────────────────


@pytest.mark.django_db
class TestEventModel:
    def test_create_event(self, active_event):
        assert active_event.id is not None
        assert active_event.name == "Jazz Festival"
        assert active_event.is_active is True

    def test_str_representation(self, active_event):
        assert str(active_event) == "Jazz Festival"

    def test_default_ordering_by_date(self, active_event, future_event):
        events = list(Event.objects.all())
        assert events[0].date <= events[1].date

    def test_end_date_before_start_date_raises_error(self, db):
        event = Event(
            name="Bad Event",
            date=timezone.now() + timedelta(days=10),
            end_date=timezone.now() + timedelta(days=5),
        )
        with pytest.raises(ValidationError):
            event.clean()

    def test_end_date_after_start_date_is_valid(self, db):
        event = Event(
            name="Good Event",
            date=timezone.now() + timedelta(days=5),
            end_date=timezone.now() + timedelta(days=10),
        )
        event.clean()  # Should not raise

    def test_category_many_to_many(self, active_event, category, another_category):
        active_event.category.add(another_category)
        assert active_event.category.count() == 2


# ─── GRAPHQL QUERY TESTS ─────────────────────────────────

GET_EVENTS_QUERY = """
    query GetEvents($offset: Int, $limit: Int, $category: String) {
        getEvents(offset: $offset, limit: $limit, category: $category) {
            ok
            events {
                id
                name
                description
                date
                locationName
                coordinates
                isActive
                category {
                    id
                    name
                }
            }
        }
    }
"""


@pytest.mark.django_db
class TestGetEventsQuery:
    def test_returns_active_events_only(self, client, active_event, inactive_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert data["ok"] is True
        names = [e["name"] for e in data["events"]]
        assert "Jazz Festival" in names
        assert "Cancelled Show" not in names

    def test_returns_empty_list_when_no_events(self, client, db):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert data["ok"] is True
        assert data["events"] == []

    def test_filter_by_category(self, client, active_event, future_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"category": "Music"},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert data["ok"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Jazz Festival"

    def test_filter_by_category_case_insensitive(self, client, active_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"category": "music"},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert len(data["events"]) == 1

    def test_pagination_offset(self, client, active_event, future_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"offset": 1, "limit": 10},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert len(data["events"]) == 1

    def test_pagination_limit(self, client, active_event, future_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"limit": 1},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert len(data["events"]) == 1

    def test_negative_offset_clamped_to_zero(self, client, active_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"offset": -5},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert data["ok"] is True
        assert len(data["events"]) == 1

    def test_limit_clamped_to_max(self, client, active_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                    "variables": {"limit": 500},
                }
            ),
            content_type="application/json",
        )
        data = response.json()["data"]["getEvents"]

        assert data["ok"] is True

    def test_event_includes_all_fields(self, client, active_event):
        response = client.post(
            "/graphql/",
            json.dumps(
                {
                    "query": GET_EVENTS_QUERY,
                }
            ),
            content_type="application/json",
        )
        event = response.json()["data"]["getEvents"]["events"][0]

        assert "id" in event
        assert "name" in event
        assert "description" in event
        assert "date" in event
        assert "locationName" in event
        assert "coordinates" in event
        assert "category" in event


# ─── CACHE TESTS ────────────────────────────────────────

LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_cache")
class TestEventsCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self, settings):
        settings.CACHES = LOCMEM_CACHE
        from django.core.cache import cache

        cache.clear()

    def test_cache_miss_then_hit(self, client, active_event):
        from django.core.cache import cache

        from apps.events.schema import _get_events_cache_version

        version = _get_events_cache_version()
        cache_key = f"events:v{version}:all:0:20"

        # First request — cache miss
        assert cache.get(cache_key) is None
        response = client.post(
            "/graphql/",
            json.dumps({"query": GET_EVENTS_QUERY}),
            content_type="application/json",
        )
        assert response.json()["data"]["getEvents"]["ok"] is True

        # Cache is now populated
        cached = cache.get(cache_key)
        assert cached is not None
        assert len(cached) == 1

    def test_cache_invalidated_on_event_save(self, active_event):
        from django.core.cache import cache

        from apps.events.signals import EVENTS_CACHE_VERSION_KEY

        cache.set(EVENTS_CACHE_VERSION_KEY, 1)
        v_before = cache.get(EVENTS_CACHE_VERSION_KEY)

        active_event.name = "Updated Name"
        active_event.save()

        v_after = cache.get(EVENTS_CACHE_VERSION_KEY)
        assert v_after == v_before + 1

    def test_cache_invalidated_on_event_delete(self, active_event):
        from django.core.cache import cache

        from apps.events.signals import EVENTS_CACHE_VERSION_KEY

        cache.set(EVENTS_CACHE_VERSION_KEY, 1)

        active_event.delete()

        v_after = cache.get(EVENTS_CACHE_VERSION_KEY)
        assert v_after == 2

    def test_cached_response_matches_fresh_response(self, client, active_event):
        query = json.dumps({"query": GET_EVENTS_QUERY})

        # First call — cache miss
        resp1 = client.post("/graphql/", query, content_type="application/json")
        # Second call — cache hit
        resp2 = client.post("/graphql/", query, content_type="application/json")

        events1 = resp1.json()["data"]["getEvents"]["events"]
        events2 = resp2.json()["data"]["getEvents"]["events"]
        assert [e["id"] for e in events1] == [e["id"] for e in events2]

    def test_category_filter_uses_separate_cache_key(self, client, active_event, future_event):
        from django.core.cache import cache

        from apps.events.schema import _get_events_cache_version

        # Fetch all
        client.post(
            "/graphql/",
            json.dumps({"query": GET_EVENTS_QUERY}),
            content_type="application/json",
        )
        # Fetch filtered
        client.post(
            "/graphql/",
            json.dumps({"query": GET_EVENTS_QUERY, "variables": {"category": "Music"}}),
            content_type="application/json",
        )

        version = _get_events_cache_version()
        all_cached = cache.get(f"events:v{version}:all:0:20")
        music_cached = cache.get(f"events:v{version}:Music:0:20")

        assert all_cached is not None
        assert music_cached is not None
        assert len(all_cached) == 2
        assert len(music_cached) == 1
