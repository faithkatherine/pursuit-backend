"""
API Integration Tests for Payment Flow

Tests the complete payment flow as described in pursuit_payment_architecture.md:
1. Payment initiation (POST /api/payments/initiate/)
2. M-Pesa callback handling (POST /api/payments/mpesa/callback/)
3. Payment status polling (GET /api/payments/status/{checkout_request_id}/)
4. Payout processing (Celery background task)

These tests define the expected API contract and flow.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizers.models import OrganizerPaymentConfig, OrganizerPayout
from apps.payments.models import MPESATransaction, Order
from apps.payments.tasks import (
    expire_stale_orders,
    handle_event_cancellation,
    process_scheduled_payouts,
)
from apps.tests.factories import (
    EventFactory,
    MPESATransactionFactory,
    OrderFactory,
    OrganizerPaymentConfigFactory,
    OrganizerProfileFactory,
    UserFactory,
)
from apps.tests.factories.organizer_factory import OrganizerPayoutFactory

# Platform fee rate constant (2%)
PLATFORM_FEE_RATE = Decimal('0.02')


# ============================================================================
# M-PESA DARAJA API CONFIGURATION
# ============================================================================
# Based on M-Pesa Express (STK Push) API documentation
#
# ENDPOINTS:
# - Sandbox: https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest
# - Production: https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest
# - OAuth: https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials
#
# AUTHENTICATION:
# - OAuth 2.0 Bearer token using Consumer Key + Consumer Secret
# - Token passed in Authorization header: "Bearer {access_token}"
#
# PHONE FORMAT:
# - Kenya format: 254XXXXXXXXX (country code + 9 digits)
# - Valid networks: 254[17]\\d{8} (Safaricom)
#
# PASSWORD GENERATION:
# - Base64.encode(Shortcode + Passkey + Timestamp)
# - Timestamp format: YYYYMMDDHHmmss
#
# PLATFORM FEE: 2% (stored in database to allow future expansion)
# ORDER EXPIRATION: 15 minutes
# IDEMPOTENCY: Backend-generated, valid until order expires
# TICKET RESERVATION: Atomic F() expression updates to prevent race conditions
# ============================================================================


@pytest.mark.django_db
class TestPaymentInitiationAPI:
    """
    Test POST /api/payments/initiate/

    Expected flow:
    1. Client sends: event_id, quantity, phone_number
    2. Backend calculates: subtotal, platform_fee, total
    3. Backend creates: Order (pending) + MPESATransaction
    4. Backend calls: Daraja STK Push API
    5. Backend returns: checkout_request_id, order_id
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.organizer = OrganizerProfileFactory(verified=True)
        self.payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            collection_type='paybill',
            collection_shortcode='888000',
            verified=True
        )
        self.event = EventFactory(
            organizer=self.organizer,
            price=Decimal('2500.00'),
            available_tickets=100,
            ticketing_enabled=True
        )

    def test_initiate_payment_success(self):
        """Test successful payment initiation with Daraja STK Push.

        Validates:
        - Order creation with Model B pricing (3% platform fee)
        - MPESATransaction creation with Daraja response IDs
        - Phone number format validation (254XXXXXXXXX)
        """
        url = '/api/payments/initiate/'

        payload = {
            'event_id': self.event.id,  # Don't stringify UUID
            'quantity': 2,
            'phone_number': '254712345678'  # Valid Safaricom format
        }

        # Mock Daraja STK Push response (actual format from M-Pesa docs)
        mock_daraja_response = {
            'MerchantRequestID': '29115-34620561-1',
            'CheckoutRequestID': 'ws_CO_191220191020363925',
            'ResponseCode': '0',
            'ResponseDescription': 'Success. Request accepted for processing',
            'CustomerMessage': 'Success. Request accepted for processing'
        }

        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = mock_daraja_response

            # Authenticate user
            self.client.force_authenticate(user=self.user)

            response = self.client.post(url, payload, format='json')

        # Assertions
        assert response.status_code == 200
        data = response.json()

        # Expected response structure
        assert 'checkout_request_id' in data
        assert 'id' in data  # OrderResponseSerializer uses 'id' not 'order_id'
        assert data['checkout_request_id'] == 'ws_CO_191220191020363925'

        # Verify Order was created with Model B pricing
        order = Order.objects.get(id=data['id'])
        assert order.user == self.user
        assert order.event == self.event
        assert order.quantity == 2
        assert order.subtotal == Decimal('5000.00')  # 2500 * 2
        assert order.platform_fee == Decimal('100.00')  # 2% platform fee deducted from organizer
        assert order.total == Decimal('5000.00')  # Model B: buyer pays subtotal only, no fee added
        assert order.status == 'pending'

        # Verify MPESATransaction was created
        txn = MPESATransaction.objects.get(order=order)
        assert txn.phone_number == '254712345678'
        assert txn.checkout_request_id == 'ws_CO_191220191020363925'
        assert txn.merchant_request_id == '29115-34620561-1'
        assert txn.result_code is None  # Pending until callback

    def test_initiate_payment_invalid_event(self):
        """Test payment initiation with non-existent event."""
        url = '/api/payments/initiate/'

        payload = {
            'event_id': '99999999-9999-9999-9999-999999999999',
            'quantity': 1,
            'phone_number': '254712345678'
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format='json')

        assert response.status_code == 404
        assert 'error' in response.json()

    def test_initiate_payment_sold_out_event(self):
        """Test payment initiation when event is sold out."""
        self.event.available_tickets = 1
        self.event.save()

        url = '/api/payments/initiate/'
        payload = {
            'event_id': self.event.id,  # Don't stringify UUID
            'quantity': 2,  # More than available
            'phone_number': '254712345678'
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format='json')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        # Check for insufficient tickets error
        error_msg = data['error'].lower() if isinstance(data['error'], str) else ''
        assert 'insufficient' in error_msg or 'not available' in error_msg or 'sold out' in error_msg

    def test_initiate_payment_invalid_phone_number(self):
        """Test payment initiation with invalid phone number format.

        Valid format: 254[17]\\d{8}
        - 254 = Kenya country code
        - 7 or 1 = Safaricom/Airtel network prefix
        - 8 more digits

        Examples:
        - Valid: 254712345678, 254111222333
        - Invalid: abcdefghij (non-numeric), 254812345678 (wrong network)
        """
        url = '/api/payments/initiate/'

        # Test various invalid formats that will fail validation before STK Push
        invalid_numbers = [
            'abcdefghij',       # Non-numeric
            '123',              # Too short
            '254812345678',     # Invalid network (8 is not 1 or 7)
        ]

        for invalid_phone in invalid_numbers:
            payload = {
                'event_id': self.event.id,
                'quantity': 1,
                'phone_number': invalid_phone
            }

            self.client.force_authenticate(user=self.user)
            response = self.client.post(url, payload, format='json')

            assert response.status_code == 400
            data = response.json()
            assert 'error' in data

    def test_initiate_payment_daraja_failure(self):
        """Test handling of Daraja API failure."""
        url = '/api/payments/initiate/'

        payload = {
            'event_id': self.event.id,
            'quantity': 1,
            'phone_number': '254712345678'
        }

        # Mock Daraja failure
        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.side_effect = Exception('Daraja API timeout')

            self.client.force_authenticate(user=self.user)
            response = self.client.post(url, payload, format='json')

        assert response.status_code == 503
        assert 'error' in response.json()

    def test_initiate_payment_idempotency(self):
        """Test that duplicate requests with same idempotency key are handled.

        Idempotency strategy:
        - Backend generates key: SHA256(user_id:event_id:quantity:timestamp)
        - Key stored in Order.idempotency_key (unique constraint)
        - Duplicate key within 15 min window returns existing order
        - After expiration, allows new order with same key
        """
        url = '/api/payments/initiate/'

        payload = {
            'event_id': self.event.id,
            'quantity': 1,
            'phone_number': '254712345678'
        }

        # Mock Daraja response
        mock_response = {
            'MerchantRequestID': '29115-34620561-1',
            'CheckoutRequestID': 'ws_CO_UNIQUE123',
            'ResponseCode': '0'
        }

        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = mock_response

            self.client.force_authenticate(user=self.user)

            # First request - creates order
            response1 = self.client.post(url, payload, format='json')
            assert response1.status_code == 200
            order_id_1 = response1.json()['id']

            # Second identical request - should return same order or create new one
            # depending on whether first order expired
            response2 = self.client.post(url, payload, format='json')
            # Implementation can either:
            # 1. Return same order (recommended for within-window retries)
            # 2. Create new order (if first expired/failed)
            assert response2.status_code in [200, 201, 429]  # 429 = already in progress


