from django.contrib.gis import admin

from .models import EditorsPick, Event, TicketTier


class TicketTierInline(admin.TabularInline):
    """Inline admin for ticket tiers"""
    model = TicketTier
    extra = 1
    fields = ['name', 'description', 'price', 'capacity', 'available', 'is_active', 'sort_order']
    readonly_fields = []


class EventAdmin(admin.GISModelAdmin):
    """Admin interface for Event model"""
    list_display = (
        "id",
        "name",
        "organizer",
        "date",
        "get_categories",
        "location_name",
        "is_active",
    )
    search_fields = ("name", "description", "location_name")
    list_filter = ("category", "is_active", "date", "organizer")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["deactivate_events", "activate_events"]
    gis_widget_kwargs = {
        "attrs": {
            "default_lon": 36.8219,  # Nairobi longitude
            "default_lat": -1.2921,   # Nairobi latitude
            "default_zoom": 11
        }
    }
    inlines = [TicketTierInline]

    fieldsets = (
        (None, {
            "fields": ("id", "name", "description", "organizer", "category")
        }),
        ("Date & Time", {
            "fields": ("date", "end_date", "timezone")
        }),
        ("Location", {
            "fields": ("location_name", "location")
        }),
        ("Media", {
            "fields": ("image",)
        }),
        ("Settings", {
            "fields": ("is_active", "more_details_url")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
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


class EditorsPickAdmin(admin.ModelAdmin):
    """Admin interface for Editor's Pick"""
    list_display = (
        "id",
        "event",
        "location_tag",
        "active_from",
        "active_until",
        "curator_name",
        "position",
    )
    list_filter = ("location_tag", "active_from", "active_until")
    search_fields = ("event__name", "curator_note", "curator_name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "active_from"

    fieldsets = (
        (None, {
            "fields": ("event", "location_tag", "position")
        }),
        ("Active Period", {
            "fields": ("active_from", "active_until")
        }),
        ("Editorial", {
            "fields": ("curator_note", "curator_name")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


class TicketTierAdmin(admin.ModelAdmin):
    """Admin interface for Ticket Tiers"""
    list_display = (
        "id",
        "event",
        "name",
        "price",
        "capacity",
        "available",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "event")
    search_fields = ("name", "description", "event__name")
    readonly_fields = []

    fieldsets = (
        (None, {
            "fields": ("event", "name", "description")
        }),
        ("Pricing & Capacity", {
            "fields": ("price", "capacity", "available")
        }),
        ("Settings", {
            "fields": ("is_active", "sort_order")
        }),
    )


admin.site.register(Event, EventAdmin)
admin.site.register(EditorsPick, EditorsPickAdmin)
admin.site.register(TicketTier, TicketTierAdmin)
