"""
Daraja M-Pesa API Integration

This is the ONLY module that makes HTTP calls to Safaricom Daraja API.
No other module may call requests directly to Daraja endpoints.

CRITICAL ARCHITECTURE:
- COLLECTION: User pays Pursuit's shortcode (settings.MPESA_SHORTCODE)
  - OrganizerPaymentConfig is NOT read during collection
- PAYOUT: Pursuit pays organizer based on OrganizerPaymentConfig.payout_type
"""

import base64
import logging
import os
import re
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Build callback URLs from base
_BASE = os.environ.get('MPESA_BASE_CALLBACK_URL', '')
STK_CALLBACK_URL = f"{_BASE}/api/payments/mpesa/callback/"
B2C_CALLBACK_URL = f"{_BASE}/api/payments/mpesa/b2c-callback/"
B2B_CALLBACK_URL = f"{_BASE}/api/payments/mpesa/b2b-callback/"
REVERSAL_CALLBACK_URL = f"{_BASE}/api/payments/mpesa/reversal-callback/"

# Daraja endpoints
MPESA_ENV = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')
if MPESA_ENV == 'production':
    BASE_URL = 'https://api.safaricom.co.ke'
else:
    BASE_URL = 'https://sandbox.safaricom.co.ke'

OAUTH_URL = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
STK_PUSH_URL = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
STK_QUERY_URL = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
B2C_URL = f"{BASE_URL}/mpesa/b2c/v1/paymentrequest"
B2B_URL = f"{BASE_URL}/mpesa/b2b/v1/paymentrequest"
REVERSAL_URL = f"{BASE_URL}/mpesa/reversal/v1/request"


