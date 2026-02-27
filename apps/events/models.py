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
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.date:
            raise ValidationError("End date cannot be before start date.")

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["location"]),
            models.Index(fields=["is_active", "date"]),
        ]


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
