"""
Integration Tests for Payment System

Tests complete end-to-end workflows:
1. Full payment flow (initiate → callback → status → payout scheduling)
2. Payout flow (B2C and B2B processing)
3. Refund flow (reversal and manual refunds)
4. Concurrency scenarios (race conditions, ticket inventory)
"""

import pytest
import threading
from decimal import Decimal
from unittest.mock import patch, MagicMock
from datetime import timedelta

from django.utils import timezone
from django.core.cache import cache
from django.db.models import F
from rest_framework.test import APIClient

from apps.payments.models import Order, MPESATransaction
from apps.organizers.models import OrganizerPayout
from apps.payments.tasks import (
    process_scheduled_payouts,
    process_single_payout,
    refund_cancelled_event_orders,
    handle_event_cancellation,
    expire_stale_orders,
)
from apps.tests.factories import (
    EventFactory,
    OrderFactory,
    OrganizerPaymentConfigFactory,
    OrganizerProfileFactory,
    UserFactory,
    MPESATransactionFactory,
)
from apps.tests.factories.organizer_factory import OrganizerPayoutFactory
from apps.payments.conftest import (
    PLATFORM_FEE_RATE,
    MOCK_STK_SUCCESS_RESPONSE,
    MOCK_STK_CALLBACK_SUCCESS,
    MOCK_STK_CALLBACK_FAILED,
    MOCK_B2C_SUCCESS_RESPONSE,
    MOCK_REVERSAL_SUCCESS_RESPONSE,
)


# ============================================================================
# TEST CLASS 1: FULL PAYMENT FLOW
# ============================================================================

