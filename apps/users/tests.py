import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# ─── GRAPHQL MUTATIONS ──────────────────────────────────

SIGN_UP_MUTATION = """
mutation SignUp($email: String!, $password: String!, $firstName: String!, $lastName: String!) {
  signUp(email: $email, password: $password, firstName: $firstName, lastName: $lastName) {
    ok
    authPayload {
      accessToken
      refreshToken
      sessionToken
      user {
        id
        username
        email
      }
    }
  }
}
"""

SIGN_IN_MUTATION = """
mutation SignIn($email: String!, $password: String!) {
  signIn(email: $email, password: $password) {
    ok
    authPayload {
      accessToken
      refreshToken
      sessionToken
      user {
        id
        username
        email
      }
    }
  }
}
"""

GOOGLE_SIGN_IN_MUTATION = """
mutation GoogleSignIn($idToken: String!) {
  googleSignIn(idToken: $idToken) {
    ok
    authPayload {
      accessToken
      refreshToken
      sessionToken
      user {
        id
        username
        email
      }
    }
  }
}
"""

REFRESH_ACCESS_TOKEN_MUTATION = """
mutation RefreshAccessToken($refreshToken: String!) {
  refreshAccessToken(refreshToken: $refreshToken) {
    ok
    accessToken
    refreshToken
    expiresIn
  }
}
"""

SIGN_OUT_MUTATION = """
mutation SignOut($refreshToken: String!) {
  signOut(refreshToken: $refreshToken) {
    ok
  }
}
"""

SIGN_OUT_ALL_MUTATION = """
mutation SignOutAll($refreshToken: String!) {
  signOutAll(refreshToken: $refreshToken) {
    ok
  }
}
"""

# ─── FIXTURES ─────────────────────────────────────────────

PASSWORD = "securepass123"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="authuser@example.com",
        password=PASSWORD,
        username="authuser",
        first_name="Auth",
    )


@pytest.fixture
def unverified_user(db):
    return User.objects.create_user(
        email="unverified@example.com",
        password=PASSWORD,
        username="unverified",
        first_name="Unverified",
        is_active=True,
    )


# ─── HELPER ──────────────────────────────────────────────


def _sign_in(client, email, password=PASSWORD):
    """Sign in and return the parsed JSON response."""
    response = client.post(
        "/graphql/",
        json.dumps({
            "query": SIGN_IN_MUTATION,
            "variables": {"email": email, "password": password},
        }),
        content_type="application/json",
    )
    return response.json()


# ─── SIGN UP TESTS ──────────────────────────────────────


@pytest.mark.django_db
class TestUserSignUp:
    def test_user_sign_up(self, client):
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_UP_MUTATION,
                "variables": {
                    "email": "newuser@example.com",
                    "password": "password123",
                    "firstName": "John",
                    "lastName": "Doe",
                },
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        data = resp_json["data"]["signUp"]
        assert data["ok"] is True
        payload = data["authPayload"]
        assert payload["user"]["email"] == "newuser@example.com"
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]

    def test_user_sign_up_existing_email(self, client, user):
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_UP_MUTATION,
                "variables": {
                    "email": user.email,
                    "password": "password123",
                    "firstName": "John",
                    "lastName": "Doe",
                },
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        errors = resp_json.get("errors")
        assert errors is not None, "Expected error for existing email"
        assert any("already registered" in err["message"] for err in errors)

    def test_user_sign_up_returned_tokens(self, client):
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_UP_MUTATION,
                "variables": {
                    "email": "tokens@example.com",
                    "password": "password123",
                    "firstName": "Token",
                    "lastName": "User",
                },
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        payload = resp_json["data"]["signUp"]["authPayload"]
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]


# ─── SIGN IN TESTS ──────────────────────────────────────


@pytest.mark.django_db
class TestUserSignIn:
    def test_user_sign_in(self, client, user):
        resp_json = _sign_in(client, user.email)
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        data = resp_json["data"]["signIn"]
        assert data["ok"] is True
        payload = data["authPayload"]
        assert payload["user"]["email"] == user.email
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]

    def test_user_sign_in_invalid_credentials(self, client):
        resp_json = _sign_in(client, "nonexistent@example.com", "wrongpassword")
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Invalid email or password" in errors[0]["message"]

    def test_user_sign_in_wrong_password(self, client, user):
        resp_json = _sign_in(client, user.email, "wrongpassword")
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Invalid email or password" in errors[0]["message"]

    def test_user_sign_in_returned_tokens(self, client, user):
        resp_json = _sign_in(client, user.email)
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        payload = resp_json["data"]["signIn"]["authPayload"]
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]


