from django.core.exceptions import ValidationError
from django.db import models

from apps.users.models import User


class Trip(models.Model):
    """A user-created trip grouping saved events into an itinerary."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trips")
    name = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    image = models.URLField(null=True, blank=True)
    events = models.ManyToManyField("events.Event", blank=True, related_name="trips")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} — {self.user.email}"

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["user", "start_date"]),
        ]
