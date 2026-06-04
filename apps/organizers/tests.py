from django.test import TestCase
import pytest

# Create your tests here.
@pytest.mark.django_db
class OrganizerProfileTestCase(TestCase):
    def setUp(self):
        # Set up any necessary data for the tests
        pass

    def test_organizer_profile_creation(self):
        # Test that an OrganizerProfile can be created successfully
        from .models import OrganizerProfile
        organizer = OrganizerProfile.objects.create(
            name="Test Organizer",
            description="This is a test organizer.",
            contact_email="test@example.com"
        )
        self.assertEqual(organizer.name, "Test Organizer")
        self.assertEqual(organizer.description, "This is a test organizer.")
        self.assertEqual(organizer.contact_email, "test@example.com")