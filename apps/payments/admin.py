from django.contrib import admin

from .models import MPESATransaction, Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event', 'quantity', 'total', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'event__name', 'idempotency_key')
    readonly_fields = ('id', 'idempotency_key', 'created_at', 'organizer_payout_amount')

    fieldsets = (
        ('Order Info', {
            'fields': ('id', 'user', 'event', 'quantity', 'status', 'idempotency_key')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'platform_fee', 'total', 'organizer_payout_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def organizer_payout_amount(self, obj):
        """Show calculated payout amount"""
        return f"KES {obj.organizer_payout_amount()}"
    organizer_payout_amount.short_description = 'Organizer Payout'


@admin.register(MPESATransaction)
class MPESATransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'phone_number', 'transaction_status', 'mpesa_receipt', 'created_at')
    list_filter = ('result_code', 'created_at')
    search_fields = (
        'checkout_request_id',
        'merchant_request_id',
        'mpesa_receipt',
        'phone_number',
        'order__idempotency_key'
    )
    readonly_fields = (
        'order',
        'checkout_request_id',
        'merchant_request_id',
        'phone_number',
        'mpesa_receipt',
        'result_code',
        'result_desc',
        'created_at'
    )

    fieldsets = (
        ('Transaction Info', {
            'fields': ('order', 'phone_number', 'checkout_request_id', 'merchant_request_id')
        }),
        ('Result', {
            'fields': ('result_code', 'result_desc', 'mpesa_receipt')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def transaction_status(self, obj):
        """Human-readable transaction status"""
        if obj.result_code == '0':
            return '✓ Success'
        elif obj.result_code:
            return f'✗ Failed ({obj.result_code})'
        return '⏳ Pending'
    transaction_status.short_description = 'Status'
