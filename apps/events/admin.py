from django.contrib.gis import admin

from .models import Event

# Register your models here.


class EventAdmin(admin.GISModelAdmin):
    form = EventAdminForm
    list_display = (
        "id",
        "name",
        "date",
        "get_categories",
        "location_name",
        "price",
        "is_free",
        "ticketing_enabled",
        "going_count",
        "is_active",
        "organizer"
    )
    search_fields = ("name", "description", "location_name", "series_name")
    list_filter = ("category", "is_active", "is_free", IsPaidFilter, "ticketing_enabled", "has_gallery", "date")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["deactivate_events", "activate_events"]
    gis_widget_kwargs = {"attrs": {"default_lon": -84.388, "default_lat": 33.749, "default_zoom": 11}}
    fieldsets = (
        (None, {"fields": ("id", "name", "description", "category", "date", "end_date", "organizer")}),
        ("Location", {"fields": ("location_name", "location", "timezone")}),
        ("Media", {"fields": ("image_file", "image")}),
        (
            "Ticketing",
            {"fields": ("price", "is_free", "ticketing_enabled", "available_tickets", "going_count")},
        ),
        ("Gallery", {"fields": ("has_gallery", "gallery_images", "gallery_description")}),
        ("Settings", {"fields": ("is_active", "more_details_url", "series_name")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Categories")
    def get_categories(self, obj):
        return ", ".join(c.name for c in obj.category.all())

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    @admin.action(description='Deactivate selected events')
    def deactivate_events(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} event(s) deactivated.')

    @admin.action(description='Activate selected events')
    def activate_events(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} event(s) activated.')

    class Media:
        js = ('events/js/geocode_location.js',)


admin.site.register(Event, EventAdmin)
