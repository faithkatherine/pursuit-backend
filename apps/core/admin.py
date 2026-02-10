from django.contrib import admin
from apps.core.models import Category

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'emoji')
    search_fields = ('name',)

admin.site.register(Category, CategoryAdmin)
