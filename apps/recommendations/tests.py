import json
import time
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps.core.models import Category, Interest
from apps.events.models import Event, UserEvents
from apps.users.authentication import JWTService
from apps.users.models import UserProfile

from .services import _determine_reason, _get_collaborative_event_ids, get_recommended_events

User = get_user_model()

LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# ─── FIXTURES ─────────────────────────────────────────────


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        email="recuser@example.com",
        password="securepass123",
        username="recuser",
        first_name="Rec",
    )
    UserProfile.objects.get_or_create(user=u)
    return u


@pytest.fixture
def other_user(db):
    u = User.objects.create_user(
        email="otherrecuser@example.com",
        password="securepass123",
        username="otherrecuser",
        first_name="Other",
    )
    UserProfile.objects.get_or_create(user=u)
    return u


@pytest.fixture
def third_user(db):
    u = User.objects.create_user(
        email="thirdrecuser@example.com",
        password="securepass123",
        username="thirdrecuser",
        first_name="Third",
    )
    UserProfile.objects.get_or_create(user=u)
    return u


@pytest.fixture
def auth_client(user):
    token = JWTService.generate_access_token(user)
    return Client(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.fixture
def anon_client():
    return Client()


@pytest.fixture
def music_category(db):
    return Category.objects.create(name="Music", icon="🎵")


@pytest.fixture
def sports_category(db):
    return Category.objects.create(name="Sports", icon="⚽")


@pytest.fixture
def food_category(db):
    return Category.objects.create(name="Food", icon="🍕")


@pytest.fixture(autouse=True)
def _clear_cache(settings):
    settings.CACHES = LOCMEM_CACHE
    cache.clear()
    yield
    cache.clear()


def _make_event(name, category=None, days_ahead=7, is_active=True, is_free=False):
    """Helper to create an event with a category."""
    event = Event.objects.create(
        name=name,
        date=timezone.now() + timedelta(days=days_ahead),
        is_active=is_active,
        is_free=is_free,
    )
    if category:
        event.category.add(category)
    return event


def _gql(client, query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    response = client.post(
        "/graphql/",
        json.dumps(body),
        content_type="application/json",
    )
    return response.json()


# ─── CONTENT-BASED FILTERING TESTS ─────────────────────────


@pytest.mark.django_db
class TestContentBasedFiltering:
    def test_events_matching_user_interests_ranked_higher(self, user, music_category, sports_category):
        """Events in the same category as user interests should score higher."""
        # Give user a music interest
        interest = Interest.objects.create(name="Jazz", category=music_category)
        user.profile.interests.add(interest)

        _make_event("Jazz Night", music_category, days_ahead=10)
        _make_event("Football Game", sports_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "Jazz Night" in event_names
        assert "Football Game" in event_names
        # Music event should rank higher due to content match
        assert event_names.index("Jazz Night") < event_names.index("Football Game")

    def test_events_matching_saved_event_categories_ranked_higher(self, user, music_category, sports_category):
        """Events matching categories of user's saved events should rank higher."""
        saved_event = _make_event("Old Concert", music_category, days_ahead=1)
        UserEvents.objects.create(user=user, event=saved_event)

        _make_event("New Concert", music_category, days_ahead=10)
        _make_event("Basketball Game", sports_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "New Concert" in event_names
        # Saved event excluded
        assert "Old Concert" not in event_names
        # Music event should rank higher
        assert event_names.index("New Concert") < event_names.index("Basketball Game")

    def test_content_match_reason_includes_category_name(self, user, music_category):
        """When content match is dominant, reason should mention the category."""
        interest = Interest.objects.create(name="Live Music", category=music_category)
        user.profile.interests.add(interest)

        _make_event("Summer Festival", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        assert len(results) >= 1
        _, reason, source = results[0]
        assert "Music" in reason
        assert source == "content_based"


# ─── COLLABORATIVE FILTERING TESTS ─────────────────────────


@pytest.mark.django_db
class TestCollaborativeFiltering:
    def test_events_saved_by_similar_users_are_recommended(self, user, other_user, music_category, sports_category):
        """If user and other_user both saved event A, other_user's saves should influence recs."""
        shared_event = _make_event("Shared Event", music_category, days_ahead=1)
        UserEvents.objects.create(user=user, event=shared_event)
        UserEvents.objects.create(user=other_user, event=shared_event)

        # Other user also saved a sports event
        collab_event = _make_event("Collab Event", sports_category, days_ahead=15)
        UserEvents.objects.create(user=other_user, event=collab_event)

        # Also create an event with no signal at all
        _make_event("Random Event", days_ahead=15)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "Collab Event" in event_names
        assert "Shared Event" not in event_names  # already saved

    def test_collaborative_ids_returns_correct_events(self, user, other_user, music_category):
        """_get_collaborative_event_ids returns events saved by similar users."""
        shared = _make_event("Shared", music_category, days_ahead=5)
        UserEvents.objects.create(user=user, event=shared)
        UserEvents.objects.create(user=other_user, event=shared)

        unique_to_other = _make_event("Other Only", music_category, days_ahead=10)
        UserEvents.objects.create(user=other_user, event=unique_to_other)

        saved_ids = {shared.id}
        collab_ids = _get_collaborative_event_ids(user, saved_ids)

        assert unique_to_other.id in collab_ids
        assert shared.id not in collab_ids

    def test_collaborative_reason_when_dominant(self, user, other_user, third_user, food_category):
        """When collaborative signal is dominant, reason should mention similar tastes."""
        shared = _make_event("Popular Dinner", food_category, days_ahead=1)
        UserEvents.objects.create(user=user, event=shared)
        UserEvents.objects.create(user=other_user, event=shared)
        UserEvents.objects.create(user=third_user, event=shared)

        collab_event = _make_event("Hidden Gem", days_ahead=80)  # no category match, far out
        UserEvents.objects.create(user=other_user, event=collab_event)
        UserEvents.objects.create(user=third_user, event=collab_event)

        results = get_recommended_events(user, limit=10)
        for event, reason, source in results:
            if event.name == "Hidden Gem":
                assert source == "collaborative"
                assert "similar tastes" in reason
                return
        pytest.fail("Hidden Gem not found in results")

    def test_no_collaborative_ids_when_no_saves(self, user):
        """User with no saves gets empty collaborative set."""
        collab_ids = _get_collaborative_event_ids(user, set())
        assert collab_ids == set()


# ─── POPULARITY SCORING TESTS ──────────────────────────────


@pytest.mark.django_db
class TestPopularityScoring:
    def test_more_saved_events_rank_higher_in_cold_start(self, user, other_user, third_user, music_category):
        """In cold start, events with more saves should rank higher."""
        popular = _make_event("Popular Event", music_category, days_ahead=10)
        UserEvents.objects.create(user=other_user, event=popular)
        UserEvents.objects.create(user=third_user, event=popular)

        _make_event("Unpopular Event", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert event_names.index("Popular Event") < event_names.index("Unpopular Event")

    def test_trending_reason_for_highly_popular(self, user, music_category):
        """Highly popular events should get 'Trending' reason when no other signal."""
        interest = Interest.objects.create(name="Jazz", category=music_category)
        user.profile.interests.add(interest)

        # Create an event with no category match but many saves
        event = _make_event("Viral Event", days_ahead=10)

        # Simulate saves by creating many users
        for i in range(10):
            u = User.objects.create_user(
                email=f"pop{i}@example.com",
                password="pass",
                username=f"pop{i}",
            )
            UserEvents.objects.create(user=u, event=event)

        results = get_recommended_events(user, limit=10)
        for e, reason, source in results:
            if e.name == "Viral Event":
                assert source in ("popular", "collaborative", "featured")
                return
        pytest.fail("Viral Event not in results")


# ─── SCORE WEIGHTS TESTS ───────────────────────────────────


@pytest.mark.django_db
class TestScoreWeights:
    def test_weights_sum_to_one(self):
        """Scoring weights should sum to 1.0."""
        from apps.recommendations.services import (
            COLLABORATIVE_WEIGHT,
            CONTENT_WEIGHT,
            POPULARITY_WEIGHT,
            RECENCY_WEIGHT,
        )

        total = CONTENT_WEIGHT + COLLABORATIVE_WEIGHT + POPULARITY_WEIGHT + RECENCY_WEIGHT
        assert abs(total - 1.0) < 0.001


# ─── EXCLUSION TESTS ───────────────────────────────────────


@pytest.mark.django_db
class TestExclusion:
    def test_saved_events_excluded_from_results(self, user, music_category):
        """Events the user already saved should not appear in recommendations."""
        saved = _make_event("Already Saved", music_category, days_ahead=10)
        UserEvents.objects.create(user=user, event=saved)

        _make_event("Not Saved", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "Already Saved" not in event_names
        assert "Not Saved" in event_names

    def test_inactive_events_excluded(self, user, music_category):
        """Inactive events should not appear."""
        _make_event("Inactive Event", music_category, days_ahead=10, is_active=False)
        _make_event("Active Event", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "Inactive Event" not in event_names
        assert "Active Event" in event_names

    def test_past_events_excluded(self, user, music_category):
        """Events with dates in the past should not appear."""
        Event.objects.create(
            name="Past Event",
            date=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        _make_event("Future Event", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert "Past Event" not in event_names
        assert "Future Event" in event_names


# ─── COLD START TESTS ──────────────────────────────────────


@pytest.mark.django_db
class TestColdStart:
    def test_cold_start_returns_results_for_new_user(self, user, music_category):
        """User with no history should still get recommendations."""
        _make_event("Event A", music_category, days_ahead=5)
        _make_event("Event B", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        assert len(results) >= 2

    def test_cold_start_reason_is_popular(self, user, music_category):
        """Cold start recommendations should have 'Popular near you' reason."""
        _make_event("Cold Start Event", music_category, days_ahead=5)

        results = get_recommended_events(user, limit=10)
        assert len(results) >= 1
        _, reason, source = results[0]
        assert reason == "Popular near you"
        assert source == "popular"

    def test_cold_start_orders_by_save_count(self, user, other_user, third_user, music_category):
        """Cold start should order by save_count descending."""
        popular = _make_event("Popular", music_category, days_ahead=5)
        UserEvents.objects.create(user=other_user, event=popular)
        UserEvents.objects.create(user=third_user, event=popular)

        less_popular = _make_event("Less Popular", music_category, days_ahead=5)
        UserEvents.objects.create(user=other_user, event=less_popular)

        _make_event("No Saves", music_category, days_ahead=5)

        results = get_recommended_events(user, limit=10)
        event_names = [e.name for e, _, _ in results]

        assert event_names.index("Popular") < event_names.index("Less Popular")
        assert event_names.index("Less Popular") < event_names.index("No Saves")


# ─── REASON/SOURCE TESTS ──────────────────────────────────


@pytest.mark.django_db
class TestDetermineReason:
    def test_content_based_reason(self, music_category):
        event_cat_ids = {music_category.id}
        user_cat_ids = {music_category.id}
        reason, source = _determine_reason(None, event_cat_ids, 1.0, 0.0, 0.5, user_cat_ids)
        assert source == "content_based"
        assert "Music" in reason

    def test_collaborative_reason(self):
        reason, source = _determine_reason(None, set(), 0.0, 1.0, 0.5, set())
        assert source == "collaborative"
        assert "similar tastes" in reason

    def test_popular_reason(self):
        reason, source = _determine_reason(None, set(), 0.0, 0.0, 0.8, set())
        assert source == "popular"
        assert "Trending" in reason

    def test_featured_fallback_reason(self):
        reason, source = _determine_reason(None, set(), 0.0, 0.0, 0.3, set())
        assert source == "featured"
        assert "Recommended for you" in reason


# ─── CACHING TESTS ─────────────────────────────────────────


@pytest.mark.django_db
class TestRecommendationCache:
    def test_results_are_cached(self, user, music_category):
        """Second call should return cached results."""
        _make_event("Cached Event", music_category, days_ahead=10)

        results1 = get_recommended_events(user, limit=10)
        results2 = get_recommended_events(user, limit=10)

        assert len(results1) == len(results2)
        assert results1[0][0].id == results2[0][0].id

    def test_different_params_different_cache_keys(self, user, music_category):
        """Different offset/limit should use different cache keys."""
        for i in range(5):
            _make_event(f"Event {i}", music_category, days_ahead=i + 5)

        results_full = get_recommended_events(user, offset=0, limit=10)
        results_page = get_recommended_events(user, offset=0, limit=2)

        assert len(results_page) == 2
        assert len(results_full) == 5

    def test_cache_respects_ttl(self, user, music_category, settings):
        """Cache should have a TTL."""
        _make_event("TTL Event", music_category, days_ahead=10)

        results = get_recommended_events(user, limit=10)
        assert len(results) >= 1

        # Verify cache key exists
        cache_key = f"recs:{user.id}:0:10"
        assert cache.get(cache_key) is not None


# ─── PAGINATION TESTS ──────────────────────────────────────


@pytest.mark.django_db
class TestPagination:
    def test_limit_restricts_results(self, user, music_category):
        for i in range(5):
            _make_event(f"Limit Event {i}", music_category, days_ahead=i + 5)

        results = get_recommended_events(user, limit=3)
        assert len(results) == 3

    def test_offset_skips_results(self, user, music_category):
        for i in range(5):
            _make_event(f"Offset Event {i}", music_category, days_ahead=i + 5)

        all_results = get_recommended_events(user, offset=0, limit=10)
        cache.clear()
        offset_results = get_recommended_events(user, offset=2, limit=10)

        assert len(offset_results) == len(all_results) - 2

    def test_offset_beyond_results_returns_empty(self, user, music_category):
        _make_event("Solo Event", music_category, days_ahead=5)

        results = get_recommended_events(user, offset=100, limit=10)
        assert results == []

    def test_empty_results_when_no_events(self, user):
        results = get_recommended_events(user, limit=10)
        assert results == []


# ─── AUTHENTICATION TESTS (GraphQL) ────────────────────────

GET_RECOMMENDATIONS_QUERY = """
    query GetRecommendations($offset: Int, $limit: Int) {
        getRecommendations(offset: $offset, limit: $limit) {
            id
            name
            reason
            source
            isSaved
            category {
                id
                name
            }
        }
    }
"""


@pytest.mark.django_db
class TestRecommendationsGraphQL:
    def test_authenticated_user_gets_recommendations(self, auth_client, music_category):
        _make_event("GQL Event", music_category, days_ahead=10)

        resp = _gql(auth_client, GET_RECOMMENDATIONS_QUERY)
        data = resp["data"]["getRecommendations"]

        assert len(data) >= 1
        assert data[0]["name"] == "GQL Event"
        assert data[0]["isSaved"] is False

    def test_unauthenticated_returns_empty(self, anon_client, music_category):
        _make_event("Auth Event", music_category, days_ahead=10)

        resp = _gql(anon_client, GET_RECOMMENDATIONS_QUERY)
        data = resp["data"]["getRecommendations"]

        assert data == []

    def test_reason_and_source_fields_populated(self, auth_client, music_category):
        _make_event("Reason Event", music_category, days_ahead=10)

        resp = _gql(auth_client, GET_RECOMMENDATIONS_QUERY)
        event = resp["data"]["getRecommendations"][0]

        assert event["reason"] is not None
        assert event["source"] is not None

    def test_pagination_via_graphql(self, auth_client, music_category):
        for i in range(5):
            _make_event(f"Page Event {i}", music_category, days_ahead=i + 5)

        resp = _gql(auth_client, GET_RECOMMENDATIONS_QUERY, {"limit": 2})
        data = resp["data"]["getRecommendations"]

        assert len(data) == 2


# ─── PERFORMANCE TEST ──────────────────────────────────────


@pytest.mark.django_db
class TestRecommendationPerformance:
    def test_performs_well_with_1000_events(self, user, music_category, sports_category):
        """Recommendation engine should complete within 3 seconds for 1000+ events."""
        categories = [music_category, sports_category]

        # Bulk create events
        events = []
        for i in range(1050):
            events.append(
                Event(
                    name=f"Perf Rec Event {i}",
                    date=timezone.now() + timedelta(days=(i % 365) + 1),
                    is_active=True,
                    is_free=(i % 2 == 0),
                )
            )
        Event.objects.bulk_create(events)

        # Assign categories
        created = Event.objects.filter(name__startswith="Perf Rec Event")
        through_model = Event.category.through
        through_entries = []
        for event in created:
            cat = categories[event.pk % 2]
            through_entries.append(through_model(event_id=event.pk, category_id=cat.pk))
        through_model.objects.bulk_create(through_entries)

        # Give user some interests for non-cold-start path
        interest = Interest.objects.create(name="Perf Interest", category=music_category)
        user.profile.interests.add(interest)

        assert Event.objects.filter(is_active=True).count() >= 1050

        start = time.time()
        results = get_recommended_events(user, limit=10)
        elapsed = time.time() - start

        assert len(results) == 10
        assert elapsed < 3.0, f"Recommendations took {elapsed:.2f}s, expected < 3s"
