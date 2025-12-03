import jwt
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User, RefreshToken


class JWTAuthentication(BaseAuthentication):
    """Custom JWT authentication class"""

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user = User.objects.get(id=payload['user_id'])

            if not user.is_active:
                raise AuthenticationFailed('User account is disabled.')

            return (user, token)

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token.')
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')
        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')


class JWTService:
    """Service class for JWT operations"""

    @staticmethod
    def generate_access_token(user):
        """Generate access token for user"""
        now = timezone.now()
        payload = {
            'user_id': str(user.id),
            'email': user.email,
            'exp': now + timedelta(seconds=settings.JWT_EXPIRATION_DELTA),
            'iat': now,
            'type': 'access'
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def generate_refresh_token(user, session=None):
        """Generate refresh token for user (does NOT store in DB - caller handles that)"""
        now = timezone.now()
        payload = {
            'user_id': str(user.id),
            'session_id': str(session.id) if session else None,
            'exp': now + timedelta(seconds=settings.JWT_REFRESH_EXPIRATION_DELTA),
            'iat': now,
            'type': 'refresh'
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        
        # NOTE: RefreshToken DB record is created by the caller (schema.py mutations)
        # This avoids duplicate creation and allows caller to link session
        return token

    @staticmethod
    def verify_token(token, token_type='access'):
        """Verify and decode token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            if payload.get('type') != token_type:
                raise jwt.InvalidTokenError('Invalid token type')

            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')

    @staticmethod
    def refresh_access_token(refresh_token):
        """Generate new access token from refresh token"""
        try:
            # Verify refresh token
            payload = JWTService.verify_token(refresh_token, 'refresh')

            # Check if refresh token exists in database and is not revoked
            db_token = RefreshToken.objects.get(
                token=refresh_token,
                is_revoked=False,
                expires_at__gt=timezone.now()
            )

            user = db_token.user

            if not user.is_active:
                raise AuthenticationFailed('User account is disabled')

            # Generate new access token
            access_token = JWTService.generate_access_token(user)

            return access_token

        except RefreshToken.DoesNotExist:
            raise AuthenticationFailed('Invalid refresh token')
        except Exception as e:
            raise AuthenticationFailed(f'Token refresh failed: {str(e)}')

    @staticmethod
    def revoke_refresh_token(refresh_token):
        """Revoke refresh token"""
        try:
            db_token = RefreshToken.objects.get(token=refresh_token)
            db_token.is_revoked = True
            db_token.save()
        except RefreshToken.DoesNotExist:
            pass  # Token doesn't exist, consider it revoked

    @staticmethod
    def revoke_all_user_tokens(user):
        """Revoke all refresh tokens for a user"""
        RefreshToken.objects.filter(user=user, is_revoked=False).update(is_revoked=True)
