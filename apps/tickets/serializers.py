from rest_framework import serializers

from apps.tickets.models import Ticket


class TicketVerificationResponseSerializer(serializers.Serializer):
    """
    Response from GET /api/tickets/verify/{token}/
    Used by the organizer dashboard scanner.
    """
    valid = serializers.BooleanField()
    already_used = serializers.BooleanField(default=False)
    token = serializers.CharField()
    attendee_name = serializers.CharField()
    tier_name = serializers.CharField()
    event_title = serializers.CharField()
    event_date = serializers.CharField()
    used_at = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(
        allow_null=True,
        default=None,
        help_text='Only set when valid=False. '
                  'Values: invalid_token | already_used | wrong_event'
    )


class TicketUseResponseSerializer(serializers.Serializer):
    """
    Response from POST /api/tickets/use/{token}/
    """
    success = serializers.BooleanField()
    used_at = serializers.DateTimeField()
    attendee_name = serializers.CharField()
    tier_name = serializers.CharField()


class TicketSummarySerializer(serializers.ModelSerializer):
    """
    Embedded in OrderResponseSerializer so the confirmation
    screen can get the token for the QR code.
    """
    tier_name = serializers.CharField(source='tier.name', read_only=True)
    event_title = serializers.CharField(
        source='order_item.tier.event.title',
        read_only=True
    )

    class Meta:
        model = Ticket
        fields = ['token', 'tier_name', 'event_title', 'is_used']
        read_only_fields = fields
