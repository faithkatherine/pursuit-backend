import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_check(client: Client):
    """Verify the health check endpoint returns 200."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
