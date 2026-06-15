"""
Payment API Views

All views use DRF except callbacks (Daraja cannot parse DRF responses).
"""

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.core.models import PlatformConfig
from apps.events.models import Event, TicketTier
from apps.organizers.models import OrganizerPayout
from apps.payments import daraja
from apps.payments.models import MPESATransaction, Order, OrderItem
from apps.payments.serializers import (
    InitiatePaymentSerializer,
    InitiatePayoutSerializer,
    InitiateReversalSerializer,
    OrderResponseSerializer,
    PaymentStatusResponseSerializer,
)
from apps.tickets.models import create_ticket_with_retry

logger = logging.getLogger(__name__)


class PaymentAPIRoot(APIView):
    """
    # Pursuit Payment API

    M-Pesa payment system for event tickets.

    ## Available Endpoints:

    - `POST /api/payments/initiate/` - Initiate STK Push payment
    - `GET /api/payments/status/<checkout_request_id>/` - Check payment status
    - `POST /api/payments/payout/initiate/` - Initiate organizer payout (Admin only)
    - `POST /api/payments/reversal/initiate/` - Initiate transaction reversal (Admin only)

    ## Callback Endpoints (M-Pesa use only):

    - `POST /api/payments/mpesa/callback/` - STK Push callback
    - `POST /api/payments/mpesa/b2c-callback/` - B2C payout callback
    - `POST /api/payments/mpesa/b2b-callback/` - B2B payout callback
    - `POST /api/payments/mpesa/reversal-callback/` - Reversal callback

    ## Authentication:

    - User endpoints require JWT token: `Authorization: Bearer <token>`
    - For testing in browser: Login via Django admin first

    ## Testing:

    See PAYMENT_SYSTEM.md for complete API documentation and test scenarios.
    """
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        return Response({
            'message': 'Pursuit Payment API',
            'endpoints': {
                'initiate_payment': reverse('payments:payment-initiate', request=request, format=format),
                'payment_status': '/api/payments/status/<checkout_request_id>/',
                'initiate_payout': reverse('payments:payout-initiate', request=request, format=format),
                'initiate_reversal': reverse('payments:reversal-initiate', request=request, format=format),
            },
            'docs': 'See PAYMENT_SYSTEM.md for complete documentation'
        })


