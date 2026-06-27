import uuid
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Abstract model for timestamped models"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    """Category model for organizing bucket items"""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly slug (e.g., 'talks-and-ideas')")
    icon = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#007AFF")  # Hex color
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "core_category"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["sort_order"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.icon} {self.name}" if self.icon else self.name


class Interest(models.Model):
    """Interest model for user personalization, linked to categories"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, blank=False, null=False)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interests",
    )

    class Meta:
        db_table = "users_interests"
        verbose_name = _("Interest")
        verbose_name_plural = _("Interests")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class PlatformConfig(models.Model):
    """
    Platform-wide configuration settings.
    Singleton model - only one active record should exist.

    Stores in database (not settings.py) to allow:
    - Runtime configuration changes without deployment
    - Future A/B testing of different fee structures
    - Historical tracking of fee changes
    """
    is_active = models.BooleanField(
        default=True,
        help_text="Only one config should be active at a time"
    )

    fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Platform fee percentage (e.g., 2.00 for 2%)"
    )

    # Future expansion fields
    min_payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        null=True,
        blank=True,
        help_text="Minimum payout amount in KES (future use)"
    )

    max_ticket_quantity = models.PositiveIntegerField(
        default=10,
        help_text="Maximum tickets per order (future use)"
    )

    order_expiration_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minutes until pending order expires"
    )

    payout_delay_hours = models.PositiveIntegerField(
        default=24,
        help_text="Hours to wait after payment before processing payout"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Admin who last updated config"
    )

    class Meta:
        db_table = "core_platform_config"
        verbose_name = "Platform Configuration"
        verbose_name_plural = "Platform Configurations"
        ordering = ['-created_at']

    def __str__(self):
        status = "ACTIVE" if self.is_active else "Inactive"
        return f"Platform Config ({status}) - {self.fee_percentage}% fee"

    def save(self, *args, **kwargs):
        """Ensure only one active config exists"""
        if self.is_active:
            # Deactivate all other configs (exclude self to avoid deactivating before save)
            PlatformConfig.objects.exclude(pk=self.pk).filter(
                is_active=True
            ).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Get the active platform configuration"""
        config, created = cls.objects.get_or_create(
            is_active=True,
            defaults={'fee_percentage': 2.00}
        )
        return config

    @classmethod
    def get_platform_fee_percentage(cls):
        """Get current platform fee percentage as decimal (e.g., 0.02 for 2%)"""
        config = cls.get_active()
        return config.fee_percentage / Decimal('100.00')
