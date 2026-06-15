from django.contrib import admin

from .models import OrganizerPaymentConfig, OrganizerPayout, OrganizerProfile


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'business_name', 'user', 'verified', 'is_active', 'created_at')
    list_filter = ('verified', 'is_active', 'created_at')
    search_fields = ('business_name', 'user__email', 'contact_email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'deactivated_at')

    fieldsets = (
        ('Business Info', {
            'fields': ('user', 'business_name', 'description', 'verified')
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone', 'website_url', 'logo_url')
        }),
        ('Status', {
            'fields': ('is_active', 'deactivated_at', 'deactivation_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['verify_organizers', 'deactivate_organizers']

    def verify_organizers(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f"{updated} organizer(s) verified.")
    verify_organizers.short_description = "Verify selected organizers"

    def deactivate_organizers(self, request, queryset):
        for org in queryset:
            org.deactivate(reason="Admin deactivated")
        self.message_user(request, f"{queryset.count()} organizer(s) deactivated.")
    deactivate_organizers.short_description = "Deactivate selected organizers"


@admin.register(OrganizerPaymentConfig)
class OrganizerPaymentConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'organizer', 'collection_type', 'payout_type', 'verified', 'created_at')
    list_filter = ('collection_type', 'payout_type', 'verified', 'created_at')
    search_fields = ('organizer__business_name', 'collection_shortcode', 'payout_destination')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Organizer', {
            'fields': ('organizer', 'verified')
        }),
        ('Collection Config (STK Push)', {
            'fields': ('collection_type', 'collection_shortcode', 'collection_passkey'),
            'description': 'How users pay for tickets (M-Pesa STK Push)'
        }),
        ('Payout Config (B2C/B2B)', {
            'fields': ('payout_type', 'payout_destination'),
            'description': 'How Pursuit pays the organizer'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['verify_payment_configs']

    def verify_payment_configs(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(request, f"{updated} payment config(s) verified.")
    verify_payment_configs.short_description = "Verify selected payment configs"


@admin.register(OrganizerPayout)
class OrganizerPayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'organizer', 'order', 'amount', 'platform_fee', 'status', 'scheduled_for', 'completed_at')
    list_filter = ('status', 'scheduled_for', 'created_at')
    search_fields = ('organizer__business_name', 'order__idempotency_key', 'mpesa_receipt')
    readonly_fields = ('id', 'organizer', 'order', 'amount', 'platform_fee', 'created_at', 'completed_at')

    fieldsets = (
        ('Payout Info', {
            'fields': ('id', 'organizer', 'order', 'status')
        }),
        ('Amounts', {
            'fields': ('amount', 'platform_fee'),
            'description': 'Amount = order.total - platform_fee (net to organizer)'
        }),
        ('Schedule', {
            'fields': ('scheduled_for', 'created_at', 'completed_at')
        }),
        ('M-Pesa Details', {
            'fields': ('mpesa_receipt', 'frozen_reason')
        }),
    )

    actions = ['freeze_payouts', 'process_scheduled_payouts']

    def freeze_payouts(self, request, queryset):
        for payout in queryset.filter(status='scheduled'):
            payout.freeze(reason="Admin frozen")
        self.message_user(request, f"{queryset.count()} payout(s) frozen.")
    freeze_payouts.short_description = "Freeze selected payouts"

    def process_scheduled_payouts(self, request, queryset):
        scheduled = queryset.filter(status='scheduled')
        self.message_user(
            request,
            f"{scheduled.count()} payout(s) marked for processing (Celery task will handle)"
        )
    process_scheduled_payouts.short_description = "Process selected scheduled payouts"
