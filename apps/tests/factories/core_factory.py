import factory
from factory.django import DjangoModelFactory

from apps.core.models import Category, Interest


class CategoryFactory(DjangoModelFactory):
    """
    Creates a Category.

    Usage:
        cat = CategoryFactory()
        cat = CategoryFactory(name="Music", icon="🎵")
    """

    class Meta:
        model = Category
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Category {n}")
    icon = "🎯"
    description = factory.Faker("sentence")


class InterestFactory(DjangoModelFactory):
    """
    Creates an Interest linked to a Category.

    Usage:
        interest = InterestFactory()
        interest = InterestFactory(name="Hiking", category=some_category)
    """

    class Meta:
        model = Interest

    name = factory.Sequence(lambda n: f"Interest {n}")
    icon = "✨"
    description = factory.Faker("sentence")
    category = factory.SubFactory(CategoryFactory)
