# kenya_bank_service.py
import requests
import base64
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class KenyaBankService:
    """Service for Kenyan Bank and Mobile Money Integrations"""

    def __init__(self, gateway_config=None):
        self.config = gateway_config or {}
        self.simulation_mode = self.config.get('test_mode', True)

    def get_mpesa_access_token(self):
        """Get access token from Safaricom Daraja API"""
        if self.simulation_mode:
            return "simulated_access_token"

        consumer_key = self.config.get('api_key')
        consumer_secret = self.config.get('api_secret')

        api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        if not self.simulation_mode:
            api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

        try:
            res = requests.get(api_url, auth=(consumer_key, consumer_secret))
            if res.status_code == 200:
                return res.json().get('access_token')
            return None
        except Exception as e:
            logger.error(f"Error getting M-Pesa token: {e}")
            return None

    def initiate_stk_push(self, phone_number, amount, account_ref, description):
        """Initiate M-Pesa STK Push (Lipa na M-Pesa Online)"""
        if self.simulation_mode:
            logger.info(f"SIMULATION: STK Push initiated for {phone_number} amount {amount}")
            return {
                'success': True,
                'CheckoutRequestID': f'ws_CO_{datetime.now().strftime("%d%m%Y%H%M%S%f")}',
                'CustomerMessage': 'Success. Request accepted for processing',
                'ResponseDescription': 'Success. Request accepted for processing',
                'simulation': True
            }

        access_token = self.get_mpesa_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to authenticate with Safaricom'}

        passkey = self.config.get('webhook_secret')
        business_short_code = self.config.get('merchant_id')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode()

        api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        callback_url = self.config.get('callback_url', "https://example.com/api/mpesa/callback")

        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": business_short_code,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_ref,
            "TransactionDesc": description
        }

        try:
            res = requests.post(api_url, json=payload, headers=headers)
            return res.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_bank_transfer_status(self, transaction_ref):
        """Verify a bank transfer via API (e.g. Equity, KCB)"""
        # Logic for local bank API transaction inquiry
        if self.simulation_mode:
            return {'success': True, 'status': 'completed', 'amount': 100.0, 'currency': 'KES'}

        # Example for a generic Kenyan Bank API
        # endpoint = self.config.get('api_url') + "/transactions/status"
        # ...
        return {'success': False, 'error': 'Bank API integration not configured'}

    def get_bank_balance(self, account_number):
        """Simulate bank balance enquiry"""
        if self.simulation_mode:
            return {'success': True, 'balance': 543210.50, 'currency': 'KES'}
        return {'success': False, 'error': 'Bank API integration not configured'}

    def initiate_b2c_transfer(self, phone_number, amount, reason):
        """Send money from Business to Customer (M-Pesa B2C)"""
        if self.simulation_mode:
            return {'success': True, 'OriginatorConversationID': 'simulated_id', 'simulation': True}

        # Real B2C logic would go here
        return {'success': False, 'error': 'B2C not implemented'}