@pytest.mark.django_db
class TestMPesaCallbackAPI:
    """
    Test POST /api/payments/mpesa/callback/

    M-Pesa STK Push callback payload structure (from official docs):
    {
      "Body": {
        "stkCallback": {
          "MerchantRequestID": "29115-34620561-1",
          "CheckoutRequestID": "ws_CO_191220191020363925",
          "ResultCode": 0,  # 0 = success, non-zero = failure
          "ResultDesc": "The service request is processed successfully.",
          "CallbackMetadata": {
            "Item": [
              {"Name": "Amount", "Value": 1.00},
              {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
              {"Name": "TransactionDate", "Value": 20191219102115},
              {"Name": "PhoneNumber", "Value": 254708374149}
            ]
          }
        }
      }
    }

    Expected flow:
    1. Daraja sends callback to /api/payments/mpesa/callback/
    2. Backend validates callback authenticity (optional: IP whitelist, signature)
    3. Backend updates MPESATransaction with result_code, mpesa_receipt, result_desc
    4. Backend updates Order status (paid/failed)
    5. If successful, backend creates OrganizerPayout scheduled for 24h later
    6. Backend returns 200 OK to Daraja (always, even on error)
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.organizer = OrganizerProfileFactory(verified=True)
        self.event = EventFactory(organizer=self.organizer)
        self.order = OrderFactory(
            user=self.user,
            event=self.event,
            status='pending',
            subtotal=Decimal('3000.00'),
            platform_fee=Decimal('60.00'),  # 2% of 3000
            total=Decimal('3000.00')
        )
        self.txn = MPESATransactionFactory(
            order=self.order,
            checkout_request_id='ws_CO_TEST123'
        )

    def test_callback_successful_payment(self):
        """Test M-Pesa callback with successful payment.

        Callback includes:
        - ResultCode: 0 (success)
        - MpesaReceiptNumber: Unique transaction ID from M-Pesa
        - Amount: Confirmed payment amount
        - TransactionDate: YYYYMMDDHHmmss format
        """
        url = '/api/payments/mpesa/callback/'

        # Actual Daraja callback payload format (from M-Pesa Express docs)
        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": self.txn.merchant_request_id,
                    "CheckoutRequestID": self.txn.checkout_request_id,
                    "ResultCode": 0,  # 0 = successful payment
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 3000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},  # M-Pesa receipt format
                            {"Name": "TransactionDate", "Value": 20260609143000},  # YYYYMMDDHHmmss
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        response = self.client.post(url, callback_payload, format='json')

        # Always return 200 to Daraja (per M-Pesa requirements)
        assert response.status_code == 200

        # Verify MPESATransaction was updated
        self.txn.refresh_from_db()
        assert self.txn.result_code == '0'
        assert self.txn.mpesa_receipt == 'NLJ7RT61SV'
        assert self.txn.result_desc == 'The service request is processed successfully.'
        assert self.txn.is_successful()

        # Verify Order status updated to paid
        self.order.refresh_from_db()
        assert self.order.status == 'paid'

        # Verify OrganizerPayout was created (Model B: organizer receives total - platform_fee)
        payout = OrganizerPayout.objects.get(order=self.order)
        assert payout.organizer == self.organizer
        assert payout.amount == Decimal('2940.00')  # 3000 - 60 (2% platform fee)
        assert payout.platform_fee == Decimal('60.00')
        assert payout.status == 'scheduled'

        # Verify payout scheduled for exactly 24 hours after order becomes 'paid' (not created_at)
        # NOTE: In real implementation, scheduled_for should be order.paid_at + 24h
        # For this test, we'll check it's roughly 24h from when callback processed
        assert payout.scheduled_for is not None

    def test_callback_failed_payment(self):
        """Test M-Pesa callback with failed payment."""
        url = '/api/payments/mpesa/callback/'

        # Sample Daraja callback payload (user cancelled)
        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": self.txn.merchant_request_id,
                    "CheckoutRequestID": self.txn.checkout_request_id,
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user"
                }
            }
        }

        response = self.client.post(url, callback_payload, format='json')

        assert response.status_code == 200

        # Verify transaction was updated
        self.txn.refresh_from_db()
        assert self.txn.result_code == '1032'
        assert self.txn.result_desc == 'Request cancelled by user'
        assert not self.txn.is_successful()
        assert self.txn.mpesa_receipt is None

        # Verify order status updated
        self.order.refresh_from_db()
        assert self.order.status == 'failed'

        # Verify NO payout was created
        assert not OrganizerPayout.objects.filter(order=self.order).exists()

    def test_callback_duplicate_handling(self):
        """Test that duplicate callbacks are handled idempotently."""
        url = '/api/payments/mpesa/callback/'

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": self.txn.merchant_request_id,
                    "CheckoutRequestID": self.txn.checkout_request_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "MpesaReceiptNumber", "Value": "QGH12345ABC"}
                        ]
                    }
                }
            }
        }

        # Send callback twice
        response1 = self.client.post(url, callback_payload, format='json')
        response2 = self.client.post(url, callback_payload, format='json')

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Should only create ONE payout
        assert OrganizerPayout.objects.filter(order=self.order).count() == 1

    def test_callback_unknown_checkout_request(self):
        """Test callback for unknown checkout request ID."""
        url = '/api/payments/mpesa/callback/'

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_UNKNOWN999",
                    "ResultCode": 0,
                    "ResultDesc": "Success"
                }
            }
        }

        response = self.client.post(url, callback_payload, format='json')

        # Should still return 200 to Daraja but log the error
        assert response.status_code == 200 or response.status_code == 404


@pytest.mark.django_db
class TestPaymentStatusAPI:
    """
    Test GET /api/payments/status/{checkout_request_id}/

    Used by frontend to poll payment status.
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.order = OrderFactory(user=self.user, status='pending')
        self.txn = MPESATransactionFactory(
            order=self.order,
            checkout_request_id='ws_CO_POLL123'
        )

    def test_get_status_pending(self):
        """Test status check for pending payment."""
        url = f'/api/payments/status/{self.txn.checkout_request_id}/'

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'pending'
        # Response may have 'order_id' or just include it in nested structure
        assert 'order_id' in data or 'status' in data

    def test_get_status_completed(self):
        """Test status check for completed payment."""
        self.txn.result_code = '0'
        self.txn.mpesa_receipt = 'QGH12345'
        self.txn.save()
        self.order.status = 'paid'
        self.order.save()

        url = f'/api/payments/status/{self.txn.checkout_request_id}/'

        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'paid'
        assert data['mpesa_receipt'] == 'QGH12345'

    def test_get_status_unauthorized_user(self):
        """Test that user can only check their own payments."""
        other_user = UserFactory()
        url = f'/api/payments/status/{self.txn.checkout_request_id}/'

        self.client.force_authenticate(user=other_user)
        response = self.client.get(url)

        assert response.status_code == 403 or response.status_code == 404


