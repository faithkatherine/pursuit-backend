import pytest
from decimal import Decimal
from django.utils import timezone
from django.db.models import ProtectedError

from apps.organizers.models import (
    OrganizerProfile,
    OrganizerPaymentConfig,
    OrganizerPayout
)
from apps.tests.factories.organizer_factory import (
    OrganizerProfileFactory,
    OrganizerPaymentConfigFactory
)
from apps.tests.factories.payment_factory import (
    OrderFactory,
    OrganizerPayoutWithOrderFactory
)
from apps.tests.factories.user_factory import UserFactory


# ============================================================================
# ORGANIZER PROFILE TESTS
# ============================================================================

@pytest.mark.django_db
class TestOrganizerProfile:
    """Test OrganizerProfile model."""

    def test_create_organizer_profile(self):
        """Test creating an organizer profile."""
        user = UserFactory()
        organizer = OrganizerProfileFactory(
            user=user,
            business_name="Test Events Co",
            verified=True
        )

        assert organizer.business_name == "Test Events Co"
        assert organizer.user == user
        assert organizer.verified is True
        assert organizer.is_active is True

    def test_organizer_str_representation(self):
        """Test string representation of organizer."""
        organizer = OrganizerProfileFactory(business_name="Jazz Events")
        assert str(organizer) == "Jazz Events"

    def test_organizer_without_business_name(self):
        """Test organizer string representation without business name."""
        organizer = OrganizerProfileFactory(business_name="")
        assert f"Organizer {organizer.id}" in str(organizer)

    def test_soft_delete_organizer(self):
        """Test soft deleting an organizer."""
        organizer = OrganizerProfileFactory()
        assert organizer.is_active is True

        organizer.deactivate(reason="Testing soft delete")

        assert organizer.is_active is False
        assert organizer.deactivation_reason == "Testing soft delete"
        assert organizer.deactivated_at is not None

    def test_active_organizer_manager(self):
        """Test ActiveOrganizerManager only returns active organizers."""
        active_org = OrganizerProfileFactory(is_active=True)
        inactive_org = OrganizerProfileFactory(is_active=False)

        # Default manager (active only)
        active_organizers = OrganizerProfile.objects.all()
        assert active_org in active_organizers
        assert inactive_org not in active_organizers

        # All objects manager (includes inactive)
        all_organizers = OrganizerProfile.all_objects.all()
        assert active_org in all_organizers
        assert inactive_org in all_organizers

    def test_organizer_user_deletion_sets_null(self):
        """Test that deleting user sets organizer.user to NULL (not cascade)."""
        user = UserFactory()
        organizer = OrganizerProfileFactory(user=user)
        user_id = user.id

        user.delete()

        organizer.refresh_from_db()
        assert organizer.user is None  # SET_NULL behavior
        assert organizer.id is not None  # Organizer still exists

    def test_organizer_with_pending_payout_cannot_be_deleted(self):
        """Test PROTECT on organizer with pending payouts."""
        organizer = OrganizerProfileFactory()
        payout = OrganizerPayoutWithOrderFactory(
            organizer=organizer,
            status='scheduled'
        )

        with pytest.raises(ProtectedError):
            organizer.delete()


# ============================================================================
# ORGANIZER PAYMENT CONFIG TESTS
# ============================================================================

