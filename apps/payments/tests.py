from decimal import Decimal

import pytest
from django.db.models import ProtectedError

from apps.organizers.models import OrganizerPayout
from apps.payments.models import MPESATransaction, Order
from apps.tests.factories.event_factory import EventFactory
from apps.tests.factories.payment_factory import MPESATransactionFactory, OrderFactory, OrganizerPayoutWithOrderFactory
from apps.tests.factories.user_factory import UserFactory

# ============================================================================
# ORDER MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestOrder:
    """Test Order model (Model B - Seller Pays Fee)."""

    def test_create_order(self):
        """Test creating an order with Model B pricing."""
        user = UserFactory()
        event = EventFactory(price=Decimal('1500.00'))

        order = OrderFactory(
            user=user,
            event=event,
            quantity=2,
            subtotal=Decimal('3000.00'),
            platform_fee=Decimal('90.00'),
            total=Decimal('3000.00')
        )

        assert order.user == user
        assert order.event == event
        assert order.quantity == 2
        assert order.subtotal == Decimal('3000.00')
        assert order.platform_fee == Decimal('90.00')
        assert order.total == Decimal('3000.00')  # No fee added to buyer
        assert order.status == 'pending'

    def test_order_save_sets_total_equal_to_subtotal(self):
        """Test save() method ensures total = subtotal in Model B."""
        order = OrderFactory(
            subtotal=Decimal('2000.00'),
            total=Decimal('0.00')  # Will be overridden
        )

        order.save()

        assert order.total == order.subtotal

    def test_organizer_payout_amount_calculation(self):
        """Test organizer_payout_amount() method."""
        order = OrderFactory(
            subtotal=Decimal('5000.00'),
            platform_fee=Decimal('150.00'),
            total=Decimal('5000.00')
        )

        payout_amount = order.organizer_payout_amount()

        assert payout_amount == Decimal('4850.00')  # 5000 - 150

    def test_order_str_representation(self):
        """Test string representation."""
        user = UserFactory(email="test@example.com")
        event = EventFactory(name="Jazz Night")
        order = OrderFactory(user=user, event=event)

        assert str(order.id) in str(order)
        assert "test@example.com" in str(order)

    def test_order_with_deleted_user(self):
        """Test order survives user deletion (SET_NULL)."""
        user = UserFactory()
        order = OrderFactory(user=user)

        user.delete()

        order.refresh_from_db()
        assert order.user is None  # SET_NULL behavior
        assert order.id is not None  # Order still exists
        assert "Deleted User" in str(order)

    def test_order_protects_event_deletion(self):
        """Test event cannot be deleted if orders exist (PROTECT)."""
        order = OrderFactory()
        event = order.event

        with pytest.raises(ProtectedError):
            event.delete()

    def test_idempotency_key_is_unique(self):
        """Test idempotency_key is unique across orders."""
        order1 = OrderFactory()

        # Attempting to create order with same key should fail
        with pytest.raises(Exception):
            OrderFactory(idempotency_key=order1.idempotency_key)

    def test_order_statuses(self):
        """Test all order status choices work."""
        statuses = ['pending', 'paid', 'failed', 'expired', 'refunded']

        for status in statuses:
            order = OrderFactory(status=status)
            assert order.status == status

    def test_model_b_pricing_no_fee_added_to_buyer(self):
        """Test Model B: buyer pays ticket price only, no fee added."""
        ticket_price = Decimal('2500.00')
        quantity = 3

        order = OrderFactory(
            quantity=quantity,
            subtotal=ticket_price * quantity,  # 7500
            platform_fee=Decimal('225.00'),     # 3% of 7500
            total=ticket_price * quantity       # 7500 (same as subtotal)
        )

        # Buyer pays exactly ticket price × quantity
        assert order.total == ticket_price * quantity
        # Organizer gets ticket price minus platform fee
        assert order.organizer_payout_amount() == Decimal('7275.00')


# ============================================================================
# MPESA TRANSACTION TESTS
# ============================================================================

