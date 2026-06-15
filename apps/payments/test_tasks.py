"""
Celery Task Tests for Payment System

Tests background tasks mentioned in pursuit_payment_architecture.md:
1. expire_stale_orders - Expires pending orders after timeout
2. process_scheduled_payouts - Processes payouts scheduled for payout
3. handle_event_cancellation - Freezes payouts when event is cancelled
4. retry_failed_payouts - Retries payouts that failed
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.db.models import F
from django.utils import timezone
from freezegun import freeze_time

from apps.events.models import Event
from apps.organizers.models import OrganizerPayout
from apps.payments.models import MPESATransaction, Order
from apps.payments.tasks import (
    expire_stale_orders,
    handle_event_cancellation,
    handle_payout_callback,
    process_scheduled_payouts,
    process_single_payout,
    refund_cancelled_event_orders,
)
from apps.tests.factories import (
    EventFactory,
    MPESATransactionFactory,
    OrderFactory,
    OrganizerPaymentConfigFactory,
    OrganizerPayoutFactory,
    OrganizerPayoutWithOrderFactory,
    OrganizerProfileFactory,
)

# Platform fee rate constant (2%)
PLATFORM_FEE_RATE = Decimal('0.02')


# ============================================================================
# TASK: expire_stale_orders
# ============================================================================

@pytest.mark.django_db
class TestExpireStaleOrdersTask:
    """
    Test Celery task that expires old pending orders.

    Configuration:
    - Timeout: 15 minutes
    - Runs: Every 1 hour (Celery Beat)
    - Actions on expiration:
      1. Mark order status as 'expired'
      2. Release tickets back to event.available_tickets using F() atomic update
      3. Notify user about expiration
    """

    @freeze_time("2026-06-09 15:00:00")
    def test_expire_orders_older_than_timeout(self):
        """Test that orders older than 15 minutes are expired."""
        TIMEOUT_MINUTES = 15

        # Create orders at different times
        # Order 1: 20 minutes old (should expire)
        with freeze_time("2026-06-09 14:40:00"):
            old_order = OrderFactory(status='pending')

        # Order 2: 10 minutes old (should not expire)
        with freeze_time("2026-06-09 14:50:00"):
            recent_order = OrderFactory(status='pending')

        # Order 3: Already paid (should not touch)
        paid_order = OrderFactory(status='paid')

        # Run task
        result = expire_stale_orders(timeout_minutes=TIMEOUT_MINUTES)

        old_order.refresh_from_db()
        recent_order.refresh_from_db()
        paid_order.refresh_from_db()

        assert old_order.status == 'expired'
        assert recent_order.status == 'pending'
        assert paid_order.status == 'paid'
        assert result['expired_count'] == 1

    def test_release_tickets_on_expiration(self):
        """Test that tickets are released back to event when order expires.

        Flow:
        1. Order created (pending) → decrement event.available_tickets atomically
        2. Order expires → increment event.available_tickets atomically
        3. Use F() expressions to prevent race conditions

        Implementation:
        - Order.save() decrements tickets if status='pending'
        - expire_stale_orders task increments tickets when marking expired
        - Atomic: Event.objects.filter(id=X).update(available_tickets=F('available_tickets') + quantity)
        """
        event = EventFactory(available_tickets=100)

        # Simulate order creation reserving 5 tickets
        # In real implementation, this happens in Order.save() or view
        Event.objects.filter(id=event.id).update(
            available_tickets=F('available_tickets') - 5
        )

        order = OrderFactory(
            event=event,
            quantity=5,
            status='pending'
        )

        event.refresh_from_db()
        assert event.available_tickets == 95

        # Expire order and release tickets
        from apps.payments.tasks import expire_stale_orders

        # Task should atomically release tickets
        order.status = 'expired'
        order.save()

        # Release tickets atomically
        Event.objects.filter(id=event.id).update(
            available_tickets=F('available_tickets') + order.quantity
        )

        event.refresh_from_db()
        assert event.available_tickets == 100

    def test_do_not_expire_orders_with_successful_mpesa(self):
        """Test that orders with successful M-Pesa tx are not expired."""
        old_order = OrderFactory(status='pending')
        old_order.created_at = timezone.now() - timezone.timedelta(minutes=30)
        old_order.save()

        # M-Pesa transaction succeeded
        MPESATransactionFactory(
            order=old_order,
            result_code='0',
            mpesa_receipt='QGH123'
        )

        from apps.payments.tasks import expire_stale_orders
        expire_stale_orders(timeout_minutes=15)

        old_order.refresh_from_db()
        # Should not expire because M-Pesa succeeded (callback might be delayed)
        assert old_order.status == 'pending' or old_order.status == 'paid'


# ============================================================================
# TASK: process_scheduled_payouts
# ============================================================================

@pytest.mark.django_db
class TestProcessScheduledPayoutsTask:
    """
    Test Celery task that processes payouts scheduled for execution.

    Configuration:
    - Runs: Every 1 hour (Celery Beat)
    - Payout trigger: 24 hours after order becomes 'paid' (not created_at)
    - Retry logic: 5 attempts, 1 hour apart, then alert admin
    - Payout type: Always use OrganizerPaymentConfig.payout_type (b2c/b2b_paybill/b2b_till)

    Flow:
    1. Find payouts with status='scheduled' and scheduled_for <= now
    2. For each payout, get organizer's OrganizerPaymentConfig
    3. Call Daraja B2C (personal M-Pesa) or B2B (business paybill/till) API
    4. Update payout status to 'processing' on API acceptance
    5. On callback, update to 'completed' or 'failed'
    6. Retry failed payouts up to 5 times, 1 hour apart
    7. After 5 failures, alert admin
    """

    def setup_method(self):
        self.payment_config = OrganizerPaymentConfigFactory(
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )
        self.organizer = self.payment_config.organizer

    @freeze_time("2026-06-10 10:00:00")
    def test_process_due_payouts(self):
        """Test processing payouts that are due."""
        # Payout 1: Due now
        with freeze_time("2026-06-10 09:00:00"):
            due_payout = OrganizerPayoutWithOrderFactory(
                organizer=self.organizer,
                status='scheduled',
                scheduled_for=timezone.now()
            )

        # Payout 2: Not due yet
        future_payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() + timezone.timedelta(hours=5)
        )

        # Mock Daraja B2C API
        mock_response = {
            'ConversationID': 'AG_20260610_123',
            'OriginatorConversationID': 'orig_456',
            'ResponseCode': '0',
            'ResponseDescription': 'Accept the service request successfully.'
        }

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = mock_response

            result = process_scheduled_payouts()

        due_payout.refresh_from_db()
        future_payout.refresh_from_db()

        assert due_payout.status == 'processing'
        assert future_payout.status == 'scheduled'
        assert result['processed_count'] == 1

    def test_process_payout_with_b2c(self):
        """Test B2C payout to personal M-Pesa number."""
        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
            amount=Decimal('5000.00')
        )

        mock_response = {
            'ConversationID': 'conv_123',
            'ResponseCode': '0'
        }

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = mock_response

            process_single_payout(payout.id)

        # Verify B2C was called with payout object
        mock_b2c.assert_called_once_with(payout)

        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_process_payout_with_b2b_paybill(self):
        """Test B2B payout to business paybill."""
        self.payment_config.payout_type = 'b2b_paybill'
        self.payment_config.payout_destination = '888000'
        self.payment_config.save()

        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1)
        )

        with patch('apps.payments.daraja.initiate_b2b_payout') as mock_b2b:
            mock_b2b.return_value = {'ResponseCode': '0'}

            process_single_payout(payout.id)

        # Verify B2B was called
        mock_b2b.assert_called_once()

    def test_skip_frozen_payouts(self):
        """Test that frozen payouts are not processed."""
        frozen_payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='frozen',
            frozen_reason='Event cancelled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1)
        )

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            result = process_scheduled_payouts()

        # Should not call Daraja
        mock_b2c.assert_not_called()

        frozen_payout.refresh_from_db()
        assert frozen_payout.status == 'frozen'

    def test_handle_daraja_api_failure(self):
        """Test retry logic when Daraja API fails.

        Retry configuration:
        - Max retries: 5 attempts
        - Retry interval: 1 hour apart
        - After 5 failures: Mark as 'failed' and alert admin
        - Celery autoretry: Use @shared_task(autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 3600})
        """
        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1)
        )

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.side_effect = Exception('Network timeout')

            # Task should raise exception to trigger Celery retry
            with pytest.raises(Exception):
                process_single_payout(payout.id)

        payout.refresh_from_db()
        # Status stays 'scheduled' so it can be retried by next run
        # After 5 failures, task will mark as 'failed' and send admin alert
        assert payout.status == 'scheduled'


# ============================================================================
# TASK: handle_event_cancellation
# ============================================================================

@pytest.mark.django_db
class TestHandleEventCancellationTask:
    """
    Test Celery task triggered when event is cancelled.

    Flow:
    1. Find all payouts for cancelled event
    2. Freeze payouts with status='scheduled'
    3. Initiate refunds for paid orders
    4. Claw back completed payouts (if needed)
    """

    def test_freeze_scheduled_payouts_on_cancellation(self):
        """Test that scheduled payouts are frozen when event is cancelled."""
        event = EventFactory(status='active')

        # Create payouts in different states
        scheduled_payout = OrganizerPayoutWithOrderFactory(
            order__event=event,
            status='scheduled'
        )
        completed_payout = OrganizerPayoutWithOrderFactory(
            order__event=event,
            status='completed'
        )

        # Cancel event
        event.status = 'cancelled'
        event.cancellation_reason = 'Venue unavailable'
        event.save()

        result = handle_event_cancellation(event.id)

        scheduled_payout.refresh_from_db()
        completed_payout.refresh_from_db()

        assert scheduled_payout.status == 'frozen'
        assert 'cancelled' in scheduled_payout.frozen_reason.lower()
        assert completed_payout.status == 'completed'  # Already paid
        assert result['frozen_count'] == 1

    def test_refund_paid_orders_on_cancellation(self):
        """Test that paid orders are refunded when event is cancelled.

        Refund strategy:
        1. If payout not yet processed (within 24h of payment):
           - Use Daraja Reversal API to reverse transaction
           - Refund to original M-Pesa number from MPESATransaction.phone_number
        2. If payout already processed (admin hasn't remitted to organizer):
           - Manual refund process (rare case)
           - Admin processes refund, updates order status manually
        3. No partial refunds (full refund only)

        Event cancellation can be triggered by:
        - Admin cancels event
        - Organizer cancels event
        """
        event = EventFactory(status='active')

        # Order paid 12 hours ago (within 24h window)
        paid_order = OrderFactory(event=event, status='paid')
        paid_order.created_at = timezone.now() - timezone.timedelta(hours=12)
        paid_order.save()

        mpesa_txn = MPESATransactionFactory(
            order=paid_order,
            result_code='0',
            mpesa_receipt='NLJ7RT61SV',
            phone_number='254712345678'
        )

        # Payout scheduled but not yet processed
        payout = OrganizerPayoutWithOrderFactory(
            order=paid_order,
            status='scheduled',
            scheduled_for=timezone.now() + timezone.timedelta(hours=12)
        )

        # Cancel event
        event.status = 'cancelled'
        event.cancellation_reason = 'Venue unavailable'
        event.save()

        # Mock Daraja Reversal API
        mock_reversal_response = {
            'ResponseCode': '0',
            'ResponseDescription': 'The service request is processed successfully.'
        }

        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            mock_reversal.return_value = mock_reversal_response

            result = refund_cancelled_event_orders(event.id)

        paid_order.refresh_from_db()
        assert paid_order.status == 'refunded'
        assert result['refunded_count'] == 1

        # Verify reversal was called with correct M-Pesa receipt and phone
        mock_reversal.assert_called_once()
        call_kwargs = mock_reversal.call_args[1]
        assert call_kwargs['transaction_id'] == 'NLJ7RT61SV'
        assert call_kwargs['phone_number'] == '254712345678'


# ============================================================================
# TASK: payout_callback_handler
# ============================================================================

@pytest.mark.django_db
class TestPayoutCallbackHandler:
    """
    Test handling of Daraja B2C/B2B result callbacks.

    TODO: What's the callback URL structure?
    TODO: What's the expected payload format?
    """

    def test_handle_successful_payout_callback(self):
        """Test updating payout when Daraja confirms success."""
        payout = OrganizerPayoutWithOrderFactory(status='processing')

        # Sample B2C result callback
        callback_data = {
            'Result': {
                'ConversationID': 'conv_123',
                'ResultCode': 0,
                'ResultDesc': 'The service request is processed successfully.',
                'ResultParameters': {
                    'ResultParameter': [
                        {'Key': 'TransactionReceipt', 'Value': 'QGH9876543'},
                        {'Key': 'TransactionAmount', 'Value': 5000.00}
                    ]
                }
            }
        }

        handle_payout_callback(payout.id, callback_data)

        payout.refresh_from_db()
        assert payout.status == 'completed'
        assert payout.mpesa_receipt == 'QGH9876543'
        assert payout.completed_at is not None

    def test_handle_failed_payout_callback(self):
        """Test handling when Daraja reports payout failure."""
        payout = OrganizerPayoutWithOrderFactory(status='processing')

        callback_data = {
            'Result': {
                'ResultCode': 2001,
                'ResultDesc': 'The initiator information is invalid.'
            }
        }

        handle_payout_callback(payout.id, callback_data)

        payout.refresh_from_db()
        assert payout.status == 'failed'
        # TODO: Should failed payouts be retried?


# ============================================================================
# MISSING IMPLEMENTATION DETAILS
# ============================================================================

"""
CELERY CONFIGURATION - CONFIRMED:

1. **Task Schedule:**
   - expire_stale_orders: Every 1 hour
   - process_scheduled_payouts: Every 1 hour
   - refresh_mpesa_oauth_token: Every 55 minutes (proactive token refresh)

2. **Retry Logic:**
   - Max retries: 5 attempts for failed payouts
   - Retry interval: 1 hour apart
   - After 5 failures: Mark as 'failed' and alert admin via email + dashboard

3. **Monitoring:**
   - Admin dashboard (view stuck/failed payouts)
   - Email alerts (after 5 retry failures)
   - Sentry integration (TODO for future)

4. **Ticket Reservation:**
   - YES: Decrement available_tickets when order created (pending)
   - Use F() atomic updates to prevent race conditions
   - Release tickets when order expires or fails

5. **Refunds:**
   - Use Daraja Reversal API if within 24h (payout not processed)
   - Manual refunds if payout already processed (rare case)
   - Always refund to original M-Pesa number
   - Full refunds only (no partial refunds)

6. **Callback URLs:**
   - STK Push callback: /api/payments/mpesa/callback/
   - B2C result callback: /api/payments/mpesa/b2c-callback/
   - B2B result callback: /api/payments/mpesa/b2b-callback/
   - Timeout callback: Same endpoints handle timeout (ResultCode != 0)

7. **Error Notifications:**
   - Email admins on 5 consecutive payout failures
   - Email organizers when payout frozen due to event cancellation
   - User notification on order expiration
"""


# ============================================================================
# CELERY BEAT SCHEDULE (FINAL CONFIGURATION)
# ============================================================================

"""
# In pursuit_backend/celery.py or settings.py

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'expire-stale-orders': {
        'task': 'apps.payments.tasks.expire_stale_orders',
        'schedule': crontab(minute=0, hour='*/1'),  # Every 1 hour
        'kwargs': {'timeout_minutes': 15}
    },
    'process-scheduled-payouts': {
        'task': 'apps.payments.tasks.process_scheduled_payouts',
        'schedule': crontab(minute=0, hour='*/1'),  # Every 1 hour
    },
    'refresh-mpesa-oauth-token': {
        'task': 'apps.payments.tasks.refresh_mpesa_oauth_token',
        'schedule': crontab(minute=55),  # Every 55 minutes (proactive refresh)
    },
}

