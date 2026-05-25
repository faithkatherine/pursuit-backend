"""
Root conftest for the pursuit-backend test suite.

Loads shared fixture plugins so all fixtures are available to every test
without any per-file imports.

Fixture resolution order (first match wins for same name):
  tests/fixtures/auth.py   — user, other_user, user_with_location,
                              user_without_location_sharing,
                              auth_client, anon_client, auth_headers
  tests/fixtures/db.py     — category, another_category, active_event,
                              inactive_event, saved_event

GraphQL helpers (import directly in tests):
  tests/graphql/client.py       — GraphQLClient
  tests/graphql/mutations.py    — mutation strings
  tests/graphql/queries.py      — query strings
  tests/helpers/assertions.py   — assert_graphql_success, assert_graphql_error

Factories (import directly in tests):
  tests/factories/user_factory.py  — UserFactory
  tests/factories/event_factory.py — EventFactory, UserEventsFactory
  tests/factories/core_factory.py  — CategoryFactory, InterestFactory
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.users.authentication import JWTService
from tests.factories.user_factory import UserFactory

# Fixture plugins are registered in the root conftest.py so they apply
# to tests in both tests/ and apps/ directories.

User = get_user_model()


# ── Legacy / extra fixtures kept for backwards compatibility ──────────────────


@pytest.fixture
def api_client():
    """DRF API client (unauthenticated)."""
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    """DRF API client with JWT auth for the default `user` fixture."""
    token = JWTService.generate_access_token(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def superuser(db):
    """Superuser for admin/permission tests."""
    return User.objects.create_superuser(
        email="admin@example.com",
        username="admin",
        first_name="Admin",
        last_name="User",
        password="adminpassword123",
    )
