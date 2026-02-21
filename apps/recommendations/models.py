from django.contrib.auth import get_user_model
from django.contrib.gis.db import models

from apps.core.models import Category, TimeStampedModel

User = get_user_model()


class Recommendation(TimeStampedModel):
    """Recommendation model for bucket items"""

    RECOMMENDATION_TYPE_CHOICES = [
        ("destination", "Destination"),
        ("activity", "Activity"),
        ("experience", "Experience"),
        ("event", "Event"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.URLField(max_length=200, blank=True, null=True)

    # Location
    location_name = models.CharField(max_length=200)
    coordinates = models.PointField(geography=True, blank=True, null=True)

    # Details
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPE_CHOICES, default="activity")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="recommendations"
    )

    # Pricing and timing
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default="USD")
    best_time_to_visit = models.CharField(max_length=100, blank=True)
    duration = models.CharField(max_length=100, blank=True)  # e.g., "2-3 hours", "1 day"

    # Metadata
    difficulty_level = models.CharField(max_length=50, blank=True)
    popularity_score = models.FloatField(default=0.0)
    rating = models.FloatField(blank=True, null=True)

    # Admin fields
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # External links
    website_url = models.URLField(blank=True)
    booking_url = models.URLField(blank=True)

    class Meta:
        db_table = "recommendations_recommendation"
        verbose_name = "Recommendation"
        verbose_name_plural = "Recommendations"
        ordering = ["-popularity_score", "-created_at"]
        indexes = [
            models.Index(fields=["recommendation_type"]),
            models.Index(fields=["category"]),
            models.Index(fields=["location_name"]),
            models.Index(fields=["is_featured", "is_active"]),
            models.Index(fields=["-popularity_score"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.location_name}"

    @property
    def amount(self):
        """Alias for estimated_cost to match frontend expectations"""
        return self.estimated_cost

    @property
    def date(self):
        """Return formatted date for frontend"""
        return self.created_at.strftime("%Y-%m-%d") if self.created_at else None

    def get_image_url(self):
        """Get image URL or return None"""
        return self.image if self.image else None


class UserRecommendation(TimeStampedModel):
    """Track user interactions with recommendations"""

    ACTION_CHOICES = [
        ("viewed", "Viewed"),
        ("liked", "Liked"),
        ("saved", "Saved"),
        ("added_to_bucket", "Added to Bucket"),
        ("dismissed", "Dismissed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recommendation_interactions")
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name="user_interactions")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    class Meta:
        db_table = "recommendations_user_recommendation"
        verbose_name = "User Recommendation"
        verbose_name_plural = "User Recommendations"
        unique_together = ["user", "recommendation", "action"]
        indexes = [
            models.Index(fields=["user", "action"]),
            models.Index(fields=["recommendation"]),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.action} {self.recommendation.title}"


class RecommendationTag(TimeStampedModel):
    """Tags for recommendations"""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#007AFF")

    class Meta:
        db_table = "recommendations_tag"
        verbose_name = "Recommendation Tag"
        verbose_name_plural = "Recommendation Tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecommendationTagRelation(models.Model):
    """Many-to-many relationship between recommendations and tags"""

    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name="tag_relations")
    tag = models.ForeignKey(RecommendationTag, on_delete=models.CASCADE, related_name="recommendation_relations")

    class Meta:
        db_table = "recommendations_recommendation_tags"
        unique_together = ["recommendation", "tag"]

    def __str__(self):
        return f"{self.recommendation.title} - {self.tag.name}"