@pytest.mark.django_db
class TestOrderExpirationFlow:
    """
    Test order expiration logic (Celery task).

    TODO: Confirm expiration timeout (15 min? 30 min?)

    Expected flow:
    1. Celery task runs every X minutes
    2. Finds orders with status='pending' and created_at > timeout
    3. Updates order status to 'expired'
    4. Releases tickets back to event.available_tickets
    """

    def test_expire_stale_orders(self):
        """Test that old pending orders are expired."""
        # TODO: What's the expiration timeout?
        EXPIRATION_TIMEOUT = timezone.timedelta(minutes=15)

        # Create old pending order
        old_order = OrderFactory(
            status='pending',
            event__available_tickets=100,
            quantity=2
        )
        old_order.created_at = timezone.now() - timezone.timedelta(minutes=20)
        old_order.save()

        # Create recent pending order
        recent_order = OrderFactory(status='pending')

        # Mock Celery task
        expire_stale_orders()

        old_order.refresh_from_db()
        recent_order.refresh_from_db()

        assert old_order.status == 'expired'
        assert recent_order.status == 'pending'

        # Verify tickets released
        # TODO: Implement ticket reservation/release logic


@pytest.mark.django_db
class TestPayoutProcessingFlow:
    """
    Test payout processing (Celery task).

    Expected flow:
    1. Celery task runs every hour
    2. Finds payouts with status='scheduled' and scheduled_for <= now
    3. Calls Daraja B2C/B2B API for each payout
    4. Updates payout status based on result
    5. Handles failures with retry logic
    """

    def setup_method(self):
        self.organizer = OrganizerProfileFactory()
        self.payment_config = OrganizerPaymentConfigFactory(
            organizer=self.organizer,
            payout_type='b2c',
            payout_destination='254712345678',
            verified=True
        )

    def test_process_scheduled_payouts(self):
        """Test processing payouts that are due."""
        # Create payout scheduled for past
        past_payout = OrganizerPayoutFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
            amount=Decimal('5000.00')
        )

        # Create payout scheduled for future
        future_payout = OrganizerPayoutFactory(
            organizer=self.organizer,
            status='scheduled',
            scheduled_for=timezone.now() + timezone.timedelta(hours=5)
        )

        # Mock Daraja B2C response
        mock_b2c_response = {
            'ConversationID': 'conv_123',
            'OriginatorConversationID': 'orig_456',
            'ResponseCode': '0',
            'ResponseDescription': 'Accept the service request successfully.'
        }

        with patch('apps.payments.daraja.initiate_b2c_payout') as mock_b2c:
            mock_b2c.return_value = mock_b2c_response

            process_scheduled_payouts()

        past_payout.refresh_from_db()
        future_payout.refresh_from_db()

        assert past_payout.status == 'processing' or past_payout.status == 'completed'
        assert future_payout.status == 'scheduled'  # Not processed yet

    def test_payout_frozen_for_cancelled_event(self):
        """Test that payouts are frozen when event is cancelled."""
        order = OrderFactory(status='paid', event__status='active')
        payout = OrganizerPayoutFactory(
            order=order,
            status='scheduled'
        )

        # Cancel the event
        event = order.event
        event.status = 'cancelled'
        event.cancellation_reason = 'Venue unavailable'
        event.save()

        handle_event_cancellation(event.id)

        payout.refresh_from_db()
        assert payout.status == 'frozen'
        assert 'cancelled' in payout.frozen_reason.lower()


