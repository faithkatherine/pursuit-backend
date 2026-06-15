"""
Location tests: user profile location management and getHome query guards.

Covers:
- enableLocation mutation
- disableLocation mutation
- completeOnboarding with/without location
- getHome location guard behaviour (weather/location null when sharing disabled)
- Location persistence across enable/disable cycles

Fixtures supplied by tests/fixtures/auth.py (via conftest pytest_plugins):
  user, user_with_location, user_without_location_sharing, auth_client, anon_client

GraphQL strings from tests/graphql/:
  mutations.ENABLE_LOCATION, DISABLE_LOCATION, COMPLETE_ONBOARDING
  queries.GET_HOME

Assertion helpers from tests/helpers/assertions:
  assert_graphql_success, assert_graphql_error
"""

from unittest.mock import patch

import pytest
from tests.graphql.client import GraphQLClient
from tests.graphql.mutations import (
    COMPLETE_ONBOARDING,
    DISABLE_LOCATION,
    ENABLE_LOCATION,
)
from tests.graphql.queries import GET_HOME
from tests.helpers.assertions import assert_graphql_error, assert_graphql_success

# ── keep legacy aliases so any remaining inline references still resolve ──────
ENABLE_LOCATION_MUTATION = ENABLE_LOCATION
DISABLE_LOCATION_MUTATION = DISABLE_LOCATION
COMPLETE_ONBOARDING_MUTATION = COMPLETE_ONBOARDING
GET_HOME_QUERY = GET_HOME

# ─── PLACEHOLDER to satisfy old parse (removed below in class rewrites) ──────
_PLACEHOLDER = """
query GetHome($offset: Int, $limit: Int, $timeFilter: String) {
  getHome(offset: $offset, limit: $limit, timeFilter: $timeFilter) {
    id
    greeting
    greetingPrompt
    timeOfDay
    dayOfWeek
    cityName
    weather {
      city
      condition
      temperature
      icon
    }
    userLocation
    allowLocationSharing
  }
}
"""

# Fixtures (user, user_with_location, user_without_location_sharing,
# auth_client, anon_client, auth_headers) are provided by
# tests/fixtures/auth.py loaded via tests/conftest.py pytest_plugins.
# The local placeholder string above is kept only so the legacy alias
# ENABLE_LOCATION_MUTATION etc. strings resolve; the real strings live in
# tests/graphql/mutations.py and tests/graphql/queries.py.


# ─── ENABLE LOCATION TESTS ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestEnableLocation:
    """Test enableLocation mutation."""

    def test_enable_location_success(self, client, user):
        """Enabling location stores coordinates and flips the sharing flag."""
        gql = GraphQLClient(client, user=user)
        response = gql.execute(
            ENABLE_LOCATION,
            variables={"locationName": "Nairobi, Kenya", "location": [-1.2921, 36.8219]},
        )

        data = assert_graphql_success(response, "enableLocation")
        assert data["ok"] is True
        assert data["user"]["profile"]["allowLocationSharing"] is True
        assert data["user"]["profile"]["locationName"] == "Nairobi, Kenya"
        assert data["user"]["profile"]["coordinates"] is not None
        assert data["user"]["profile"]["hasLocation"] is True

        user.refresh_from_db()
        assert user.profile.allow_location_sharing is True
        assert user.profile.location_name == "Nairobi, Kenya"
        assert user.profile.has_location is True
        coords = user.profile.coordinates
        assert coords[0] == pytest.approx(-1.2921, abs=0.0001)
        assert coords[1] == pytest.approx(36.8219, abs=0.0001)

    def test_enable_location_update_existing(self, client, user_with_location):
        """Updating location when already enabled."""
        gql = GraphQLClient(client, user=user_with_location)
        response = gql.execute(
            ENABLE_LOCATION,
            variables={"locationName": "Mombasa, Kenya", "location": [-4.0435, 39.6682]},
        )

        data = assert_graphql_success(response, "enableLocation")
        assert data["ok"] is True
        assert data["user"]["profile"]["locationName"] == "Mombasa, Kenya"

        user_with_location.refresh_from_db()
        coords = user_with_location.profile.coordinates
        assert coords[0] == pytest.approx(-4.0435, abs=0.0001)
        assert coords[1] == pytest.approx(39.6682, abs=0.0001)

    def test_enable_location_unauthenticated(self, anon_client):
        """enableLocation fails without authentication."""
        response = anon_client.execute(
            ENABLE_LOCATION,
            variables={"locationName": "Nairobi, Kenya", "location": [-1.2921, 36.8219]},
        )
        assert_graphql_error(response, "Not authenticated")