class InitiatePaymentView(APIView):
    """
    Initiate M-Pesa STK Push payment for event tickets.

    ## Request Body:
    ```json
    {
        "event_id": 1,
        "quantity": 2,
        "phone_number": "254712345678"
    }
    ```

    ## Response (Success):
    ```json
    {
        "id": "abc123",
        "event_id": 1,
        "quantity": 2,
        "subtotal": "2000.00",
        "platform_fee": "40.00",
        "total": "2000.00",
        "status": "pending",
        "checkout_request_id": "ws_CO_123",
        "resuming": false
    }
    ```

    ## Error Codes:
    - `400` - Invalid phone, already purchased, insufficient tickets
    - `429` - Payment already in progress (retry after 10 seconds)
    - `503` - M-Pesa service unavailable

    ## Notes:
    - Phone number must be Kenyan format: 254712345678 or 254112345678
    - Buyer pays ticket price only (Model B pricing)
    - Platform fee (2%) deducted from organizer payout
    - STK Push prompt appears on user's phone within 10 seconds
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InitiatePaymentSerializer,
        responses={
            200: OrderResponseSerializer,
            400: OpenApiResponse(
                description='Invalid phone / sold out / '
                            'already purchased / tier not found'
            ),
            429: OpenApiResponse(
                description='Payment already in progress — '
                            'retry after 10 seconds'
            ),
            503: OpenApiResponse(description='Daraja unavailable'),
        },
        tags=['payments'],
        summary='Initiate M-Pesa STK Push for event tickets',
        description=(
            'Acquires a Redis lock, creates a pending order with '
            'ticket reservations, and fires an STK Push to the '
            'user\'s phone. All money flows to Pursuit\'s shortcode. '
            'Model B pricing: buyer pays face value, platform fee '
            'deducted from organizer payout.'
        )
    )
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        event_id = serializer.validated_data['event_id']
        tiers_data = serializer.validated_data['tiers']
        user = request.user

        # Validate phone number format
        try:
            validated_phone = daraja.validate_phone(phone_number)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Acquire Redis lock to prevent duplicate payments
        lock_key = f"payment_lock:{user.id}:{event_id}"
        lock_acquired = cache.add(lock_key, 'locked', timeout=10)

        if not lock_acquired:
            return Response(
                {'error': 'payment_in_progress'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            # Check for existing order
            existing_order = Order.objects.filter(
                user=user,
                event_id=event_id
            ).order_by('-created_at').first()

            if existing_order:
                if existing_order.status == 'paid':
                    cache.delete(lock_key)
                    return Response(
                        {'error': 'already_purchased'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Resume if pending and recent (< 90 seconds)
                age_seconds = (timezone.now() - existing_order.created_at).total_seconds()
                if existing_order.status == 'pending' and age_seconds < 90:
                    cache.delete(lock_key)

                    # Get existing checkout request ID
                    txn = MPESATransaction.objects.filter(order=existing_order).first()
                    if txn:
                        serializer_context = {
                            'checkout_request_id': txn.checkout_request_id,
                            'resuming': True
                        }
                        response_data = OrderResponseSerializer(
                            existing_order,
                            context=serializer_context
                        ).data
                        return Response(response_data)

                # Expire old pending order
                if existing_order.status == 'pending' and age_seconds >= 90:
                    existing_order.status = 'expired'
                    existing_order.save()

                    # Release tickets atomically (tier-aware)
                    for item in existing_order.items.select_related('tier').all():
                        TicketTier.objects.filter(id=item.tier_id).update(
                            available=F('available') + item.quantity
                        )

            # Create new order inside atomic transaction
            with transaction.atomic():
                # Lock event row (for reference)
                event = Event.objects.select_for_update().get(id=event_id)

                # Lock all requested tier rows
                tier_ids = [t['tier_id'] for t in tiers_data]
                locked_tiers = TicketTier.objects.select_for_update().filter(
                    id__in=tier_ids,
                    event_id=event_id,
                    is_active=True
                )

                if locked_tiers.count() != len(tier_ids):
                    cache.delete(lock_key)
                    return Response(
                        {'error': 'One or more ticket tiers not found or unavailable'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check availability per tier
                for tier_data in tiers_data:
                    tier = locked_tiers.get(id=tier_data['tier_id'])
                    if tier.available < tier_data['quantity']:
                        cache.delete(lock_key)
                        return Response(
                            {'error': f"Only {tier.available} {tier.name} tickets left"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # Decrement each tier atomically
                for tier_data in tiers_data:
                    TicketTier.objects.filter(
                        id=tier_data['tier_id']
                    ).update(
                        available=F('available') - tier_data['quantity']
                    )

                # Get platform config
                config = PlatformConfig.get_active()
                fee_percentage = config.get_platform_fee_percentage()

                # Calculate totals
                subtotal = sum(
                    locked_tiers.get(id=t['tier_id']).price * t['quantity']
                    for t in tiers_data
                )
                platform_fee = (subtotal * fee_percentage).quantize(Decimal('0.01'))
                total = subtotal  # Model B: buyer pays subtotal only

                # Generate idempotency key
                now = timezone.now()
                total_quantity = sum(t['quantity'] for t in tiers_data)
                idem_data = f"{user.id}:{event_id}:{total_quantity}:{now.isoformat()}"
                idempotency_key = hashlib.sha256(idem_data.encode()).hexdigest()[:64]

                # Create order
                order = Order.objects.create(
                    user=user,
                    event=event,
                    quantity=total_quantity,
                    subtotal=subtotal,
                    platform_fee=platform_fee,
                    total=total,
                    status='pending',
                    idempotency_key=idempotency_key,
                    attendee_name=serializer.validated_data.get('name', ''),
                    attendee_email=serializer.validated_data.get('email', ''),
                )

                # Create OrderItems
                for tier_data in tiers_data:
                    tier = locked_tiers.get(id=tier_data['tier_id'])
                    OrderItem.objects.create(
                        order=order,
                        tier=tier,
                        quantity=tier_data['quantity'],
                        unit_price=tier.price
                    )

            # Initiate STK Push (outside transaction)
            try:
                daraja_response = daraja.initiate_stk_push(
                    phone=validated_phone,
                    amount=int(order.total),
                    order=order
                )
            except Exception as e:
                logger.error(f"STK Push failed for order {order.id}: {e}")

                # Rollback: mark order failed and release tickets (tier-aware)
                order.status = 'failed'
                order.save()
                for item in order.items.select_related('tier').all():
                    TicketTier.objects.filter(id=item.tier_id).update(
                        available=F('available') + item.quantity
                    )

                cache.delete(lock_key)
                return Response(
                    {'error': 'payment_initiation_failed'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Create M-Pesa transaction record
            MPESATransaction.objects.create(
                order=order,
                phone_number=validated_phone,
                checkout_request_id=daraja_response['CheckoutRequestID'],
                merchant_request_id=daraja_response['MerchantRequestID']
            )

            # Release lock
            cache.delete(lock_key)

            # Return response
            serializer_context = {
                'checkout_request_id': daraja_response['CheckoutRequestID'],
                'resuming': False
            }
            response_data = OrderResponseSerializer(order, context=serializer_context).data

            return Response(response_data, status=status.HTTP_200_OK)

        except Event.DoesNotExist:
            cache.delete(lock_key)
            return Response(
                {'error': 'event_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            cache.delete(lock_key)
            logger.exception(f"Payment initiation error: {e}")
            return Response(
                {'error': 'internal_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentStatusView(APIView):
    """
    Check payment status for a checkout request.

    ## URL Parameter:
    - `checkout_request_id` - The CheckoutRequestID from initiate response

    ## Response (Success):
    ```json
    {
        "status": "paid",
        "order_id": "abc123",
        "mpesa_receipt": "QA12BC34DE"
    }
    ```

    ## Status Values:
    - `pending` - Awaiting M-Pesa callback
    - `paid` - Payment successful
    - `failed` - Payment failed or cancelled by user
    - `expired` - Order timeout (15 minutes)
    - `refunded` - Payment reversed

    ## Notes:
    - Poll this endpoint every 5 seconds after initiation
    - Status changes from `pending` to `paid` or `failed` when callback arrives
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: PaymentStatusResponseSerializer},
        tags=['payments'],
        summary='Poll payment status',
        description='Poll every 3 seconds. Status: pending|paid|failed|expired'
    )
    def get(self, request, checkout_request_id):
        try:
            txn = MPESATransaction.objects.select_related('order').get(
                checkout_request_id=checkout_request_id
            )

            # Verify user owns this order
            if txn.order.user != request.user:
                return Response(
                    {'error': 'forbidden'},
                    status=status.HTTP_403_FORBIDDEN
                )

            response_data = PaymentStatusResponseSerializer({
                'status': txn.order.status,
                'order_id': txn.order.id,
                'mpesa_receipt': txn.mpesa_receipt
            }).data

            return Response(response_data)

        except MPESATransaction.DoesNotExist:
            return Response(
                {'error': 'transaction_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )


class OrderDetailView(APIView):
    """
    GET /api/payments/orders/{order_id}/

    Retrieve order details with ticket items (for confirmation screen).

    ## Response (Success):
    ```json
    {
        "id": "abc123",
        "subtotal": "3500.00",
        "platform_fee": "70.00",
        "total": "3500.00",
        "status": "paid",
        "items": [
            {
                "tier_name": "General Admission",
                "quantity": 2,
                "unit_price": "1500.00",
                "subtotal": "3000.00"
            },
            {
                "tier_name": "VIP",
                "quantity": 1,
                "unit_price": "500.00",
                "subtotal": "500.00"
            }
        ]
    }
    ```

    ## Notes:
    - User can only view their own orders
    - Returns 403 if order belongs to different user
    - Returns 404 if order does not exist
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OrderResponseSerializer},
        tags=['payments'],
        summary='Get order details with ticket items'
    )
    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related('items__tier').get(id=order_id)

            # Verify user owns this order
            if order.user != request.user:
                return Response(
                    {'error': 'forbidden'},
                    status=status.HTTP_403_FORBIDDEN
                )

            response_data = OrderResponseSerializer(order).data
            return Response(response_data)

        except Order.DoesNotExist:
            return Response(
                {'error': 'order_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    """
    POST /api/payments/mpesa/callback/

    Handles M-Pesa STK Push callbacks.
    ALWAYS returns HTTP 200 to Daraja.
    """
    permission_classes = []  # No auth for callbacks
    authentication_classes = []

    @extend_schema(exclude=True)  # Daraja internal — not consumer-facing
    def post(self, request):
        # ALWAYS return 200 to Daraja
        success_response = JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

        try:
            callback_data = request.data
            stk_callback = callback_data.get('Body', {}).get('stkCallback', {})

            if not stk_callback:
                logger.warning("Malformed M-Pesa callback received")
                return success_response

            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')

            # Find transaction
            try:
                txn = MPESATransaction.objects.select_related('order').get(
                    checkout_request_id=checkout_request_id
                )
            except MPESATransaction.DoesNotExist:
                logger.error(f"Transaction not found for {checkout_request_id}")
                return success_response

            order = txn.order

            # Guard against duplicate callbacks
            if order.status in ['paid', 'failed', 'refunded']:
                logger.info(f"Duplicate callback for order {order.id}, already {order.status}")
                return success_response

            # Process callback inside atomic transaction
            with transaction.atomic():
                if result_code == 0:
                    # Payment successful
                    result_desc = stk_callback.get('ResultDesc', '')
                    callback_metadata = stk_callback.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])

                    # Extract M-Pesa receipt
                    mpesa_receipt = None
                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            mpesa_receipt = item.get('Value')
                            break

                    # Update transaction
                    txn.result_code = '0'
                    txn.result_desc = result_desc
                    txn.mpesa_receipt = mpesa_receipt
                    txn.save()

                    # Update order
                    order.status = 'paid'
                    order.paid_at = timezone.now()
                    order.save()

                    # Create payout scheduled 24h after paid_at
                    config = PlatformConfig.get_active()
                    payout_delay = timedelta(hours=config.payout_delay_hours)

                    OrganizerPayout.objects.create(
                        organizer=order.event.organizer,
                        order=order,
                        amount=order.total - order.platform_fee,
                        platform_fee=order.platform_fee,
                        status='scheduled',
                        scheduled_for=order.paid_at + payout_delay
                    )

                    # Create one Ticket per physical ticket purchased
                    # OrderItem.quantity=2 → 2 Ticket records, each with unique token
                    for item in order.items.select_related('tier').all():
                        for _ in range(item.quantity):
                            create_ticket_with_retry(
                                order_item=item,
                                attendee_name=order.attendee_name,
                                attendee_email=order.attendee_email,
                            )

                    logger.info(f"Payment successful for order {order.id}, receipt {mpesa_receipt}")

                else:
                    # Payment failed
                    result_desc = stk_callback.get('ResultDesc', '')

                    # Update transaction
                    txn.result_code = str(result_code)
                    txn.result_desc = result_desc
                    txn.save()

                    # Update order
                    order.status = 'failed'
                    order.save()

                    # Release tickets atomically (tier-aware)
                    for item in order.items.select_related('tier').all():
                        TicketTier.objects.filter(id=item.tier_id).update(
                            available=F('available') + item.quantity
                        )

                    logger.info(
                        f"Payment failed for order {order.id}: "
                        f"code={result_code}, desc={result_desc}"
                    )

            return success_response

        except Exception as e:
            logger.exception(f"Error processing M-Pesa callback: {e}")
            return success_response


class InitiatePayoutView(APIView):
    """
    POST /api/payments/payout/initiate/

    Manually trigger a specific payout (admin only).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        request=InitiatePayoutSerializer,
        responses={200: OpenApiResponse(description='Payout initiated')},
        tags=['admin'],
        summary='Manually trigger organizer payout (admin only)'
    )
    def post(self, request):
        serializer = InitiatePayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payout_id = serializer.validated_data['payout_id']

        try:
            payout = OrganizerPayout.objects.select_related(
                'organizer__organizerpaymentconfig'
            ).get(id=payout_id)

            if payout.status != 'scheduled':
                return Response(
                    {'error': f'payout_not_scheduled, current status: {payout.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine payout method
            payment_config = payout.organizer.organizerpaymentconfig
            payout_type = payment_config.payout_type

            # Call appropriate Daraja function
            if payout_type == 'b2c':
                daraja_response = daraja.initiate_b2c_payout(payout)
            elif payout_type in ['b2b_paybill', 'b2b_till']:
                daraja_response = daraja.initiate_b2b_payout(payout)
            else:
                return Response(
                    {'error': f'invalid_payout_type: {payout_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update payout status
            payout.status = 'processing'
            payout.save()

            return Response({
                'payout_id': payout.id,
                'status': payout.status,
                'daraja_response': daraja_response
            })

        except OrganizerPayout.DoesNotExist:
            return Response(
                {'error': 'payout_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Payout initiation error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class B2CCallbackView(APIView):
    """
    POST /api/payments/mpesa/b2c-callback/

    Handles B2C payout result callbacks.
    ALWAYS returns HTTP 200.
    """
    permission_classes = []
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        success_response = JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

        try:
            callback_data = request.data
            result = callback_data.get('Result', {})
            result_code = result.get('ResultCode')

            # Extract ConversationID or receipt to find payout
            conversation_id = result.get('ConversationID')

            # For now, log the callback
            logger.info(f"B2C callback received: {callback_data}")

            # Payout lookup by ConversationID would go here
            # Update payout.status = 'completed' or 'failed'

            return success_response

        except Exception as e:
            logger.exception(f"Error processing B2C callback: {e}")
            return success_response


@method_decorator(csrf_exempt, name='dispatch')
class B2BCallbackView(APIView):
    """
    POST /api/payments/mpesa/b2b-callback/

    Handles B2B payout result callbacks.
    ALWAYS returns HTTP 200.
    """
    permission_classes = []
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        success_response = JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

        try:
            callback_data = request.data
            result = callback_data.get('Result', {})
            result_code = result.get('ResultCode')

            conversation_id = result.get('ConversationID')

            logger.info(f"B2B callback received: {callback_data}")

            # Payout lookup by ConversationID would go here
            # Update payout.status = 'completed' or 'failed'

            return success_response

        except Exception as e:
            logger.exception(f"Error processing B2B callback: {e}")
            return success_response


class InitiateReversalView(APIView):
    """
    POST /api/payments/reversal/initiate/

    Initiates refund for a paid order (admin only).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        request=InitiateReversalSerializer,
        responses={
            200: OpenApiResponse(description='Reversal initiated'),
            400: OpenApiResponse(description='Order not paid'),
        },
        tags=['admin'],
        summary='Initiate transaction reversal (admin only)'
    )
    def post(self, request):
        serializer = InitiateReversalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data['order_id']

        try:
            order = Order.objects.select_related('mpesa_transaction').get(id=order_id)

            if order.status != 'paid':
                return Response(
                    {'error': f'order_not_paid, current status: {order.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            txn = order.mpesa_transaction

            # Check if within reversal window (24 hours)
            reversal_window = order.paid_at + timedelta(hours=24)

            if timezone.now() <= reversal_window:
                # Use Daraja Reversal API
                daraja_response = daraja.initiate_reversal(
                    transaction_id=txn.mpesa_receipt,
                    amount=int(order.total),
                    phone=txn.phone_number
                )

                return Response({
                    'order_id': order.id,
                    'method': 'reversal_api',
                    'daraja_response': daraja_response
                })
            else:
                # Outside reversal window - would need manual B2C refund
                raise NotImplementedError(
                    "B2C refund flow for orders outside 24h window not yet implemented"
                )

        except Order.DoesNotExist:
            return Response(
                {'error': 'order_not_found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except NotImplementedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        except Exception as e:
            logger.exception(f"Reversal initiation error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class ReversalCallbackView(APIView):
    """
    POST /api/payments/mpesa/reversal-callback/

    Handles reversal result callbacks.
    ALWAYS returns HTTP 200.
    """
    permission_classes = []
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        success_response = JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

        try:
            callback_data = request.data
            result = callback_data.get('Result', {})
            result_code = result.get('ResultCode')

            logger.info(f"Reversal callback received: {callback_data}")

            # Order lookup by original transaction ID would go here
            # If result_code == 0: order.status = 'refunded', freeze payouts
            # If result_code != 0: alert admin

            return success_response

        except Exception as e:
            logger.exception(f"Error processing reversal callback: {e}")
            return success_response
