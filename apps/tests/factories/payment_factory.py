import uuid
from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.events.models import TicketTier
from apps.organizers.models import OrganizerPayout
from apps.payments.models import MPESATransaction, Order, OrderItem
from apps.tests.factories.event_factory import EventFactory
from apps.tests.factories.organizer_factory import OrganizerProfileFactory
from apps.tests.factories.user_factory import UserFactory

# Platform fee rate constant (2%)
PLATFORM_FEE_RATE = Decimal('0.02')


class TicketTierFactory(DjangoModelFactory):
    """
    Creates a ticket tier for an event.

    Usage:
        tier = TicketTierFactory(event=some_event)
        tier = TicketTierFactory(price=Decimal('1500.00'), available=50)
    """

    class Meta:
        model = TicketTier

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Tier {n}")
    description = factory.Faker('sentence')
    price = Decimal('1500.00')
    capacity = 100
    available = 100
    is_active = True
    sort_order = 0


class OrderItemFactory(DjangoModelFactory):
    """
    Creates an order item linking an order to a ticket tier.

    Usage:
        item = OrderItemFactory(order=some_order, tier=some_tier)
        item = OrderItemFactory(quantity=2)
    """

    class Meta:
        model = OrderItem

    order = factory.SubFactory('apps.tests.factories.payment_factory.OrderFactory')
    tier = factory.SubFactory(TicketTierFactory)
    quantity = 1
    unit_price = factory.LazyAttribute(lambda o: o.tier.price)


class OrderFactory(DjangoModelFactory):
    """
    Creates a pending Order with Model B pricing (seller pays fee).

    Usage:
        order = OrderFactory()
        order = OrderFactory(user=some_user, event=some_event)
        paid_order = OrderFactory(status='paid')

    Model B calculation:
        subtotal = event.price * quantity  # What buyer pays
        platform_fee = subtotal * 0.02     # 2% deducted from organizer
        total = subtotal                   # Same as subtotal (no fee added)
    """

    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    event = factory.SubFactory(EventFactory)
    quantity = 1

    subtotal = factory.LazyAttribute(
        lambda o: Decimal('1500.00') * o.quantity
    )
    platform_fee = factory.LazyAttribute(
        lambda o: (o.subtotal * PLATFORM_FEE_RATE).quantize(Decimal('0.01'))
    )
    total = factory.LazyAttribute(lambda o: o.subtotal)

    status = 'pending'
    idempotency_key = factory.LazyFunction(lambda: str(uuid.uuid4()))

    @factory.post_generation
    def set_paid_at(obj, create, extracted, **kwargs):
        """Automatically set paid_at when status is 'paid'"""
        if create and obj.status == 'paid':
            obj.paid_at = timezone.now()
            obj.save()

    @factory.post_generation
    def create_order_item(obj, create, extracted, **kwargs):
        """Create an associated OrderItem for this order"""
        if create:
            # Create a tier for the event if one doesn't exist
            tier = TicketTier.objects.filter(event=obj.event, is_active=True).first()
            if not tier:
                tier = TicketTierFactory(
                    event=obj.event,
                    name='General Admission',
                    price=obj.event.price,
                    available=obj.event.available_tickets or 100
                )

            # Create order item
            OrderItem.objects.create(
                order=obj,
                tier=tier,
                quantity=obj.quantity,
                unit_price=tier.price
            )


class MPESATransactionFactory(DjangoModelFactory):
    """
    Creates an M-Pesa STK Push transaction record.

    Usage:
        txn = MPESATransactionFactory(order=some_order)
        successful_txn = MPESATransactionFactory(result_code='0')
    """

    class Meta:
        model = MPESATransaction

    order = factory.SubFactory(OrderFactory)
    phone_number = factory.Sequence(lambda n: f"254712{n:06d}")
    checkout_request_id = factory.LazyFunction(
        lambda: f"ws_CO_{timezone.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    )
    merchant_request_id = factory.LazyFunction(
        lambda: f"{uuid.uuid4().hex[:16]}"
    )
    mpesa_receipt = factory.Maybe(
        'result_code',
        yes_declaration=factory.Sequence(lambda n: f"QGH{n:07d}XYZ"),
        no_declaration=None
    )
    result_code = None  # None = pending, '0' = success
    result_desc = None


class OrganizerPayoutWithOrderFactory(DjangoModelFactory):
    """
    Creates an organizer payout with a linked order.

    Usage:
        payout = OrganizerPayoutWithOrderFactory()
        payout = OrganizerPayoutWithOrderFactory(status='completed')
        payout = OrganizerPayoutWithOrderFactory(organizer=my_organizer)
    """

    class Meta:
        model = OrganizerPayout

    organizer = factory.SubFactory(OrganizerProfileFactory)

    @factory.lazy_attribute
    def order(self):
        # Create order with event that belongs to this payout's organizer
        event = EventFactory(organizer=self.organizer)
        return OrderFactory(event=event, status='paid')

    amount = factory.LazyAttribute(
        lambda o: o.order.total - o.order.platform_fee
    )
    platform_fee = factory.LazyAttribute(lambda o: o.order.platform_fee)

    status = 'scheduled'
    scheduled_for = factory.LazyAttribute(
        lambda o: (o.order.paid_at or o.order.created_at) + timezone.timedelta(hours=24)
    )
