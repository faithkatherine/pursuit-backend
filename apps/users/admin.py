from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import LoginAttempt, RefreshToken, User, UserProfile, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom user admin"""

    list_display = ["id", "email", "first_name", "last_name", "is_active", "is_staff", "date_joined", "last_login"]
    list_filter = ["is_active", "is_staff", "is_superuser", "auth_provider", "is_email_verified"]
    search_fields = ["email", "first_name", "last_name", "username"]
    ordering = ["-date_joined"]
    readonly_fields = ["id", "date_joined", "updated_at", "last_login_at"]

    fieldsets = (
        (None, {"fields": ("id", "username", "email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "profile_picture")}),
        (_("Authentication"), {"fields": ("auth_provider", "provider_id")}),
        (
            _("Security"),
            {
                "fields": (
                    "is_email_verified",
                    "email_verification_token_hash",
                    "email_verification_sent_at",
                    "password_reset_token_hash",
                    "password_reset_expires",
                )
            },
        ),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (
            _("Important dates"),
            {"fields": ("last_login", "date_joined", "updated_at", "last_login_at"), "classes": ("collapse",)},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User profile admin"""

    list_display = [
        "user",
        "location_name",
        "is_profile_public",
        "payment_plan",
        "has_skipped_onboarding",
        "is_onboarding_completed",
        "created_at",
    ]
    list_filter = [
        "is_profile_public",
        "allow_email_notifications",
        "allow_push_notifications",
        "payment_plan",
        "is_onboarding_completed",
    ]
    search_fields = ["user__email", "user__first_name", "user__last_name", "location_name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Profile"), {"fields": ("user", "bio", "birth_date", "phone_number")}),
        (_("Location"), {"fields": ("location_name", "location", "search_radius_km", "timezone")}),
        (_("Onboarding"), {"fields": ("has_skipped_onboarding", "is_onboarding_completed", "interests")}),
        (
            _("Privacy"),
            {
                "fields": (
                    "is_profile_public",
                    "allow_location_sharing",
                    "allow_email_notifications",
                    "allow_push_notifications",
                )
            },
        ),
        (
            _("Calendar"),
            {
                "fields": (
                    "calendar_integrated",
                    "calendar_provider",
                    "calendar_sync_token",
                    "calendar_last_synced_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Subscription"),
            {"fields": ("payment_plan", "subscription_expires_at", "last_billing_date"), "classes": ("collapse",)},
        ),
        (_("Usage"), {"fields": ("last_active_at", "login_count", "theme"), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Login attempt admin"""

    list_display = ["email", "ip_address", "success", "failure_reason", "created_at"]
    list_filter = ["success", "created_at"]
    search_fields = ["email", "ip_address"]
    readonly_fields = ["email", "ip_address", "user_agent", "success", "failure_reason", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    """Refresh token admin"""

    list_display = ["user", "session", "is_revoked", "expires_at", "created_at"]
    list_filter = ["is_revoked", "expires_at", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "user", "session", "token", "expires_at", "created_at"]

    def has_add_permission(self, request):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """User session admin for managing device sessions"""

    list_display = ["user", "device_info", "ip_address", "is_active", "created_at", "last_active_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["user__email", "device_info", "ip_address"]
    readonly_fields = [
        "id",
        "user",
        "session_token",
        "device_info",
        "ip_address",
        "user_agent",
        "created_at",
        "last_active_at",
    ]

    def has_add_permission(self, request):
        return False
        return False
