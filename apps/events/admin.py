from django.contrib.gis import admin
from .models import  Event

# Register your models here.

class EventAdmin(admin.GISModelAdmin):
    list_display = ('name', 'date', 'location_name')
    search_fields = ('name', 'location_name')
    list_filter = ('date', 'category')
    readonly_fields = ('created_at', 'updated_at')
    gis_widget_kwargs = {
          'attrs': {'default_lon': -84.388, 'default_lat': 33.749, 'default_zoom': 11}
      }

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    class Media:
        js = ('events/js/geocode_location.js',)

admin.site.register(Event, EventAdmin)