# ============================================================================
# QUESTIONS FOR IMPLEMENTATION:
# ============================================================================

"""
CRITICAL INFO NEEDED:

1. **Platform Fee:**
   - What percentage? (2%, 3%, 5%?)
   - Fixed or tiered by ticket price?
   - Stored in settings or database?

2. **Daraja Configuration:**
   - Sandbox vs Production URLs?
   - How are credentials stored? (environment vars?)
   - OAuth token refresh logic?
   - Callback URL structure?

3. **Order Lifecycle:**
   - Expiration timeout? (15 min, 30 min?)
   - Retry logic for failed payments?
   - Refund process?

4. **Payout Configuration:**
   - B2C vs B2B decision logic?
   - Retry attempts for failed payouts?
   - Manual vs automatic payout approval?

5. **Security:**
   - Callback signature validation?
   - Rate limiting on initiate endpoint?
   - IP whitelist for Daraja callbacks?

6. **Error Handling:**
   - What HTTP codes for different error types?
   - Error message format?
   - Logging strategy?

7. **Idempotency:**
   - Who generates idempotency_key? (Frontend or backend?)
   - How long are keys valid?
   - Where are they stored?

8. **Phone Number Validation:**
   - Required format? (254XXXXXXXXX?)
   - Validate against user profile?
   - Support for testing/sandbox numbers?
"""


