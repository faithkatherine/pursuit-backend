from django.contrib import admin

from .models import Category, Interest, PlatformConfig


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "icon")
    search_fields = ("name",)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "category", "description")
    list_filter = ("category",)
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = (
        "is_active",
        "fee_percentage",
        "order_expiration_minutes",
        "payout_delay_hours",
        "updated_at",
        "updated_by"
    )
    list_filter = ("is_active", "created_at")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Status", {
            "fields": ("is_active",)
        }),
        ("Fee Configuration", {
            "fields": ("fee_percentage",)
        }),
        ("Timing Configuration", {
            "fields": ("order_expiration_minutes", "payout_delay_hours")
        }),
        ("Future Features", {
            "fields": ("min_payout_amount", "max_ticket_quantity"),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("updated_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Automatically set updated_by to current admin user"""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Category, CategoryAdmin)
