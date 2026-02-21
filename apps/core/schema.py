import graphene

from .models import Category, Interest
from .types import CategoryType, InterestType


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
        return CategoryListPayload(
            ok=True,
            categories=Category.objects.all(),
        )

    def resolve_get_interests(self, info):
        return InterestListPayload(
            ok=True,
            interests=Interest.objects.all(),
        )