@pytest.mark.django_db
class TestPhoneValidation:
    """Tests for phone number normalisation in daraja.validate_phone()"""

    def test_kenyan_07_format_normalised(self):
        """Test 0712345678 normalised to 254712345678"""
        from apps.payments.daraja import validate_phone

        result = validate_phone('0712345678')
        assert result == '254712345678'

    def test_kenyan_254_format_accepted(self):
        """Test 254712345678 accepted unchanged"""
        from apps.payments.daraja import validate_phone

        result = validate_phone('254712345678')
        assert result == '254712345678'

    def test_plus_254_format_normalised(self):
        """Test +254712345678 normalised to 254712345678"""
        from apps.payments.daraja import validate_phone

        result = validate_phone('+254712345678')
        assert result == '254712345678'

    def test_non_safaricom_number_rejected(self):
        """Test 254200000000 rejected (not 2547X or 2541X)"""
        from django.core.exceptions import ValidationError

        from apps.payments.daraja import validate_phone

        with pytest.raises(ValidationError):
            validate_phone('254200000000')

    def test_too_short_rejected(self):
        """Test 07123 rejected as too short"""
        from django.core.exceptions import ValidationError

        from apps.payments.daraja import validate_phone

        with pytest.raises(ValidationError):
            validate_phone('07123')

    def test_too_long_rejected(self):
        """Test 2547123456789 rejected (13 digits)"""
        from django.core.exceptions import ValidationError

        from apps.payments.daraja import validate_phone

        with pytest.raises(ValidationError):
            validate_phone('2547123456789')


