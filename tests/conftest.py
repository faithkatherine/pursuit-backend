import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from apps.users.authentication import JWTService

User = get_user_model()


@pytest.fixture
def client():
    """Django test client"""
    return Client()


@pytest.fixture
def api_client():
    """DRF API client"""
    return APIClient()


@pytest.fixture
def user():
    """Test user"""
    return User.objects.create_user(
        email='test@example.com',
        username='testuser',
        first_name='Test',
        last_name='User',
        password='testpassword123'
    )


@pytest.fixture
def authenticated_api_client(api_client, user):
    """API client with authenticated user"""
    token = JWTService.generate_access_token(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client


@pytest.fixture
def superuser():
    """Test superuser"""
    return User.objects.create_superuser(
        email='admin@example.com',
        username='admin',
        first_name='Admin',
        last_name='User',
        password='adminpassword123'
    )
