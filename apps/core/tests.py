import pytest
from django.test import Client

from apps.core.models import Category, Interest
from apps.core.schema import CATEGORIES_CACHE_KEY, INTERESTS_CACHE_KEY, CoreQueries


@pytest.mark.django_db
def test_health_check(client: Client):
    """Verify the health check endpoint returns 200."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data


# ─── FIXTURES ─────────────────────────────────────────────


@pytest.fixture
def category(db):
    return Category.objects.create(name="Travel", icon="✈️", description="Travel destinations")


@pytest.fixture
def interest(db, category):
    return Interest.objects.create(
        name="Hiking",
        icon="🥾",
        description="Outdoor hiking",
        category=category,
    )


# ─── CACHE TESTS ────────────────────────────────────────

LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.mark.django_db
class TestCategoriesCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self, settings):
        settings.CACHES = LOCMEM_CACHE
        from django.core.cache import cache

        cache.clear()

    def test_cache_miss_then_hit(self, category):
        from django.core.cache import cache

        assert cache.get(CATEGORIES_CACHE_KEY) is None

        result = CoreQueries.resolve_get_categories(None, info=None)
        assert result.ok is True
        assert len(result.categories) == 1

        cached = cache.get(CATEGORIES_CACHE_KEY)
        assert cached is not None
        assert len(cached) == 1

    def test_second_call_uses_cache(self, category):
        from django.core.cache import cache

        # First call populates cache
        CoreQueries.resolve_get_categories(None, info=None)
        assert cache.get(CATEGORIES_CACHE_KEY) is not None

        # Delete from DB — second call should still return cached data
        Category.objects.all().delete()
        # Re-seed cache since delete signal cleared it
        cache.set(CATEGORIES_CACHE_KEY, [category])

        result = CoreQueries.resolve_get_categories(None, info=None)
        assert len(result.categories) == 1

    def test_cache_invalidated_on_category_save(self, category):
        from django.core.cache import cache

        cache.set(CATEGORIES_CACHE_KEY, [category])
        assert cache.get(CATEGORIES_CACHE_KEY) is not None

        category.name = "Updated"
        category.save()

        assert cache.get(CATEGORIES_CACHE_KEY) is None

    def test_cache_invalidated_on_category_delete(self, category):
        from django.core.cache import cache

        cache.set(CATEGORIES_CACHE_KEY, [category])

        category.delete()

        assert cache.get(CATEGORIES_CACHE_KEY) is None


@pytest.mark.django_db
class TestInterestsCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self, settings):
        settings.CACHES = LOCMEM_CACHE
        from django.core.cache import cache

        cache.clear()

    def test_cache_miss_then_hit(self, interest):
        from django.core.cache import cache

        assert cache.get(INTERESTS_CACHE_KEY) is None

        result = CoreQueries.resolve_get_interests(None, info=None)
        assert result.ok is True
        assert len(result.interests) == 1

        cached = cache.get(INTERESTS_CACHE_KEY)
        assert cached is not None
        assert len(cached) == 1

    def test_interest_has_category(self, interest):
        result = CoreQueries.resolve_get_interests(None, info=None)
        fetched = result.interests[0]
        assert fetched.category is not None
        assert fetched.category.name == "Travel"

    def test_cache_invalidated_on_interest_save(self, interest):
        from django.core.cache import cache

        cache.set(INTERESTS_CACHE_KEY, [interest])
        assert cache.get(INTERESTS_CACHE_KEY) is not None

        interest.name = "Updated Hiking"
        interest.save()

        assert cache.get(INTERESTS_CACHE_KEY) is None

    def test_cache_invalidated_on_interest_delete(self, interest):
        from django.core.cache import cache

        cache.set(INTERESTS_CACHE_KEY, [interest])

        interest.delete()

        assert cache.get(INTERESTS_CACHE_KEY) is None

    def test_cached_response_matches_fresh(self, interest):
        result1 = CoreQueries.resolve_get_interests(None, info=None)
        result2 = CoreQueries.resolve_get_interests(None, info=None)

        ids1 = [i.pk for i in result1.interests]
        ids2 = [i.pk for i in result2.interests]
        assert ids1 == ids2
