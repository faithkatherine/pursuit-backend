"""
Payment API Serializers

All payment views use DRF serializers for request/response validation.
"""

from rest_framework import serializers

from apps.events.models import TicketTier
from apps.payments.models import MPESATransaction, Order, OrderItem
from apps.tickets.serializers import TicketSummarySerializer


class TierSelectionSerializer(serializers.Serializer):
    """Individual tier selection within an order"""
    tier_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class InitiatePaymentSerializer(serializers.Serializer):
    """Request serializer for POST /api/payments/initiate/"""
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in any format (0712..., 254712..., +254712...)"
    )
    event_id = serializers.UUIDField(help_text="Event UUID")
    tiers = TierSelectionSerializer(many=True, help_text="List of tier selections")
    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default=''
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        default=''
    )

    def validate_tiers(self, value):
        active = [t for t in value if t['quantity'] > 0]
        if not active:
            raise serializers.ValidationError(
                "Select at least one ticket"
            )
        return active


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order line items"""
    tier_name = serializers.CharField(
        source='tier.name',
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ['tier_name', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = fields


class OrderResponseSerializer(serializers.ModelSerializer):
    """Response serializer for order creation

    Note: checkout_request_id and resuming are added manually by the view
    """
    items = OrderItemSerializer(many=True, read_only=True)
    tickets = serializers.SerializerMethodField()
    checkout_request_id = serializers.SerializerMethodField()
    resuming = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'subtotal', 'platform_fee', 'total',
            'status', 'items', 'tickets',
            'checkout_request_id', 'resuming'
        ]
        read_only_fields = fields

    def get_tickets(self, obj):
        tickets = []
        for item in obj.items.all():
            tickets.extend(item.tickets.all())
        return TicketSummarySerializer(tickets, many=True).data

    def get_checkout_request_id(self, obj):
        return self.context.get('checkout_request_id')

    def get_resuming(self, obj):
        return self.context.get('resuming', False)


class PaymentStatusSerializer(serializers.Serializer):
    """Request serializer for GET /api/payments/status/{checkout_request_id}/"""
    checkout_request_id = serializers.CharField(max_length=100)


class PaymentStatusResponseSerializer(serializers.Serializer):
    """Response serializer for payment status"""
    status = serializers.ChoiceField(
        choices=['pending', 'paid', 'failed', 'expired', 'refunded']
    )
    order_id = serializers.UUIDField()
    mpesa_receipt = serializers.CharField(allow_null=True)


class InitiatePayoutSerializer(serializers.Serializer):
    """Request serializer for POST /api/payments/payout/initiate/"""
    payout_id = serializers.IntegerField(help_text="OrganizerPayout ID to process")


class InitiateReversalSerializer(serializers.Serializer):
    """Request serializer for POST /api/payments/reversal/initiate/"""
    order_id = serializers.UUIDField(help_text="Order UUID to refund")


class TicketTierSerializer(serializers.ModelSerializer):
    """Serializer for ticket tiers in event detail responses"""
    class Meta:
        model = TicketTier
        fields = [
            'id', 'name', 'description', 'price',
            'available', 'capacity', 'is_active', 'sort_order'
        ]
        read_only_fields = fields
