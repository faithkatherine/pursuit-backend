from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


# Create your models here.
class Event(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    category = models.ManyToManyField("core.Category", blank=True, related_name="events")
    date = models.DateTimeField(null=False, blank=False)
    end_date = models.DateTimeField(null=True, blank=True)
    image = models.URLField(null=True, blank=True)
    timezone = models.CharField(max_length=255, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    location = models.PointField(null=True, blank=True, geography=True, srid=4326)
    more_details_url = models.URLField(null=True, blank=True)
    is_free = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

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
