from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import TimeStampedModel

User = get_user_model()


class Neighborhood(models.Model):
    """Neighborhoods for location-based filtering on the home feed."""

    name = models.CharField(max_length=100, unique=True)
    city = models.CharField(max_length=100, default="Nairobi")
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)

    class Meta:
        db_table = "insights_neighborhood"
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}, {self.city}"


class WeatherData(TimeStampedModel):
    """Weather data for locations"""

    city = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)
    temperature = models.FloatField()
    icon = models.CharField(max_length=10, blank=True, default="01d")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)

    class Meta:
        db_table = "insights_weather_data"
        verbose_name = "Weather Data"
        verbose_name_plural = "Weather Data"
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.city} - {self.condition} - {self.temperature}°"


class UserInsight(TimeStampedModel):
    """User insights and analytics"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="insights")

    # Progress metrics
    total_bucket_items = models.PositiveIntegerField(default=0)
    completed_items = models.PositiveIntegerField(default=0)
    yearly_goal = models.PositiveIntegerField(default=12)

    # Location data
    current_city = models.CharField(max_length=100, blank=True)
    next_destination = models.CharField(max_length=200, blank=True)
    days_to_next_trip = models.PositiveIntegerField(blank=True, null=True)

    # Achievements
    recent_achievement = models.CharField(max_length=200, blank=True)
    total_countries_visited = models.PositiveIntegerField(default=0)
    total_experiences = models.PositiveIntegerField(default=0)

    # Spending insights
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_cost_per_item = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = "insights_user_insight"
        verbose_name = "User Insight"
        verbose_name_plural = "User Insights"
        unique_together = ["user"]

    def __str__(self):
        return f"Insights for {self.user.first_name}"

    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.yearly_goal == 0:
            return 0
        return min(int((self.completed_items / self.yearly_goal) * 100), 100)

    @property
    def remaining_items(self):
        """Calculate remaining items to reach yearly goal"""
        return max(0, self.yearly_goal - self.completed_items)