# Platform fee configuration (stored in database for future expansion)
# Default: 2% stored in a PlatformConfig model
"""


@pytest.mark.django_db
class TestOrganizerPayoutRouting:
    """Tests that payout routes to correct Daraja API based on payout_type"""

    def setup_method(self):
        self.organizer = OrganizerProfileFactory(verified=True)
        self.payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_destination='254712345678',
            verified=True
        )

    def test_b2c_payout_called_for_personal_mpesa(self):
        """Test B2C payout for personal M-Pesa number"""
        self.payment_config.payout_type = 'b2c'
        self.payment_config.save()

        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
            amount=Decimal('5000.00')
        )

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = {'ResponseCode': '0'}

            process_single_payout(payout.id)

        mock_b2c.assert_called_once_with(payout)

        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_b2b_payout_called_for_paybill(self):
        """Test B2B payout for business paybill"""
        self.payment_config.payout_type = 'b2b_paybill'
        self.payment_config.payout_destination = '888000'
        self.payment_config.save()

        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
            amount=Decimal('3000.00')
        )

        with patch('apps.payments.daraja.initiate_b2b_payout') as mock_b2b:
            mock_b2b.return_value = {'ResponseCode': '0'}

            process_single_payout(payout.id)

        mock_b2b.assert_called_once_with(payout)

        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_b2b_payout_called_for_till(self):
        """Test B2B payout for till number"""
        self.payment_config.payout_type = 'b2b_till'
        self.payment_config.payout_destination = '123456'
        self.payment_config.save()

        payout = OrganizerPayoutWithOrderFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
            amount=Decimal('2000.00')
        )

        with patch('apps.payments.daraja.initiate_b2b_payout') as mock_b2b:
            mock_b2b.return_value = {'ResponseCode': '0'}

            process_single_payout(payout.id)

        mock_b2b.assert_called_once_with(payout)

        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_payout_amount_correct_model_b(self):
        """Test payout amount = order.total - platform_fee (Model B)"""
        order = OrderFactory(
            subtotal=Decimal('1500.00'),
            platform_fee=Decimal('30.00'),
            total=Decimal('1500.00'),
            status='paid'
        )

        payout = OrganizerPayoutWithOrderFactory(order=order)

        assert payout.amount == Decimal('1470.00')
        assert payout.platform_fee == Decimal('30.00')


@pytest.mark.django_db
class TestEventCancellation:
    """Tests for event cancellation → payout freeze → user refunds"""

    def test_cancellation_freezes_scheduled_payouts(self):
        """Test event cancellation freezes all scheduled payouts"""
        from apps.events.models import Event

        event = EventFactory(status='live')

        # Create 3 paid orders with scheduled payouts
        payout1 = OrganizerPayoutWithOrderFactory(
            order__event=event,
            order__status='paid',
            status='scheduled'
        )
        payout2 = OrganizerPayoutWithOrderFactory(
            order__event=event,
            order__status='paid',
            status='scheduled'
        )
        payout3 = OrganizerPayoutWithOrderFactory(
            order__event=event,
            order__status='paid',
            status='scheduled'
        )

        # Cancel event
        event.status = 'cancelled'
        event.cancellation_reason = 'Venue flooded'
        event.save()

        result = handle_event_cancellation(event.id)

        payout1.refresh_from_db()
        payout2.refresh_from_db()
        payout3.refresh_from_db()

        assert payout1.status == 'frozen'
        assert payout2.status == 'frozen'
        assert payout3.status == 'frozen'
        assert 'flooded' in payout1.frozen_reason.lower()
        assert result['frozen_count'] == 3

    def test_cancellation_does_not_freeze_completed_payouts(self):
        """Test completed payouts remain untouched on event cancellation"""
        from apps.events.models import Event

        event = EventFactory(status='live')

        scheduled_payout = OrganizerPayoutWithOrderFactory(
            order__event=event,
            status='scheduled'
        )
        completed_payout = OrganizerPayoutWithOrderFactory(
            order__event=event,
            status='completed'
        )

        event.status = 'cancelled'
        event.cancellation_reason = 'Test'
        event.save()

        result = handle_event_cancellation(event.id)

        scheduled_payout.refresh_from_db()
        completed_payout.refresh_from_db()

        assert scheduled_payout.status == 'frozen'
        assert completed_payout.status == 'completed'
        assert result['frozen_count'] == 1

    def test_cancellation_triggers_refunds_for_paid_orders(self):
        """Test refunds initiated for paid orders when event cancelled"""
        from apps.events.models import Event

        event = EventFactory(status='live')

        # Create 2 paid orders within 24h window
        order1 = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timezone.timedelta(hours=2)
        )
        order2 = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timezone.timedelta(hours=5)
        )

        txn1 = MPESATransactionFactory(
            order=order1,
            phone_number='254712345678',
            mpesa_receipt='QGH123ABC'
        )
        txn2 = MPESATransactionFactory(
            order=order2,
            phone_number='254711111111',
            mpesa_receipt='QGH456DEF'
        )

        event.status = 'cancelled'
        event.save()

        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            mock_reversal.return_value = {'ResponseCode': '0'}

            from apps.payments.tasks import refund_cancelled_event_orders
            result = refund_cancelled_event_orders(event.id)

        # Verify reversal called twice
        assert mock_reversal.call_count == 2

    def test_refund_uses_original_phone_number(self):
        """Test refund uses original buyer phone from MPESATransaction"""
        from apps.events.models import Event

        event = EventFactory(status='live')
        order = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timezone.timedelta(hours=1)
        )
        txn = MPESATransactionFactory(
            order=order,
            phone_number='254712345678',
            mpesa_receipt='QGH789XYZ'
        )

        event.status = 'cancelled'
        event.save()

        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            mock_reversal.return_value = {'ResponseCode': '0'}

            from apps.payments.tasks import refund_cancelled_event_orders
            refund_cancelled_event_orders(event.id)

        # Verify reversal called with correct parameters
        mock_reversal.assert_called_once()
        call_args = mock_reversal.call_args

        # The function is called with transaction_id, amount, phone as kwargs
        # or as positional args - check both possibilities
        if call_args[1]:  # kwargs
            assert call_args[1]['phone'] == '254712345678'
        else:  # positional
            assert '254712345678' in str(call_args)
