from graphene_django import DjangoObjectType

from .models import Category, Interest


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "icon",
            "description",
            "color",
            "is_active",
            "sort_order",
        )


class InterestType(DjangoObjectType):
    class Meta:
        model = Interest
        fields = "__all__"
