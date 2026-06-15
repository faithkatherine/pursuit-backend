"""
Pytest configuration and shared fixtures for payment tests.

All Daraja API mocks are defined here to ensure consistency across all tests.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

PLATFORM_FEE_RATE = Decimal('0.02')

MOCK_STK_SUCCESS_RESPONSE = {
    'MerchantRequestID': '29115-34620561-1',
    'CheckoutRequestID': 'ws_CO_191220191020363925',
    'ResponseCode': '0',
    'ResponseDescription': 'Success. Request accepted for processing',
    'CustomerMessage': 'Success. Request accepted for processing',
}

MOCK_STK_CALLBACK_SUCCESS = {
    'Body': {
        'stkCallback': {
            'MerchantRequestID': '29115-34620561-1',
            'CheckoutRequestID': 'ws_CO_191220191020363925',
            'ResultCode': 0,
            'ResultDesc': 'The service request is processed successfully.',
            'CallbackMetadata': {
                'Item': [
                    {'Name': 'Amount', 'Value': 1500},
                    {'Name': 'MpesaReceiptNumber', 'Value': 'NLJ7RT61SV'},
                    {'Name': 'TransactionDate', 'Value': 20191219102115},
                    {'Name': 'PhoneNumber', 'Value': 254712345678},
                ]
            }
        }
    }
}

MOCK_STK_CALLBACK_FAILED = {
    'Body': {
        'stkCallback': {
            'MerchantRequestID': 'f1e2-4b95-a71d-b30d3cdbb7a7942864',
            'CheckoutRequestID': 'ws_CO_21072024125243250722943992',
            'ResultCode': 1032,
            'ResultDesc': 'Request cancelled by user',
        }
    }
}

MOCK_B2C_SUCCESS_RESPONSE = {
    'ConversationID': 'AG_20180223_0000493344ae97d86f75',
    'OriginatorConversationID': '3213-416199-2',
    'ResponseCode': '0',
    'ResponseDescription': 'Accept the service request successfully.',
}

MOCK_REVERSAL_SUCCESS_RESPONSE = {
    'ResponseCode': '0',
    'ResponseDescription': 'The service request is processed successfully.',
}


@pytest.fixture
def mock_daraja_stk_push():
    """Mock successful STK Push initiation."""
    with patch('apps.payments.daraja.initiate_stk_push') as mock:
        mock.return_value = MOCK_STK_SUCCESS_RESPONSE
        yield mock


@pytest.fixture
def mock_daraja_b2c():
    """Mock successful B2C payout."""
    with patch('apps.payments.daraja.initiate_b2c_payout') as mock:
        mock.return_value = MOCK_B2C_SUCCESS_RESPONSE
        yield mock


@pytest.fixture
def mock_daraja_b2b():
    """Mock successful B2B payout."""
    with patch('apps.payments.daraja.initiate_b2b_payout') as mock:
        mock.return_value = MOCK_B2C_SUCCESS_RESPONSE
        yield mock


@pytest.fixture
def mock_daraja_reversal():
    """Mock successful reversal."""
    with patch('apps.payments.daraja.initiate_reversal') as mock:
        mock.return_value = MOCK_REVERSAL_SUCCESS_RESPONSE
        yield mock


@pytest.fixture
def mock_daraja_token():
    """Mock OAuth token generation."""
    with patch('apps.payments.daraja.get_access_token') as mock:
        mock.return_value = 'test_access_token_12345'
        yield mock
