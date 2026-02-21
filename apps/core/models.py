import uuid

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
    emoji = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007AFF')  # Hex color
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'core_category'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sort_order']),
        ]

    def __str__(self):
        return f"{self.emoji} {self.name}" if self.emoji else self.name


class Emoji(models.Model):
    """Emoji library for categories and items"""

    symbol = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True)  # e.g., 'travel', 'food', 'activities'
    unicode_value = models.CharField(max_length=20)

    class Meta:
        db_table = 'core_emoji'
        verbose_name = 'Emoji'
        verbose_name_plural = 'Emojis'
        ordering = ['category', 'description']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['symbol']),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.description}"


class Interest(models.Model):
    """Interest model for user personalization, linked to categories"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, blank=False, null=False)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='interests',
    )

    class Meta:
        db_table = 'users_interests'
        verbose_name = _('Interest')
        verbose_name_plural = _('Interests')
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name
