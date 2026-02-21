import graphene
from graphene_django import DjangoObjectType
from .models import Category, Interest

class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = "__all__"

class InterestType(DjangoObjectType):
    class Meta:
        model = Interest
        fields = "__all__"
