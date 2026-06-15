import secrets
import string

from django.db import IntegrityError, models
from django.utils import timezone


def generate_ticket_token() -> str:
    """
    Generate a short unique token for QR code encoding.
    20 uppercase alphanumeric characters.
    Short enough for dense-free QR scanning in poor lighting.
    Example: A3KX9MNP2QRTV8WYLZ4F
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(20))


def create_ticket_with_retry(order_item, attendee_name, attendee_email,
                              max_retries=5):
    """
    Creates a Ticket with a unique token. Retries on the rare
    IntegrityError from token collision (unique constraint violation).
    """
    for attempt in range(max_retries):
        try:
            return Ticket.objects.create(
                order_item=order_item,
                attendee_name=attendee_name,
                attendee_email=attendee_email,
            )
        except IntegrityError:
            if attempt == max_retries - 1:
                raise
            continue


class Ticket(models.Model):
    """
    One physical ticket. One OrderItem with quantity=N creates N Tickets.
    The token is what gets encoded in the QR code.
    The organizer scans the token at the door to verify entry.
    """
    order_item = models.ForeignKey(
        'payments.OrderItem',
        on_delete=models.PROTECT,
        related_name='tickets'
    )
    token = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=generate_ticket_token,
        editable=False
    )
    attendee_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Name from checkout user details. '
                  'Stored at ticket creation time — immutable.'
    )
    attendee_email = models.EmailField(
        blank=True,
        help_text='Email from checkout user details. '
                  'Stored at ticket creation time — immutable.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Entry tracking
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the ticket was scanned at the door.'
    )
    used_by = models.ForeignKey(
        'organizers.OrganizerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scanned_tickets',
        help_text='Which organizer scanned this ticket.'
    )

    class Meta:
        db_table = 'tickets_ticket'
        ordering = ['created_at']

    def __str__(self):
        event = self.order_item.tier.event.title
        tier = self.order_item.tier.name
        return f"{event} — {tier} — {self.token}"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def event(self):
        return self.order_item.tier.event

    @property
    def tier(self):
        return self.order_item.tier

    @property
    def order(self):
        return self.order_item.order
