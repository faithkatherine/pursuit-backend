from django import forms
from django.contrib.gis import admin

from apps.core.storage import upload_image

from .models import Event, UserEvents


class EventAdminForm(forms.ModelForm):
    """Custom admin form that supports image file upload alongside URL input,
    and enforces at least one category."""

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
            url = upload_image(image_file, folder="events")
            cleaned_data["image"] = url
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("image_file"):
            instance.image = self.cleaned_data["image"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class EventAdmin(admin.GISModelAdmin):
    form = EventAdminForm
    list_display = ("name", "date", "get_categories", "location_name", "is_free", "is_active")
    search_fields = ("name", "description", "location_name")
    list_filter = ("category", "is_active", "is_free", "date")
    readonly_fields = ("created_at", "updated_at")
    actions = ["deactivate_events", "activate_events"]
    gis_widget_kwargs = {"attrs": {"default_lon": -84.388, "default_lat": 33.749, "default_zoom": 11}}
    fieldsets = (
        (None, {"fields": ("name", "description", "category", "date", "end_date")}),
        ("Location", {"fields": ("location_name", "location", "timezone")}),
        ("Media", {"fields": ("image_file", "image")}),
        ("Editorial", {"fields": ("curator_note", "curator_name"), "classes": ("collapse",)}),
        ("Settings", {"fields": ("is_free", "is_active", "more_details_url")}),
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
