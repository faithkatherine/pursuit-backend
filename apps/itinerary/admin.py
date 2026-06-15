from django.contrib import admin

from .models import Trip


class TripAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "destination", "start_date", "end_date", "event_count")
    search_fields = ("name", "destination", "user__email", "user__first_name")
    list_filter = ("destination", "start_date")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("events",)
    fieldsets = (
        (None, {"fields": ("user", "name", "destination")}),
        ("Dates", {"fields": ("start_date", "end_date")}),
        ("Media", {"fields": ("image",)}),
        ("Events", {"fields": ("events",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Events")
    def event_count(self, obj):
        return obj.events.count()


admin.site.register(Trip, TripAdmin)
