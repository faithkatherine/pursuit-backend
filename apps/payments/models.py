import uuid
from django.db import models


class Order(models.Model):
    """
    Model B (Seller Pays Fee):
    - Buyer pays: total (all-inclusive, no fee added)
    - Organizer gets: total - platform_fee
    - In Model B: subtotal = total (kept separate for audit trail & future flexibility)
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Financial record survives user deletion"
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Cannot delete event with existing orders"
    )

    quantity = models.PositiveIntegerField(default=1)

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Ticket price × quantity (base amount before any adjustments)"
    )

    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Platform fee deducted from organizer payout (NOT added to buyer total in Model B)"
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final amount buyer pays (equals subtotal in Model B; leaves room for discounts in V2)"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('expired', 'Expired'),
            ('refunded', 'Refunded'),
        ],
        default='pending'
    )

    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When order status changed to 'paid' (triggers 24h payout countdown)"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['event', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['idempotency_key']),
        ]

    def save(self, *args, **kwargs):
        # Model B: total always equals subtotal (no fee added to buyer)
        # V2: could have total = subtotal - discount_amount
        if self.subtotal and not self.total:
            self.total = self.subtotal
        super().save(*args, **kwargs)

    def organizer_payout_amount(self):
        """Calculate net amount organizer receives after platform fee"""
        return self.total - self.platform_fee

    def __str__(self):
        user_str = self.user.email if self.user else "Deleted User"
        return f"Order {self.id} by {user_str} for {self.event.name}"


class MPESATransaction(models.Model):
    """
    Tracks M-Pesa STK Push transaction details.
    One transaction per order.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="mpesa_transaction",
        help_text="Transaction is part of the order lifecycle"
    )

    phone_number = models.CharField(max_length=15)
    checkout_request_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Daraja STK Push unique identifier"
    )
    merchant_request_id = models.CharField(max_length=100)

    mpesa_receipt = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="M-Pesa receipt number (e.g., QGH1234567)"
    )
    result_code = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Daraja result code (0 = success)"
    )
    result_desc = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Daraja result description"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "M-Pesa Transaction"
        verbose_name_plural = "M-Pesa Transactions"
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['result_code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"M-Pesa Transaction for Order {self.order.id}"

    def is_successful(self):
        """Check if transaction completed successfully"""
        return self.result_code == '0'
