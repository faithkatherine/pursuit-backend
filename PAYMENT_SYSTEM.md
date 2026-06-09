# Pursuit Payment System — Complete Documentation

> **Last Updated:** June 2026
> **Author:** Faith Catherine
> **Status:** Production Ready

This is the single source of truth for Pursuit's M-Pesa payment system. It documents the architecture, implementation, API endpoints, and testing procedures.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Decisions](#architecture-decisions)
3. [Money Flow](#money-flow)
4. [Database Models](#database-models)
5. [API Endpoints](#api-endpoints)
6. [Security & Idempotency](#security--idempotency)
7. [Testing Guide](#testing-guide)
8. [Deployment Checklist](#deployment-checklist)

---

## System Overview

**What is Pursuit?**
Hyperlocal event discovery and ticketing app for Nairobi, Kenya. M-Pesa native, editorial-first curation.

**Tech Stack:**
- Backend: Django 5 + PostgreSQL + Redis + Celery
- Payments: Safaricom Daraja API (M-Pesa STK Push, B2C, B2B, Reversal)
- API: REST for payments, GraphQL for app data
- Auth: JWT

**Core Principle:**
All ticket revenue flows to Pursuit's M-Pesa shortcode first. Organizers receive their share (total - platform fee) via automated payout 24 hours after payment.

---

## Architecture Decisions

### 1. Money Flows to Pursuit First

**Decision:** Pursuit collects 100% of ticket revenue, then pays organizers.

**Why:**
- Control over refunds (can reverse within 24h window)
- Clean audit trail
- Freeze payouts if event cancelled
- Support both personal M-Pesa (B2C) and business accounts (B2B)

**Model:** Same as Eventbrite, Ticketsasa, Ticketmaster.

---

### 2. Model B Pricing (Seller Pays Fee)

**Decision:** Buyer pays ticket price only. Platform fee (2%) deducted from organizer payout.

**Example:**
```
Ticket price:       KES 1,500
Buyer pays:         KES 1,500  (subtotal = total)
Platform fee:       KES 30     (2% of 1,500)
Organizer receives: KES 1,470  (total - platform_fee)
```

**Why:** Kenyan buyers expect all-inclusive pricing. Adding a "booking fee" reduces conversion.

---

### 3. Collection ALWAYS Uses Pursuit's Shortcode

**CRITICAL:** During payment collection, the organizer's payment config (their Paybill, their Till) is **completely ignored**.

**STK Push Request:**
```json
{
  "BusinessShortCode": "<PURSUIT_SHORTCODE>",
  "PartyB": "<PURSUIT_SHORTCODE>",
  "PartyA": "<USER_PHONE>",
  "PhoneNumber": "<USER_PHONE>",
  "TransactionType": "CustomerPayBillOnline"
}
```

Organizer's `collection_shortcode` and `collection_passkey` are **reserved for future direct collection flows** and are NOT used in V1.

---

### 4. Payout Uses Organizer's Config

**Decision:** 24 hours after payment, read `OrganizerPaymentConfig.payout_type` and route to:
- `b2c` → Daraja B2C API → Personal M-Pesa number
- `b2b_paybill` → Daraja B2B API → Business Paybill
- `b2b_till` → Daraja B2B API → Business Till

**Payout scheduled from:** `order.paid_at + 24 hours` (NOT `order.created_at`)

---

### 5. REST for Payments, GraphQL for App Data

**Decision:** Payment endpoints use Django REST Framework, not GraphQL.

**Why:**
- Daraja callbacks are plain HTTP POST (cannot be GraphQL mutations)
- Payment operations are commands with strict contracts
- Per-endpoint security (IP whitelisting, rate limiting) simpler with DRF
- Audit logging cleaner with explicit REST URLs

---

### 6. Ticket Reservation on Order Creation

**Decision:** Decrement `event.available_tickets` when Order is created (status='pending'), not when paid.

**Why:**
- Prevents overselling during STK Push wait period
- Simpler refund logic (just increment back)
- Tickets released if order expires/fails

**Implementation:**
```python
# Reserve tickets atomically
Event.objects.filter(id=event_id).update(
    available_tickets=F('available_tickets') - quantity
)

# Release tickets on failure/expiration
Event.objects.filter(id=event_id).update(
    available_tickets=F('available_tickets') + order.quantity
)
```

---

### 7. Platform Fee from Database, Not Settings

**Decision:** Store platform fee percentage in `PlatformConfig` model (database), not `settings.py`.

**Why:**
- Runtime configuration changes without deployment
- A/B testing different fee structures
- Historical tracking of fee changes
- Future: tiered fees by event category

**Current Default:** 2%

---

## Money Flow

### Collection Flow (User → Pursuit)

```
┌──────────────┐
│ User taps    │
│ "Pay KES X"  │
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────┐
│ POST /api/payments/initiate/           │
│ • Redis lock (10s)                     │
│ • Check existing order (idempotency)   │
│ • SELECT FOR UPDATE on Event           │
│ • Calculate fees (PlatformConfig)      │
│ • Create Order (pending)               │
│ • Reserve tickets (F() atomic update)  │
│ • Call Daraja STK Push                 │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ STK Push Request to Daraja           │
│ BusinessShortCode: PURSUIT_SHORTCODE │
│ PartyB:            PURSUIT_SHORTCODE │
│ Amount:            int(order.total)  │
│ AccountReference:  PST-{order_id}    │
│ TransactionDesc:   "Ticket"          │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────┐
│ User's phone receives    │
│ STK Push prompt          │
│ User enters M-Pesa PIN   │
└────────────────┬─────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ Daraja → POST /api/payments/mpesa/       │
│          callback/                       │
│                                          │
│ ResultCode = 0 (success):                │
│ • order.status = 'paid'                  │
│ • order.paid_at = now()                  │
│ • Create OrganizerPayout                 │
│   scheduled_for = paid_at + 24h          │
│                                          │
│ ResultCode != 0 (failure):               │
│ • order.status = 'failed'                │
│ • Release tickets atomically             │
└──────────────────────────────────────────┘
```

---

### Payout Flow (Pursuit → Organizer)

```
┌────────────────────────────────────┐
│ Celery Beat (runs every hour)     │
│ Task: process_scheduled_payouts()  │
│                                    │
│ Finds OrganizerPayout records:    │
│ • status = 'scheduled'             │
│ • scheduled_for <= now()           │
└────────────────┬───────────────────┘
                 │
                 ▼
┌────────────────────────────────────┐
│ Read OrganizerPaymentConfig        │
│ • payout_type                      │
│ • payout_destination               │
└────────────────┬───────────────────┘
                 │
         ┌───────┴────────┐
         ▼                ▼
┌─────────────┐   ┌────────────────┐
│ payout_type │   │ payout_type =  │
│ = 'b2c'     │   │ 'b2b_paybill'  │
│             │   │ or 'b2b_till'  │
│ Call Daraja │   │                │
│ B2C API     │   │ Call Daraja    │
│             │   │ B2B API        │
└─────────────┘   └────────────────┘
         │                │
         └───────┬────────┘
                 ▼
┌──────────────────────────────────┐
│ Money leaves Pursuit's account   │
│ → Organizer's M-Pesa/Paybill     │
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Daraja → POST /api/payments/     │
│          mpesa/b2c-callback/     │
│          or b2b-callback/        │
│                                  │
│ ResultCode = 0:                  │
│ • payout.status = 'completed'    │
│ • payout.completed_at = now()    │
│ • payout.mpesa_receipt = receipt │
│                                  │
│ ResultCode != 0:                 │
│ • payout.status = 'failed'       │
│ • Celery retries (5 attempts,    │
│   1 hour apart)                  │
└──────────────────────────────────┘
```

---

## Database Models

### Order
```python
class Order(models.Model):
    user = ForeignKey(User, SET_NULL, null=True)  # Financial audit trail
    event = ForeignKey(Event, PROTECT)             # Cannot delete event with orders
    quantity = PositiveIntegerField(default=1)

    subtotal = DecimalField()      # ticket_price × quantity
    platform_fee = DecimalField()  # subtotal × PlatformConfig.fee_percentage
    total = DecimalField()         # = subtotal (Model B, no fee added to buyer)

    status = CharField(choices=[
        'pending',   # STK Push initiated, awaiting payment
        'paid',      # Payment confirmed by Daraja callback
        'failed',    # User cancelled or insufficient funds
        'expired',   # Pending > 15 minutes (Celery task marked it)
        'refunded',  # Event cancelled or manual admin refund
    ])

    idempotency_key = CharField(max_length=64, unique=True)
    created_at = DateTimeField(auto_now_add=True)
    paid_at = DateTimeField(null=True)  # When status changed to 'paid'

    # Payout calculation
    def organizer_payout_amount(self):
        return self.total - self.platform_fee
```

**Key Points:**
- `user` is SET_NULL for GDPR compliance (financial records survive user deletion)
- `paid_at` triggers payout countdown (scheduled_for = paid_at + 24h)
- `total == subtotal` in Model B (leaves room for discounts in V2)

---

### MPESATransaction
```python
class MPESATransaction(models.Model):
    order = OneToOneField(Order, CASCADE)
    phone_number = CharField(max_length=15)            # 254712345678 format
    checkout_request_id = CharField(unique=True)       # Daraja's unique ID
    merchant_request_id = CharField(max_length=100)

    mpesa_receipt = CharField(null=True)               # e.g., "NLJ7RT61SV"
    result_code = CharField(null=True)                 # '0' = success
    result_desc = CharField(null=True)
    created_at = DateTimeField(auto_now_add=True)

    def is_successful(self):
        return self.result_code == '0'
```

---

### OrganizerPaymentConfig
```python
class OrganizerPaymentConfig(models.Model):
    organizer = OneToOneField(OrganizerProfile, CASCADE)

    # Collection (RESERVED - not used in V1)
    collection_type = CharField(choices=['paybill', 'till'])
    collection_shortcode = CharField(max_length=20)
    collection_passkey = CharField(max_length=255)

    # Payout (ACTIVE - used for organizer payouts)
    payout_type = CharField(choices=[
        'b2c',           # Personal M-Pesa number
        'b2b_paybill',   # Business Paybill shortcode
        'b2b_till',      # Business Till number
    ])
    payout_destination = CharField(max_length=20)  # Phone or shortcode

    verified = BooleanField(default=False)
```

**Critical:** `collection_*` fields are ignored during payment collection. Only `payout_*` fields are read.

---

### OrganizerPayout
```python
class OrganizerPayout(models.Model):
    organizer = ForeignKey(OrganizerProfile, PROTECT)
    order = ForeignKey(Order, PROTECT)

    amount = DecimalField()          # order.total - order.platform_fee
    platform_fee = DecimalField()    # Copy from order for audit

    status = CharField(choices=[
        'scheduled',   # Payout queued, scheduled_for in future
        'processing',  # Daraja API called, awaiting callback
        'completed',   # Payout successful, money sent
        'failed',      # Payout failed (Celery retries up to 5 times)
        'frozen',      # Event cancelled, payout blocked
    ])

    scheduled_for = DateTimeField()  # order.paid_at + 24h
    mpesa_receipt = CharField(null=True)
    frozen_reason = CharField(null=True)
    completed_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)
```

---

### PlatformConfig (Core App)
```python
class PlatformConfig(models.Model):
    is_active = BooleanField(default=True)
    fee_percentage = DecimalField(default=2.00)  # 2% = Decimal('2.00')

    order_expiration_minutes = PositiveIntegerField(default=15)
    payout_delay_hours = PositiveIntegerField(default=24)

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    updated_by = ForeignKey(User, SET_NULL, null=True)

    @classmethod
    def get_platform_fee_percentage(cls):
        """Returns Decimal('0.02') for 2%"""
        config = cls.get_active()
        return config.fee_percentage / Decimal('100.00')
```

**Singleton pattern:** Only one `is_active=True` record exists at a time.

---

## API Endpoints

### 1. Initiate Payment

**Endpoint:** `POST /api/payments/initiate/`
**Auth:** Required (IsAuthenticated)
**Purpose:** User taps "Pay" button in app

**Request:**
```json
{
  "phone_number": "0712345678",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "quantity": 2
}
```

**Response (200):**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "checkout_request_id": "ws_CO_191220191020363925",
  "status": "pending",
  "total": "3000.00",
  "resuming": false
}
```

**Response (429) - Duplicate Request:**
```json
{
  "error": "payment_in_progress"
}
```

**Response (400) - Already Purchased:**
```json
{
  "error": "already_purchased"
}
```

**Response (400) - Sold Out:**
```json
{
  "error": "insufficient_tickets",
  "details": {
    "requested": 5,
    "available": 2
  }
}
```

**What Happens:**
1. Redis lock acquired (`payment_lock:{user_id}:{event_id}`, 10s TTL)
2. Check for existing order (idempotency)
3. If pending order < 90s old, return existing checkout_request_id with `resuming: true`
4. If pending order >= 90s, mark expired, release tickets, continue
5. Atomic transaction: SELECT FOR UPDATE on Event, check tickets, create Order, reserve tickets
6. Call Daraja STK Push with Pursuit's shortcode
7. Create MPESATransaction record
8. Return checkout_request_id for polling

**Constraints:**
- Phone validated to `254[17]\d{8}` format
- AccountReference max 12 chars: `PST-{order_id[:8]}`
- TransactionDesc max 13 chars: `"Ticket"`
- Amount sent as `int(order.total)` (whole shillings)

---

### 2. Payment Status (Polling)

**Endpoint:** `GET /api/payments/status/{checkout_request_id}/`
**Auth:** Required (IsAuthenticated)
**Purpose:** Frontend polls every 3 seconds while waiting for payment

**Response:**
```json
{
  "status": "pending",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "mpesa_receipt": null
}
```

**Status Values:**
- `pending` - Waiting for user to enter PIN / Daraja callback
- `paid` - Payment successful, mpesa_receipt populated
- `failed` - User cancelled or insufficient funds
- `expired` - Order timeout (15 minutes)

**Authorization:** Returns 403 if user doesn't own the order.

---

### 3. M-Pesa Callback (STK Push)

**Endpoint:** `POST /api/payments/mpesa/callback/`
**Auth:** None (@csrf_exempt)
**Purpose:** Daraja sends payment result here

**Request (Success):**
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220191020363925",
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 3000},
          {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
          {"Name": "TransactionDate", "Value": 20260609143000},
          {"Name": "PhoneNumber", "Value": 254712345678}
        ]
      }
    }
  }
}
```

**Request (Failure):**
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220191020363925",
      "ResultCode": 1032,
      "ResultDesc": "Request cancelled by user"
    }
  }
}
```

**Response (ALWAYS):**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

**What Happens (Success):**
1. Find MPESATransaction by CheckoutRequestID
2. Check order not already processed (duplicate callback guard)
3. Atomic transaction:
   - Update txn: `result_code='0'`, `mpesa_receipt='NLJ7RT61SV'`
   - Update order: `status='paid'`, `paid_at=now()`
   - Create OrganizerPayout: `scheduled_for = paid_at + 24h`

**What Happens (Failure):**
1. Update txn: `result_code='1032'`, `result_desc='Request cancelled by user'`
2. Update order: `status='failed'`
3. Release tickets atomically: `Event.objects.filter(...).update(available_tickets=F(...) + quantity)`

**CRITICAL:** Always return HTTP 200. If non-200 returned, Daraja retries infinitely.

---

### 4. Initiate Payout (Manual Trigger)

**Endpoint:** `POST /api/payments/payout/initiate/`
**Auth:** Admin only
**Purpose:** Manually trigger a specific payout (for testing or stuck payouts)

**Request:**
```json
{
  "payout_id": 123
}
```

**Response:**
```json
{
  "payout_id": 123,
  "status": "processing",
  "daraja_response": {
    "ConversationID": "AG_20260609_123",
    "ResponseCode": "0",
    "ResponseDescription": "Accept the service request successfully."
  }
}
```

**What Happens:**
1. Verify payout status is 'scheduled'
2. Read `OrganizerPaymentConfig.payout_type`
3. Route to `daraja.initiate_b2c_payout()` or `daraja.initiate_b2b_payout()`
4. Update payout status to 'processing'

---

### 5. B2C/B2B Payout Callbacks

**Endpoints:**
- `POST /api/payments/mpesa/b2c-callback/`
- `POST /api/payments/mpesa/b2b-callback/`

**Auth:** None (@csrf_exempt)
**Purpose:** Daraja sends payout result here

**Response (ALWAYS):**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

**Implementation Status:** Currently logs callback data. Payout lookup by ConversationID to be implemented.

---

### 6. Initiate Refund

**Endpoint:** `POST /api/payments/reversal/initiate/`
**Auth:** Admin only
**Purpose:** Refund a paid order (event cancellation or customer request)

**Request:**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Within 24h Window):**
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "reversal_api",
  "daraja_response": {
    "ConversationID": "AG_20260609_456",
    "ResponseCode": "0"
  }
}
```

**Response (Outside 24h Window):**
```json
{
  "error": "B2C refund flow for orders outside 24h window not yet implemented"
}
```

**What Happens:**
1. Verify order status is 'paid'
2. Check if `order.paid_at + 24h >= now()`
3. If within window: call Daraja Reversal API
4. If outside window: raise NotImplementedError (manual B2C refund needed)

---

### 7. Reversal Callback

**Endpoint:** `POST /api/payments/mpesa/reversal-callback/`
**Auth:** None (@csrf_exempt)

**Response (ALWAYS):**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

**Implementation Status:** Currently logs callback. Order lookup by transaction ID to be implemented.

---

## Security & Idempotency

### Threat Model

**Four attack vectors defended:**

1. **Double Initiation** - User taps Pay twice
   - **Defense:** Redis lock (10s TTL, nx=True)

2. **Race Condition** - Two users grab last ticket simultaneously
   - **Defense:** `SELECT FOR UPDATE` inside `transaction.atomic()`

3. **Callback Replay** - Daraja sends same callback twice (it does this)
   - **Defense:** Check `order.status not in ['paid', 'failed', 'refunded']` before processing

4. **Spoofed Callback** - External actor hits callback URL
   - **Defense:** IP whitelist (Safaricom IPs), callback structure validation

---

### Redis Lock Pattern

**Purpose:** Prevent duplicate payment initiations before hitting database.

**Implementation:**
```python
lock_key = f"payment_lock:{user.id}:{event_id}"
lock_acquired = cache.add(lock_key, 'locked', timeout=10)

if not lock_acquired:
    return Response({'error': 'payment_in_progress'}, status=429)

try:
    # Payment initiation logic
finally:
    cache.delete(lock_key)  # Release lock
```

**Why 10 seconds?** Daraja STK Push initiation takes 1-3 seconds. 10s allows retries but prevents abuse.

---

### Idempotency Strategy

**Frontend Retry Scenario:**
1. User taps Pay
2. STK Push initiated successfully
3. Network drops before response reaches app
4. User taps Pay again

**Backend Response:**
```python
existing_order = Order.objects.filter(
    user=user,
    event_id=event_id,
    status='pending'
).order_by('-created_at').first()

if existing_order:
    age_seconds = (timezone.now() - existing_order.created_at).total_seconds()

    if age_seconds < 90:
        # Return existing checkout_request_id
        return Response({
            'checkout_request_id': existing_order.mpesa_transaction.checkout_request_id,
            'resuming': True
        })
```

**Idempotency Key:** SHA256 hash of `user_id:event_id:quantity:timestamp` (64 chars, unique constraint).

---

### Callback Security

**Always Return 200:**
```python
def post(self, request):
    success_response = JsonResponse({
        'ResultCode': 0,
        'ResultDesc': 'Accepted'
    })

    try:
        # Process callback
    except Exception as e:
        logger.exception(f"Callback error: {e}")

    return success_response  # ALWAYS return this
```

**Why?** Non-200 responses cause Daraja to retry infinitely. Log errors internally, return 200 externally.

---

## Testing Guide

### Prerequisites

1. **Create PlatformConfig:**
```python
from apps.core.models import PlatformConfig

PlatformConfig.objects.create(
    is_active=True,
    fee_percentage=2.00,
    order_expiration_minutes=15,
    payout_delay_hours=24
)
```

2. **Set Environment Variables in `.env`:**
```bash
MPESA_ENVIRONMENT=sandbox
MPESA_CONSUMER_KEY=your_sandbox_key
MPESA_CONSUMER_SECRET=your_sandbox_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_sandbox_passkey
MPESA_INITIATOR_NAME=testapi
MPESA_SECURITY_CREDENTIAL=your_encrypted_credential
MPESA_BASE_CALLBACK_URL=https://your-ngrok-url.ngrok.io
```

3. **Start ngrok:**
```bash
ngrok http 8000
```
Copy the HTTPS URL to `MPESA_BASE_CALLBACK_URL`.

---

### Test Scenarios

#### Scenario 1: Successful Payment

**Step 1 - Initiate Payment:**
```bash
curl -X POST http://localhost:8000/api/payments/initiate/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "254708374149",
    "event_id": "<event_uuid>",
    "quantity": 1
  }'
```

**Expected Response:**
```json
{
  "order_id": "...",
  "checkout_request_id": "ws_CO_...",
  "status": "pending",
  "total": "1500.00",
  "resuming": false
}
```

**Step 2 - Check Phone:**
Test phone receives STK Push. Enter PIN.

**Step 3 - Monitor Callback:**
```bash
# Watch ngrok traffic at http://localhost:4040
# You should see POST to /api/payments/mpesa/callback/
```

**Step 4 - Poll Status:**
```bash
curl http://localhost:8000/api/payments/status/<checkout_request_id>/ \
  -H "Authorization: Bearer <token>"
```

**Expected Response:**
```json
{
  "status": "paid",
  "order_id": "...",
  "mpesa_receipt": "NLJ7RT61SV"
}
```

**Verify in Database:**
```python
order = Order.objects.get(id='...')
assert order.status == 'paid'
assert order.paid_at is not None

payout = OrganizerPayout.objects.get(order=order)
assert payout.status == 'scheduled'
assert payout.scheduled_for == order.paid_at + timedelta(hours=24)
```

---

#### Scenario 2: User Cancels Payment

**Step 1 - Initiate Payment** (same as above)

**Step 2 - Cancel on Phone:** Tap "Cancel" on STK Push prompt

**Step 3 - Verify Callback:**
```json
{
  "Body": {
    "stkCallback": {
      "ResultCode": 1032,
      "ResultDesc": "Request cancelled by user"
    }
  }
}
```

**Step 4 - Poll Status:**
```json
{
  "status": "failed",
  "order_id": "...",
  "mpesa_receipt": null
}
```

**Verify Tickets Released:**
```python
event.refresh_from_db()
# available_tickets should be back to original count
```

---

#### Scenario 3: Duplicate Request (Idempotency)

**Step 1 - Initiate Payment**

**Step 2 - Initiate Again (Within 90s):**
```bash
# Same request as Step 1
```

**Expected Response:**
```json
{
  "order_id": "<same_order_id>",
  "checkout_request_id": "<same_checkout_id>",
  "status": "pending",
  "total": "1500.00",
  "resuming": true  // ← Note this flag
}
```

**Verify:** No new Order or MPESATransaction created.

---

#### Scenario 4: Sold Out Event

**Setup:**
```python
event.available_tickets = 2
event.save()
```

**Request:** Try to buy 5 tickets

**Expected Response (400):**
```json
{
  "error": "insufficient_tickets",
  "details": {
    "requested": 5,
    "available": 2
  }
}
```

---

#### Scenario 5: Manual Payout Trigger

**Setup:**
```python
# Create a payout record
payout = OrganizerPayout.objects.create(
    organizer=organizer,
    order=order,
    amount=Decimal('1470.00'),
    platform_fee=Decimal('30.00'),
    status='scheduled',
    scheduled_for=timezone.now()  # Due now
)
```

**Request:**
```bash
curl -X POST http://localhost:8000/api/payments/payout/initiate/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "payout_id": <payout.id>
  }'
```

**Expected:** Daraja B2C/B2B call made, payout status = 'processing'

---

#### Scenario 6: Refund Within 24h

**Setup:**
```python
order.status = 'paid'
order.paid_at = timezone.now() - timedelta(hours=12)  # 12 hours ago
order.save()
```

**Request:**
```bash
curl -X POST http://localhost:8000/api/payments/reversal/initiate/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "<order_id>"
  }'
```

**Expected Response:**
```json
{
  "order_id": "...",
  "method": "reversal_api",
  "daraja_response": {
    "ConversationID": "...",
    "ResponseCode": "0"
  }
}
```

---

### Celery Tasks Testing

**Test Expire Stale Orders:**
```python
from apps.payments.tasks import expire_stale_orders

# Create old pending order
old_order = OrderFactory(status='pending')
old_order.created_at = timezone.now() - timedelta(minutes=20)
old_order.save()

# Run task
result = expire_stale_orders()

# Verify
old_order.refresh_from_db()
assert old_order.status == 'expired'
assert result['expired_count'] == 1
```

**Test Process Scheduled Payouts:**
```python
from apps.payments.tasks import process_scheduled_payouts

# Create due payout
payout = OrganizerPayoutWithOrderFactory(
    status='scheduled',
    scheduled_for=timezone.now() - timedelta(hours=1)
)

# Mock Daraja call
with patch('apps.payments.daraja.initiate_b2c_payout') as mock:
    mock.return_value = {'ResponseCode': '0'}
    result = process_scheduled_payouts()

# Verify
payout.refresh_from_db()
assert payout.status == 'processing'
```

---

## Deployment Checklist

### Sandbox → Production Migration

- [ ] **Daraja Production App Created**
  - Products enabled: STK Push + B2C + B2B
  - Do NOT add C2B Register URL

- [ ] **Go-Live Approvals Submitted**
  - STK Push: Auto-approved
  - B2C: 1-2 weeks review
  - B2B: 1-2 weeks review

- [ ] **Production Credentials Updated**
  - `MPESA_ENVIRONMENT=production`
  - `MPESA_CONSUMER_KEY` (production)
  - `MPESA_CONSUMER_SECRET` (production)
  - `MPESA_SHORTCODE` (Pursuit's registered Paybill/Till)
  - `MPESA_PASSKEY` (from Daraja portal)
  - `MPESA_SECURITY_CREDENTIAL` (RSA-encrypted)

- [ ] **Callback URLs on Real Domain**
  - `MPESA_BASE_CALLBACK_URL=https://api.pursuitapp.co.ke`
  - All callbacks using HTTPS (not HTTP, not ngrok)

- [ ] **Safaricom IP Whitelisting**
  - Get official Safaricom callback IP range
  - Configure firewall/nginx to only accept callbacks from those IPs

- [ ] **Redis Configured**
  - OAuth token caching working (55min TTL)
  - Payment locks working (10s TTL)

- [ ] **Celery Beat Running**
  - `expire_stale_orders` every 1 hour
  - `process_scheduled_payouts` every 1 hour
  - Verify with Celery Flower or logs

- [ ] **Database Migrations Applied**
  - All payment models created
  - PlatformConfig record exists with `is_active=True`

- [ ] **Test Transaction in Production**
  - KES 1 test payment
  - Verify full flow: initiate → callback → payout scheduled
  - Verify refund works

- [ ] **Monitoring Configured**
  - Failed payment alerts (email/Slack)
  - Stuck payout alerts (5 consecutive failures)
  - Daraja API downtime alerts

---

## Support & Troubleshooting

### Common Issues

**Issue:** STK Push not received on phone
**Fix:** Verify phone number format (254XXXXXXXXX). Check Daraja sandbox test numbers.

**Issue:** Callback not hitting server
**Fix:** Verify `MPESA_BASE_CALLBACK_URL` is HTTPS and publicly accessible. Check ngrok tunnel active.

**Issue:** "Payment in progress" error persists
**Fix:** Redis lock stuck. Clear manually: `cache.delete(f"payment_lock:{user_id}:{event_id}")`

**Issue:** Payout not processing
**Fix:** Check Celery Beat running. Verify `scheduled_for <= now()`. Check B2C/B2B approval status in Daraja portal.

**Issue:** Tickets not releasing on failure
**Fix:** Verify atomic F() update in callback view. Check database transaction isolation level.

---

## Code Locations

**Payment Logic:**
- `apps/payments/daraja.py` - All Daraja API calls
- `apps/payments/views.py` - REST endpoints
- `apps/payments/serializers.py` - Request/response validation
- `apps/payments/tasks.py` - Celery background tasks
- `apps/payments/urls.py` - URL routing
- `apps/payments/models.py` - Order, MPESATransaction
- `apps/organizers/models.py` - OrganizerPayout, OrganizerPaymentConfig
- `apps/core/models.py` - PlatformConfig

**Tests:**
- `apps/payments/test_api.py` - API endpoint tests
- `apps/payments/test_tasks.py` - Celery task tests
- `apps/payments/tests.py` - Model tests
- `apps/organizers/tests.py` - Organizer model tests

---

**Document Version:** 1.0
**Last Review:** June 2026
**Next Review:** After first production transaction
