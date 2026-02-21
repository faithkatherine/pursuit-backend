from django.contrib import admin

from .models import Category, Interest


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'icon')
    search_fields = ('name',)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'category', 'description')
    list_filter = ('category',)
    search_fields = ('name', 'description')
    ordering = ('name',)


admin.site.register(Category, CategoryAdmin)
