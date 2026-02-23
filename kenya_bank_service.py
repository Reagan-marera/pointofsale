# kenya_bank_service.py
import requests
import base64
from datetime import datetime, timedelta
import json
import logging
import random

logger = logging.getLogger(__name__)

class KenyaBankService:
    """Service for Kenyan Mobile Money Integrations (M-Pesa)"""

    def __init__(self, gateway_config=None):
        self.config = gateway_config or {}
        # Simulation mode is only True if explicitly requested OR if keys are missing
        self.is_sandbox = self.config.get('test_mode', True)
        self.simulation_mode = self.config.get('simulate', False) or not self.config.get('api_key')

    def get_mpesa_access_token(self):
        """Get access token from Safaricom Daraja API"""
        if self.simulation_mode:
            return "simulated_access_token"

        consumer_key = self.config.get('api_key')
        consumer_secret = self.config.get('api_secret')

        if self.is_sandbox:
            api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        else:
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

        if self.is_sandbox:
            api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        else:
            api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

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
            logger.info(f"Calling M-Pesa API: {api_url}")
            res = requests.post(api_url, json=payload, headers=headers)
            logger.info(f"M-Pesa Response: {res.status_code} - {res.text}")
            return res.json()
        except Exception as e:
            logger.error(f"M-Pesa API Error: {e}")
            return {'success': False, 'error': str(e)}

    def query_stk_push_status(self, checkout_request_id):
        """Query the status of an STK push transaction"""
        if self.simulation_mode:
            # Simulate a successful payment after a few attempts
            # In a real app, we'd check a cache or DB for the callback status
            import random
            result = random.random()
            if result > 0.7:
                return {'success': True, 'status': 'Completed', 'ResultCode': '0', 'ResultDesc': 'The service request is processed successfully.'}
            elif result > 0.4:
                return {'success': False, 'status': 'Pending', 'ResultCode': '1', 'ResultDesc': 'Request is still being processed.'}
            else:
                return {'success': False, 'status': 'Failed', 'ResultCode': '1032', 'ResultDesc': 'Request cancelled by user.'}

        access_token = self.get_mpesa_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to authenticate'}

        passkey = self.config.get('webhook_secret')
        business_short_code = self.config.get('merchant_id')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode()

        if self.is_sandbox:
            api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
        else:
            api_url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"

        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }

        try:
            res = requests.post(api_url, json=payload, headers=headers)
            data = res.json()
            if data.get('ResultCode') == '0':
                return {'success': True, 'status': 'Completed', 'data': data}
            return {'success': False, 'status': 'Failed', 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}
