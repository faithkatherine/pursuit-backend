from django.db import models

from apps.core.models import TimeStampedModel

# Insights app is a query-layer-only app that aggregates data from other apps.
# Models here serve infrastructure purposes (caching, temporary data) only.
# Analytics and stats should be computed on-the-fly or stored in their respective domain apps.


class WeatherData(TimeStampedModel):
    """Weather data cache for external API responses"""

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
