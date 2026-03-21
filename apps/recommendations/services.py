"""
Personalized event recommendation engine:
- Content-based filtering (user interests + saved event categories)
- Collaborative filtering (similar users' preferences)
- Popularity-based scoring
- Recency scoring (sooner events rank higher)
- Cold-start fallback (popular events)
"""

import logging
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

# Scoring weights
CONTENT_WEIGHT = 0.4
COLLABORATIVE_WEIGHT = 0.3
POPULARITY_WEIGHT = 0.2
RECENCY_WEIGHT = 0.1

CACHE_TTL = 600  # 10 minutes
MIN_RESULTS = 3  # backfill with popular events if fewer than this


def get_recommended_events(user, offset=0, limit=10):
    """
    Returns a list of (Event, reason_str, source_str) tuples
    personalized for the given user.
    """
    cache_key = f"recs:{user.id}:{offset}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.events.models import Event, UserEvents

    now = timezone.now()

    # IDs of events the user already saved
    saved_event_ids = set(
        UserEvents.objects.filter(user=user).values_list("event_id", flat=True)
    )

    # Build candidate queryset: active, future, not already saved
    candidates = (
        Event.objects.filter(is_active=True, date__gte=now)
        .exclude(id__in=saved_event_ids)
        .annotate(save_count=Count("user_interactions"))
        .prefetch_related("category")
    )

    if not candidates.exists():
        cache.set(cache_key, [], CACHE_TTL)
        return []

    # Gather user category signals
    profile = getattr(user, "profile", None)
    user_category_ids = set()

    # From onboarding interests
    if profile:
        interest_category_ids = set(
            profile.interests.exclude(category__isnull=True).values_list(
                "category_id", flat=True
            )
        )
        user_category_ids |= interest_category_ids

    # From saved events
    saved_event_category_ids = set(
        UserEvents.objects.filter(user=user).values_list(
            "event__category__id", flat=True
        )
    )
    user_category_ids |= saved_event_category_ids
    user_category_ids.discard(None)

    has_history = bool(user_category_ids)

    if not has_history:
        # Cold start: return by popularity
        results = [
            (event, "Popular near you", "popular")
            for event in candidates.order_by("-save_count")[offset : offset + limit]
        ]
        cache.set(cache_key, results, CACHE_TTL)
        return results

    target_count = min(limit, MIN_RESULTS)

    # Collaborative filtering set
    collaborative_ids = _get_collaborative_event_ids(user, saved_event_ids)

    # Max save count for normalization
    max_save_count = max((c.save_count for c in candidates), default=1) or 1

    scored = []
    for event in candidates:
        # Content score: does event share a category with user interests?
        event_category_ids = set(event.category.values_list("id", flat=True))
        content_score = 1.0 if event_category_ids & user_category_ids else 0.0

        # Collaborative score
        collab_score = 1.0 if event.id in collaborative_ids else 0.0

        # Popularity score
        popularity_score = event.save_count / max_save_count

        # Recency score: sooner events score higher
        days_until = (event.date - now).days
        if days_until <= 0:
            recency_score = 1.0
        elif days_until >= 90:
            recency_score = 0.0
        else:
            recency_score = 1.0 - (days_until / 90.0)

        total = (
            CONTENT_WEIGHT * content_score
            + COLLABORATIVE_WEIGHT * collab_score
            + POPULARITY_WEIGHT * popularity_score
            + RECENCY_WEIGHT * recency_score
        )

        reason, source = _determine_reason(
            event, event_category_ids, content_score, collab_score,
            popularity_score, user_category_ids,
        )

        scored.append((event, total, reason, source))

    scored.sort(key=lambda x: x[1], reverse=True)

    results = [
        (event, reason, source)
        for event, _score, reason, source in scored[offset : offset + limit]
    ]

    # Backfill with popular events if we have fewer than target_count
    if len(results) < target_count:
        result_ids = {event.id for event, _, _ in results}
        backfill_candidates = (
            candidates.exclude(id__in=result_ids)
            .order_by("-save_count", "date")
        )
        for event in backfill_candidates[: target_count - len(results)]:
            results.append((event, "Popular near you", "popular"))

    cache.set(cache_key, results, CACHE_TTL)
    return results


def _get_collaborative_event_ids(user, saved_event_ids):
    """
    Simple collaborative filtering on events: find users who saved the same
    events as this user, then get what else those users saved.
    """
    from apps.events.models import UserEvents

    if not saved_event_ids:
        return set()

    # Users who saved the same events (limit for performance)
    similar_user_ids = set(
        UserEvents.objects.filter(event_id__in=saved_event_ids)
        .exclude(user=user)
        .values_list("user_id", flat=True)[:50]
    )

    if not similar_user_ids:
        return set()

    # Events those similar users saved (excluding ones this user already saved)
    collaborative_ids = set(
        UserEvents.objects.filter(user_id__in=similar_user_ids)
        .exclude(event_id__in=saved_event_ids)
        .values_list("event_id", flat=True)
    )

    return collaborative_ids


def _determine_reason(event, event_category_ids, content_score, collab_score,
                      popularity_score, user_category_ids):
    """Determine the human-readable reason and source type for a recommendation."""
    if content_score > 0:
        # Find the matching category name
        matching_ids = event_category_ids & user_category_ids
        if matching_ids:
            from apps.core.models import Category
            cat = Category.objects.filter(id__in=matching_ids).first()
            if cat:
                return (f"Based on your interest in {cat.name}", "content_based")
        return ("Matches your interests", "content_based")
    if collab_score > 0:
        return ("People with similar tastes enjoyed this", "collaborative")
    if popularity_score > 0.7:
        return ("Trending in your area", "popular")
    return ("Recommended for you", "featured")


def get_trending_events(user, limit=5):
    """
    Returns a list of (Event, reason_str, source_str) tuples
    for the most popular events — purely by save_count, no personalization.
    """
    cache_key = f"trending:{user.id}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.events.models import Event, UserEvents

    now = timezone.now()

    saved_event_ids = set(
        UserEvents.objects.filter(user=user).values_list("event_id", flat=True)
    )

    trending = (
        Event.objects.filter(is_active=True, date__gte=now)
        .exclude(id__in=saved_event_ids)
        .annotate(save_count=Count("user_interactions"))
        .filter(save_count__gt=0)
        .order_by("-save_count", "date")
        .prefetch_related("category")[:limit]
    )

    results = [(event, "Trending", "trending") for event in trending]
    cache.set(cache_key, results, CACHE_TTL)
    return results
