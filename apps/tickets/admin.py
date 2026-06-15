from django.contrib import admin

from apps.tickets.models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'token',
        'attendee_name',
        'attendee_email',
        'event_title',
        'tier_name',
        'is_used',
        'used_at',
        'created_at',
    ]
    list_filter = [
        'used_at',
        'order_item__tier__event',
        'order_item__tier',
    ]
    search_fields = [
        'token',
        'attendee_name',
        'attendee_email',
        'order_item__order__id',
    ]
    readonly_fields = [
        'token',
        'order_item',
        'created_at',
        'used_at',
        'used_by',
    ]
    ordering = ['-created_at']

    @admin.display(description='Event')
    def event_title(self, obj: Ticket) -> str:
        return obj.event.title

    @admin.display(description='Tier')
    def tier_name(self, obj: Ticket) -> str:
        return obj.tier.name

    @admin.display(boolean=True, description='Used')
    def is_used(self, obj: Ticket) -> bool:
        return obj.used_at is not None
