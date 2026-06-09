"""
Payment API URL Configuration
"""

from django.urls import path

from apps.payments import views

app_name = 'payments'

urlpatterns = [
    path('', views.PaymentAPIRoot.as_view(), name='api-root'),
    path('initiate/', views.InitiatePaymentView.as_view(), name='payment-initiate'),
    path('status/<str:checkout_request_id>/', views.PaymentStatusView.as_view(), name='payment-status'),
    path('mpesa/callback/', views.MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('payout/initiate/', views.InitiatePayoutView.as_view(), name='payout-initiate'),
    path('mpesa/b2c-callback/', views.B2CCallbackView.as_view(), name='b2c-callback'),
    path('mpesa/b2b-callback/', views.B2BCallbackView.as_view(), name='b2b-callback'),
    path('reversal/initiate/', views.InitiateReversalView.as_view(), name='reversal-initiate'),
    path('mpesa/reversal-callback/', views.ReversalCallbackView.as_view(), name='reversal-callback'),
]
