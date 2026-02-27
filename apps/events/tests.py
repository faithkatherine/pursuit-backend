import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import Event, UserEvents
from apps.users.authentication import JWTService

User = get_user_model()

# ─── FIXTURES ─────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="eventuser@example.com",
        password="securepass123",
        username="eventuser",
        first_name="Event",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="otheruser@example.com",
        password="securepass123",
        username="otheruser",
        first_name="Other",
    )


@pytest.fixture
def auth_client(user):
    """Django test client with JWT Authorization header."""
    token = JWTService.generate_access_token(user)
    client = Client(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def anon_client():
    """Django test client without authentication."""
    return Client()


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


# ─── HELPERS ──────────────────────────────────────────────


def _gql(client, query, variables=None):
    """Execute a GraphQL request and return parsed JSON."""
    body = {"query": query}
    if variables:
        body["variables"] = variables
    response = client.post(
        "/graphql/",
        json.dumps(body),
        content_type="application/json",
    )
    return response.json()


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


@pytest.mark.django_db
class TestUserEventsModel:
    def test_create_saved_event(self, user, active_event):
        saved = UserEvents.objects.create(user=user, event=active_event)
        assert saved.id is not None
        assert saved.user == user
        assert saved.event == active_event

    def test_str_representation(self, user, active_event):
        saved = UserEvents.objects.create(user=user, event=active_event)
        assert str(saved) == "eventuser@example.com saved Jazz Festival"

    def test_unique_together_prevents_duplicates(self, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            UserEvents.objects.create(user=user, event=active_event)

    def test_cascade_delete_user(self, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        user.delete()
        assert UserEvents.objects.count() == 0

    def test_cascade_delete_event(self, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        active_event.delete()
        assert UserEvents.objects.count() == 0


# ─── GRAPHQL QUERY STRINGS ───────────────────────────────

GET_EVENTS_QUERY = """
    query GetEvents($offset: Int, $limit: Int, $category: [String]) {
        events(offset: $offset, limit: $limit, category: $category) {
            ok
            events {
                id
                name
                description
                date
                locationName
                coordinates
                isActive
                isFree
                category {
                    id
                    name
                }
            }
        }
    }
"""

SEARCH_EVENTS_QUERY = """
    query SearchEvents(
        $search: String,
        $category: [String],
        $dateFrom: DateTime,
        $dateTo: DateTime,
        $latitude: Float,
        $longitude: Float,
        $radiusKm: Float,
        $isFree: Boolean,
        $offset: Int,
        $limit: Int
    ) {
        events(
            search: $search,
            category: $category,
            dateFrom: $dateFrom,
            dateTo: $dateTo,
            latitude: $latitude,
            longitude: $longitude,
            radiusKm: $radiusKm,
            isFree: $isFree,
            offset: $offset,
            limit: $limit
        ) {
            ok
            events {
                id
                name
                description
                isFree
                category { name }
            }
        }
    }
"""

GET_EVENT_QUERY = """
    query GetEvent($id: ID!) {
        event(id: $id) {
            ok
            event {
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

SAVE_EVENT_MUTATION = """
    mutation SaveEvent($id: ID!) {
        saveEvent(id: $id) {
            ok
            event {
                id
                name
            }
            errors
        }
    }
"""

UNSAVE_EVENT_MUTATION = """
    mutation UnsaveEvent($id: ID!) {
        unsaveEvent(id: $id) {
            ok
            event {
                id
                name
            }
            errors
        }
    }
"""

SAVED_EVENTS_QUERY = """
    query SavedEvents($offset: Int, $limit: Int) {
        savedEvents(offset: $offset, limit: $limit) {
            ok
            events {
                id
                name
                isSaved
            }
        }
    }
"""

GET_EVENTS_WITH_SAVED_QUERY = """
    query GetEvents($offset: Int, $limit: Int) {
        events(offset: $offset, limit: $limit) {
            ok
            events {
                id
                name
                isSaved
            }
        }
    }
"""


# ─── EVENTS LIST QUERY TESTS ─────────────────────────────


@pytest.mark.django_db
class TestEventsQuery:
    def test_returns_active_events_only(self, auth_client, active_event, inactive_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY)
        data = resp["data"]["events"]

        assert data["ok"] is True
        names = [e["name"] for e in data["events"]]
        assert "Jazz Festival" in names
        assert "Cancelled Show" not in names

    def test_returns_empty_list_when_no_events(self, auth_client):
        resp = _gql(auth_client, GET_EVENTS_QUERY)
        data = resp["data"]["events"]

        assert data["ok"] is True
        assert data["events"] == []

    def test_filter_by_category(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"category": ["Music"]})
        data = resp["data"]["events"]

        assert data["ok"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Jazz Festival"

    def test_filter_by_multiple_categories(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"category": ["Music", "Sports"]})
        data = resp["data"]["events"]

        assert data["ok"] is True
        assert len(data["events"]) == 2

    def test_pagination_offset(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"offset": 1, "limit": 10})
        data = resp["data"]["events"]

        assert len(data["events"]) == 1

    def test_pagination_limit(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"limit": 1})
        data = resp["data"]["events"]

        assert len(data["events"]) == 1

    def test_negative_offset_clamped_to_zero(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"offset": -5})
        data = resp["data"]["events"]

        assert data["ok"] is True
        assert len(data["events"]) == 1

    def test_limit_clamped_to_max(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"limit": 500})
        data = resp["data"]["events"]

        assert data["ok"] is True

    def test_event_includes_all_fields(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY)
        event = resp["data"]["events"]["events"][0]

        assert "id" in event
        assert "name" in event
        assert "description" in event
        assert "date" in event
        assert "locationName" in event
        assert "coordinates" in event
        assert "category" in event

    def test_event_category_data(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENTS_QUERY)
        event = resp["data"]["events"]["events"][0]

        assert len(event["category"]) == 1
        assert event["category"][0]["name"] == "Music"


# ─── SEARCH & FILTER TESTS ──────────────────────────────


@pytest.mark.django_db
class TestSearchFilter:
    def test_search_by_name(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"search": "Jazz"})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_search_by_description(self, auth_client, active_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"search": "night of jazz"})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_search_case_insensitive(self, auth_client, active_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"search": "JAZZ"})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1

    def test_search_no_match(self, auth_client, active_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"search": "nonexistent"})
        events = resp["data"]["events"]["events"]

        assert len(events) == 0


@pytest.mark.django_db
class TestCategoryFilter:
    def test_single_category(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": ["Music"]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_multiple_categories(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": ["Music", "Sports"]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 2

    def test_nonexistent_category(self, auth_client, active_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": ["Nonexistent"]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 0

    def test_no_duplicates_for_multi_category_event(self, auth_client, active_event, another_category):
        """Event with both Music and Sports should only appear once."""
        active_event.category.add(another_category)
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": ["Music", "Sports"]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"


@pytest.mark.django_db
class TestDateRangeFilter:
    def test_date_from(self, auth_client, active_event, future_event):
        """dateFrom filters out events before that date."""
        cutoff = (timezone.now() + timedelta(days=14)).isoformat()
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"dateFrom": cutoff})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Football Match"

    def test_date_to(self, auth_client, active_event, future_event):
        """dateTo filters out events after that date."""
        cutoff = (timezone.now() + timedelta(days=14)).isoformat()
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"dateTo": cutoff})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_date_range(self, auth_client, active_event, future_event):
        """Both dateFrom and dateTo together."""
        from_date = (timezone.now() + timedelta(days=1)).isoformat()
        to_date = (timezone.now() + timedelta(days=14)).isoformat()
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"dateFrom": from_date, "dateTo": to_date})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_no_events_in_range(self, auth_client, active_event, future_event):
        """Date range that contains no events."""
        from_date = (timezone.now() + timedelta(days=100)).isoformat()
        to_date = (timezone.now() + timedelta(days=200)).isoformat()
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"dateFrom": from_date, "dateTo": to_date})
        events = resp["data"]["events"]["events"]

        assert len(events) == 0


@pytest.mark.django_db
class TestLocationFilter:
    def test_events_within_radius(self, auth_client):
        """Events near the search point are returned."""
        event = Event.objects.create(
            name="Nearby Event",
            date=timezone.now() + timedelta(days=5),
            location=Point(-73.9857, 40.7484, srid=4326),  # NYC
            is_active=True,
        )
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"latitude": 40.7580, "longitude": -73.9855, "radiusKm": 10},
        )
        events = resp["data"]["events"]["events"]

        names = [e["name"] for e in events]
        assert "Nearby Event" in names

    def test_events_outside_radius(self, auth_client):
        """Events far from the search point are excluded."""
        Event.objects.create(
            name="Far Away Event",
            date=timezone.now() + timedelta(days=5),
            location=Point(-118.2437, 34.0522, srid=4326),  # Los Angeles
            is_active=True,
        )
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"latitude": 40.7580, "longitude": -73.9855, "radiusKm": 10},  # NYC center
        )
        events = resp["data"]["events"]["events"]

        names = [e["name"] for e in events]
        assert "Far Away Event" not in names

    def test_events_without_location_excluded(self, auth_client, active_event):
        """Events with no location are excluded when location filter is used."""
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"latitude": 40.7580, "longitude": -73.9855, "radiusKm": 50},
        )
        events = resp["data"]["events"]["events"]

        # active_event has no location, should not appear
        assert len(events) == 0


@pytest.mark.django_db
class TestIsFreeFilter:
    def test_returns_only_free_events(self, auth_client):
        Event.objects.create(
            name="Free Concert",
            date=timezone.now() + timedelta(days=5),
            is_active=True,
            is_free=True,
        )
        Event.objects.create(
            name="Paid Gala",
            date=timezone.now() + timedelta(days=5),
            is_active=True,
            is_free=False,
        )
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"isFree": True})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Free Concert"

    def test_is_free_false_returns_paid(self, auth_client):
        Event.objects.create(
            name="Free Concert",
            date=timezone.now() + timedelta(days=5),
            is_active=True,
            is_free=True,
        )
        Event.objects.create(
            name="Paid Gala",
            date=timezone.now() + timedelta(days=5),
            is_active=True,
            is_free=False,
        )
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"isFree": False})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Paid Gala"


@pytest.mark.django_db
class TestCombinedFilters:
    def test_search_plus_category(self, auth_client, active_event, future_event):
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"search": "Festival", "category": ["Music"]},
        )
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_search_plus_category_no_match(self, auth_client, active_event, future_event):
        """Search matches but category doesn't."""
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"search": "Jazz", "category": ["Sports"]},
        )
        events = resp["data"]["events"]["events"]

        assert len(events) == 0

    def test_search_plus_date_range(self, auth_client, active_event, future_event):
        from_date = (timezone.now() + timedelta(days=1)).isoformat()
        to_date = (timezone.now() + timedelta(days=14)).isoformat()
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"search": "Jazz", "dateFrom": from_date, "dateTo": to_date},
        )
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_all_filters_combined(self, auth_client, category):
        event = Event.objects.create(
            name="Free Jazz Night",
            description="An amazing free jazz event",
            date=timezone.now() + timedelta(days=5),
            location=Point(-73.9857, 40.7484, srid=4326),
            is_active=True,
            is_free=True,
        )
        event.category.add(category)

        from_date = (timezone.now() + timedelta(days=1)).isoformat()
        to_date = (timezone.now() + timedelta(days=10)).isoformat()
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {
                "search": "jazz",
                "category": ["Music"],
                "dateFrom": from_date,
                "dateTo": to_date,
                "latitude": 40.7580,
                "longitude": -73.9855,
                "radiusKm": 10,
                "isFree": True,
            },
        )
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Free Jazz Night"

    def test_empty_filters_returns_all_active(self, auth_client, active_event, future_event):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY)
        events = resp["data"]["events"]["events"]

        assert len(events) == 2


