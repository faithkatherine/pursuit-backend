from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone as django_timezone
from django.utils.crypto import get_random_string
import uuid
import hashlib

class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier"""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError(_('Users must have an email address'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """Custom user model extending Django's AbstractUser, supporting Google OAuth and email/password authentication"""

    AUTH_PROVIDER_CHOICES = [
        ('email', 'Email'),
        ('google', 'Google SSO'),
    ]

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)

    # Authentication fields
    auth_provider = models.CharField(
        max_length=20,
        choices=AUTH_PROVIDER_CHOICES,
        default='email',
    )
    provider_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID from the authentication provider")

    # Personal information
    first_name = models.CharField(_('first name'), max_length=150, blank=False)
    last_name = models.CharField(_('last name'), max_length=150, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    # Status fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(blank=True, null=True)

    # Security and verification
    is_email_verified = models.BooleanField(default=False)
    email_verification_token_hash = models.CharField(max_length=64, blank=True, null=True, help_text="SHA-256 hash of verification token")
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    password_reset_token_hash = models.CharField(max_length=64, blank=True, null=True, help_text="SHA-256 hash of reset token")
    password_reset_expires = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name']

    objects = UserManager()

    class Meta:
        db_table = 'users_user'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['provider_id']),
            models.Index(fields=['auth_provider']),
            models.Index(fields=['date_joined']),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        """Return the user's full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def name(self):
        """Alias for full_name to match frontend expectations"""
        return self.full_name

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token using SHA-256 for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()

    def generate_email_verification_token(self) -> str:
        """Generate and store a hashed email verification token. Returns the raw token to send to user."""
        raw_token = get_random_string(64)
        self.email_verification_token_hash = self.hash_token(raw_token)
        self.email_verification_sent_at = django_timezone.now()
        return raw_token

    def verify_email_token(self, token: str) -> bool:
        """Verify an email verification token against the stored hash"""
        if not self.email_verification_token_hash:
            return False
        return self.email_verification_token_hash == self.hash_token(token)

    def generate_password_reset_token(self, expires_in_hours: int = 24) -> str:
        """Generate and store a hashed password reset token. Returns the raw token to send to user."""
        raw_token = get_random_string(64)
        self.password_reset_token_hash = self.hash_token(raw_token)
        self.password_reset_expires = django_timezone.now() + django_timezone.timedelta(hours=expires_in_hours)
        return raw_token

    def verify_password_reset_token(self, token: str) -> bool:
        """Verify a password reset token against the stored hash and check expiry"""
        if not self.password_reset_token_hash or not self.password_reset_expires:
            return False
        if django_timezone.now() > self.password_reset_expires:
            return False
        return self.password_reset_token_hash == self.hash_token(token)

    def clear_password_reset_token(self):
        """Clear the password reset token after successful reset"""
        self.password_reset_token_hash = None
        self.password_reset_expires = None

class UserProfile(models.Model):
    """Extended user profile information"""

    PAYMENT_PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
    ]

    CALENDAR_PROVIDER_CHOICES = [
        ('none', 'None'),
        ('google_calendar', 'Google Calendar'),
        ('outlook', 'Microsoft Outlook'),
        ('apple_calendar', 'Apple Calendar'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', primary_key=True)
    bio = models.TextField(blank=True, max_length=500)
    
    # Location fields for geo-based recommendations
    location = models.CharField(max_length=100, blank=True, help_text="City, State/Country display name")
    home_latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Latitude coordinate")
    home_longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Longitude coordinate")
    search_radius_km = models.PositiveIntegerField(default=50, help_text="Default search radius for nearby events in kilometers")
    
    timezone = models.CharField(max_length=50, blank=True, default='UTC')
    birth_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)

    # Onboarding and preferences
    is_onboarding_completed = models.BooleanField(default=False)
    has_skipped_onboarding = models.BooleanField(default=False)
    interests = models.ManyToManyField('Interest', blank=True, related_name='users', help_text="User's selected interests for personalization")

    # Privacy settings
    is_profile_public = models.BooleanField(default=True)
    allow_email_notifications = models.BooleanField(default=True)
    allow_push_notifications = models.BooleanField(default=True)

    #Calendar integration
    calendar_integrated = models.BooleanField(default=False)
    calendar_provider = models.CharField(
        max_length=30,
        choices=CALENDAR_PROVIDER_CHOICES,
        default='none',
    )
    calendar_sync_token = models.CharField(max_length=255, blank=True, null=True)
    calendar_last_synced_at = models.DateTimeField(blank=True, null=True)
    
    # Payment and subscription
    payment_plan = models.CharField(
        max_length=20,
        choices=PAYMENT_PLAN_CHOICES,
        default='free',
    )
    subscription_expires_at = models.DateTimeField(blank=True, null=True)
    last_billing_date = models.DateTimeField(blank=True, null=True)

    # Usage tracking
    last_active_at = models.DateTimeField(null=True, blank=True)
    login_count = models.IntegerField(default=0)
    
    # Preferences
    theme = models.CharField(
        max_length=20,
        choices=(('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')),
        default='auto'
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users_user_profile'
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

    def __str__(self):
        return f"{self.user.full_name}'s Profile"
    
    @property
    def is_premium(self):
        """Check if the user has a premium subscription"""
        return self.payment_plan == 'premium' and (self.subscription_expires_at is None or self.subscription_expires_at > django_timezone.now())

    @property
    def has_location(self) -> bool:
        """Check if user has set their home coordinates"""
        return self.home_latitude is not None and self.home_longitude is not None

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Return (latitude, longitude) tuple or None if not set"""
        if self.has_location:
            return (float(self.home_latitude), float(self.home_longitude))
        return None

    def set_coordinates(self, latitude: float, longitude: float):
        """Set the user's home coordinates"""
        self.home_latitude = latitude
        self.home_longitude = longitude


class Interest(models.Model):
    """List of interests for personalization"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, blank=False, null=False)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'users_interests'
        verbose_name = _('Interest')
        verbose_name_plural = _('Interests')
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


class LoginAttempt(models.Model):
    """Track login attempts for security"""

    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users_login_attempt'
        verbose_name = _('Login Attempt')
        verbose_name_plural = _('Login Attempts')
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{status} login attempt for {self.email} at {self.created_at}"
    
class UserSession(models.Model):
    """Track user device sessions for security"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_sessions')
    session_token = models.CharField(max_length=500, unique=True)
    device_info = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'users_device_session'
        verbose_name = _('Device Session')
        verbose_name_plural = _('Device Sessions')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Session for {self.user.email} on {self.device_info}"


class RefreshToken(models.Model):
    """JWT Refresh tokens"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='refresh_tokens', blank=True, null=True)
    token = models.CharField(max_length=500, unique=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users_refresh_token'
        verbose_name = _('Refresh Token')
        verbose_name_plural = _('Refresh Tokens')
        indexes = [
            models.Index(fields=['user', 'is_revoked']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Refresh token for {self.user.email}"

