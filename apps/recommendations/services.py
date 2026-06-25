"""
Personalized event recommendation engine:
- Content-based filtering (user interests + saved event categories)
- Collaborative filtering (similar users' preferences)
- Popularity-based scoring
- Recency scoring (sooner events rank higher)
- Cold-start fallback (popular events)
"""

import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, OuterRef, Subquery
from django.utils import timezone

from apps.core.models import Category
from apps.events.models import Event, EventGoing, UserEvents

logger = logging.getLogger(__name__)

# Scoring weights
CONTENT_WEIGHT = 0.4
COLLABORATIVE_WEIGHT = 0.3
POPULARITY_WEIGHT = 0.2
RECENCY_WEIGHT = 0.1

CACHE_TTL = 600  # 10 minutes
MIN_RESULTS = 3  # backfill with popular events if fewer than this

# Trending constants
TRENDING_WINDOW_HOURS = 72
TRENDING_MIN_INTERACTIONS = 2


def get_recommended_events(
    user, offset=0, limit=10, date_from=None, date_to=None, exclude_event_ids=None
):
    """
    Returns a list of (Event, reason_str, source_str) tuples
    personalized for the given user.

    Args:
        exclude_event_ids: List/set of event IDs to exclude (e.g., EditorsPick already shown)
    """
    exclude_event_ids = exclude_event_ids or []
    exclude_key = ",".join(str(eid) for eid in sorted(exclude_event_ids)) if exclude_event_ids else "none"
    cache_key = f"recs:{user.id}:{offset}:{limit}:{date_from}:{date_to}:{exclude_key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = timezone.now()

    # Hard exclusions: events the user already interacted with
    saved_event_ids = set(UserEvents.objects.filter(user=user).values_list("event_id", flat=True))
    going_event_ids = set(EventGoing.objects.filter(user=user).values_list("event_id", flat=True))
    user_interaction_ids = saved_event_ids | going_event_ids

    # Build candidate queryset: active, future, not past, not already saved/going, not excluded
    candidates = (
        Event.objects.filter(is_active=True, date__gte=date_from or now)
        .exclude(status='ended')
        .exclude(id__in=user_interaction_ids)
        .annotate(save_count=Count("user_interactions"))
        .prefetch_related("category")
    )
    if exclude_event_ids:
        candidates = candidates.exclude(id__in=exclude_event_ids)
    if date_to:
        candidates = candidates.filter(date__lte=date_to)

    if not candidates.exists():
        cache.set(cache_key, [], CACHE_TTL)
        return []

    # Gather user category signals
    profile = getattr(user, "profile", None)
    user_category_ids = set()

    # From onboarding interests
    if profile:
        interest_category_ids = set(
            profile.interests.exclude(category__isnull=True).values_list("category_id", flat=True)
        )
        user_category_ids |= interest_category_ids

    # From saved events
    saved_event_category_ids = set(UserEvents.objects.filter(user=user).values_list("event__category__id", flat=True))
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
            event_category_ids,
            content_score,
            collab_score,
            popularity_score,
            user_category_ids,
        )

        scored.append((event, total, reason, source))

    scored.sort(key=lambda x: x[1], reverse=True)

    results = [(event, reason, source) for event, score, reason, source in scored[offset : offset + limit]]

    # Backfill with popular events if we have fewer than target_count
    if len(results) < target_count:
        result_ids = {event.id for event, _, _ in results}
        backfill_candidates = candidates.exclude(id__in=result_ids).order_by("-save_count", "date")
        for event in backfill_candidates[: target_count - len(results)]:
            results.append((event, "Popular near you", "popular"))

    cache.set(cache_key, results, CACHE_TTL)
    return results


def _get_collaborative_event_ids(user, saved_event_ids):
    """
    Simple collaborative filtering on events: find users who saved the same
    events as this user, then get what else those users saved.
    """
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


def _determine_reason(event_category_ids, content_score, collab_score, popularity_score, user_category_ids):
    """Determine the human-readable reason and source type for a recommendation."""
    if content_score > 0:
        # Find the matching category name
        matching_ids = event_category_ids & user_category_ids
        if matching_ids:
            cat = Category.objects.filter(id__in=matching_ids).first()
            if cat:
                return (f"Based on your interest in {cat.name}", "content_based")
        return ("Matches your interests", "content_based")
    if collab_score > 0:
        return ("People with similar tastes enjoyed this", "collaborative")
    if popularity_score > 0.7:
        return ("Trending in your area", "popular")
    return ("Recommended for you", "featured")


def get_trending_events(user, limit=5, date_from=None, date_to=None, exclude_event_ids=None):
    """
    Returns a list of (Event, reason_str, source_str) tuples
    for events with the most momentum — based on recent interactions (last 72 hours).

    Trending is a pure social signal, not personalized. Shows events gaining traction
    right now based on saves and going RSVPs from all users.

    Args:
        exclude_event_ids: List/set of event IDs to exclude (e.g., EditorsPick, recommendations)
    """
    exclude_event_ids = exclude_event_ids or []
    exclude_key = ",".join(str(eid) for eid in sorted(exclude_event_ids)) if exclude_event_ids else "none"
    cache_key = f"trending:{user.id}:{limit}:{date_from}:{date_to}:{exclude_key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = timezone.now()
    trending_cutoff = now - timedelta(hours=TRENDING_WINDOW_HOURS)

    # Count recent interactions (saves + going) from ALL users in the last 72 hours
    # We use a subquery to count distinct users who interacted with each event
    # Subquery: count unique users who saved OR went to each event in last 72 hours
    recent_saves = UserEvents.objects.filter(
        event_id=OuterRef('pk'),
        created_at__gte=trending_cutoff
    ).values('event_id').annotate(
        save_count=Count('user_id', distinct=True)
    ).values('save_count')

    recent_going = EventGoing.objects.filter(
        event_id=OuterRef('pk'),
        created_at__gte=trending_cutoff
    ).values('event_id').annotate(
        going_count=Count('user_id', distinct=True)
    ).values('going_count')

    # Build queryset: upcoming events with recent momentum
    qs = (
        Event.objects.filter(is_active=True, date__gte=date_from or now)
        .exclude(status='ended')
        .annotate(
            recent_save_count=Subquery(recent_saves),
            recent_going_count=Subquery(recent_going)
        )
    )

    if exclude_event_ids:
        qs = qs.exclude(id__in=exclude_event_ids)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # Fetch and score in Python (sum save + going, filter by threshold)
    events_with_scores = []
    for event in qs.prefetch_related("category"):
        save_count = event.recent_save_count or 0
        going_count = event.recent_going_count or 0
        total_interactions = save_count + going_count

        # Apply minimum threshold
        if total_interactions >= TRENDING_MIN_INTERACTIONS:
            events_with_scores.append((event, total_interactions))

    # Sort by interaction count descending, then by date ascending (sooner first)
    events_with_scores.sort(key=lambda x: (-x[1], x[0].date))

    # Take top N and format as results
    trending_events = [event for event, _score in events_with_scores[:limit]]
    results = [(event, "Trending", "trending") for event in trending_events]

    cache.set(cache_key, results, CACHE_TTL)
    return results
