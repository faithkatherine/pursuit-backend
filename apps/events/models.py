from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


# Create your models here.
class Event(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    organizer = models.ForeignKey(
        "organizers.OrganizerProfile",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
        help_text="Event organizer (cannot delete organizer with events)",
    )
    category = models.ManyToManyField("core.Category", blank=True, related_name="events")
    date = models.DateTimeField(null=False, blank=False)
    end_date = models.DateTimeField(null=True, blank=True)
    image = models.URLField(null=True, blank=True)
    timezone = models.CharField(max_length=255, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    location = models.PointField(null=True, blank=True, geography=True, srid=4326)
    more_details_url = models.URLField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Ticket price in KES. 0 for free events.",
    )
    ticketing_enabled = models.BooleanField(
        default=False,
        help_text="True if tickets are sold in-app. False if event links externally.",
    )
    available_tickets = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Remaining ticket count. Null for free or externally ticketed events.",
    )
    going_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of users who have saved or are attending.",
    )
    has_gallery = models.BooleanField(
        default=False,
        help_text="True if this event has a gallery of images.",
    )
    gallery_images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs for the event gallery.",
    )
    gallery_description = models.TextField(
        null=True,
        blank=True,
        help_text="Description of the gallery content.",
    )
    series_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text=(
            "Name of the recurring series this event belongs to. "
            "e.g. 'Blankets & Wine'. Soft reference only — no FK. "
            "Full series model is V2."
        ),
    )
    is_free = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('live', 'Live'),
        ('cancelled', 'Cancelled'),   # triggers payout freeze + refunds
        ('ended', 'Ended'),           # event date passed, payouts released
    ], default='draft')

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def starting_price(self):
        """Cheapest active tier price."""
        from django.db.models import Min

        result = self.ticket_tiers.filter(is_active=True).aggregate(min_price=Min("price"))
        return result["min_price"]

    @property
    def total_available(self):
        """Sum of available tickets across active tiers."""
        from django.db.models import Sum

        result = self.ticket_tiers.filter(is_active=True).aggregate(total=Sum("available"))
        return result["total"] or 0

    def save(self, *args, **kwargs):
        self.is_free = self.price == 0
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.date:
            raise ValidationError(message="End date cannot be before start date.")

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["location"]),
            models.Index(fields=["is_active", "date"]),
            models.Index(fields=["is_free", "date"]),
        ]


class EditorsPick(models.Model):
    """Curated Editor's Pick events scoped by location tag"""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="editors_picks")
    location_tag = models.CharField(
        max_length=100, db_index=True, help_text="Location scope for this pick (e.g., 'nairobi', 'mombasa')"
    )
    active_from = models.DateTimeField(help_text="When this pick becomes active")
    active_until = models.DateTimeField(help_text="When this pick expires")
    curator_note = models.TextField(help_text="Required editorial note explaining why this event is featured")
    curator_name = models.CharField(
        max_length=100,
        blank=True,
        default="Pursuit team",
        help_text="Attribution for the curator (e.g., 'Pursuit team', 'Jane Doe')",
    )
    position = models.PositiveSmallIntegerField(
        default=1, help_text="Reserved for future multi-pick surfaces; v1 always uses position=1"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-active_from", "position"]
        verbose_name = "Editor's Pick"
        verbose_name_plural = "Editor's Picks"
        indexes = [
            models.Index(fields=["location_tag", "active_from"]),
            models.Index(fields=["active_from", "active_until"]),
        ]

    def save(self, *args, **kwargs):
        # Normalize location_tag for reliable matching
        if self.location_tag:
            self.location_tag = self.location_tag.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event.name} — {self.location_tag} ({self.active_from.date()})"

class TicketTier(models.Model):
    """Ticket tier for events with multiple pricing levels"""

    event = models.ForeignKey(
        "Event",
        on_delete=models.PROTECT,
        related_name="ticket_tiers",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.PositiveIntegerField()
    available = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price"]
        unique_together = [["event", "name"]]
        verbose_name = "Ticket Tier"
        verbose_name_plural = "Ticket Tiers"

    def __str__(self):
        return f"{self.event.name} — {self.name} (KES {self.price})"


class UserEvents(models.Model):
    """Track user interactions with events for personalization"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_events")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="user_interactions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_user_events"
        verbose_name = _("User's Saved Event")
        verbose_name_plural = _("User's Saved Events")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["event"]),
        ]
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user.email} saved {self.event.name}"