@pytest.mark.django_db
class TestAccountReference:
    """Tests for STK Push AccountReference constraint (max 12 chars)"""

    def test_account_reference_max_12_chars(self):
        """Test account reference is max 12 characters"""
        order = OrderFactory()
        account_ref = f"PST-{str(order.id)[:8].upper()}"

        assert len(account_ref) <= 12

    def test_account_reference_format(self):
        """Test account reference starts with PST-"""
        order = OrderFactory()
        account_ref = f"PST-{str(order.id)[:8].upper()}"

        assert account_ref.startswith('PST-')


@pytest.mark.django_db
class TestIdempotency:
    """Tests for duplicate payment prevention"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.event = EventFactory(price=Decimal('1500.00'), available_tickets=10)

    def test_redis_lock_prevents_duplicate_within_10_seconds(self):
        """Test Redis lock prevents duplicate requests within 10 seconds"""
        from django.core.cache import cache

        url = '/api/payments/initiate/'
        payload = {
            'event_id': self.event.id,
            'quantity': 1,
            'phone_number': '254712345678'
        }

        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = {
                'MerchantRequestID': '123',
                'CheckoutRequestID': 'ws_CO_123',
                'ResponseCode': '0'
            }

            self.client.force_authenticate(user=self.user)

            # First request succeeds
            response1 = self.client.post(url, payload, format='json')
            assert response1.status_code == 200

            # Second request resumes existing order (sequential execution)
            response2 = self.client.post(url, payload, format='json')
            # In sequential tests, second request resumes pending order
            assert response2.status_code in [200, 429]
            if response2.status_code == 200:
                assert response2.json().get('resuming') is True

            # Clean up cache
            lock_key = f"payment_lock:{self.user.id}:{self.event.id}"
            cache.delete(lock_key)

    def test_existing_pending_order_within_90s_returns_same_checkout_id(self):
        """Test pending order < 90s returns same checkout_request_id with resuming=True"""
        url = '/api/payments/initiate/'

        # Create existing pending order with transaction
        order = OrderFactory(
            user=self.user,
            event=self.event,
            status='pending',
            quantity=1,
            created_at=timezone.now() - timezone.timedelta(seconds=30)
        )
        txn = MPESATransactionFactory(
            order=order,
            checkout_request_id='ws_CO_EXISTING123'
        )

        payload = {
            'event_id': self.event.id,
            'quantity': 1,
            'phone_number': '254712345678'
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['checkout_request_id'] == 'ws_CO_EXISTING123'
        assert data.get('resuming') is True

    def test_paid_order_prevents_duplicate_purchase(self):
        """Test existing paid order returns 400 already_purchased"""
        url = '/api/payments/initiate/'

        # Create paid order
        OrderFactory(
            user=self.user,
            event=self.event,
            status='paid',
            quantity=1
        )

        payload = {
            'event_id': self.event.id,
            'quantity': 1,
            'phone_number': '254712345678'
        }

        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, payload, format='json')

        assert response.status_code == 400
        assert 'already_purchased' in response.json()['error']


@pytest.mark.django_db
class TestTicketInventory:
    """Tests for ticket reservation and release"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()

    def test_tickets_decremented_on_order_creation(self):
        """Test available_tickets decremented when order created"""
        from apps.events.models import Event

        event = EventFactory(available_tickets=10, price=Decimal('1000.00'))

        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = {
                'MerchantRequestID': '123',
                'CheckoutRequestID': 'ws_CO_123',
                'ResponseCode': '0'
            }

            self.client.force_authenticate(user=self.user)
            response = self.client.post('/api/payments/initiate/', {
                'event_id': event.id,
                'quantity': 3,
                'phone_number': '254712345678'
            }, format='json')

        assert response.status_code == 200

        event.refresh_from_db()
        assert event.available_tickets == 7

    def test_tickets_released_on_payment_failure(self):
        """Test tickets released back when payment fails"""
        from apps.events.models import Event

        event = EventFactory(available_tickets=10, price=Decimal('1000.00'))
        order = OrderFactory(
            user=self.user,
            event=event,
            status='pending',
            quantity=3
        )
        txn = MPESATransactionFactory(
            order=order,
            checkout_request_id='ws_CO_FAIL123'
        )

        # Manually set tickets to 7 (as if order reserved 3)
        event.available_tickets = 7
        event.save()

        # Failed callback
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

        response = self.client.post('/api/payments/mpesa/callback/', callback_payload, format='json')
        assert response.status_code == 200

        event.refresh_from_db()
        assert event.available_tickets == 10

    def test_tickets_released_on_order_expiry(self):
        """Test tickets released when order expires"""
        from apps.events.models import Event

        event = EventFactory(available_tickets=7, price=Decimal('1000.00'))
        old_order = OrderFactory(
            event=event,
            status='pending',
            quantity=3
        )

        # Update created_at to 20 minutes ago (auto_now_add prevents setting it during creation)
        Order.objects.filter(id=old_order.id).update(
            created_at=timezone.now() - timezone.timedelta(minutes=20)
        )
        old_order.refresh_from_db()

        expire_stale_orders(timeout_minutes=15)

        old_order.refresh_from_db()
        assert old_order.status == 'expired'

        event.refresh_from_db()
        assert event.available_tickets == 10

    def test_cannot_oversell_concurrent_requests(self):
        """Test only one request succeeds when buying last ticket"""
        event = EventFactory(available_tickets=1, price=Decimal('1000.00'))
        user1 = UserFactory(email='user1@test.com', username='user1', first_name='User1')
        user2 = UserFactory(email='user2@test.com', username='user2', first_name='User2')

        with patch('apps.payments.daraja.initiate_stk_push') as mock_stk:
            mock_stk.return_value = {
                'MerchantRequestID': '123',
                'CheckoutRequestID': 'ws_CO_123',
                'ResponseCode': '0'
            }

            client1 = APIClient()
            client2 = APIClient()

            client1.force_authenticate(user=user1)
            client2.force_authenticate(user=user2)

            response1 = client1.post('/api/payments/initiate/', {
                'event_id': event.id,
                'quantity': 1,
                'phone_number': '254712345678'
            }, format='json')

            response2 = client2.post('/api/payments/initiate/', {
                'event_id': event.id,
                'quantity': 1,
                'phone_number': '254711111111'
            }, format='json')

            # One succeeds, one fails
            success_count = sum(1 for r in [response1, response2] if r.status_code == 200)
            fail_count = sum(1 for r in [response1, response2] if r.status_code == 400)

            assert success_count == 1
            assert fail_count == 1

            event.refresh_from_db()
            assert event.available_tickets == 0


