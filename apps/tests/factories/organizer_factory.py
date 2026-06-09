import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from django.utils import timezone

from apps.organizers.models import (
    OrganizerProfile,
    OrganizerPaymentConfig,
    OrganizerPayout
)
from apps.tests.factories.user_factory import UserFactory


class OrganizerProfileFactory(DjangoModelFactory):
    """
    Creates an active, verified OrganizerProfile with a linked User.

    Usage:
        org = OrganizerProfileFactory()
        org = OrganizerProfileFactory(business_name="My Events Co")
        inactive_org = OrganizerProfileFactory(is_active=False)
    """

    class Meta:
        model = OrganizerProfile

    user = factory.SubFactory(UserFactory)
    business_name = factory.Sequence(lambda n: f"Event Organizer {n}")
    description = factory.Faker("paragraph")
    website_url = factory.Faker("url")
    contact_email = factory.Faker("email")
    contact_phone = factory.Sequence(lambda n: f"+254712{n:06d}")
    verified = True
    is_active = True


class OrganizerPaymentConfigFactory(DjangoModelFactory):
    """
    Creates payment configuration for an organizer.

    Usage:
        config = OrganizerPaymentConfigFactory(organizer=some_organizer)
        config = OrganizerPaymentConfigFactory(payout_type='b2c')
    """

    class Meta:
        model = OrganizerPaymentConfig

    organizer = factory.SubFactory(OrganizerProfileFactory)
    collection_type = 'paybill'
    collection_shortcode = factory.Sequence(lambda n: f"{888000 + n}")
    collection_passkey = factory.Faker("sha256")
    payout_type = 'b2c'
    payout_destination = factory.Sequence(lambda n: f"254712{n:06d}")
    verified = True


class OrganizerPayoutFactory(DjangoModelFactory):
    """
    Creates an organizer payout record.

    Usage:
        payout = OrganizerPayoutFactory(organizer=org, order=order)
        payout = OrganizerPayoutFactory(status='completed')
    """

    class Meta:
        model = OrganizerPayout

    organizer = factory.SubFactory(OrganizerProfileFactory)
    # order will be set via SubFactory in payment_factory to avoid circular import
    amount = factory.LazyAttribute(lambda o: Decimal('1000.00'))
    platform_fee = factory.LazyAttribute(lambda o: Decimal('30.00'))
    status = 'scheduled'
    scheduled_for = factory.LazyFunction(
        lambda: timezone.now() + timezone.timedelta(hours=24)
    )
