import uuid
from datetime import timedelta

import graphene
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone
from google.auth.transport import requests as google_requests
# Google OAuth
from google.oauth2 import id_token
from graphql import GraphQLError

from apps.users.authentication import JWTService
from apps.users.models import Interest, RefreshToken
from apps.users.models import User as UserModel
from apps.users.models import UserSession as UserSessionModel
from apps.users.types import AuthPayloadType, UserProfileType, UserType

# =============================================================================
# Helper Functions
# =============================================================================


def verify_google_token(token):
    """Verify Google ID token and return user info"""
    # List of all valid client IDs (Web, iOS, Android)
    valid_client_ids = [
        settings.GOOGLE_CLIENT_ID,           # Web
        settings.GOOGLE_IOS_CLIENT_ID,       # iOS
        settings.GOOGLE_ANDROID_CLIENT_ID,   # Android
    ]

    # Try to verify with each client ID
    for client_id in valid_client_ids:
        if not client_id:
            continue

        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                client_id
            )

            # Token is valid, return user info
            return {
                'google_id': idinfo['sub'],
                'email': idinfo['email'],
                'email_verified': idinfo.get('email_verified', False),
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'picture': idinfo.get('picture', ''),
            }
        except ValueError:
            # Try next client ID
            continue

    # Token is invalid for all client IDs
    return None


# =============================================================================
# Mutation Classes (Alphabetical Order)
# =============================================================================

class CompleteOnboarding(graphene.Mutation):
    """Complete onboarding mutation"""
    class Arguments:
        allow_location_sharing = graphene.Boolean()
        location_name = graphene.String()
        location = graphene.List(graphene.Float)  # Expecting [latitude, longitude]
        allow_push_notifications = graphene.Boolean()
        allow_email_notifications = graphene.Boolean()
        interests = graphene.List(graphene.String)  # List of interest IDs

    ok = graphene.Boolean()
    user = graphene.Field(UserType)

    def mutate(
        self, info, allow_location_sharing=None, location_name=None,
        location=None, allow_push_notifications=None,
        allow_email_notifications=None, interests=None
    ):
        user = info.context.user
        if user.is_anonymous:
            raise GraphQLError(message="Not authenticated", extensions={"code": "NOT_AUTHENTICATED"})

        profile = user.profile

        if allow_location_sharing is not None:
            profile.allow_location_sharing = allow_location_sharing
        if location_name is not None:
            profile.location_name = location_name
        if location is not None and len(location) == 2:
            latitude, longitude = location
            profile.location = Point(longitude, latitude, srid=4326)
        if allow_push_notifications is not None:
            profile.allow_push_notifications = allow_push_notifications
        if allow_email_notifications is not None:
            profile.allow_email_notifications = allow_email_notifications

        profile.is_onboarding_completed = True
        profile.save()

        if interests is not None:
            interest_objs = Interest.objects.filter(id__in=interests)
            profile.interests.set(interest_objs)

        return CompleteOnboarding(ok=True, user=user)