@pytest.mark.django_db
class TestMPESATransaction:
    """Test MPESATransaction model."""

    def test_create_mpesa_transaction(self):
        """Test creating an M-Pesa transaction."""
        order = OrderFactory()
        txn = MPESATransactionFactory(
            order=order,
            phone_number='254712345678',
            checkout_request_id='ws_CO_12345',
            merchant_request_id='merchant_123'
        )

        assert txn.order == order
        assert txn.phone_number == '254712345678'
        assert txn.checkout_request_id == 'ws_CO_12345'
        assert txn.result_code is None  # Pending

    def test_mpesa_transaction_str_representation(self):
        """Test string representation."""
        order = OrderFactory()
        txn = MPESATransactionFactory(order=order)

        assert "M-Pesa Transaction" in str(txn)
        assert str(order.id) in str(txn)

    def test_is_successful_method(self):
        """Test is_successful() method."""
        # Successful transaction
        success_txn = MPESATransactionFactory(result_code='0')
        assert success_txn.is_successful() is True

        # Failed transaction
        failed_txn = MPESATransactionFactory(result_code='1032')
        assert failed_txn.is_successful() is False

        # Pending transaction
        pending_txn = MPESATransactionFactory(result_code=None)
        assert pending_txn.is_successful() is False

    def test_mpesa_transaction_cascades_with_order(self):
        """Test transaction is deleted when order is deleted (CASCADE)."""
        order = OrderFactory()
        txn = MPESATransactionFactory(order=order)
        txn_id = txn.id

        # Note: Order has PROTECT from payouts, so delete only works if no payouts exist
        order.delete()

        # Transaction should be deleted
        assert not MPESATransaction.objects.filter(id=txn_id).exists()

    def test_one_transaction_per_order(self):
        """Test OneToOne relationship - one transaction per order."""
        order = OrderFactory()
        txn1 = MPESATransactionFactory(order=order)

        # Attempting to create second transaction for same order should fail
        with pytest.raises(Exception):
            MPESATransactionFactory(order=order)

    def test_checkout_request_id_is_unique(self):
        """Test checkout_request_id is unique."""
        txn1 = MPESATransactionFactory(checkout_request_id='ws_CO_UNIQUE123')

        with pytest.raises(Exception):
            MPESATransactionFactory(checkout_request_id='ws_CO_UNIQUE123')

    def test_mpesa_receipt_for_successful_transaction(self):
        """Test successful transaction has M-Pesa receipt."""
        txn = MPESATransactionFactory(
            result_code='0',
            result_desc='The service request is processed successfully.',
            mpesa_receipt='QGH1234567ABC'
        )

        assert txn.is_successful()
        assert txn.mpesa_receipt == 'QGH1234567ABC'
        assert 'successfully' in txn.result_desc.lower()

    def test_mpesa_failed_transaction_no_receipt(self):
        """Test failed transaction has no receipt."""
        txn = MPESATransactionFactory(
            result_code='1032',
            result_desc='Request cancelled by user',
            mpesa_receipt=None
        )

        assert not txn.is_successful()
        assert txn.mpesa_receipt is None


# ============================================================================
# ORDER + PAYOUT INTEGRATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestOrderPayoutIntegration:
    """Test Order and OrganizerPayout integration."""

    def test_order_with_payout_cannot_be_deleted(self):
        """Test order with payout cannot be deleted (PROTECT)."""
        payout = OrganizerPayoutWithOrderFactory()
        order = payout.order

        with pytest.raises(ProtectedError):
            order.delete()

    def test_payout_amount_matches_order_calculation(self):
        """Test payout amount = order.total - order.platform_fee."""
        order = OrderFactory(
            subtotal=Decimal('10000.00'),
            platform_fee=Decimal('300.00'),
            total=Decimal('10000.00'),
            status='paid'
        )

        payout = OrganizerPayoutWithOrderFactory(order=order)

        assert payout.amount == order.organizer_payout_amount()
        assert payout.amount == Decimal('9700.00')
        assert payout.platform_fee == order.platform_fee

    def test_multiple_orders_create_multiple_payouts(self):
        """Test each order creates its own payout (per-order model)."""
        organizer_profile = EventFactory().organizer

        order1 = OrderFactory(event__organizer=organizer_profile, status='paid')
        order2 = OrderFactory(event__organizer=organizer_profile, status='paid')

        payout1 = OrganizerPayoutWithOrderFactory(
            organizer=organizer_profile,
            order=order1
        )
        payout2 = OrganizerPayoutWithOrderFactory(
            organizer=organizer_profile,
            order=order2
        )

        assert payout1.order == order1
        assert payout2.order == order2
        assert OrganizerPayout.objects.filter(
            organizer=organizer_profile
        ).count() == 2


# ============================================================================
# MODEL B BUSINESS LOGIC TESTS
# ============================================================================

@pytest.mark.django_db
class TestModelBBusinessLogic:
    """Test Model B (Seller Pays Fee) business logic."""

    def test_buyer_pays_ticket_price_only(self):
        """Test buyer sees and pays only ticket price × quantity."""
        ticket_price = Decimal('1500.00')
        quantity = 2

        order = OrderFactory(
            subtotal=ticket_price * quantity,
            platform_fee=(ticket_price * quantity * Decimal('0.03')),
            total=ticket_price * quantity
        )

        # What buyer sees at checkout
        assert order.total == Decimal('3000.00')

        # No separate fee line shown to buyer
        assert order.total == order.subtotal

    def test_organizer_receives_net_amount(self):
        """Test organizer receives ticket revenue minus platform fee."""
        order = OrderFactory(
            subtotal=Decimal('5000.00'),
            platform_fee=Decimal('150.00'),  # 3%
            total=Decimal('5000.00'),
            status='paid'
        )

        payout_amount = order.organizer_payout_amount()

        # Organizer gets: buyer payment - platform fee
        assert payout_amount == Decimal('4850.00')

    def test_pursuit_keeps_platform_fee(self):
        """Test Pursuit revenue is the platform fee."""
        order = OrderFactory(
            total=Decimal('10000.00'),
            platform_fee=Decimal('300.00')
        )

        buyer_payment = order.total  # 10000
        organizer_payout = order.organizer_payout_amount()  # 9700
        pursuit_revenue = order.platform_fee  # 300

        assert buyer_payment == organizer_payout + pursuit_revenue
        assert pursuit_revenue == Decimal('300.00')