# ─── DISABLE LOCATION TESTS ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestDisableLocation:
    """Test disableLocation mutation."""

    def test_disable_location_success(self, client, user_with_location):
        """Disabling location clears coordinates and flips the sharing flag."""
        gql = GraphQLClient(client, user=user_with_location)
        response = gql.execute(DISABLE_LOCATION)

        data = assert_graphql_success(response, "disableLocation")
        assert data["ok"] is True
        assert data["user"]["profile"]["allowLocationSharing"] is False
        assert data["user"]["profile"]["coordinates"] is None
        assert data["user"]["profile"]["hasLocation"] is False

        user_with_location.refresh_from_db()
        assert user_with_location.profile.allow_location_sharing is False
        assert user_with_location.profile.has_location is False

    def test_disable_location_unauthenticated(self, anon_client):
        """disableLocation requires authentication."""
        response = anon_client.execute(DISABLE_LOCATION)
        assert_graphql_error(response, "Not authenticated")


# ─── COMPLETE ONBOARDING LOCATION TESTS ───────────────────────────────────────


@pytest.mark.django_db
class TestCompleteOnboardingLocation:
    """Location handling inside the completeOnboarding mutation."""

    def test_complete_onboarding_with_location(self, auth_client, user):
        """Completing onboarding with location data stores all fields."""
        response = auth_client.execute(
            COMPLETE_ONBOARDING,
            variables={
                "allowLocationSharing": True,
                "locationName": "Nairobi, Kenya",
                "location": [-1.2921, 36.8219],
                "allowPushNotifications": True,
                "allowEmailNotifications": True,
            },
        )

        data = assert_graphql_success(response, "completeOnboarding")
        assert data["ok"] is True
        assert data["user"]["profile"]["allowLocationSharing"] is True
        assert data["user"]["profile"]["locationName"] == "Nairobi, Kenya"
        assert data["user"]["profile"]["coordinates"] is not None
        assert data["user"]["profile"]["hasLocation"] is True
        assert data["user"]["profile"]["isOnboardingCompleted"] is True

    def test_complete_onboarding_without_location(self, auth_client):
        """Completing onboarding with location disabled leaves location fields null."""
        response = auth_client.execute(
            COMPLETE_ONBOARDING,
            variables={
                "allowLocationSharing": False,
                "allowPushNotifications": True,
                "allowEmailNotifications": True,
            },
        )

        data = assert_graphql_success(response, "completeOnboarding")
        assert data["ok"] is True
        assert data["user"]["profile"]["allowLocationSharing"] is False
        assert data["user"]["profile"]["isOnboardingCompleted"] is True


# ─── GET HOME LOCATION GUARD TESTS ────────────────────────────────────────────