class GoogleSignIn(graphene.Mutation):
    """Google sign in mutation - handles both sign up and sign in"""
    class Arguments:
        id_token = graphene.String(required=True)

    ok = graphene.Boolean()
    auth_payload = graphene.Field(lambda: AuthPayloadType)

    def mutate(self, info, id_token):
        # 1. Verify Google token
        google_user = verify_google_token(id_token)

        if not google_user:
            raise GraphQLError(message="Invalid Google token", extensions={"code": "INVALID_GOOGLE_TOKEN"})

        if not google_user['email_verified']:
            raise GraphQLError(message="Google email not verified", extensions={"code": "GOOGLE_EMAIL_NOT_VERIFIED"})

        try:
            with transaction.atomic():
                # 2. Check if user exists (by provider_id OR email)
                user = UserModel.objects.filter(
                    provider_id=google_user['google_id'],
                    auth_provider='google'
                ).first()

                if not user:
                    # Check if email exists with different auth provider
                    existing_email_user = UserModel.objects.filter(email=google_user['email']).first()

                    if existing_email_user:
                        # User exists with email/password - link Google account
                        existing_email_user.provider_id = google_user['google_id']
                        existing_email_user.auth_provider = 'google'
                        existing_email_user.is_email_verified = True
                        existing_email_user.save(update_fields=['provider_id', 'auth_provider', 'is_email_verified'])
                        user = existing_email_user
                    else:
                        # 3. Create new user
                        user = UserModel.objects.create(
                            email=google_user['email'],
                            username=google_user['email'],
                            first_name=google_user['first_name'],
                            last_name=google_user['last_name'] or '',
                            auth_provider='google',
                            provider_id=google_user['google_id'],
                            is_email_verified=True,  # Google already verified
                            # No password for Google users
                        )
                        user.set_unusable_password()
                        user.save()
                        # UserProfile is auto-created by signal

                # 4. Check if user is active
                if not user.is_active:
                    raise GraphQLError(message="Account is deactivated", extensions={"code": "ACCOUNT_DEACTIVATED"})

                # 5. Create UserSession
                session = UserSessionModel.objects.create(
                    user=user,
                    session_token=str(uuid.uuid4()),
                    device_info=info.context.META.get('HTTP_USER_AGENT', 'Unknown')[:255],
                    ip_address=info.context.META.get('REMOTE_ADDR', '127.0.0.1'),
                    user_agent=info.context.META.get('HTTP_USER_AGENT', '')
                )

                # 6. Generate access token
                access_token = JWTService.generate_access_token(user)

                # 7. Handle refresh token (same logic as SignIn)
                existing_refresh = RefreshToken.objects.filter(
                    user=user,
                    is_revoked=False,
                    expires_at__gt=timezone.now()
                ).first()

                if existing_refresh:
                    refresh_token_str = existing_refresh.token
                    existing_refresh.session = session
                    existing_refresh.save(update_fields=['session'])
                else:
                    refresh_token_str = JWTService.generate_refresh_token(user, session)
                    RefreshToken.objects.create(
                        user=user,
                        session=session,
                        token=refresh_token_str,
                        expires_at=timezone.now() + timedelta(days=30),
                    )

            # 8. Return response
            return GoogleSignIn(
                ok=True,
                auth_payload=AuthPayloadType(
                    access_token=access_token,
                    session_token=session.session_token,
                    refresh_token=refresh_token_str,
                    expires_in=3600,
                    user=user,
                )
            )
        except GraphQLError:
            raise  # Re-raise GraphQL errors as-is
        except Exception as e:
            raise GraphQLError(message=str(e), extensions={"code": "GOOGLE_SIGN_IN_ERROR"})


class RefreshAccessToken(graphene.Mutation):
    """Get new access token using refresh token"""
    class Arguments:
        refresh_token = graphene.String(required=True)

    ok = graphene.Boolean()
    access_token = graphene.String()
    refresh_token = graphene.String()  # Return same or rotated token
    expires_in = graphene.Int()

    def mutate(self, info, refresh_token):
        # 1. Find the refresh token
        token_obj = RefreshToken.objects.filter(
            token=refresh_token,
            is_revoked=False
        ).select_related('user', 'session').first()

        if not token_obj:
            raise GraphQLError(message="Invalid refresh token", extensions={"code": "INVALID_REFRESH_TOKEN"})

        # 2. Check if expired
        if token_obj.expires_at < timezone.now():
            raise GraphQLError(
                message="Refresh token expired. Please sign in again.",
                extensions={"code": "REFRESH_TOKEN_EXPIRED"}
            )

        # 3. Check if user is still active
        if not token_obj.user.is_active:
            raise GraphQLError(message="Account is deactivated", extensions={"code": "ACCOUNT_DEACTIVATED"})

        # 4. Generate new access token
        access_token = JWTService.generate_access_token(token_obj.user)

        # 5. Sliding expiration - extend refresh token life if user is active
        token_obj.expires_at = timezone.now() + timedelta(days=30)
        token_obj.save(update_fields=['expires_at'])

        return RefreshAccessToken(
            ok=True,
            access_token=access_token,
            refresh_token=refresh_token,  # Return same token (with extended life)
            expires_in=3600
        )


