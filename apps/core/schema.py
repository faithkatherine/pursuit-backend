import graphene
from django.core.cache import cache

from .models import Category, Interest
from .types import CategoryType, InterestType

CATEGORIES_CACHE_KEY = "core:categories"
INTERESTS_CACHE_KEY = "core:interests"
CORE_CACHE_TTL = 900  # 15 minutes


class CategoryListPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    categories = graphene.List(graphene.NonNull(CategoryType), required=True)


class InterestListPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    interests = graphene.List(graphene.NonNull(InterestType), required=True)


class CoreQueries(graphene.ObjectType):
    get_categories = graphene.Field(CategoryListPayload, required=True)
    get_interests = graphene.Field(InterestListPayload, required=True)

    def resolve_get_categories(self, info):
        categories = cache.get(CATEGORIES_CACHE_KEY)
        if categories is None:
            categories = list(Category.objects.all())
            cache.set(CATEGORIES_CACHE_KEY, categories, CORE_CACHE_TTL)
        return CategoryListPayload(ok=True, categories=categories)

    def resolve_get_interests(self, info):
        interests = cache.get(INTERESTS_CACHE_KEY)
        if interests is None:
            interests = list(Interest.objects.select_related("category").all())
            cache.set(INTERESTS_CACHE_KEY, interests, CORE_CACHE_TTL)
        return InterestListPayload(ok=True, interests=interests)
