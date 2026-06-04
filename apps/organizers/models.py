from django.db import models

# Create your models here.



class OrganizerProfile(models.Model):
    user = models.OneToOneField("users.User", on_delete=models.SET_NULL, null=True, related_name="organizer_profile")
    business_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    website_url = models.URLField(null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name or f"Organizer {self.id}"
    
class OrganizerPaymentInfo(models.Model):
    organizer = models.OneToOneField(OrganizerProfile, on_delete=models.CASCADE, related_name="payment_info")
    collection_type = models.CharField(max_length=20, choices=[
        ("paybill", "Paybill"),
        ("till_number", "Till Number"),
    ])
    collection_short_code = models.CharField(max_length=20)
    collection_passkey = models.CharField(max_length=255) # For MPESA, this is the Lipa Na MPESA Online Passkey
    payout_type = models.CharField(max_length=20, choices=[
        ("b2c", "Personal Phone Number"),
        ("b2b_paybill", "Business Paybill"),
        ("b2b_till", "Business Till Number"),
    ])

    payout_destination = models.CharField(max_length=20) #Phone number or shortcode
    verified = models.BooleanField(default=False)
 
    def __str__(self):
        return f"Payment Info for {self.organizer.business_name or self.organizer.id}"

class OrganizerPayoutHistory(models.Model):
    organizer = models.ForeignKey(OrganizerProfile, on_delete=models.CASCADE, related_name="payout_history")
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    payout_date = models.DateTimeField(auto_now_add=True)
    payout_method = models.CharField(max_length=20, choices=[
        ("b2c", "Personal Phone Number"),
        ("b2b_paybill", "Business Paybill"),
        ("b2b_till", "Business Till Number"),
    ])
    payout_destination = models.CharField(max_length=20) #Phone number or shortcode
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"),
        ("scheduled", "Scheduled"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("frozen", "Frozen"),  # For payouts that are on hold due to event cancellation or disputes
    ], default="pending")
    transaction_id = models.CharField(max_length=255, null=True, blank=True)

    scheduled_for = models.DateTimeField()       # every 24 hours if there are pending payouts, or specific date for manual payouts
    mpesa_receipt = models.CharField(max_length=50, null=True, blank=True)
    frozen_reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout of {self.amount} to {self.organizer.business_name or self.organizer.id} on {self.payout_date.strftime('%Y-%m-%d')}"
  