# ─── SINGLE EVENT QUERY TESTS ────────────────────────────


@pytest.mark.django_db
class TestEventQuery:
    def test_returns_active_event_by_id(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": str(active_event.id)})
        data = resp["data"]["event"]

        assert data["ok"] is True
        assert data["event"]["name"] == "Jazz Festival"
        assert data["event"]["id"] == str(active_event.id)

    def test_returns_all_fields(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": str(active_event.id)})
        event = resp["data"]["event"]["event"]

        assert "id" in event
        assert "name" in event
        assert "description" in event
        assert "date" in event
        assert "locationName" in event
        assert "coordinates" in event
        assert "isActive" in event
        assert "category" in event

    def test_includes_category_relationship(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": str(active_event.id)})
        event = resp["data"]["event"]["event"]

        assert len(event["category"]) == 1
        assert event["category"][0]["name"] == "Music"

    def test_nonexistent_event_returns_error(self, auth_client):
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": "99999"})

        errors = resp.get("errors")
        assert errors is not None
        assert "Event not found" in errors[0]["message"]

    def test_inactive_event_returns_error(self, auth_client, inactive_event):
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": str(inactive_event.id)})

        errors = resp.get("errors")
        assert errors is not None
        assert "Event not found" in errors[0]["message"]

    def test_event_with_multiple_categories(self, auth_client, active_event, another_category):
        active_event.category.add(another_category)
        resp = _gql(auth_client, GET_EVENT_QUERY, {"id": str(active_event.id)})
        event = resp["data"]["event"]["event"]

        assert len(event["category"]) == 2
        names = {c["name"] for c in event["category"]}
        assert names == {"Music", "Sports"}


# ─── SAVE EVENT MUTATION TESTS ────────────────────────────


@pytest.mark.django_db
class TestSaveEventMutation:
    def test_save_event_success(self, auth_client, user, active_event):
        resp = _gql(auth_client, SAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["saveEvent"]

        assert data["ok"] is True
        assert data["event"]["id"] == str(active_event.id)
        assert data["event"]["name"] == "Jazz Festival"
        assert data["errors"] == []
        assert UserEvents.objects.filter(user=user, event=active_event).exists()

    def test_duplicate_save_is_idempotent(self, auth_client, user, active_event):
        _gql(auth_client, SAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        resp = _gql(auth_client, SAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["saveEvent"]

        assert data["ok"] is True
        assert UserEvents.objects.filter(user=user, event=active_event).count() == 1

    def test_save_nonexistent_event(self, auth_client):
        resp = _gql(auth_client, SAVE_EVENT_MUTATION, {"id": "99999"})
        data = resp["data"]["saveEvent"]

        assert data["ok"] is False
        assert data["event"] is None
        assert "Event not found." in data["errors"]

    def test_save_inactive_event(self, auth_client, inactive_event):
        resp = _gql(auth_client, SAVE_EVENT_MUTATION, {"id": str(inactive_event.id)})
        data = resp["data"]["saveEvent"]

        assert data["ok"] is False
        assert "Event not found." in data["errors"]

    def test_save_event_unauthenticated(self, anon_client, active_event):
        resp = _gql(anon_client, SAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["saveEvent"]

        assert data["ok"] is False
        assert "Authentication required." in data["errors"]


# ─── UNSAVE EVENT MUTATION TESTS ──────────────────────────


@pytest.mark.django_db
class TestUnsaveEventMutation:
    def test_unsave_event_success(self, auth_client, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        resp = _gql(auth_client, UNSAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["unsaveEvent"]

        assert data["ok"] is True
        assert data["event"]["id"] == str(active_event.id)
        assert data["errors"] == []
        assert not UserEvents.objects.filter(user=user, event=active_event).exists()

    def test_unsave_event_not_saved(self, auth_client, active_event):
        resp = _gql(auth_client, UNSAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["unsaveEvent"]

        assert data["ok"] is False
        assert "Event is not in your saved list." in data["errors"]

    def test_unsave_nonexistent_event(self, auth_client):
        resp = _gql(auth_client, UNSAVE_EVENT_MUTATION, {"id": "99999"})
        data = resp["data"]["unsaveEvent"]

        assert data["ok"] is False
        assert "Event not found." in data["errors"]

    def test_unsave_event_unauthenticated(self, anon_client, active_event):
        resp = _gql(anon_client, UNSAVE_EVENT_MUTATION, {"id": str(active_event.id)})
        data = resp["data"]["unsaveEvent"]

        assert data["ok"] is False
        assert "Authentication required." in data["errors"]


# ─── SAVED EVENTS QUERY TESTS ────────────────────────────


@pytest.mark.django_db
class TestSavedEventsQuery:
    def test_returns_saved_events(self, auth_client, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        assert data["ok"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Jazz Festival"

    def test_returns_empty_when_nothing_saved(self, auth_client):
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        assert data["ok"] is True
        assert data["events"] == []

    def test_excludes_inactive_events(self, auth_client, user, inactive_event):
        UserEvents.objects.create(user=user, event=inactive_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        assert data["ok"] is True
        assert data["events"] == []

    def test_only_returns_own_saved_events(self, auth_client, user, other_user, active_event, future_event):
        UserEvents.objects.create(user=user, event=active_event)
        UserEvents.objects.create(user=other_user, event=future_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Jazz Festival"

    def test_unauthenticated_returns_error(self, anon_client):
        resp = _gql(anon_client, SAVED_EVENTS_QUERY)

        errors = resp.get("errors")
        assert errors is not None
        assert "Authentication required." in errors[0]["message"]

    def test_pagination_limit(self, auth_client, user, active_event, future_event):
        UserEvents.objects.create(user=user, event=active_event)
        UserEvents.objects.create(user=user, event=future_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY, {"limit": 1})
        data = resp["data"]["savedEvents"]

        assert data["ok"] is True
        assert len(data["events"]) == 1

    def test_pagination_offset(self, auth_client, user, active_event, future_event):
        UserEvents.objects.create(user=user, event=active_event)
        UserEvents.objects.create(user=user, event=future_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY, {"offset": 1, "limit": 10})
        data = resp["data"]["savedEvents"]

        assert len(data["events"]) == 1

    def test_ordered_by_most_recently_saved(self, auth_client, user, active_event, future_event):
        UserEvents.objects.create(user=user, event=active_event)
        UserEvents.objects.create(user=user, event=future_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        # Most recently saved should be first
        assert data["events"][0]["name"] == "Football Match"
        assert data["events"][1]["name"] == "Jazz Festival"

    def test_default_limit_applied(self, auth_client, user, category):
        # Create 25 events and save them all
        events = []
        for i in range(25):
            e = Event.objects.create(
                name=f"Event {i}",
                date=timezone.now() + timedelta(days=i + 1),
                is_active=True,
            )
            e.category.add(category)
            events.append(e)
            UserEvents.objects.create(user=user, event=e)

        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        data = resp["data"]["savedEvents"]

        assert len(data["events"]) == 20  # default limit


# ─── IS_SAVED FIELD TESTS ───────────────────────────────


@pytest.mark.django_db
class TestIsSavedField:
    def test_is_saved_true_for_saved_event(self, auth_client, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        resp = _gql(auth_client, GET_EVENTS_WITH_SAVED_QUERY)
        event = resp["data"]["events"]["events"][0]

        assert event["isSaved"] is True

    def test_is_saved_false_for_unsaved_event(self, auth_client, active_event):
        resp = _gql(auth_client, GET_EVENTS_WITH_SAVED_QUERY)
        event = resp["data"]["events"]["events"][0]

        assert event["isSaved"] is False

    def test_is_saved_mixed_results(self, auth_client, user, active_event, future_event):
        UserEvents.objects.create(user=user, event=active_event)
        resp = _gql(auth_client, GET_EVENTS_WITH_SAVED_QUERY)
        events = resp["data"]["events"]["events"]

        saved_map = {e["name"]: e["isSaved"] for e in events}
        assert saved_map["Jazz Festival"] is True
        assert saved_map["Football Match"] is False

    def test_is_saved_false_for_anonymous(self, anon_client, active_event):
        resp = _gql(anon_client, GET_EVENTS_WITH_SAVED_QUERY)
        event = resp["data"]["events"]["events"][0]

        assert event["isSaved"] is False

    def test_is_saved_on_saved_events_query(self, auth_client, user, active_event):
        UserEvents.objects.create(user=user, event=active_event)
        resp = _gql(auth_client, SAVED_EVENTS_QUERY)
        event = resp["data"]["savedEvents"]["events"][0]

        assert event["isSaved"] is True

    def test_is_saved_on_single_event_fallback(self, auth_client, user, active_event):
        """Single event query uses the fallback DB lookup (not annotation)."""
        UserEvents.objects.create(user=user, event=active_event)
        query = """
            query GetEvent($id: ID!) {
                event(id: $id) {
                    ok
                    event { id isSaved }
                }
            }
        """
        resp = _gql(auth_client, query, {"id": str(active_event.id)})
        assert resp["data"]["event"]["event"]["isSaved"] is True


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

    def test_cache_miss_then_hit(self, auth_client, active_event):
        # First call — cache miss
        resp1 = _gql(auth_client, GET_EVENTS_QUERY)
        assert resp1["data"]["events"]["ok"] is True
        assert len(resp1["data"]["events"]["events"]) == 1

        # Second call — cache hit (same result)
        resp2 = _gql(auth_client, GET_EVENTS_QUERY)
        assert resp2["data"]["events"]["ok"] is True
        assert [e["id"] for e in resp1["data"]["events"]["events"]] == [
            e["id"] for e in resp2["data"]["events"]["events"]
        ]

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

    def test_cached_response_matches_fresh_response(self, auth_client, active_event):
        # First call — cache miss
        resp1 = _gql(auth_client, GET_EVENTS_QUERY)
        # Second call — cache hit
        resp2 = _gql(auth_client, GET_EVENTS_QUERY)

        events1 = resp1["data"]["events"]["events"]
        events2 = resp2["data"]["events"]["events"]
        assert [e["id"] for e in events1] == [e["id"] for e in events2]

    def test_category_filter_uses_separate_cache_key(self, auth_client, active_event, future_event):
        # Fetch all — returns 2 events
        resp_all = _gql(auth_client, GET_EVENTS_QUERY)
        assert len(resp_all["data"]["events"]["events"]) == 2

        # Fetch filtered — returns 1 event
        resp_music = _gql(auth_client, GET_EVENTS_QUERY, {"category": ["Music"]})
        assert len(resp_music["data"]["events"]["events"]) == 1

        # Re-fetch all — still returns 2 (cache not poisoned by filter)
        resp_all2 = _gql(auth_client, GET_EVENTS_QUERY)
        assert len(resp_all2["data"]["events"]["events"]) == 2
