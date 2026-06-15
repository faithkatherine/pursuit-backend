from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.events.models import Event, UserEvents
from apps.tests.factories.core_factory import CategoryFactory
from apps.tests.factories.user_factory import UserFactory


class EventFactory(DjangoModelFactory):
    """
    Creates an active, future-dated Event with an organizer.

    Usage:
        event = EventFactory()
        event = EventFactory(name="Jazz Night", is_free=True)
        event = EventFactory(organizer=my_organizer)
        past_event = EventFactory(date=timezone.now() - timedelta(days=1))
    """

    class Meta:
        model = Event

    # Lazy import to avoid circular dependency
    organizer = factory.LazyAttribute(
        lambda _: __import__('apps.tests.factories.organizer_factory', fromlist=['OrganizerProfileFactory']).OrganizerProfileFactory()
    )

    name = factory.Sequence(lambda n: f"Event {n}")
    description = factory.Faker("paragraph")
    date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    location_name = factory.Faker("city")
    is_active = True
    is_free = False

    @factory.post_generation
    def category(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for cat in extracted:
                self.category.add(cat)
        else:
            self.category.add(CategoryFactory())


class UserEventsFactory(DjangoModelFactory):
    """
    Creates a saved event (UserEvents) linking a user and an event.

    Usage:
        saved = UserEventsFactory(user=some_user, event=some_event)
        saved = UserEventsFactory()  # creates its own user + event
    """

    class Meta:
        model = UserEvents

    user = factory.SubFactory(UserFactory)
    event = factory.SubFactory(EventFactory)