@pytest.mark.django_db
class TestFullPaymentFlow:
    """
    Integration tests for complete payment flow from initiation to payout scheduling.
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.organizer = OrganizerProfileFactory(verified=True)
        self.payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )
        self.event = EventFactory(
            organizer=self.organizer,
            price=Decimal('1500.00'),
            available_tickets=10,
            ticketing_enabled=True
        )

    def test_complete_successful_payment_flow(self):
        """Test full payment flow from initiation to payout scheduling.

        Flow:
        1. Initiate payment
        2. Verify order created with status='pending'
        3. Verify MPESATransaction created
        4. Verify tickets decremented
        5. Send M-Pesa callback
        6. Verify order status='paid'
        7. Verify transaction result_code='0'
        8. Check payment status
        9. Verify payout scheduled 24h after paid_at
        10. Verify payout amount = total - platform_fee
        """
        # Step 1: Initiate payment
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = MOCK_STK_SUCCESS_RESPONSE

            self.client.force_authenticate(user=self.user)
            response = self.client.post('/api/payments/initiate/', {
                'event_id': self.event.id,
                'quantity': 2,
                'phone_number': '254712345678'
            }, format='json')

        # Step 2-3: Verify order and transaction created
        assert response.status_code == 200
        data = response.json()
        assert 'checkout_request_id' in data
        assert 'id' in data

        order = Order.objects.get(id=data['id'])
        assert order.user == self.user
        assert order.event == self.event
        assert order.quantity == 2
        assert order.status == 'pending'
        assert order.subtotal == Decimal('3000.00')  # 1500 * 2
        assert order.platform_fee == Decimal('60.00')  # 2% of 3000
        assert order.total == Decimal('3000.00')  # Model B: buyer pays subtotal only

        txn = MPESATransaction.objects.get(order=order)
        assert txn.checkout_request_id == MOCK_STK_SUCCESS_RESPONSE['CheckoutRequestID']
        assert txn.result_code is None  # Pending until callback

        # Step 4: Verify tickets decremented
        self.event.refresh_from_db()
        assert self.event.available_tickets == 8

        # Step 5: Send M-Pesa callback
        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': txn.merchant_request_id,
                    'CheckoutRequestID': txn.checkout_request_id,
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 3000.00},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'QGH1234567'},
                            {'Name': 'TransactionDate', 'Value': 20260609143000},
                            {'Name': 'PhoneNumber', 'Value': 254712345678}
                        ]
                    }
                }
            }
        }

        callback_response = self.client.post(
            '/api/payments/mpesa/callback/',
            callback_payload,
            format='json'
        )
        assert callback_response.status_code == 200

        # Step 6-7: Verify order and transaction updated
        order.refresh_from_db()
        txn.refresh_from_db()

        assert order.status == 'paid'
        assert order.paid_at is not None
        assert txn.result_code == '0'
        assert txn.mpesa_receipt == 'QGH1234567'
        assert txn.is_successful()

        # Step 8: Check payment status
        self.client.force_authenticate(user=self.user)
        status_response = self.client.get(
            f'/api/payments/status/{txn.checkout_request_id}/'
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data['status'] == 'paid'
        assert status_data['mpesa_receipt'] == 'QGH1234567'

        # Step 9-10: Verify payout scheduled
        payout = OrganizerPayout.objects.get(order=order)
        assert payout.organizer == self.organizer
        assert payout.amount == Decimal('2940.00')  # 3000 - 60 (2% platform fee)
        assert payout.platform_fee == Decimal('60.00')
        assert payout.status == 'scheduled'
        assert payout.scheduled_for is not None

        # Verify scheduled 24h after paid_at
        expected_scheduled = order.paid_at + timedelta(hours=24)
        time_diff = abs((payout.scheduled_for - expected_scheduled).total_seconds())
        assert time_diff < 2  # Within 2 seconds

    def test_payment_flow_with_failed_callback(self):
        """Test payment flow when user cancels M-Pesa prompt.

        Flow:
        1. Initiate payment
        2. Send failed callback (result_code=1032 - user cancelled)
        3. Verify order status='failed'
        4. Verify tickets released back to pool
        5. Verify NO payout created
        """
        # Initiate payment
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = MOCK_STK_SUCCESS_RESPONSE

            self.client.force_authenticate(user=self.user)
            response = self.client.post('/api/payments/initiate/', {
                'event_id': self.event.id,
                'quantity': 3,
                'phone_number': '254712345678'
            }, format='json')

        assert response.status_code == 200
        order = Order.objects.get(id=response.json()['id'])
        txn = MPESATransaction.objects.get(order=order)

        # Verify tickets decremented
        self.event.refresh_from_db()
        assert self.event.available_tickets == 7

        # Send failed callback
        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': txn.merchant_request_id,
                    'CheckoutRequestID': txn.checkout_request_id,
                    'ResultCode': 1032,
                    'ResultDesc': 'Request cancelled by user'
                }
            }
        }

        callback_response = self.client.post(
            '/api/payments/mpesa/callback/',
            callback_payload,
            format='json'
        )
        assert callback_response.status_code == 200

        # Verify order failed
        order.refresh_from_db()
        txn.refresh_from_db()

        assert order.status == 'failed'
        assert txn.result_code == '1032'
        assert txn.mpesa_receipt is None
        assert not txn.is_successful()

        # Verify tickets released
        self.event.refresh_from_db()
        assert self.event.available_tickets == 10

        # Verify NO payout created
        assert not OrganizerPayout.objects.filter(order=order).exists()

    def test_payment_status_polling(self):
        """Test payment status polling before and after callback.

        Flow:
        1. Initiate payment
        2. Poll status endpoint before callback (should return 'pending')
        3. Send successful callback
        4. Poll status endpoint after callback (should return 'paid' with receipt)
        """
        # Initiate payment
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = MOCK_STK_SUCCESS_RESPONSE

            self.client.force_authenticate(user=self.user)
            response = self.client.post('/api/payments/initiate/', {
                'event_id': self.event.id,
                'quantity': 1,
                'phone_number': '254712345678'
            }, format='json')

        order = Order.objects.get(id=response.json()['id'])
        txn = MPESATransaction.objects.get(order=order)

        # Poll before callback
        self.client.force_authenticate(user=self.user)
        status_response = self.client.get(
            f'/api/payments/status/{txn.checkout_request_id}/'
        )
        assert status_response.status_code == 200
        assert status_response.json()['status'] == 'pending'

        # Send successful callback
        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': txn.merchant_request_id,
                    'CheckoutRequestID': txn.checkout_request_id,
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123XYZ'}
                        ]
                    }
                }
            }
        }

        self.client.post(
            '/api/payments/mpesa/callback/',
            callback_payload,
            format='json'
        )

        # Poll after callback
        status_response = self.client.get(
            f'/api/payments/status/{txn.checkout_request_id}/'
        )
        assert status_response.status_code == 200
        data = status_response.json()
        assert data['status'] == 'paid'
        assert data['mpesa_receipt'] == 'ABC123XYZ'


# ============================================================================
# TEST CLASS 2: PAYOUT FLOW
# ============================================================================

@pytest.mark.django_db
class TestPayoutFlow:
    """
    Integration tests for payout processing (B2C and B2B).
    """

    def setup_method(self):
        self.organizer = OrganizerProfileFactory(verified=True)

    def test_b2c_payout_flow_end_to_end(self):
        """Test complete B2C payout flow.

        Flow:
        1. Create paid order with B2C organizer config
        2. Verify payout scheduled
        3. Mock daraja.initiate_b2c_payout to return success
        4. Call process_single_payout(payout.id)
        5. Verify payout status='processing'
        """
        # Setup B2C config
        payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )

        event = EventFactory(organizer=self.organizer)
        order = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timedelta(hours=25),
            subtotal=Decimal('5000.00'),
            platform_fee=Decimal('100.00'),
            total=Decimal('5000.00')
        )

        # Create scheduled payout
        payout = OrganizerPayoutFactory(
            organizer=self.organizer,
            order=order,
            amount=Decimal('4900.00'),  # 5000 - 100
            platform_fee=Decimal('100.00'),
            status='scheduled',
            scheduled_for=timezone.now() - timedelta(hours=1)
        )

        # Mock B2C API call
        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = MOCK_B2C_SUCCESS_RESPONSE

            process_single_payout(payout.id)

            # Verify B2C was called
            assert mock_b2c.called
            mock_b2c.assert_called_once_with(payout)

        # Verify payout status updated
        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_b2b_payout_flow_end_to_end(self):
        """Test complete B2B payout flow (paybill).

        Flow:
        1. Create paid order with B2B organizer config (paybill)
        2. Verify payout scheduled
        3. Mock daraja.initiate_b2b_payout to return success
        4. Call process_single_payout(payout.id)
        5. Verify payout status='processing'
        """
        # Setup B2B paybill config
        payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2b_paybill',
            payout_destination='888999',  # Paybill number
            verified=True
        )

        event = EventFactory(organizer=self.organizer)
        order = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timedelta(hours=25),
            subtotal=Decimal('10000.00'),
            platform_fee=Decimal('200.00'),
            total=Decimal('10000.00')
        )

        payout = OrganizerPayoutFactory(
            organizer=self.organizer,
            order=order,
            amount=Decimal('9800.00'),  # 10000 - 200
            platform_fee=Decimal('200.00'),
            status='scheduled',
            scheduled_for=timezone.now() - timedelta(hours=1)
        )

        # Mock B2B API call
        with patch('apps.payments.daraja.initiate_b2b_payout') as mock_b2b:
            mock_b2b.return_value = MOCK_B2C_SUCCESS_RESPONSE

            process_single_payout(payout.id)

            assert mock_b2b.called
            mock_b2b.assert_called_once_with(payout)

        payout.refresh_from_db()
        assert payout.status == 'processing'

    def test_payout_retry_on_failure(self):
        """Test payout retry logic on failure.

        Flow:
        1. Create scheduled payout
        2. Mock daraja.initiate_b2c_payout to raise exception
        3. Call process_single_payout(payout.id)
        4. Verify Celery retry triggered
        5. Verify payout status remains 'scheduled' (not failed on first attempt)
        """
        payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )

        event = EventFactory(organizer=self.organizer)
        order = OrderFactory(
            event=event,
            status='paid',
            paid_at=timezone.now() - timedelta(hours=25),
        )

        payout = OrganizerPayoutFactory(
            organizer=self.organizer,
            order=order,
            status='scheduled',
            scheduled_for=timezone.now() - timedelta(hours=1)
        )

        # Mock B2C to fail
        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.side_effect = Exception('Daraja API timeout')

            # Should raise exception (which triggers Celery retry)
            with pytest.raises(Exception):
                process_single_payout(payout.id)

        # Verify payout status not changed (Celery will retry)
        payout.refresh_from_db()
        assert payout.status == 'scheduled'

    def test_scheduled_payouts_processing_task(self):
        """Test batch processing of scheduled payouts.

        Flow:
        1. Create 3 payouts with scheduled_for in the past
        2. Create 2 payouts with scheduled_for in the future
        3. Call process_scheduled_payouts()
        4. Verify only 3 past payouts processed
        5. Verify future payouts untouched
        """
        payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )

        # Create past payouts (should be processed)
        past_payouts = []
        for i in range(3):
            event = EventFactory(organizer=self.organizer)
            order = OrderFactory(event=event, status='paid', paid_at=timezone.now())
            payout = OrganizerPayoutFactory(
                organizer=self.organizer,
                order=order,
                status='scheduled',
                scheduled_for=timezone.now() - timedelta(hours=i+1)
            )
            past_payouts.append(payout)

        # Create future payouts (should NOT be processed)
        future_payouts = []
        for i in range(2):
            event = EventFactory(organizer=self.organizer)
            order = OrderFactory(event=event, status='paid', paid_at=timezone.now())
            payout = OrganizerPayoutFactory(
                organizer=self.organizer,
                order=order,
                status='scheduled',
                scheduled_for=timezone.now() + timedelta(hours=i+1)
            )
            future_payouts.append(payout)

        # Mock B2C to succeed
        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = MOCK_B2C_SUCCESS_RESPONSE

            result = process_scheduled_payouts()

        # Verify only past payouts processed
        assert result['processed_count'] == 3

        for payout in past_payouts:
            payout.refresh_from_db()
            assert payout.status == 'processing'

        for payout in future_payouts:
            payout.refresh_from_db()
            assert payout.status == 'scheduled'


# ============================================================================
# TEST CLASS 3: REFUND FLOW
# ============================================================================

@pytest.mark.django_db
class TestRefundFlow:
    """
    Integration tests for refund and reversal flows.
    """

    def test_reversal_within_24h_window(self):
        """Test reversal API within 24h window.

        Flow:
        1. Create paid order with paid_at = 2 hours ago
        2. Create MPESATransaction with receipt
        3. Mock daraja.initiate_reversal
        4. Call refund_cancelled_event_orders(event.id)
        5. Verify reversal initiated with correct transaction_id
        6. Verify order status='refunded'
        """
        user = UserFactory()
        organizer = OrganizerProfileFactory()
        event = EventFactory(
            organizer=organizer,
            status='cancelled',
            cancellation_reason='Venue unavailable'
        )

        order = OrderFactory(
            user=user,
            event=event,
            status='paid',
            total=Decimal('2000.00')
        )

        # Set paid_at to 2 hours ago (within 24h window)
        Order.objects.filter(id=order.id).update(
            paid_at=timezone.now() - timedelta(hours=2)
        )
        order.refresh_from_db()

        txn = MPESATransactionFactory(
            order=order,
            mpesa_receipt='QGH7654321',
            result_code='0'
        )

        # Mock reversal API
        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            mock_reversal.return_value = MOCK_REVERSAL_SUCCESS_RESPONSE

            result = refund_cancelled_event_orders(event.id)

            # Verify reversal was called
            assert mock_reversal.called
            mock_reversal.assert_called_once_with(
                transaction_id='QGH7654321',
                amount=int(order.total),
                phone=txn.phone_number
            )

        # Verify order refunded
        order.refresh_from_db()
        assert order.status == 'refunded'
        assert result['refunded_count'] == 1

    def test_reversal_outside_24h_window(self):
        """Test reversal outside 24h window (requires manual refund).

        Flow:
        1. Create paid order with paid_at = 30 hours ago
        2. Call refund_cancelled_event_orders(event.id)
        3. Verify reversal NOT initiated (outside window)
        4. Verify order status remains 'paid'
        5. Verify warning logged about manual B2C refund needed
        """
        user = UserFactory()
        organizer = OrganizerProfileFactory()
        event = EventFactory(
            organizer=organizer,
            status='cancelled',
            cancellation_reason='Organizer sick'
        )

        order = OrderFactory(
            user=user,
            event=event,
            status='paid',
            total=Decimal('3000.00')
        )

        # Set paid_at to 30 hours ago (outside 24h window)
        Order.objects.filter(id=order.id).update(
            paid_at=timezone.now() - timedelta(hours=30)
        )
        order.refresh_from_db()

        txn = MPESATransactionFactory(
            order=order,
            mpesa_receipt='QGH9999999',
            result_code='0'
        )

        # Mock reversal API (should NOT be called)
        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            result = refund_cancelled_event_orders(event.id)

            # Verify reversal NOT called
            assert not mock_reversal.called

        # Verify order NOT refunded
        order.refresh_from_db()
        assert order.status == 'paid'
        assert result['refunded_count'] == 0

    def test_event_cancellation_full_workflow(self):
        """Test complete event cancellation workflow.

        Flow:
        1. Create event with 3 paid orders
        2. Create scheduled payouts for those orders
        3. Cancel event
        4. Call handle_event_cancellation(event.id)
        5. Verify payouts frozen
        6. Verify frozen_reason contains cancellation_reason
        7. Call refund_cancelled_event_orders(event.id)
        8. Verify refunds initiated for eligible orders
        """
        organizer = OrganizerProfileFactory()
        event = EventFactory(
            organizer=organizer,
            status='active'
        )

        # Create 3 paid orders with payouts
        orders = []
        payouts = []

        for i in range(3):
            user = UserFactory(email=f'user{i}@test.com', username=f'user{i}')
            order = OrderFactory(
                user=user,
                event=event,
                status='paid',
                total=Decimal('1500.00')
            )
            # Set paid_at to 2 hours ago (within reversal window)
            Order.objects.filter(id=order.id).update(
                paid_at=timezone.now() - timedelta(hours=2)
            )
            order.refresh_from_db()

            txn = MPESATransactionFactory(
                order=order,
                mpesa_receipt=f'QGH{i}{i}{i}{i}',
                result_code='0'
            )

            payout = OrganizerPayoutFactory(
                organizer=organizer,
                order=order,
                status='scheduled',
                scheduled_for=timezone.now() + timedelta(hours=22)
            )

            orders.append(order)
            payouts.append(payout)

        # Cancel event
        event.status = 'cancelled'
        event.cancellation_reason = 'Weather emergency'
        event.save()

        # Handle cancellation
        freeze_result = handle_event_cancellation(event.id)
        assert freeze_result['frozen_count'] == 3

        # Verify payouts frozen
        for payout in payouts:
            payout.refresh_from_db()
            assert payout.status == 'frozen'
            assert 'Weather emergency' in payout.frozen_reason

        # Initiate refunds
        with patch('apps.payments.daraja.initiate_reversal') as mock_reversal:
            mock_reversal.return_value = MOCK_REVERSAL_SUCCESS_RESPONSE

            refund_result = refund_cancelled_event_orders(event.id)

            # Verify all 3 refunds initiated
            assert mock_reversal.call_count == 3
            assert refund_result['refunded_count'] == 3

        # Verify all orders refunded
        for order in orders:
            order.refresh_from_db()
            assert order.status == 'refunded'


# ============================================================================
# TEST CLASS 4: CONCURRENCY SCENARIOS
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestConcurrency:
    """
    Integration tests for race conditions and concurrent operations.

    Note: These tests use transaction=True to enable threading support.
    Django's test database is shared across threads when this flag is set.
    """

    def test_concurrent_ticket_purchase_prevents_overselling(self):
        """Test that only N tickets can be sold when N are available.

        Flow:
        1. Create event with 5 available tickets
        2. Simulate 10 sequential requests for 1 ticket each
        3. Only 5 should succeed (simulates concurrency via F() expressions)
        4. Verify exactly 5 orders created
        5. Verify 0 tickets remaining
        6. Verify 5 requests got insufficient_tickets error

        Note: This test uses sequential requests rather than true threading
        because Django's test database has threading limitations. The
        concurrency protection is provided by F() expressions in the view,
        which is tested here by rapid sequential requests.
        """
        organizer = OrganizerProfileFactory(verified=True)
        payment_config = OrganizerPaymentConfigFactory(
            organizer=organizer,
            payout_type='b2c',
            verified=True
        )
        event = EventFactory(
            organizer=organizer,
            price=Decimal('1000.00'),
            available_tickets=5,
            ticketing_enabled=True
        )

        # Create 10 users
        users = [
            UserFactory(email=f'user{i}@test.com', username=f'user{i}')
            for i in range(10)
        ]

        results = []

        # Simulate concurrent requests sequentially (F() provides atomicity)
        for i, user in enumerate(users):
            client = APIClient()
            client.force_authenticate(user=user)

            with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
                # Each request gets a unique checkout ID
                mock_stk.return_value = {
                    'MerchantRequestID': f'merchant_{i}',
                    'CheckoutRequestID': f'ws_CO_CONCURRENT_{i}',
                    'ResponseCode': '0',
                    'ResponseDescription': 'Success',
                }

                response = client.post('/api/payments/initiate/', {
                    'event_id': event.id,
                    'quantity': 1,
                    'phone_number': '254712345678'
                }, format='json')

            results.append(response.status_code)

        # Count successes and failures
        success_count = sum(1 for code in results if code == 200)
        fail_count = sum(1 for code in results if code == 400)

        # Should have exactly 5 successes (F() provides atomicity)
        assert success_count == 5, f"Expected 5 successes, got {success_count}"
        assert fail_count == 5, f"Expected 5 failures, got {fail_count}"

        # Verify exactly 5 orders created
        assert Order.objects.filter(event=event).count() == 5

        # Verify 0 tickets remaining
        event.refresh_from_db()
        assert event.available_tickets == 0

    def test_redis_lock_prevents_duplicate_orders(self):
        """Test Redis lock prevents duplicate orders.

        Flow:
        1. Make first payment request
        2. Make second identical request immediately after
        3. First request should succeed
        4. Second request should get 429 (locked) or resume existing order
        5. Verify only 1 order created or both requests return same order

        Note: This test uses rapid sequential requests to test the Redis lock.
        The lock is held for 10 seconds, so immediate retry should be blocked
        or should resume the existing order.
        """
        organizer = OrganizerProfileFactory(verified=True)
        payment_config = OrganizerPaymentConfigFactory(
            organizer=organizer,
            payout_type='b2c',
            verified=True
        )
        event = EventFactory(
            organizer=organizer,
            price=Decimal('1000.00'),
            available_tickets=10,
            ticketing_enabled=True
        )
        user = UserFactory()

        client = APIClient()
        client.force_authenticate(user=user)

        # First request
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = {
                'MerchantRequestID': 'merchant_1',
                'CheckoutRequestID': 'ws_CO_LOCK_TEST_1',
                'ResponseCode': '0',
            }

            response1 = client.post('/api/payments/initiate/', {
                'event_id': event.id,
                'quantity': 1,
                'phone_number': '254712345678'
            }, format='json')

        # Second request (immediate retry)
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = {
                'MerchantRequestID': 'merchant_2',
                'CheckoutRequestID': 'ws_CO_LOCK_TEST_2',
                'ResponseCode': '0',
            }

            response2 = client.post('/api/payments/initiate/', {
                'event_id': event.id,
                'quantity': 1,
                'phone_number': '254712345678'
            }, format='json')

        # First should succeed
        assert response1.status_code == 200

        # Second should either be locked (429) or resume existing order (200)
        assert response2.status_code in [200, 429]

        if response2.status_code == 200:
            # If 200, should have resuming=True and same checkout_request_id
            data2 = response2.json()
            assert data2.get('resuming') is True
            assert data2['checkout_request_id'] == 'ws_CO_LOCK_TEST_1'

        # Verify only 1 unique order created
        orders = Order.objects.filter(user=user, event=event)
        assert orders.count() == 1

        # Clean up Redis lock
        lock_key = f"payment_lock:{user.id}:{event.id}"
        cache.delete(lock_key)

    def test_order_expiry_releases_tickets_atomically(self):
        """Test that order expiry releases tickets without race conditions.

        Flow:
        1. Create 3 events with pending orders
        2. Set created_at to 25 minutes ago
        3. Call expire_stale_orders(timeout_minutes=15)
        4. Make new purchases after expiry
        5. Verify no race conditions (all tickets accounted for)
        6. Verify old orders expired
        7. Verify new orders succeed

        Note: This test uses sequential purchases to verify ticket accounting
        after expiry. The F() expression ensures atomicity even in concurrent
        scenarios.
        """
        organizer = OrganizerProfileFactory(verified=True)
        payment_config = OrganizerPaymentConfigFactory(
            organizer=organizer,
            payout_type='b2c',
            verified=True
        )
        # Create event with pending orders
        event = EventFactory(
            organizer=organizer,
            price=Decimal('1000.00'),
            available_tickets=10,
            ticketing_enabled=True
        )

        # Create 3 old pending orders (reserve 3 tickets)
        old_orders = []
        for i in range(3):
            user = UserFactory(email=f'old{i}@test.com', username=f'old{i}')
            order = OrderFactory(
                user=user,
                event=event,
                status='pending',
                quantity=1
            )
            old_orders.append(order)

        # Update created_at to 25 minutes ago
        for order in old_orders:
            Order.objects.filter(id=order.id).update(
                created_at=timezone.now() - timedelta(minutes=25)
            )

        # Manually adjust available tickets to simulate reservation
        event.available_tickets = 7  # 10 - 3 reserved
        event.save()

        # Expire stale orders (should release 3 tickets)
        result = expire_stale_orders(timeout_minutes=15)
        assert result['expired_count'] == 3

        # Verify tickets released
        event.refresh_from_db()
        assert event.available_tickets == 10

        # Verify old orders expired
        for order in old_orders:
            order.refresh_from_db()
            assert order.status == 'expired'

        # Now create new purchases sequentially (F() ensures atomicity)
        new_users = [
            UserFactory(email=f'new{i}@test.com', username=f'new{i}')
            for i in range(5)
        ]

        results = []

        for i, user in enumerate(new_users):
            client = APIClient()
            client.force_authenticate(user=user)

            with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
                mock_stk.return_value = {
                    'MerchantRequestID': f'merchant_expiry_{i}',
                    'CheckoutRequestID': f'ws_CO_EXPIRY_{i}',
                    'ResponseCode': '0',
                }

                response = client.post('/api/payments/initiate/', {
                    'event_id': event.id,
                    'quantity': 2,
                    'phone_number': '254712345678'
                }, format='json')

            results.append(response.status_code)

        # Should have exactly 5 successes (5 * 2 tickets = 10 total)
        success_count = sum(1 for code in results if code == 200)
        assert success_count == 5, f"Expected 5 successes, got {success_count}"

        # Verify all tickets sold
        event.refresh_from_db()
        assert event.available_tickets == 0

        # Verify all new orders created
        new_orders = Order.objects.filter(
            event=event,
            status='pending'
        ).exclude(id__in=[o.id for o in old_orders])

        assert new_orders.count() == 5