@pytest.mark.django_db
class TestGetHomeLocationGuards:
    """getHome returns null weather/location when allow_location_sharing is False."""

    @patch("apps.insights.schema.fetch_weather_for_coordinates")
    @patch("apps.insights.schema.fetch_weather_for_city")
    def test_get_home_with_location_enabled(self, mock_weather_city, mock_weather_coords, client, user_with_location):
        """getHome returns weather and location when sharing is enabled."""
        from apps.insights.services import WeatherData

        mock_weather_coords.return_value = WeatherData(
            city="Nairobi", condition="Partly Cloudy", temperature=22, icon="partly-cloudy"
        )

        gql = GraphQLClient(client, user=user_with_location)
        response = gql.execute(GET_HOME, variables={"offset": 0, "limit": 5})

        data = assert_graphql_success(response, "getHome")
        assert data["allowLocationSharing"] is True
        assert data["weather"] is not None
        assert data["weather"]["city"] == "Nairobi"
        assert data["weather"]["temperature"] == 22
        assert data["cityName"] == "Nairobi"
        assert data["userLocation"] == "Nairobi, Kenya"
        mock_weather_coords.assert_called_once()

    @patch("apps.insights.schema.fetch_weather_for_coordinates")
    @patch("apps.insights.schema.fetch_weather_for_city")
    def test_get_home_with_location_disabled(
        self, mock_weather_city, mock_weather_coords, client, user_without_location_sharing
    ):
        """getHome returns null weather/location when sharing is disabled."""
        gql = GraphQLClient(client, user=user_without_location_sharing)
        response = gql.execute(GET_HOME, variables={"offset": 0, "limit": 5})

        data = assert_graphql_success(response, "getHome")
        assert data["allowLocationSharing"] is False
        assert data["weather"] is None
        assert data["cityName"] is None
        assert data["userLocation"] is None
        mock_weather_coords.assert_not_called()
        mock_weather_city.assert_not_called()

    @patch("apps.insights.schema.fetch_weather_for_city")
    def test_get_home_with_sharing_enabled_but_no_coords(self, mock_weather_city, client, user):
        """Falls back to city-name weather fetch when coordinates are null."""
        from apps.insights.services import WeatherData

        user.profile.allow_location_sharing = True
        user.profile.location = None
        user.profile.location_name = "Nairobi"
        user.profile.save()

        mock_weather_city.return_value = WeatherData(city="Nairobi", condition="Sunny", temperature=25, icon="sunny")

        gql = GraphQLClient(client, user=user)
        response = gql.execute(GET_HOME, variables={"offset": 0, "limit": 5})

        data = assert_graphql_success(response, "getHome")
        assert data["allowLocationSharing"] is True
        assert data["weather"] is not None
        assert data["cityName"] == "Nairobi"
        assert data["userLocation"] == "Nairobi"
        mock_weather_city.assert_called_once_with("Nairobi")

    @patch("apps.insights.schema.fetch_weather_for_city")
    def test_get_home_unauthenticated_returns_none(self, mock_weather_city, anon_client):
        """getHome returns None (not an error) for unauthenticated users."""
        response = anon_client.execute(GET_HOME, variables={"offset": 0, "limit": 5})

        assert "errors" not in response
        assert response["data"]["getHome"] is None
        mock_weather_city.assert_not_called()


# ─── LOCATION PERSISTENCE TESTS ───────────────────────────────────────────────


@pytest.mark.django_db
class TestLocationPersistence:
    """Location data survives enable/disable mutation cycles."""

    def test_enable_disable_reenable_cycle(self, client, user_with_location):
        """Disable clears location; re-enable with new coords persists correctly."""
        gql = GraphQLClient(client, user=user_with_location)

        assert user_with_location.profile.allow_location_sharing is True
        assert user_with_location.profile.has_location is True

        gql.execute(DISABLE_LOCATION)
        user_with_location.refresh_from_db()
        assert user_with_location.profile.allow_location_sharing is False
        assert user_with_location.profile.has_location is False

        gql.execute(
            ENABLE_LOCATION,
            variables={"locationName": "Kisumu, Kenya", "location": [-0.0917, 34.7680]},
        )
        user_with_location.refresh_from_db()
        assert user_with_location.profile.allow_location_sharing is True
        assert user_with_location.profile.has_location is True
        assert user_with_location.profile.location_name == "Kisumu, Kenya"
        coords = user_with_location.profile.coordinates
        assert coords[0] == pytest.approx(-0.0917, abs=0.0001)

    def test_coordinate_format_is_latitude_longitude(self, client, user):
        """Coordinates are stored and returned as (latitude, longitude)."""
        gql = GraphQLClient(client, user=user)
        gql.execute(
            ENABLE_LOCATION,
            variables={"locationName": "Test City", "location": [10.5, 20.3]},
        )

        user.refresh_from_db()
        coords = user.profile.coordinates
        assert coords is not None
        assert coords[0] == pytest.approx(10.5, abs=0.0001)  # latitude
        assert coords[1] == pytest.approx(20.3, abs=0.0001)  # longitude
