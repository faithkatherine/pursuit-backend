"""
Celery Tasks for Payment System

Background tasks for order expiration, payout processing, and refunds.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.models import PlatformConfig
from apps.events.models import Event
from apps.organizers.models import OrganizerPayout
from apps.payments import daraja
from apps.payments.models import MPESATransaction, Order

logger = logging.getLogger(__name__)


@shared_task
def expire_stale_orders(timeout_minutes=None):
    """
    Expires pending orders older than timeout.
    Releases tickets back to available pool.
    Should run every hour via Celery Beat.

    Args:
        timeout_minutes: Order expiration timeout (defaults to PlatformConfig value)

    Returns:
        dict with expired_count
    """
    if timeout_minutes is None:
        config = PlatformConfig.get_active()
        timeout_minutes = config.order_expiration_minutes

    cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)

    # Find stale pending orders
    stale_orders = Order.objects.filter(
        status='pending',
        created_at__lt=cutoff_time
    ).select_related('event')

    # Exclude orders with successful M-Pesa transactions (callback might be delayed)
    stale_orders = stale_orders.exclude(
        mpesa_transaction__result_code='0'
    )

    expired_count = 0

    for order in stale_orders:
        with transaction.atomic():
            # Mark as expired
            order.status = 'expired'
            order.save()

            # Release tickets atomically
            Event.objects.filter(id=order.event_id).update(
                available_tickets=F('available_tickets') + order.quantity
            )

            expired_count += 1

            logger.info(f"Expired order {order.id}, released {order.quantity} tickets")

    logger.info(f"Expired {expired_count} stale orders")
    return {'expired_count': expired_count}


@shared_task
def process_scheduled_payouts():
    """
    Processes payouts scheduled for execution.
    Should run every hour via Celery Beat.

    Finds payouts with status='scheduled' and scheduled_for <= now,
    calls appropriate Daraja API (B2C or B2B) based on payout_type.

    Returns:
        dict with processed_count
    """
    due_payouts = OrganizerPayout.objects.filter(
        status='scheduled',
        scheduled_for__lte=timezone.now()
    ).select_related('organizer__payment_config', 'order')

    processed_count = 0

    for payout in due_payouts:
        try:
            process_single_payout(payout.id)
            processed_count += 1
        except Exception as e:
            logger.error(f"Failed to process payout {payout.id}: {e}")

    logger.info(f"Processed {processed_count} scheduled payouts")
    return {'processed_count': processed_count}


@shared_task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 5, 'countdown': 3600},
    retry_backoff=False
)
def process_single_payout(payout_id):
    """
    Processes a single payout.
    Retries up to 5 times with 1 hour delay on failure.

    Args:
        payout_id: OrganizerPayout ID

    Raises:
        Exception on failure (triggers Celery retry)
    """
    payout = OrganizerPayout.objects.select_related(
        'organizer__payment_config'
    ).get(id=payout_id)

    if payout.status != 'scheduled':
        logger.warning(f"Payout {payout_id} not in scheduled status: {payout.status}")
        return

    if payout.status == 'frozen':
        logger.info(f"Payout {payout_id} frozen: {payout.frozen_reason}")
        return

    payment_config = payout.organizer.payment_config
    payout_type = payment_config.payout_type

    logger.info(f"Processing payout {payout_id} ({payout_type})")

    # Call appropriate Daraja function
    if payout_type == 'b2c':
        daraja_response = daraja.initiate_b2c_payout(payout)
    elif payout_type in ['b2b_paybill', 'b2b_till']:
        daraja_response = daraja.initiate_b2b_payout(payout)
    else:
        raise ValueError(f"Invalid payout_type: {payout_type}")

    # Update status
    payout.status = 'processing'
    payout.save()

    logger.info(f"Payout {payout_id} initiated successfully")


@shared_task
def handle_event_cancellation(event_id):
    """
    Handles event cancellation.
    Freezes scheduled payouts and initiates refunds.

    Args:
        event_id: Event ID

    Returns:
        dict with frozen_count
    """
    from apps.events.models import Event

    event = Event.objects.get(id=event_id)

    if event.status != 'cancelled':
        logger.warning(f"Event {event_id} not cancelled, status: {event.status}")
        return {'frozen_count': 0}

    # Freeze all scheduled payouts for this event
    scheduled_payouts = OrganizerPayout.objects.filter(
        order__event=event,
        status='scheduled'
    )

    frozen_count = 0
    for payout in scheduled_payouts:
        payout.status = 'frozen'
        payout.frozen_reason = f"Event cancelled: {event.cancellation_reason}"
        payout.save()
        frozen_count += 1

    logger.info(f"Frozen {frozen_count} payouts for cancelled event {event_id}")
    return {'frozen_count': frozen_count}


@shared_task
def refund_cancelled_event_orders(event_id):
    """
    Initiates refunds for all paid orders of a cancelled event.

    Args:
        event_id: Event ID

    Returns:
        dict with refunded_count
    """
    from apps.events.models import Event

    event = Event.objects.get(id=event_id)

    paid_orders = Order.objects.filter(
        event=event,
        status='paid'
    ).select_related('mpesa_transaction')

    refunded_count = 0

    for order in paid_orders:
        try:
            # Check if within reversal window (24 hours)
            reversal_window = order.paid_at + timedelta(hours=24)

            if timezone.now() <= reversal_window:
                # Use Daraja Reversal API
                txn = order.mpesa_transaction
                daraja.initiate_reversal(
                    transaction_id=txn.mpesa_receipt,
                    amount=int(order.total),
                    phone=txn.phone_number
                )

                order.status = 'refunded'
                order.save()
                refunded_count += 1

                logger.info(f"Refund initiated for order {order.id}")
            else:
                logger.warning(
                    f"Order {order.id} outside reversal window, "
                    "requires manual B2C refund"
                )

        except Exception as e:
            logger.error(f"Failed to refund order {order.id}: {e}")

    logger.info(f"Initiated {refunded_count} refunds for event {event_id}")
    return {'refunded_count': refunded_count}


@shared_task
def handle_payout_callback(payout_id, callback_data):
    """
    Handles B2C/B2B payout result callbacks.

    Args:
        payout_id: OrganizerPayout ID
        callback_data: Daraja callback payload

    Note: In production, this would be called from the callback view
    after extracting ConversationID to find the payout.
    """
    payout = OrganizerPayout.objects.get(id=payout_id)

    result = callback_data.get('Result', {})
    result_code = result.get('ResultCode')

    if result_code == 0:
        # Payout successful
        result_params = result.get('ResultParameters', {}).get('ResultParameter', [])

        # Extract M-Pesa receipt
        mpesa_receipt = None
        for param in result_params:
            if param.get('Key') == 'TransactionReceipt':
                mpesa_receipt = param.get('Value')
                break

        payout.status = 'completed'
        payout.mpesa_receipt = mpesa_receipt
        payout.completed_at = timezone.now()
        payout.save()

        logger.info(f"Payout {payout_id} completed, receipt {mpesa_receipt}")
    else:
        # Payout failed
        result_desc = result.get('ResultDesc', '')

        payout.status = 'failed'
        payout.save()

        logger.error(f"Payout {payout_id} failed: {result_desc}")
