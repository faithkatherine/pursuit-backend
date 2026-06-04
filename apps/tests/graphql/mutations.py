# ─── AUTH MUTATIONS ──────────────────────────────────────────────────────────

SIGN_UP = """
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

SIGN_IN = """
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

GOOGLE_SIGN_IN = """
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

REFRESH_ACCESS_TOKEN = """
mutation RefreshAccessToken($refreshToken: String!) {
  refreshAccessToken(refreshToken: $refreshToken) {
    ok
    accessToken
    refreshToken
    expiresIn
  }
}
"""

SIGN_OUT = """
mutation SignOut($refreshToken: String!) {
  signOut(refreshToken: $refreshToken) {
    ok
  }
}
"""

SIGN_OUT_ALL = """
mutation SignOutAll($refreshToken: String!) {
  signOutAll(refreshToken: $refreshToken) {
    ok
  }
}
"""

# ─── LOCATION MUTATIONS ───────────────────────────────────────────────────────

ENABLE_LOCATION = """
mutation EnableLocation($locationName: String!, $location: [Float!]!) {
  enableLocation(locationName: $locationName, location: $location) {
    ok
    user {
      id
      profile {
        allowLocationSharing
        locationName
        coordinates
        hasLocation
      }
    }
  }
}
"""

DISABLE_LOCATION = """
mutation DisableLocation {
  disableLocation {
    ok
    user {
      id
      profile {
        allowLocationSharing
        locationName
        coordinates
        hasLocation
      }
    }
  }
}
"""

COMPLETE_ONBOARDING = """
mutation CompleteOnboarding(
  $allowLocationSharing: Boolean,
  $locationName: String,
  $location: [Float],
  $allowPushNotifications: Boolean,
  $allowEmailNotifications: Boolean
) {
  completeOnboarding(
    allowLocationSharing: $allowLocationSharing,
    locationName: $locationName,
    location: $location,
    allowPushNotifications: $allowPushNotifications,
    allowEmailNotifications: $allowEmailNotifications
  ) {
    ok
    user {
      id
      profile {
        allowLocationSharing
        locationName
        coordinates
        hasLocation
        isOnboardingCompleted
      }
    }
  }
}
"""
