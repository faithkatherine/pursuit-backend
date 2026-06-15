from django import forms
from django.contrib import admin as django_admin
from django.contrib.gis import admin
from django.utils import timezone

from apps.core.storage import upload_image

from .models import EditorsPick, Event, TicketTier, UserEvents


class IsPaidFilter(django_admin.SimpleListFilter):
    title = "is paid"
    parameter_name = "is_paid"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Paid"),
            ("no", "Free"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(price__gt=0)
        if self.value() == "no":
            return queryset.filter(price=0)
        return queryset


class EventAdminForm(forms.ModelForm):
    """Supports image upload alongside URL input and requires a category."""

    image_file = forms.ImageField(
        required=False,
        help_text="Upload an image file. This takes priority over the URL field below.",
    )

    class Meta:
        model = Event
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True
        self.fields["image"].required = False
        self.fields["image"].help_text = "Or paste an external image URL directly."

    def clean(self):
        cleaned_data = super().clean()
        image_file = cleaned_data.get("image_file")
        if image_file:
            cleaned_data["image"] = upload_image(image_file, folder="events")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("image_file"):
            instance.image = self.cleaned_data["image"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TicketTierInline(admin.TabularInline):
    model = TicketTier
    extra = 1
    fields = ("name", "description", "price", "capacity", "available", "is_active", "sort_order")


class EventAdmin(admin.GISModelAdmin):
    form = EventAdminForm
    list_display = (
        "id",
        "name",
        "organizer",
        "date",
        "get_categories",
        "location_name",
        "price",
        "is_free",
        "ticketing_enabled",
        "going_count",
        "is_active",
    )
    search_fields = ("name", "description", "location_name", "series_name", "organizer__business_name")
    list_filter = (
        "category",
        "is_active",
        "is_free",
        IsPaidFilter,
        "ticketing_enabled",
        "has_gallery",
        "date",
        "organizer",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["deactivate_events", "activate_events"]
    gis_widget_kwargs = {
        "attrs": {
            "default_lon": 36.8219,
            "default_lat": -1.2921,
            "default_zoom": 11,
        }
    }
    inlines = [TicketTierInline]
    fieldsets = (
        (None, {"fields": ("id", "name", "description", "organizer", "category")}),
        ("Date & Time", {"fields": ("date", "end_date", "timezone")}),
        ("Location", {"fields": ("location_name", "location")}),
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
    search_fields = ("user__username", "user__email", "user__first_name", "event__name")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


admin.site.register(UserEvents, UserEventsAdmin)


@admin.register(EditorsPick)
class EditorsPickAdmin(admin.ModelAdmin):
    """Admin interface for Editor's Pick curation."""

    list_display = ("event", "location_tag", "active_from", "active_until", "curator_name", "is_active")
    list_filter = ("location_tag", "active_from")
    search_fields = ("event__name", "curator_note", "location_tag")
    raw_id_fields = ("event",)
    date_hierarchy = "active_from"
    ordering = ("-active_from", "position")

    fieldsets = (
        (None, {"fields": ("event", "location_tag", "curator_note", "curator_name")}),
        ("Scheduling", {"fields": ("active_from", "active_until", "position")}),
    )

    def is_active(self, obj):
        now = timezone.now()
        return obj.active_from <= now <= obj.active_until

    is_active.boolean = True
    is_active.short_description = "Active"

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.active_from:
                obj.active_from = timezone.now()
            if not obj.active_until:
                obj.active_until = obj.active_from + timezone.timedelta(days=7)
        super().save_model(request, obj, form, change)


class TicketTierAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "name", "price", "capacity", "available", "is_active", "sort_order")
    list_filter = ("is_active", "event")
    search_fields = ("name", "description", "event__name")
    fieldsets = (
        (None, {"fields": ("event", "name", "description")}),
        ("Pricing & Capacity", {"fields": ("price", "capacity", "available")}),
        ("Settings", {"fields": ("is_active", "sort_order")}),
    )


admin.site.register(TicketTier, TicketTierAdmin)
