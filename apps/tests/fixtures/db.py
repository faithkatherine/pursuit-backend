import pytest

from tests.factories.core_factory import CategoryFactory, InterestFactory
from tests.factories.event_factory import EventFactory, UserEventsFactory


@pytest.fixture
def category(db):
    """A single Category."""
    return CategoryFactory(name="Music", icon="🎵")


@pytest.fixture
def another_category(db):
    """A second Category for multi-category tests."""
    return CategoryFactory(name="Sports", icon="⚽")


@pytest.fixture
def active_event(db, category):
    """An active, upcoming Event with one Category."""
    return EventFactory(name="Jazz Festival", is_active=True, category=[category])


@pytest.fixture
def inactive_event(db, category):
    """An inactive Event."""
    return EventFactory(name="Cancelled Show", is_active=False, category=[category])


@pytest.fixture
def saved_event(db, user, active_event):
    """A UserEvents record linking `user` to `active_event`."""
    return UserEventsFactory(user=user, event=active_event)

@pytest.fixture
def organizer_category(db):
    """A Category for organizers."""
    return CategoryFactory(name="Music", icon="🎵")
