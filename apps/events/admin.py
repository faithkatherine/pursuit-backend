from django.contrib.gis import admin

from .models import Event, UserEvents

# Register your models here.


class EventAdmin(admin.GISModelAdmin):
    list_display = ("name", "date", "location_name", "is_active")
    search_fields = ("name", "location_name")
    list_filter = ("date", "category", "is_active")
    readonly_fields = ("created_at", "updated_at")
    actions = ["deactivate_events", "activate_events"]
    gis_widget_kwargs = {"attrs": {"default_lon": -84.388, "default_lat": 33.749, "default_zoom": 11}}

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    @admin.action(description="Deactivate selected events")
    def deactivate_events(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} event(s) deactivated.")

    @admin.action(description="Activate selected events")
    def activate_events(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} event(s) activated.")

    class Media:
        js = ("events/js/geocode_location.js",)


admin.site.register(Event, EventAdmin)


class UserEventsAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at")
    search_fields = ("user__username", "event__name")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


admin.site.register(UserEvents, UserEventsAdmin)