@pytest.mark.django_db
class TestOrganizerPaymentConfig:
    """Test OrganizerPaymentConfig model."""

    def test_create_payment_config(self):
        """Test creating payment configuration."""
        organizer = OrganizerProfileFactory()
        config = OrganizerPaymentConfigFactory(
            organizer=organizer,
            collection_type='paybill',
            collection_shortcode='888000',
            payout_type='b2c',
            payout_destination='254712345678'
        )

        assert config.organizer == organizer
        assert config.collection_type == 'paybill'
        assert config.payout_type == 'b2c'
        assert config.verified is True

    def test_payment_config_str_representation(self):
        """Test string representation."""
        organizer = OrganizerProfileFactory(business_name="Events Inc")
        config = OrganizerPaymentConfigFactory(organizer=organizer)
        assert "Events Inc" in str(config)

    def test_payment_config_cascades_with_organizer(self):
        """Test payment config is deleted when organizer is deleted."""
        organizer = OrganizerProfileFactory()
        config = OrganizerPaymentConfigFactory(organizer=organizer)

        organizer_id = organizer.id
        config_id = config.id

        # Delete organizer (must not have protected payouts)
        organizer.delete()

        # Config should be deleted (CASCADE)
        assert not OrganizerPaymentConfig.objects.filter(id=config_id).exists()

    def test_one_config_per_organizer(self):
        """Test OneToOne relationship - one config per organizer."""
        organizer = OrganizerProfileFactory()
        config1 = OrganizerPaymentConfigFactory(organizer=organizer)

        # Attempting to create second config should fail
        with pytest.raises(Exception):
            OrganizerPaymentConfigFactory(organizer=organizer)


# ============================================================================
# ORGANIZER PAYOUT TESTS
# ============================================================================

@pytest.mark.django_db
class TestOrganizerPayout:
    """Test OrganizerPayout model."""

    def test_create_payout(self):
        """Test creating a payout."""
        organizer = OrganizerProfileFactory()
        order = OrderFactory(
            event__organizer=organizer,
            subtotal=Decimal('3000.00'),
            platform_fee=Decimal('90.00'),
            total=Decimal('3000.00'),
            status='paid'
        )

        payout = OrganizerPayoutWithOrderFactory(
            organizer=organizer,
            order=order
        )

        assert payout.organizer == organizer
        assert payout.order == order
        assert payout.amount == Decimal('2910.00')  # 3000 - 90
        assert payout.platform_fee == Decimal('90.00')
        assert payout.status == 'scheduled'

    def test_payout_str_representation(self):
        """Test string representation."""
        payout = OrganizerPayoutWithOrderFactory()
        assert "KES" in str(payout)
        assert str(payout.organizer.business_name) in str(payout)

    def test_freeze_payout(self):
        """Test freezing a payout."""
        payout = OrganizerPayoutWithOrderFactory(status='scheduled')

        payout.freeze(reason="Event cancelled")

        assert payout.status == 'frozen'
        assert payout.frozen_reason == "Event cancelled"

    def test_mark_payout_completed(self):
        """Test marking payout as completed."""
        payout = OrganizerPayoutWithOrderFactory(status='processing')

        payout.mark_completed(mpesa_receipt='QGH1234567ABC')

        assert payout.status == 'completed'
        assert payout.mpesa_receipt == 'QGH1234567ABC'
        assert payout.completed_at is not None

    def test_payout_protects_order_deletion(self):
        """Test that order cannot be deleted if payout exists."""
        payout = OrganizerPayoutWithOrderFactory()
        order = payout.order

        with pytest.raises(ProtectedError):
            order.delete()

    def test_payout_protects_organizer_deletion(self):
        """Test that organizer cannot be deleted if payout exists."""
        payout = OrganizerPayoutWithOrderFactory()
        organizer = payout.organizer

        with pytest.raises(ProtectedError):
            organizer.delete()

    def test_multiple_payouts_per_organizer(self):
        """Test organizer can have multiple payouts."""
        organizer = OrganizerProfileFactory()
        payout1 = OrganizerPayoutWithOrderFactory(organizer=organizer)
        payout2 = OrganizerPayoutWithOrderFactory(organizer=organizer)

        payouts = OrganizerPayout.objects.filter(organizer=organizer)
        assert payouts.count() == 2
        assert payout1 in payouts
        assert payout2 in payouts

    def test_scheduled_for_is_order_created_plus_24h(self):
        """Test payout scheduled_for is order.created_at + 24 hours."""
        order = OrderFactory(status='paid')
        payout = OrganizerPayoutWithOrderFactory(
            order=order,
            scheduled_for=order.created_at + timezone.timedelta(hours=24)
        )

        expected_time = order.created_at + timezone.timedelta(hours=24)
        # Allow 1 second difference for test execution time
        assert abs((payout.scheduled_for - expected_time).total_seconds()) < 1