# ─── GOOGLE SIGN IN TESTS ───────────────────────────────

MOCK_GOOGLE_USER = {
    "google_id": "google-123456",
    "email": "googleuser@example.com",
    "email_verified": True,
    "first_name": "Google",
    "last_name": "User",
    "picture": "https://example.com/photo.jpg",
}


@pytest.mark.django_db
class TestGoogleSignIn:
    @patch("apps.users.schema.verify_google_token")
    def test_google_sign_in_new_user(self, mock_verify, client):
        mock_verify.return_value = MOCK_GOOGLE_USER
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": GOOGLE_SIGN_IN_MUTATION,
                "variables": {"idToken": "mocked-google-id-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        data = resp_json["data"]["googleSignIn"]
        assert data["ok"] is True
        payload = data["authPayload"]
        assert payload["user"]["email"] == "googleuser@example.com"
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]

    @patch("apps.users.schema.verify_google_token")
    def test_google_sign_in_invalid_token(self, mock_verify, client):
        mock_verify.return_value = None
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": GOOGLE_SIGN_IN_MUTATION,
                "variables": {"idToken": "invalid-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Invalid Google token" in errors[0]["message"]

    @patch("apps.users.schema.verify_google_token")
    def test_google_sign_in_unverified_email(self, mock_verify, client):
        mock_verify.return_value = {**MOCK_GOOGLE_USER, "email_verified": False}
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": GOOGLE_SIGN_IN_MUTATION,
                "variables": {"idToken": "mocked-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Google email not verified" in errors[0]["message"]

    @patch("apps.users.schema.verify_google_token")
    def test_google_sign_in_returned_tokens(self, mock_verify, client):
        mock_verify.return_value = MOCK_GOOGLE_USER
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": GOOGLE_SIGN_IN_MUTATION,
                "variables": {"idToken": "mocked-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        payload = resp_json["data"]["googleSignIn"]["authPayload"]
        assert payload["accessToken"]
        assert payload["refreshToken"]
        assert payload["sessionToken"]


# ─── REFRESH TOKEN TESTS ────────────────────────────────


@pytest.mark.django_db
class TestRefreshAccessToken:
    def test_refresh_access_token(self, client, user):
        # Sign in first to get a refresh token
        sign_in_json = _sign_in(client, user.email)
        assert "errors" not in sign_in_json, f"Sign-in failed: {sign_in_json.get('errors')}"
        refresh_token = sign_in_json["data"]["signIn"]["authPayload"]["refreshToken"]

        # Refresh the access token
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": REFRESH_ACCESS_TOKEN_MUTATION,
                "variables": {"refreshToken": refresh_token},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"

        data = resp_json["data"]["refreshAccessToken"]
        assert data["ok"] is True
        assert data["accessToken"]
        assert data["refreshToken"]
        assert data["expiresIn"] == 3600

    def test_refresh_access_token_invalid(self, client):
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": REFRESH_ACCESS_TOKEN_MUTATION,
                "variables": {"refreshToken": "invalid-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Invalid refresh token" in errors[0]["message"]


# ─── SIGN OUT TESTS ─────────────────────────────────────


@pytest.mark.django_db
class TestSignOut:
    def test_sign_out(self, client, user):
        sign_in_json = _sign_in(client, user.email)
        assert "errors" not in sign_in_json, f"Sign-in failed: {sign_in_json.get('errors')}"
        refresh_token = sign_in_json["data"]["signIn"]["authPayload"]["refreshToken"]

        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_OUT_MUTATION,
                "variables": {"refreshToken": refresh_token},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"
        assert resp_json["data"]["signOut"]["ok"] is True

    def test_sign_out_invalid_token(self, client):
        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_OUT_MUTATION,
                "variables": {"refreshToken": "invalid-token"},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        errors = resp_json.get("errors")
        assert errors is not None
        assert "Invalid or already revoked token" in errors[0]["message"]

    def test_sign_out_all(self, client, user):
        sign_in_json = _sign_in(client, user.email)
        assert "errors" not in sign_in_json, f"Sign-in failed: {sign_in_json.get('errors')}"
        refresh_token = sign_in_json["data"]["signIn"]["authPayload"]["refreshToken"]

        response = client.post(
            "/graphql/",
            json.dumps({
                "query": SIGN_OUT_ALL_MUTATION,
                "variables": {"refreshToken": refresh_token},
            }),
            content_type="application/json",
        )
        resp_json = response.json()
        assert "errors" not in resp_json, f"GraphQL error: {resp_json.get('errors')}"
        assert resp_json["data"]["signOutAll"]["ok"] is True
