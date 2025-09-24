import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth import authenticate
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime
from .models import User, UserProfile
from .authentication import JWTService
from .serializers import SignUpSerializer, OnboardingSerializer
from .views import log_login_attempt, get_client_ip


class UserType(DjangoObjectType):
    """GraphQL User type"""
    
    name = graphene.String()
    avatar = graphene.String()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'has_completed_onboarding', 'interests', 'is_email_verified',
            'created_at', 'updated_at'
        ]
    
    def resolve_name(self, info):
        return self.full_name
    
    def resolve_avatar(self, info):
        return self.get_avatar_url()


class UserProfileType(DjangoObjectType):
    """GraphQL UserProfile type"""
    
    class Meta:
        model = UserProfile
        fields = '__all__'


class AuthPayloadType(graphene.ObjectType):
    """GraphQL Auth payload type"""
    
    user = graphene.Field(UserType)
    access_token = graphene.String()
    refresh_token = graphene.String()
    message = graphene.String()


# Mutations
class SignUp(graphene.Mutation):
    """Sign up mutation"""
    
    class Arguments:
        email = graphene.String(required=True)
        username = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String()
        password = graphene.String(required=True)
    
    Output = AuthPayloadType
    
    def mutate(self, info, email, username, first_name, password, last_name=''):
        serializer = SignUpSerializer(data={
            'email': email,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'password': password,
            'password_confirm': password
        })
        
        if serializer.is_valid():
            user = serializer.save()
            UserProfile.objects.create(user=user)
            
            access_token = JWTService.generate_access_token(user)
            refresh_token = JWTService.generate_refresh_token(user)
            
            return AuthPayloadType(
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
                message='User created successfully'
            )
        else:
            raise Exception(str(serializer.errors))


class SignIn(graphene.Mutation):
    """Sign in mutation"""
    
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
    
    Output = AuthPayloadType
    
    def mutate(self, info, email, password):
        user = authenticate(email=email, password=password)
        
        if not user:
            raise Exception('Invalid credentials')
        
        if not user.is_active:
            raise Exception('User account is disabled')
        
        access_token = JWTService.generate_access_token(user)
        refresh_token = JWTService.generate_refresh_token(user)
        
        return AuthPayloadType(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            message='Login successful'
        )


class GoogleSignIn(graphene.Mutation):
    """Google Sign in mutation"""
    
    class Arguments:
        token = graphene.String(required=True)
    
    Output = AuthPayloadType
    
    def mutate(self, info, token):
        try:
            # Verify Google token
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_OAUTH2_CLIENT_ID
            )
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise Exception('Invalid token issuer')
            
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
                    UserProfile.objects.get_or_create(user=user)
            
            # Update last login
            user.last_login_at = datetime.now()
            user.save(update_fields=['last_login_at'])
            
            # Generate tokens
            access_token = JWTService.generate_access_token(user)
            refresh_token = JWTService.generate_refresh_token(user)
            
            # Log successful login
            log_login_attempt(
                email=user.email,
                ip_address=get_client_ip(info.context),
                user_agent=info.context.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            
            return AuthPayloadType(
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
                message='Google login successful'
            )
            
        except ValueError as e:
            raise Exception(f'Invalid Google token: {str(e)}')
        except Exception as e:
            raise Exception(f'Google login failed: {str(e)}')


class CompleteOnboarding(graphene.Mutation):
    """Complete onboarding mutation"""
    
    class Arguments:
        interests = graphene.List(graphene.String, required=True)
    
    user = graphene.Field(UserType)
    message = graphene.String()
    
    def mutate(self, info, interests):
        user = info.context.user
        
        if not user.is_authenticated:
            raise Exception('Authentication required')
        
        serializer = OnboardingSerializer(data={'interests': interests})
        
        if serializer.is_valid():
            user.interests = serializer.validated_data['interests']
            user.has_completed_onboarding = True
            user.save()
            
            return CompleteOnboarding(
                user=user,
                message='Onboarding completed successfully'
            )
        else:
            raise Exception(str(serializer.errors))


# Queries
class AccountsQueries(graphene.ObjectType):
    """Accounts GraphQL queries"""
    
    me = graphene.Field(UserType)
    
    def resolve_me(self, info):
        user = info.context.user
        if user.is_authenticated:
            return user
        return None


# Mutations
class AccountsMutations(graphene.ObjectType):
    """Accounts GraphQL mutations"""
    
    sign_up = SignUp.Field()
    sign_in = SignIn.Field()
    google_sign_in = GoogleSignIn.Field()
    complete_onboarding = CompleteOnboarding.Field()