class SignIn(graphene.Mutation):
    """Sign in mutation"""
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    ok = graphene.Boolean()
    auth_payload = graphene.Field(lambda: AuthPayloadType)

    def mutate(self, info, email, password):
        # 1. Find user by email
        user = UserModel.objects.filter(email=email).first()

        if not user:
            raise GraphQLError(message="Invalid email or password", extensions={"code": "INVALID_CREDENTIALS"})

        # 2. Check password
        if not user.check_password(password):
            raise GraphQLError(message="Invalid email or password", extensions={"code": "INVALID_CREDENTIALS"})

        # 3. Check if user is active
        if not user.is_active:
            raise GraphQLError(message="Account is deactivated", extensions={"code": "ACCOUNT_DEACTIVATED"})

        try:
            with transaction.atomic():
                # 4. Create new UserSession for this device/login
                session = UserSessionModel.objects.create(
                    user=user,
                    session_token=str(uuid.uuid4()),
                    device_info=info.context.META.get('HTTP_USER_AGENT', 'Unknown')[:255],
                    ip_address=info.context.META.get('REMOTE_ADDR', '127.0.0.1'),
                    user_agent=info.context.META.get('HTTP_USER_AGENT', '')
                )

                # 5. Generate access token (short-lived, always new)
                access_token = JWTService.generate_access_token(user)

                # 6. Check for existing valid refresh token
                existing_refresh = RefreshToken.objects.filter(
                    user=user,
                    is_revoked=False,
                    expires_at__gt=timezone.now()
                ).first()

                if existing_refresh:
                    # Reuse existing refresh token, update session link
                    refresh_token_str = existing_refresh.token
                    existing_refresh.session = session
                    existing_refresh.save(update_fields=['session'])
                else:
                    # Create new refresh token
                    refresh_token_str = JWTService.generate_refresh_token(user, session)
                    RefreshToken.objects.create(
                        user=user,
                        session=session,
                        token=refresh_token_str,
                        expires_at=timezone.now() + timedelta(days=30),
                    )

            # 7. Return response
            return SignIn(
                ok=True,
                auth_payload=AuthPayloadType(
                    access_token=access_token,
                    session_token=session.session_token,
                    refresh_token=refresh_token_str,
                    expires_in=3600,
                    user=user,
                )
            )
        except Exception as e:
            raise GraphQLError(message=str(e), extensions={"code": "SIGN_IN_ERROR"})


class SignOut(graphene.Mutation):
    """Sign out mutation - revokes only the current session/device"""
    class Arguments:
        refresh_token = graphene.String(required=True)  # Identify which session to revoke

    ok = graphene.Boolean()

    def mutate(self, info, refresh_token):
        # Find the refresh token
        token_obj = RefreshToken.objects.filter(
            token=refresh_token,
            is_revoked=False
        ).select_related('session').first()

        if not token_obj:
            raise GraphQLError(message="Invalid or already revoked token", extensions={"code": "INVALID_TOKEN"})

        # Revoke only THIS refresh token
        token_obj.is_revoked = True
        token_obj.save(update_fields=['is_revoked'])

        # Deactivate only the associated session
        if token_obj.session:
            token_obj.session.is_active = False
            token_obj.session.save(update_fields=['is_active'])

        return SignOut(ok=True)


class SignOutAll(graphene.Mutation):
    """Sign out from ALL devices - useful for security (password change, account compromise)"""
    class Arguments:
        refresh_token = graphene.String(required=True)  # Verify user owns this account

    ok = graphene.Boolean()

    def mutate(self, info, refresh_token):
        # Find the token to get the user
        token_obj = RefreshToken.objects.filter(
            token=refresh_token
        ).select_related('user').first()

        if not token_obj:
            raise GraphQLError(message="Invalid token", extensions={"code": "INVALID_TOKEN"})

        user = token_obj.user

        # Revoke ALL refresh tokens for this user
        RefreshToken.objects.filter(user=user, is_revoked=False).update(is_revoked=True)

        # Deactivate ALL sessions
        UserSessionModel.objects.filter(user=user, is_active=True).update(is_active=False)

        return SignOutAll(ok=True)


