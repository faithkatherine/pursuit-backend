import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """
    Creates a User with an auto-created UserProfile (via signal).

    Usage:
        user = UserFactory()
        user = UserFactory(email="custom@example.com")
        user = UserFactory.create(first_name="Alice")
    """

    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpassword123")
