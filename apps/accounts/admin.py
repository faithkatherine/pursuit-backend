from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile, LoginAttempt, RefreshToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom user admin"""
    
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at', 'last_login']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'has_completed_onboarding', 'is_email_verified']
    search_fields = ['email', 'first_name', 'last_name', 'username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login_at']
    
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'avatar')
        }),
        (_('Profile'), {
            'fields': ('has_completed_onboarding', 'interests')
        }),
        (_('OAuth'), {
            'fields': ('google_id',)
        }),
        (_('Security'), {
            'fields': ('is_email_verified', 'email_verification_token', 'password_reset_token', 'password_reset_expires')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at', 'last_login_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User profile admin"""
    
    list_display = ['user', 'location', 'is_profile_public', 'created_at']
    list_filter = ['is_profile_public', 'allow_email_notifications', 'allow_push_notifications']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'location']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Profile'), {
            'fields': ('user', 'bio', 'location', 'birth_date', 'phone_number')
        }),
        (_('Privacy'), {
            'fields': ('is_profile_public', 'allow_email_notifications', 'allow_push_notifications')
        }),
        (_('Social Links'), {
            'fields': ('website', 'twitter_username', 'instagram_username'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Login attempt admin"""
    
    list_display = ['email', 'ip_address', 'success', 'failure_reason', 'created_at']
    list_filter = ['success', 'created_at']
    search_fields = ['email', 'ip_address']
    readonly_fields = ['email', 'ip_address', 'user_agent', 'success', 'failure_reason', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    """Refresh token admin"""
    
    list_display = ['user', 'is_revoked', 'expires_at', 'created_at']
    list_filter = ['is_revoked', 'expires_at', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['id', 'user', 'token', 'expires_at', 'created_at']
    
    def has_add_permission(self, request):
        return False
