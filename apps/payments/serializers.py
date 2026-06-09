"""
Payment API Serializers

All payment views use DRF serializers for request/response validation.
"""

from rest_framework import serializers

from apps.payments.models import MPESATransaction, Order


class InitiatePaymentSerializer(serializers.Serializer):
    """Request serializer for POST /api/payments/initiate/"""
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in any format (0712..., 254712..., +254712...)"
    )
    event_id = serializers.UUIDField(help_text="Event UUID")
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Number of tickets to purchase"
    )


class OrderResponseSerializer(serializers.ModelSerializer):
    """Response serializer for order creation

    Note: checkout_request_id and resuming are added manually by the view
    """

    class Meta:
        model = Order
        fields = ['id', 'event_id', 'quantity', 'subtotal', 'platform_fee', 'total', 'status']
        read_only_fields = fields


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
