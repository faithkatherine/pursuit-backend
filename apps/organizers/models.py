from django.db import models
from django.utils import timezone


class ActiveOrganizerManager(models.Manager):
    """Manager that returns only active (non-deactivated) organizers by default"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class OrganizerProfile(models.Model):
    """
    Organizer business profile. Linked to User but survives user deletion
    for financial audit trail purposes.
    """
    user = models.OneToOneField(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizer_profile",
        help_text="User can be deleted for GDPR; organizer record survives for financial history"
    )

    business_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    website_url = models.URLField(null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)

    verified = models.BooleanField(
        default=False,
        help_text="Manually verified by admin before organizer can create events"
    )

    # Soft delete fields
    is_active = models.BooleanField(
        default=True,
        help_text="False = organizer role deactivated (soft delete)"
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveOrganizerManager()  # Default: only active organizers
    all_objects = models.Manager()      # Explicit: includes deactivated

    class Meta:
        verbose_name = "Organizer Profile"
        verbose_name_plural = "Organizer Profiles"
        ordering = ['-created_at']

    def __str__(self):
        return self.business_name or f"Organizer {self.id}"

    def deactivate(self, reason="User requested removal"):
        """Soft delete the organizer profile"""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.deactivation_reason = reason
        self.save(update_fields=['is_active', 'deactivated_at', 'deactivation_reason'])


class OrganizerPaymentConfig(models.Model):
    """
    M-Pesa payment configuration for organizer.
    - Collection: How users pay (STK Push to organizer's Paybill/Till)
    - Payout: How Pursuit pays organizer (B2C to phone or B2B to shortcode)
    """
    organizer = models.OneToOneField(
        OrganizerProfile,
        on_delete=models.CASCADE,
        related_name="payment_config",
        help_text="Config has no value without organizer"
    )

    # Collection — how users pay via STK Push
    collection_type = models.CharField(
        max_length=20,
        choices=[
            ('paybill', 'Paybill'),
            ('till', 'Till'),
        ],
        help_text="Organizer's M-Pesa collection method"
    )
    collection_shortcode = models.CharField(
        max_length=20,
        help_text="Paybill number or Till number"
    )
    collection_passkey = models.CharField(
        max_length=255,
        help_text="Lipa Na M-Pesa Online Passkey (store encrypted in production)"
    )

    # Payout — how Pursuit sends organizer their money
    payout_type = models.CharField(
        max_length=20,
        choices=[
            ('b2c', 'Personal M-Pesa'),
            ('b2b_paybill', 'Business Paybill'),
            ('b2b_till', 'Business Till'),
        ],
        help_text="How organizer wants to receive payouts"
    )
    payout_destination = models.CharField(
        max_length=20,
        help_text="Phone number (B2C) or shortcode (B2B)"
    )

    verified = models.BooleanField(
        default=False,
        help_text="Admin verified payment config is correct"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organizer Payment Config"
        verbose_name_plural = "Organizer Payment Configs"

    def __str__(self):
        return f"Payment Config for {self.organizer.business_name or self.organizer.id}"


class OrganizerPayout(models.Model):
    """
    One payout per order, scheduled 24 hours after order creation.

    Model B (Seller Pays):
    - amount = order.total - order.platform_fee (net to organizer)
    - Pursuit keeps the platform_fee
    """
    organizer = models.ForeignKey(
        OrganizerProfile,
        on_delete=models.PROTECT,
        related_name="payouts",
        help_text="PROTECT: Never auto-delete financial records"
    )
    order = models.ForeignKey(
        'payments.Order',
        on_delete=models.PROTECT,
        related_name="payout",
        help_text="PROTECT: Never auto-delete financial records"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Net amount paid to organizer (order.total - platform_fee)"
    )

    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Platform fee deducted from order (denormalized for reporting)"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),    # Created, waiting for scheduled_for time
            ('processing', 'Processing'),  # Daraja B2C/B2B call in progress
            ('completed', 'Completed'),    # Successfully paid out
            ('failed', 'Failed'),          # Daraja returned error
            ('frozen', 'Frozen'),          # Event cancelled or dispute
        ],
        default='scheduled'
    )

    scheduled_for = models.DateTimeField(
        help_text="When to process this payout (order.created_at + 24 hours)"
    )

    mpesa_receipt = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="M-Pesa receipt from B2C/B2B transaction"
    )
    frozen_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Why payout was frozen (e.g., 'Event cancelled')"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payout completed successfully"
    )

    class Meta:
        verbose_name = "Organizer Payout"
        verbose_name_plural = "Organizer Payouts"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organizer', 'status']),
            models.Index(fields=['scheduled_for', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Payout KES {self.amount} to {self.organizer.business_name} (Order {self.order.id})"

    def freeze(self, reason):
        """Freeze payout (e.g., event cancelled)"""
        self.status = 'frozen'
        self.frozen_reason = reason
        self.save(update_fields=['status', 'frozen_reason'])

    def mark_completed(self, mpesa_receipt):
        """Mark payout as successfully completed"""
        self.status = 'completed'
        self.mpesa_receipt = mpesa_receipt
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'mpesa_receipt', 'completed_at'])
