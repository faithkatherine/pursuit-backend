from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category, Interest


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, **kwargs):
    cache.delete("core:categories")


@receiver([post_save, post_delete], sender=Interest)
def invalidate_interest_cache(sender, **kwargs):
    cache.delete("core:interests")