def get_access_token() -> str:
    """
    Returns a valid Daraja OAuth access token.
    Checks cache key 'mpesa:oauth_token' first.
    On miss, fetches from Daraja and caches with TTL 3300s (55 min buffer).
    """
    token = cache.get('mpesa:oauth_token')
    if token:
        logger.debug("Using cached M-Pesa OAuth token")
        return token

    logger.info("Fetching new M-Pesa OAuth token from Daraja")

    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    response = requests.get(
        OAUTH_URL,
        auth=(consumer_key, consumer_secret),
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    token = data['access_token']

    # Cache for 55 minutes (3300 seconds) - 5 min buffer on 60 min expiry
    cache.set('mpesa:oauth_token', token, 3300)

    logger.info("M-Pesa OAuth token cached successfully")
    return token


def validate_phone(phone: str) -> str:
    """
    Normalises phone to 254XXXXXXXXX format (12 digits).
    Accepts: "0712345678", "254712345678", "+254712345678"
    Raises ValidationError if the number cannot be normalised
    or is not a valid Safaricom/Airtel number (2547X or 2541X prefix).
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Handle different input formats
    if digits.startswith('254'):
        normalized = digits
    elif digits.startswith('0'):
        normalized = '254' + digits[1:]
    elif digits.startswith('7') or digits.startswith('1'):
        normalized = '254' + digits
    else:
        raise ValidationError(
            f"Invalid phone number format: {phone}. "
            "Must start with 254, 0, 7, or 1."
        )

    # Validate Safaricom (7) or Airtel (1) network prefix and length
    if not re.match(r'^254[17]\d{8}$', normalized):
        raise ValidationError(
            f"Invalid phone number: {phone}. "
            "Must be Safaricom (2547XXXXXXXX) or Airtel (2541XXXXXXXX) Kenya number."
        )

    logger.debug(f"Phone validated: {phone} -> {normalized}")
    return normalized


def build_stk_password(shortcode: str, passkey: str, timestamp: str) -> str:
    """
    Returns base64(shortcode + passkey + timestamp).
    Timestamp format: YYYYMMDDHHmmss
    """
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    encoded = base64.b64encode(data_to_encode.encode()).decode('utf-8')
    return encoded


def initiate_stk_push(phone: str, amount: int, order) -> dict:
    """
    Initiates STK Push to the user's phone.

    IMPORTANT: Always uses Pursuit's own shortcode for collection.
    OrganizerPaymentConfig is NOT read here.

    BusinessShortCode = settings.MPESA_SHORTCODE
    PartyB            = settings.MPESA_SHORTCODE
    PartyA            = validated phone (user paying)
    PhoneNumber       = validated phone
    TransactionType   = "CustomerPayBillOnline"
    AccountReference  = f"PST-{str(order.id)[:8].upper()}"  (max 12)
    TransactionDesc   = "Ticket"  (max 13)
    Amount            = int(amount)  (whole shillings only)

    Returns full Daraja response dict.
    Raises requests.HTTPError on non-200 from Daraja.
    """
    validated_phone = validate_phone(phone)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    password = build_stk_password(shortcode, passkey, timestamp)

    # Account reference max 12 characters
    account_ref = f"PST-{str(order.id)[:8].upper()}"

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": validated_phone,
        "PartyB": shortcode,
        "PhoneNumber": validated_phone,
        "CallBackURL": STK_CALLBACK_URL,
        "AccountReference": account_ref,
        "TransactionDesc": "Ticket"  # Max 13 characters
    }

    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }

    logger.info(
        f"Initiating STK Push for order {order.id}: "
        f"phone={validated_phone[-4:]}, amount={amount}"
    )

    response = requests.post(
        STK_PUSH_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    logger.info(
        f"STK Push initiated successfully: "
        f"CheckoutRequestID={data.get('CheckoutRequestID')}, "
        f"ResponseCode={data.get('ResponseCode')}"
    )

    return data


def query_stk_status(checkout_request_id: str) -> dict:
    """
    Queries the status of an STK Push transaction directly from Daraja.
    Used as fallback if callback is delayed or not received.
    Returns Daraja query response dict.
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    password = build_stk_password(shortcode, passkey, timestamp)

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id
    }

    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }

    logger.info(f"Querying STK status for {checkout_request_id}")

    response = requests.post(
        STK_QUERY_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    return response.json()


def initiate_b2c_payout(payout) -> dict:
    """
    Sends organizer's cut to their personal M-Pesa number.
    Reads payout.organizer.organizerpaymentconfig.payout_destination
    CommandID: "BusinessPayment"
    Amount: int(payout.amount)
    ResultURL: B2C_CALLBACK_URL
    QueueTimeOutURL: B2C_CALLBACK_URL
    Requires SecurityCredential from settings.MPESA_SECURITY_CREDENTIAL
    Returns Daraja B2C response dict.
    """
    payment_config = payout.organizer.organizerpaymentconfig
    destination = payment_config.payout_destination
    validated_phone = validate_phone(destination)

    payload = {
        "InitiatorName": settings.MPESA_INITIATOR_NAME,
        "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
        "CommandID": "BusinessPayment",
        "Amount": int(payout.amount),
        "PartyA": settings.MPESA_SHORTCODE,
        "PartyB": validated_phone,
        "Remarks": f"Payout {payout.id}",
        "QueueTimeOutURL": B2C_CALLBACK_URL,
        "ResultURL": B2C_CALLBACK_URL,
        "Occasion": f"Order {payout.order_id}"
    }

    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }

    logger.info(
        f"Initiating B2C payout {payout.id}: "
        f"phone={validated_phone[-4:]}, amount={int(payout.amount)}"
    )

    response = requests.post(
        B2C_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    logger.info(
        f"B2C payout initiated: "
        f"ConversationID={data.get('ConversationID')}, "
        f"ResponseCode={data.get('ResponseCode')}"
    )

    return data


def initiate_b2b_payout(payout) -> dict:
    """
    Sends organizer's cut to their business Paybill or Till.
    Reads payout_type and payout_destination from payment config.
    For b2b_paybill: ReceiverIdentifierType = 4
    For b2b_till:    ReceiverIdentifierType = 2
    Amount: int(payout.amount)
    ResultURL: B2B_CALLBACK_URL
    QueueTimeOutURL: B2B_CALLBACK_URL
    Returns Daraja B2B response dict.
    """
    payment_config = payout.organizer.organizerpaymentconfig
    payout_type = payment_config.payout_type
    destination = payment_config.payout_destination

    # Determine receiver identifier type
    if payout_type == 'b2b_paybill':
        receiver_identifier_type = 4
        command_id = "BusinessPayBill"
    elif payout_type == 'b2b_till':
        receiver_identifier_type = 2
        command_id = "BusinessBuyGoods"
    else:
        raise ValueError(f"Invalid payout_type for B2B: {payout_type}")

    payload = {
        "Initiator": settings.MPESA_INITIATOR_NAME,
        "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
        "CommandID": command_id,
        "SenderIdentifierType": 4,  # Paybill
        "RecieverIdentifierType": receiver_identifier_type,
        "Amount": int(payout.amount),
        "PartyA": settings.MPESA_SHORTCODE,
        "PartyB": destination,
        "AccountReference": f"Payout {payout.id}",
        "Remarks": f"Order {payout.order_id}",
        "QueueTimeOutURL": B2B_CALLBACK_URL,
        "ResultURL": B2B_CALLBACK_URL
    }

    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }

    logger.info(
        f"Initiating B2B payout {payout.id}: "
        f"type={payout_type}, destination={destination}, amount={int(payout.amount)}"
    )

    response = requests.post(
        B2B_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    logger.info(
        f"B2B payout initiated: "
        f"ConversationID={data.get('ConversationID')}, "
        f"ResponseCode={data.get('ResponseCode')}"
    )

    return data


def initiate_reversal(transaction_id: str, amount: int, phone: str) -> dict:
    """
    Reverses an M-Pesa transaction using Daraja Reversal API.
    transaction_id: MpesaReceiptNumber from the original transaction
    amount: int, full amount to reverse
    phone: original payer's phone number
    ResultURL: REVERSAL_CALLBACK_URL
    QueueTimeOutURL: REVERSAL_CALLBACK_URL
    Returns Daraja Reversal response dict.
    """
    validated_phone = validate_phone(phone)

    payload = {
        "Initiator": settings.MPESA_INITIATOR_NAME,
        "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
        "CommandID": "TransactionReversal",
        "TransactionID": transaction_id,
        "Amount": int(amount),
        "ReceiverParty": settings.MPESA_SHORTCODE,
        "RecieverIdentifierType": 4,  # Paybill
        "ResultURL": REVERSAL_CALLBACK_URL,
        "QueueTimeOutURL": REVERSAL_CALLBACK_URL,
        "Remarks": f"Refund {transaction_id}",
        "Occasion": "Event cancelled"
    }

    headers = {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }

    logger.info(
        f"Initiating reversal: "
        f"transaction_id={transaction_id}, amount={amount}, phone={validated_phone[-4:]}"
    )

    response = requests.post(
        REVERSAL_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    logger.info(
        f"Reversal initiated: "
        f"ConversationID={data.get('ConversationID')}, "
        f"ResponseCode={data.get('ResponseCode')}"
    )

    return data