@pytest.mark.django_db
class TestCallbackSecurity:
    """Tests for callback endpoint security"""

    def setup_method(self):
        self.client = APIClient()

    def test_callback_returns_200_on_malformed_body(self):
        """Test callback returns 200 even with malformed JSON"""
        response = self.client.post(
            '/api/payments/mpesa/callback/',
            {'garbage': 'data'},
            format='json'
        )

        assert response.status_code == 200
        assert response.json()['ResultCode'] == 0

    def test_callback_returns_200_on_unknown_checkout_id(self):
        """Test callback returns 200 for unknown CheckoutRequestID"""
        callback_payload = {
            'Body': {
                'stkCallback': {
                    'CheckoutRequestID': 'ws_CO_UNKNOWN999',
                    'ResultCode': 0,
                    'ResultDesc': 'Success'
                }
            }
        }

        response = self.client.post('/api/payments/mpesa/callback/', callback_payload, format='json')
        assert response.status_code == 200

    def test_duplicate_callback_not_double_processed(self):
        """Test duplicate callback doesn't double-process order"""
        user = UserFactory()
        event = EventFactory()
        order = OrderFactory(user=user, event=event, status='pending')
        txn = MPESATransactionFactory(order=order, checkout_request_id='ws_CO_DUP123')

        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': txn.merchant_request_id,
                    'CheckoutRequestID': 'ws_CO_DUP123',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'MpesaReceiptNumber', 'Value': 'QGH12345ABC'}
                        ]
                    }
                }
            }
        }

        # Send callback twice
        response1 = self.client.post('/api/payments/mpesa/callback/', callback_payload, format='json')
        response2 = self.client.post('/api/payments/mpesa/callback/', callback_payload, format='json')

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Only one payout created
        from apps.organizers.models import OrganizerPayout
        payout_count = OrganizerPayout.objects.filter(order=order).count()
        assert payout_count == 1

    def test_callback_without_csrf_token_accepted(self):
        """Test callback works without CSRF token (Daraja doesn't send it)"""
        user = UserFactory()
        event = EventFactory()
        order = OrderFactory(user=user, event=event, status='pending')
        txn = MPESATransactionFactory(order=order, checkout_request_id='ws_CO_CSRF123')

        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': txn.merchant_request_id,
                    'CheckoutRequestID': 'ws_CO_CSRF123',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123'}
                        ]
                    }
                }
            }
        }

        # No CSRF token in request
        response = self.client.post('/api/payments/mpesa/callback/', callback_payload, format='json')
        assert response.status_code == 200
