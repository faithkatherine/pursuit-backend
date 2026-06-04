import factory
from factory.django import  DjangoModelFactory
from .user_factory import UserFactory
from apps.organizers.models import OrganizerProfile

class OrganizerProfileFactory(DjangoModelFactory):
    class Meta:
        model = OrganizerProfile

    user = factory.SubFactory(UserFactory)
    bio = factory.Faker("paragraph")
    profile_picture = factory.django.ImageField(color="blue")