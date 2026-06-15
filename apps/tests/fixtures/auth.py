import pytest
from django.contrib.gis.geos import Point

from apps.tests.factories.user_factory import UserFactory
from apps.tests.graphql.client import GraphQLClient


@pytest.fixture
def user(db):
    """
    A standard user with a default profile (allow_location_sharing=True by default).
    Uses UserFactory so emails never collide between tests.
    """
    return UserFactory()


@pytest.fixture
def other_user(db):
    """A second user for tests that need multiple users."""
    return UserFactory()


@pytest.fixture
def user_with_location(db):
    """User with location sharing enabled and GPS coordinates set."""
    u = UserFactory()
    profile = u.profile
    profile.allow_location_sharing = True
    profile.location_name = "Nairobi, Kenya"
    profile.location = Point(36.8219, -1.2921)  # (longitude, latitude)
    profile.save()
    return u


@pytest.fixture
def user_without_location_sharing(db):
    """User with location sharing explicitly disabled."""
    u = UserFactory()
    profile = u.profile
    profile.allow_location_sharing = False
    profile.location = None
    profile.location_name = ""
    profile.save()
    return u


@pytest.fixture
def auth_client(client, user):
    """
    Authenticated GraphQLClient for the default `user` fixture.

    Usage:
        def test_something(auth_client):
            response = auth_client.execute(MY_QUERY)
    """
    return GraphQLClient(client, user=user)


@pytest.fixture
def anon_client(client):
    """
    Unauthenticated GraphQLClient.

    Usage:
        def test_something(anon_client):
            response = anon_client.execute(MY_QUERY)
    """
    return GraphQLClient(client)


@pytest.fixture
def auth_headers(client, user):
    """
    Raw auth headers dict for tests that still use Django's `client.post()` directly.
    Prefer `auth_client` for GraphQL tests.
    """
    from apps.users.authentication import JWTService

    token = JWTService.generate_access_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}
