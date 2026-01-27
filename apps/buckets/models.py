from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel, Category

User = get_user_model()


class BucketList(TimeStampedModel):
    """Main bucket list model"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bucket_lists')
    name = models.CharField(max_length=100, default='My Bucket List')
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'buckets_bucket_list'
        verbose_name = 'Bucket List'
        verbose_name_plural = 'Bucket Lists'
        unique_together = ['user', 'name']
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.first_name}'s {self.name}"


class BucketItem(TimeStampedModel):
    """Individual bucket list item"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('challenging', 'Challenging'),
        ('extreme', 'Extreme'),
    ]
    
    bucket_list = models.ForeignKey(BucketList, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='bucket_items')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Media
    image = models.URLField(max_length=500, blank=True, null=True)
    
    # Location and timing
    location = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    
    # Cost and planning
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default='USD')
    target_date = models.DateField(blank=True, null=True)
    
    # Metadata
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    difficulty = models.CharField(max_length=15, choices=DIFFICULTY_CHOICES, default='moderate')
    
    # Progress tracking
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(blank=True, null=True)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    
    # Social features
    is_public = models.BooleanField(default=False)
    likes_count = models.PositiveIntegerField(default=0)
    
    # Ordering
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'buckets_bucket_item'
        verbose_name = 'Bucket Item'
        verbose_name_plural = 'Bucket Items'
        ordering = ['sort_order', '-created_at']
        indexes = [
            models.Index(fields=['bucket_list', 'is_completed']),
            models.Index(fields=['category']),
            models.Index(fields=['priority']),
            models.Index(fields=['target_date']),
            models.Index(fields=['is_public']),
            models.Index(fields=['location']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def amount(self):
        """Alias for estimated_cost to match frontend expectations"""
        return self.estimated_cost
    
    def get_image_url(self):
        """Get image URL or return None"""
        return self.image if self.image else None


class BucketItemPhoto(TimeStampedModel):
    """Additional photos for bucket items"""

    bucket_item = models.ForeignKey(BucketItem, on_delete=models.CASCADE, related_name='photos')
    image = models.URLField(max_length=500)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'buckets_bucket_item_photo'
        verbose_name = 'Bucket Item Photo'
        verbose_name_plural = 'Bucket Item Photos'
        ordering = ['-is_primary', '-created_at']
    
    def __str__(self):
        return f"Photo for {self.bucket_item.title}"


class BucketItemProgress(TimeStampedModel):
    """Track progress updates for bucket items"""

    bucket_item = models.ForeignKey(BucketItem, on_delete=models.CASCADE, related_name='progress_updates')
    title = models.CharField(max_length=200)
    description = models.TextField()
    progress_percentage = models.PositiveSmallIntegerField()
    image = models.URLField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'buckets_bucket_item_progress'
        verbose_name = 'Bucket Item Progress'
        verbose_name_plural = 'Bucket Item Progress Updates'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bucket_item.title} - {self.progress_percentage}%"


class BucketItemLike(TimeStampedModel):
    """Likes for bucket items"""
    
    bucket_item = models.ForeignKey(BucketItem, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bucket_item_likes')
    
    class Meta:
        db_table = 'buckets_bucket_item_like'
        verbose_name = 'Bucket Item Like'
        verbose_name_plural = 'Bucket Item Likes'
        unique_together = ['bucket_item', 'user']
        indexes = [
            models.Index(fields=['bucket_item']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.first_name} likes {self.bucket_item.title}"


class BucketItemComment(TimeStampedModel):
    """Comments for bucket items"""
    
    bucket_item = models.ForeignKey(BucketItem, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bucket_item_comments')
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='replies')
    
    class Meta:
        db_table = 'buckets_bucket_item_comment'
        verbose_name = 'Bucket Item Comment'
        verbose_name_plural = 'Bucket Item Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bucket_item', '-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.first_name} on {self.bucket_item.title}"
