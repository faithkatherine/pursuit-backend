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
    query GetEvents($offset: Int, $limit: Int, $category: [ID]) {
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
        $category: [ID],
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

    def test_filter_by_category(self, auth_client, active_event, future_event, category):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"category": [str(category.id)]})
        data = resp["data"]["events"]

        assert data["ok"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["name"] == "Jazz Festival"

    def test_filter_by_multiple_categories(self, auth_client, active_event, future_event, category, another_category):
        resp = _gql(auth_client, GET_EVENTS_QUERY, {"category": [str(category.id), str(another_category.id)]})
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
    def test_single_category(self, auth_client, active_event, future_event, category):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": [str(category.id)]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_multiple_categories(self, auth_client, active_event, future_event, category, another_category):
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": [str(category.id), str(another_category.id)]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 2

    def test_nonexistent_category(self, auth_client, active_event):
        import uuid

        fake_id = str(uuid.uuid4())
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": [fake_id]})
        events = resp["data"]["events"]["events"]

        assert len(events) == 0

    def test_no_duplicates_for_multi_category_event(self, auth_client, active_event, category, another_category):
        """Event with both Music and Sports should only appear once."""
        active_event.category.add(another_category)
        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"category": [str(category.id), str(another_category.id)]})
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
    def test_search_plus_category(self, auth_client, active_event, future_event, category):
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"search": "Festival", "category": [str(category.id)]},
        )
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Jazz Festival"

    def test_search_plus_category_no_match(self, auth_client, active_event, future_event, another_category):
        """Search matches but category doesn't."""
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {"search": "Jazz", "category": [str(another_category.id)]},
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
                "category": [str(category.id)],
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

    def test_category_filter_uses_separate_cache_key(self, auth_client, active_event, future_event, category):
        # Fetch all — returns 2 events
        resp_all = _gql(auth_client, GET_EVENTS_QUERY)
        assert len(resp_all["data"]["events"]["events"]) == 2

        # Fetch filtered — returns 1 event
        resp_music = _gql(auth_client, GET_EVENTS_QUERY, {"category": [str(category.id)]})
        assert len(resp_music["data"]["events"]["events"]) == 1

        # Re-fetch all — still returns 2 (cache not poisoned by filter)
        resp_all2 = _gql(auth_client, GET_EVENTS_QUERY)
        assert len(resp_all2["data"]["events"]["events"]) == 2


# ─── PERFORMANCE TESTS ─────────────────────────────────


@pytest.mark.django_db
class TestEventsPerformance:
    def test_query_performs_well_with_1000_events(self, auth_client, category, another_category):
        """Events query with filters should complete within 2 seconds for 1000+ events."""
        import time

        categories = [category, another_category]
        events = []
        for i in range(1050):
            events.append(
                Event(
                    name=f"Perf Event {i}",
                    description=f"Description for performance event {i}",
                    date=timezone.now() + timedelta(days=(i % 365) + 1),
                    is_active=True,
                    is_free=(i % 2 == 0),
                )
            )
        Event.objects.bulk_create(events)

        # Assign categories via through model
        created = Event.objects.filter(name__startswith="Perf Event")
        through_model = Event.category.through
        through_entries = []
        for event in created:
            cat = categories[event.pk % 2]
            through_entries.append(through_model(event_id=event.pk, category_id=cat.pk))
        through_model.objects.bulk_create(through_entries)

        assert Event.objects.filter(is_active=True).count() >= 1050

        # Query with multiple filters
        from_date = (timezone.now() + timedelta(days=10)).isoformat()
        to_date = (timezone.now() + timedelta(days=200)).isoformat()

        start = time.time()
        resp = _gql(
            auth_client,
            SEARCH_EVENTS_QUERY,
            {
                "search": "performance",
                "category": [str(category.id)],
                "dateFrom": from_date,
                "dateTo": to_date,
                "isFree": True,
                "limit": 20,
            },
        )
        elapsed = time.time() - start

        assert resp["data"]["events"]["ok"] is True
        assert elapsed < 2.0, f"Query took {elapsed:.2f}s, expected < 2s"


# ─── ADMIN TESTS ────────────────────────────────────────


