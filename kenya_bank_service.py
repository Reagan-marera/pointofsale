# kenya_bank_service.py
import requests
import base64
from datetime import datetime, timedelta
import json
import logging
import random

logger = logging.getLogger(__name__)

class KenyaBankService:
    """Service for Kenyan Bank and Mobile Money Integrations"""

    BANKS = {
        'equity': {'name': 'Equity Bank', 'code': 'EQBL'},
        'kcb': {'name': 'KCB Bank', 'code': 'KCBL'},
        'coop': {'name': 'Co-operative Bank', 'code': 'COOP'},
        'absa': {'name': 'Absa Bank', 'code': 'ABSA'},
        'ncba': {'name': 'NCBA Bank', 'code': 'NCBA'},
        'stanbic': {'name': 'Stanbic Bank', 'code': 'STAN'},
        'dtb': {'name': 'DTB Bank', 'code': 'DTBL'},
        'family': {'name': 'Family Bank', 'code': 'FAML'},
    }

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

    @staticmethod
    def get_bank_list():
        """Get list of available banks"""
        return [
            {'id': code, 'name': info['name'], 'code': info['code']}
            for code, info in KenyaBankService.BANKS.items()
        ]

    def connect_bank(self, bank_id, account_number):
        """Connect to bank account API"""
        if self.simulation_mode:
            bank_info = self.BANKS.get(bank_id, {'name': 'Unknown Bank', 'code': 'UNKN'})
            connection_id = f"bank_{bank_id}_{int(datetime.now().timestamp())}"
            return {
                'success': True,
                'connection_id': connection_id,
                'bank_name': bank_info['name'],
                'bank_code': bank_info['code'],
                'account_number': f"****{account_number[-4:]}" if len(account_number) > 4 else f"****{account_number}",
                'account_type': random.choice(['Checking', 'Savings', 'Current']),
                'balance': round(random.uniform(1000, 500000), 2),
                'currency': 'KES',
                'connected_at': datetime.now().isoformat(),
                'account_holder': 'Business Account'
            }
        return {'success': False, 'error': 'Bank API not configured'}

    def get_transactions(self, days=30):
        """Get bank transactions via API"""
        if self.simulation_mode:
            transactions = []
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            current_sim_balance = 250000.00
            for i in range(random.randint(15, 40)):
                date = start_date + timedelta(days=random.randint(0, days))
                is_deposit = random.random() > 0.6
                amount = round(random.uniform(100, 50000), 2) * (1 if is_deposit else -1)
                trans_type = 'deposit' if is_deposit else 'withdrawal'

                transactions.append({
                    'id': f"txn_{int(date.timestamp())}_{i}",
                    'date': date.strftime('%Y-%m-%d'),
                    'time': date.strftime('%H:%M'),
                    'description': f"{trans_type.capitalize()} Transaction",
                    'type': trans_type,
                    'category': random.choice(['Sales', 'Supplies', 'Utilities', 'Rent', 'Payroll', 'Other']),
                    'amount': amount,
                    'balance': current_sim_balance,
                    'reference': f"REF{random.randint(1000, 9999)}",
                    'status': 'completed'
                })
                current_sim_balance -= amount # Reverse to simulate backward in time
            transactions.sort(key=lambda x: x['date'], reverse=True)
            return {'success': True, 'transactions': transactions}
        return {'success': False, 'error': 'Bank API not configured'}

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

        api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
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
