from django.contrib.gis import admin
from django.template.response import TemplateResponse
from .models import  Event

# Register your models here.

class EventAdmin(admin.GISModelAdmin):
    list_display = ('name', 'date', 'location_name', 'is_active')
    search_fields = ('name', 'location_name')
    list_filter = ('date', 'category', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['deactivate_events', 'activate_events']
    gis_widget_kwargs = {
          'attrs': {'default_lon': -84.388, 'default_lat': 33.749, 'default_zoom': 11}
      }

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

    @admin.action(description='Deactivate selected events')
    def deactivate_events(self, request, queryset):
        if request.POST.get('post'):
            count = queryset.update(is_active=False)
            self.message_user(request, f'{count} event(s) deactivated.')
            return None
        return TemplateResponse(request, 'admin/events/confirm_action.html', {
            **self.admin_site.each_context(request),
            'title': 'Confirm Deactivation',
            'queryset': queryset,
            'opts': self.model._meta,
            'action': 'deactivate_events',
            'action_description': 'deactivate',
        })

    @admin.action(description='Activate selected events')
    def activate_events(self, request, queryset):
        if request.POST.get('post'):
            count = queryset.update(is_active=True)
            self.message_user(request, f'{count} event(s) activated.')
            return None
        return TemplateResponse(request, 'admin/events/confirm_action.html', {
            **self.admin_site.each_context(request),
            'title': 'Confirm Activation',
            'queryset': queryset,
            'opts': self.model._meta,
            'action': 'activate_events',
            'action_description': 'activate',
        })

    class Media:
        js = ('events/js/geocode_location.js',)

admin.site.register(Event, EventAdmin)
