from django.contrib import admin
from .models import Order, MPESATransaction

# Register your models here.
class OrderAdmin(admin.ModelAdmin):
    class Meta:
        model = Order
    
    list_display = ("id", "user", "event", "total_price", "status", "created_at")
    search_fields = ("user__email", "event__title")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "idempotency_key")

class MPESATransactionAdmin(admin.ModelAdmin):
    class Meta:
        model = MPESATransaction

    list_display = ('id', 'order', 'phone_number', 'result_code',
        'mpesa_receipt', 'created_at')
    search_fields = ("checkout_request_id", "merchant_request_id", "mpesa_receipt", "phone_number")
    list_filter = ("created_at", "result_code")
    readonly_fields = ("created_at", "checkout_request_id", "merchant_request_id", "transaction_id")

admin.site.register(Order, OrderAdmin)
admin.site.register(MPESATransaction, MPESATransactionAdmin)