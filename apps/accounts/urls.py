from django.urls import path
from .views import (
    SignUpView, SignInView, GoogleSignInView, RefreshTokenView,
    SignOutView, UserProfileView, OnboardingView, ChangePasswordView
)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('signin/', SignInView.as_view(), name='signin'),
    path('google-signin/', GoogleSignInView.as_view(), name='google-signin'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh-token'),
    path('signout/', SignOutView.as_view(), name='signout'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('onboarding/', OnboardingView.as_view(), name='onboarding'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]
