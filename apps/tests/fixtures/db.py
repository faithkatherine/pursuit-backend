import pytest
from decimal import Decimal

from apps.tests.factories.core_factory import CategoryFactory, InterestFactory
from apps.tests.factories.event_factory import EventFactory, UserEventsFactory
from apps.tests.factories.organizer_factory import (
    OrganizerProfileFactory,
    OrganizerPaymentConfigFactory,
    OrganizerPayoutFactory
)
from apps.tests.factories.payment_factory import (
    OrderFactory,
    MPESATransactionFactory,
    OrganizerPayoutWithOrderFactory
)


# ============================================================================
# CORE FIXTURES
# ============================================================================

@pytest.fixture
def category(db):
    """A single Category."""
    return CategoryFactory(name="Music", icon="🎵")


@pytest.fixture
def another_category(db):
    """A second Category for multi-category tests."""
    return CategoryFactory(name="Sports", icon="⚽")


# ============================================================================
# EVENT FIXTURES
# ============================================================================

@pytest.fixture
def active_event(db, category, organizer):
    """An active, upcoming Event with one Category."""
    return EventFactory(
        name="Jazz Festival",
        is_active=True,
        category=[category],
        organizer=organizer
    )


@pytest.fixture
def inactive_event(db, category, organizer):
    """An inactive Event."""
    return EventFactory(
        name="Cancelled Show",
        is_active=False,
        category=[category],
        organizer=organizer
    )


@pytest.fixture
def saved_event(db, user, active_event):
    """A UserEvents record linking `user` to `active_event`."""
    return UserEventsFactory(user=user, event=active_event)


# ============================================================================
# ORGANIZER FIXTURES
# ============================================================================

@pytest.fixture
def organizer(db):
    """A verified, active organizer."""
    return OrganizerProfileFactory(
        business_name="Pursuit Events HQ",
        verified=True,
        is_active=True
    )


@pytest.fixture
def unverified_organizer(db):
    """An unverified organizer."""
    return OrganizerProfileFactory(
        business_name="New Event Organizer",
        verified=False
    )


@pytest.fixture
def inactive_organizer(db):
    """A deactivated organizer."""
    return OrganizerProfileFactory(
        business_name="Deactivated Organizer",
        is_active=False,
        deactivation_reason="User requested removal"
    )


@pytest.fixture
def organizer_payment_config(db, organizer):
    """Payment configuration for organizer."""
    return OrganizerPaymentConfigFactory(
        organizer=organizer,
        collection_type='paybill',
        collection_shortcode='888000',
        payout_type='b2c',
        verified=True
    )


# ============================================================================
# PAYMENT FIXTURES
# ============================================================================

@pytest.fixture
def pending_order(db, user, active_event):
    """A pending order (not yet paid)."""
    return OrderFactory(
        user=user,
        event=active_event,
        quantity=2,
        status='pending'
    )


@pytest.fixture
def paid_order(db, user, active_event):
    """A paid order."""
    return OrderFactory(
        user=user,
        event=active_event,
        quantity=1,
        subtotal=Decimal('1500.00'),
        platform_fee=Decimal('45.00'),
        total=Decimal('1500.00'),
        status='paid'
    )


@pytest.fixture
def mpesa_transaction_pending(db, pending_order):
    """A pending M-Pesa transaction."""
    return MPESATransactionFactory(
        order=pending_order,
        result_code=None,
        result_desc=None,
        mpesa_receipt=None
    )


@pytest.fixture
def mpesa_transaction_success(db, paid_order):
    """A successful M-Pesa transaction."""
    return MPESATransactionFactory(
        order=paid_order,
        result_code='0',
        result_desc='The service request is processed successfully.',
        mpesa_receipt='QGH1234567XYZ'
    )


@pytest.fixture
def mpesa_transaction_failed(db, pending_order):
    """A failed M-Pesa transaction."""
    return MPESATransactionFactory(
        order=pending_order,
        result_code='1032',
        result_desc='Request cancelled by user',
        mpesa_receipt=None
    )


@pytest.fixture
def scheduled_payout(db, organizer, paid_order):
    """A scheduled payout (24 hours after order)."""
    return OrganizerPayoutWithOrderFactory(
        organizer=organizer,
        order=paid_order,
        status='scheduled'
    )


@pytest.fixture
def completed_payout(db, organizer, paid_order):
    """A completed payout."""
    return OrganizerPayoutWithOrderFactory(
        organizer=organizer,
        order=paid_order,
        status='completed',
        mpesa_receipt='QGH9876543ABC'
    )


@pytest.fixture
def frozen_payout(db, organizer, paid_order):
    """A frozen payout (event cancelled)."""
    return OrganizerPayoutWithOrderFactory(
        organizer=organizer,
        order=paid_order,
        status='frozen',
        frozen_reason='Event cancelled'
    )