@pytest.fixture
def staff_user(db):
    return User.objects.create_superuser(
        email="admin@example.com",
        password="adminpass123",
        username="adminuser",
        first_name="Admin",
    )


@pytest.fixture
def admin_client(staff_user):
    client = Client(enforce_csrf_checks=False)
    client.force_login(staff_user)
    return client


@pytest.fixture
def non_staff_client(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestEventAdmin:
    def _admin_add_url(self):
        return "/admin/events/event/add/"

    def _admin_list_url(self):
        return "/admin/events/event/"

    def _valid_event_data(self, category):
        return {
            "name": "Admin Created Event",
            "description": "Created via admin",
            "date_0": "2026-06-01",
            "date_1": "18:00:00",
            "category": [str(category.id)],
            "is_active": "on",
            "is_free": "",
        }

    def test_create_event_with_valid_data(self, admin_client, category):
        data = self._valid_event_data(category)
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 302  # redirect on success
        assert Event.objects.filter(name="Admin Created Event").exists()

    def test_created_event_appears_in_graphql(self, admin_client, auth_client, category):
        data = self._valid_event_data(category)
        admin_client.post(self._admin_add_url(), data)

        resp = _gql(auth_client, SEARCH_EVENTS_QUERY, {"search": "Admin Created"})
        events = resp["data"]["events"]["events"]

        assert len(events) == 1
        assert events[0]["name"] == "Admin Created Event"

    def test_submit_without_name_returns_error(self, admin_client, category):
        data = self._valid_event_data(category)
        data["name"] = ""
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 200  # re-renders form with errors
        assert not Event.objects.filter(description="Created via admin").exists()

    def test_submit_without_category_returns_error(self, admin_client, category):
        data = self._valid_event_data(category)
        data["category"] = []
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 200  # re-renders form with errors
        assert not Event.objects.filter(name="Admin Created Event").exists()

    def test_end_date_before_start_date_returns_error(self, admin_client, category):
        data = self._valid_event_data(category)
        data["end_date_0"] = "2026-05-01"
        data["end_date_1"] = "18:00:00"
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 200
        assert not Event.objects.filter(name="Admin Created Event").exists()

    def test_only_staff_can_access_admin(self, non_staff_client):
        resp = non_staff_client.get(self._admin_list_url())

        # Non-staff redirected to admin login
        assert resp.status_code == 302
        assert "/admin/login/" in resp.url

    def test_unauthenticated_cannot_access_admin(self):
        client = Client()
        resp = client.get(self._admin_list_url())

        assert resp.status_code == 302
        assert "/admin/login/" in resp.url

    def test_create_event_with_image_url(self, admin_client, category):
        data = self._valid_event_data(category)
        data["image"] = "https://example.com/photo.jpg"
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 302
        event = Event.objects.get(name="Admin Created Event")
        assert event.image == "https://example.com/photo.jpg"

    def _make_test_image(self, name="test.png", fmt="PNG"):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format=fmt)
        content_type = "image/png" if fmt == "PNG" else "image/jpeg"
        return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)

    def test_create_event_with_image_upload(self, admin_client, category, mocker):
        mocker.patch(
            "apps.events.admin.upload_image",
            return_value="https://storage.example.com/events/test.png",
        )
        data = self._valid_event_data(category)
        data["image_file"] = self._make_test_image()
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 302
        event = Event.objects.get(name="Admin Created Event")
        assert event.image == "https://storage.example.com/events/test.png"

    def test_image_upload_takes_priority_over_url(self, admin_client, category, mocker):
        mocker.patch(
            "apps.events.admin.upload_image",
            return_value="https://storage.example.com/events/priority.jpg",
        )
        data = self._valid_event_data(category)
        data["image"] = "https://example.com/should-be-overridden.jpg"
        data["image_file"] = self._make_test_image("priority.jpg", "JPEG")
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 302
        event = Event.objects.get(name="Admin Created Event")
        assert event.image == "https://storage.example.com/events/priority.jpg"

    def test_create_event_with_is_free(self, admin_client, category):
        data = self._valid_event_data(category)
        data["is_free"] = "on"
        resp = admin_client.post(self._admin_add_url(), data)

        assert resp.status_code == 302
        event = Event.objects.get(name="Admin Created Event")
        assert event.is_free is True