class SignUp(graphene.Mutation):
    """Sign up mutation"""
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String()

    ok = graphene.Boolean()
    auth_payload = graphene.Field(lambda: AuthPayloadType)
    errors = graphene.List(graphene.String)
    user_exists = graphene.Boolean()  # Flag to tell frontend to redirect to sign-in
    requires_verification = graphene.Boolean()  # Tell frontend email verification is needed

    def mutate(self, info, email, password, first_name, last_name=None):
        # 1. Check if user already exists
        if UserModel.objects.filter(email=email).exists():
            raise GraphQLError(
                message="Email already registered. Please sign in instead.",
                extensions={"code": "USER_EXISTS"}
            )

        try:
            with transaction.atomic():
                # 2. Create User (create_user already saves and hashes password)
                user = UserModel.objects.create_user(
                    email=email,
                    password=password,
                    username=email,  # Use email as username
                    first_name=first_name,
                    last_name=last_name or '',
                    auth_provider='email',
                    is_email_verified=False,  # TODO: Implement email verification later
                )

                # 4. UserProfile is auto-created by signal (post_save on User)
                # Access it via user.profile if needed

                # 5. Create UserSession
                session = UserSessionModel.objects.create(
                    user=user,
                    session_token=str(uuid.uuid4()),
                    device_info=info.context.META.get('HTTP_USER_AGENT', 'Unknown')[:255],
                    ip_address=info.context.META.get('REMOTE_ADDR', '127.0.0.1'),
                    user_agent=info.context.META.get('HTTP_USER_AGENT', '')
                )

                # 6. Generate tokens (user can use app but with limited access until verified)
                access_token = JWTService.generate_access_token(user)
                refresh_token_str = JWTService.generate_refresh_token(user, session)

                # 7. Store RefreshToken in database
                RefreshToken.objects.create(
                    user=user,
                    session=session,
                    token=refresh_token_str,
                    expires_at=timezone.now() + timedelta(days=30),
                )

                # TODO: Implement email verification
                # raw_token = user.generate_email_verification_token()
                # user.save()
                # send_verification_email(user.email, raw_token)

            # 8. Return response
            return SignUp(
                ok=True,
                requires_verification=True,  # Frontend should prompt user to verify email
                auth_payload=AuthPayloadType(
                    access_token=access_token,
                    session_token=session.session_token,
                    refresh_token=refresh_token_str,
                    expires_in=3600,
                    user=user,
                )
            )
        except Exception as e:
            raise GraphQLError(message=str(e))


class SkipOnboarding(graphene.Mutation):

    """Skip onboarding mutation"""
    user = graphene.Field(UserType)
    ok = graphene.Boolean()

    def mutate(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise GraphQLError(message="Not authenticated", extensions={"code": "NOT_AUTHENTICATED"})

        # Skip onboarding logic here
        user.profile.has_skipped_onboarding = True
        user.profile.save()

        return SkipOnboarding(ok=True, user=user)

# =============================================================================
# Combined Query and Mutation Classes
# =============================================================================


class UserQueries(graphene.ObjectType):
    """User Queries"""
    user = graphene.Field(UserType)
    user_profile = graphene.Field(UserProfileType)

    def resolve_user(self, info):
        """Get current authenticated user"""
        user = info.context.user
        if user.is_anonymous:
            raise GraphQLError(message="Not authenticated", extensions={"code": "NOT_AUTHENTICATED"})
        return user

    def resolve_user_profile(self, info):
        """Get current authenticated user's profile"""
        user = info.context.user
        if user.is_anonymous:
            raise GraphQLError(message="Not authenticated", extensions={"code": "NOT_AUTHENTICATED"})
        return user.profile


class UserMutations(graphene.ObjectType):
    """User Mutations"""
    complete_onboarding = CompleteOnboarding.Field()
    google_sign_in = GoogleSignIn.Field()
    refresh_access_token = RefreshAccessToken.Field()
    sign_in = SignIn.Field()
    sign_out = SignOut.Field()
    sign_out_all = SignOutAll.Field()
    sign_up = SignUp.Field()
    skip_onboarding = SkipOnboarding.Field()
