import pytest
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test User model"""
    
    def test_create_user(self):
        """Test creating a user"""
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User',
            password='testpassword123'
        )
        
        assert user.email == 'test@example.com'
        assert user.username == 'testuser'
        assert user.first_name == 'Test'
        assert user.last_name == 'User'
        assert user.full_name == 'Test User'
        assert user.check_password('testpassword123')
        assert not user.is_staff
        assert user.is_active
    
    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            first_name='Admin',
            last_name='User',
            password='adminpassword123'
        )
        
        assert user.email == 'admin@example.com'
        assert user.is_staff
        assert user.is_superuser
    
    def test_user_profile_created_automatically(self):
        """Test that user profile is created automatically"""
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            password='testpassword123'
        )
        
        # Profile should be created automatically via signals
        assert hasattr(user, 'profile')
        assert isinstance(user.profile, UserProfile)
