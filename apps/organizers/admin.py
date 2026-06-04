from django.contrib import admin
from .models import OrganizerProfile

# Register your models here.
class OrganizersProfileAdmin(admin.ModelAdmin):
    class Meta:
        model = OrganizerProfile

    list_display = ("user", "business_name", "website_url")
    search_fields = ("user__email", "business_name")

admin.site.register(OrganizerProfile, OrganizersProfileAdmin)