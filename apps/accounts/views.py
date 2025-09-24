from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.shortcuts import get_object_or_404
from google.oauth2 import id_token
from google.auth.transport import requests
import logging
from datetime import datetime

from .models import User, UserProfile, LoginAttempt
from .serializers import (
    UserSerializer, SignUpSerializer, SignInSerializer, GoogleSignInSerializer,
    PasswordResetSerializer, PasswordResetConfirmSerializer, ChangePasswordSerializer,
    OnboardingSerializer, UserProfileSerializer
)
from .authentication import JWTService

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_login_attempt(email, ip_address, user_agent, success, failure_reason=None):
    """Log login attempt"""
    # For successful logins, set failure_reason to empty string instead of None
    if success and failure_reason is None:
        failure_reason = ""
        
    LoginAttempt.objects.create(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=failure_reason or ""
    )


class SignUpView(APIView):
    """User signup view"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Create user profile if it doesn't exist
            UserProfile.objects.get_or_create(user=user)
            
            # Generate tokens
            access_token = JWTService.generate_access_token(user)
            refresh_token = JWTService.generate_refresh_token(user)
            
            # Log successful registration
            log_login_attempt(
                email=user.email,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            
            return Response({
                'user': UserSerializer(user).data,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'message': 'User created successfully'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SignInView(APIView):
    """User signin view"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = SignInSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Update last login
            user.last_login_at = datetime.now()
            user.save(update_fields=['last_login_at'])
            
            # Generate tokens
            access_token = JWTService.generate_access_token(user)
            refresh_token = JWTService.generate_refresh_token(user)
            
            # Log successful login
            log_login_attempt(
                email=user.email,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            
            return Response({
                'user': UserSerializer(user).data,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        
        # Log failed login attempt
        email = request.data.get('email', '')
        if email:
            log_login_attempt(
                email=email,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=False,
                failure_reason='Invalid credentials'
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleSignInView(APIView):
    """Google OAuth signin view"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = GoogleSignInSerializer(data=request.data)
        
        if serializer.is_valid():
            token = serializer.validated_data['token']
            
            try:
                # Verify Google token
                idinfo = id_token.verify_oauth2_token(
                    token, requests.Request(), settings.GOOGLE_OAUTH2_CLIENT_ID
                )
                
                if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                    raise ValueError('Wrong issuer.')
                
                google_id = idinfo['sub']
                email = idinfo['email']
                first_name = idinfo.get('given_name', '')
                last_name = idinfo.get('family_name', '')
                avatar_url = idinfo.get('picture', '')
                
                # Check if user exists with Google ID
                try:
                    user = User.objects.get(google_id=google_id)
                except User.DoesNotExist:
                    # Check if user exists with email
                    try:
                        user = User.objects.get(email=email)
                        user.google_id = google_id
                        user.save()
                    except User.DoesNotExist:
                        # Create new user
                        user = User.objects.create_user(
                            email=email,
                            username=email,
                            first_name=first_name,
                            last_name=last_name,
                            google_id=google_id,
                            is_email_verified=True
                        )
                        UserProfile.objects.create(user=user)
                
                # Update last login
                user.last_login_at = datetime.now()
                user.save(update_fields=['last_login_at'])
                
                # Generate tokens
                access_token = JWTService.generate_access_token(user)
                refresh_token = JWTService.generate_refresh_token(user)
                
                # Log successful login
                log_login_attempt(
                    email=user.email,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True
                )
                
                return Response({
                    'user': UserSerializer(user).data,
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'message': 'Google login successful'
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                logger.error(f"Google token verification failed: {e}")
                return Response({
                    'error': 'Invalid Google token'
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Google login error: {e}")
                return Response({
                    'error': 'Google login failed'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenView(APIView):
    """Refresh token view"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            access_token = JWTService.refresh_access_token(refresh_token)
            
            return Response({
                'access_token': access_token,
                'message': 'Token refreshed successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SignOutView(APIView):
    """User signout view"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            JWTService.revoke_refresh_token(refresh_token)
        else:
            # Revoke all user tokens
            JWTService.revoke_all_user_tokens(request.user)
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)


class UserProfileView(APIView):
    """User profile view"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OnboardingView(APIView):
    """User onboarding view"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = OnboardingSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            user.interests = serializer.validated_data['interests']
            user.has_completed_onboarding = True
            user.save()
            
            return Response({
                'user': UserSerializer(user).data,
                'message': 'Onboarding completed successfully'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """Change password view"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # Revoke all existing refresh tokens
            JWTService.revoke_all_user_tokens(user)
            
            return Response({
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
