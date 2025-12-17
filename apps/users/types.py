import graphene
from graphene_django import DjangoObjectType
from apps.users.models import User as UserModel, UserProfile as UserProfileModel, Interest as InterestModel, UserSession as UserSessionModel


# =============================================================================
# GraphQL Types (Alphabetical Order)
# =============================================================================

class AuthPayloadType(graphene.ObjectType):
    """Standard auth response"""
    access_token = graphene.String(required=True)
    session_token = graphene.String(required=True)
    refresh_token = graphene.String(required=True)
    expires_in = graphene.Int()  # seconds until access token expires
    user = graphene.Field(lambda: UserType, required=True)


class InterestType(DjangoObjectType):
    """Interest GraphQL type"""

    class Meta:
        model = InterestModel
        fields = ('id', 'name', 'description', 'icon')


class UserProfileType(DjangoObjectType):
    """User profile GraphQL type"""

    interests = graphene.List(InterestType)
    coordinates = graphene.List(graphene.Float)
    has_location = graphene.Boolean()
    is_premium = graphene.Boolean()

    class Meta:
        model = UserProfileModel
        fields = (
            'bio', 'location', 'home_latitude', 'home_longitude',
            'search_radius_km', 'timezone', 'birth_date', 'phone_number',
            'is_onboarding_completed', 'is_profile_public',
            'allow_email_notifications', 'allow_push_notifications',
            'calendar_integrated', 'calendar_provider', 'calendar_last_synced_at',
            'payment_plan', 'subscription_expires_at', 'last_billing_date',
            'last_active_at', 'login_count', 'theme', 'created_at', 'updated_at'
        )

    def resolve_interests(self, info):
        """Resolve interests many-to-many relationship"""
        return self.interests.all()

    def resolve_coordinates(self, info):
        """Return coordinates as [latitude, longitude] or None"""
        coords = self.coordinates
        if coords:
            return list(coords)
        return None

    def resolve_has_location(self, info):
        """Check if user has set their home location"""
        return self.has_location

    def resolve_is_premium(self, info):
        """Check if user has premium subscription"""
        return self.is_premium


class UserSessionType(DjangoObjectType):
    """User session GraphQL type"""

    class Meta:
        model = UserSessionModel
        fields = (
            'id', 'session_token', 'device_info', 'ip_address',
            'created_at', 'last_active_at', 'is_active'
        )


class UserType(DjangoObjectType):
    """User GraphQL type"""

    profile = graphene.Field(UserProfileType)
    full_name = graphene.String()
    name = graphene.String()
    active_sessions = graphene.List(UserSessionType)
    session_count = graphene.Int()

    class Meta:
        model = UserModel
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'profile_picture', 'is_active', 'date_joined', 'updated_at',
            'last_login_at', 'auth_provider', 'is_email_verified'
        )

    def resolve_profile(self, info):
        """Resolve user profile relationship"""
        return self.profile

    def resolve_full_name(self, info):
        """Return user's full name"""
        return self.full_name

    def resolve_name(self, info):
        """Return user's name (alias for full_name)"""
        return self.name

    def resolve_active_sessions(self, info):
        """Return only active sessions for the user"""
        return self.device_sessions.filter(is_active=True).order_by('-last_active_at')

    def resolve_session_count(self, info):
        """Return count of active sessions"""
        return self.device_sessions.filter(is_active=True).count()
