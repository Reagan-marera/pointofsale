# bank_integration.py
import requests
import json

class SimpleBankAPIProcessor:
    def __init__(self, connection_type='plaid'):
        self.connection_type = connection_type
    
    def create_link_token(self, user_id):
        """Create a Plaid link token using direct API call"""
        try:
            # Use these working test credentials
            client_id = "64764c7c7a744700138841cc"  # Updated test client ID
            secret = "34c0b638dd5ae8d2f9e9e49b7e5d2d"  # Updated test secret
            
            # Or try these alternative test credentials
            # client_id = "test_id"
            # secret = "test_secret"
            
            # Direct API call to Plaid
            url = "https://sandbox.plaid.com/link/token/create"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            payload = {
                "client_id": client_id,
                "secret": secret,
                "client_name": "My POS System",
                "user": {
                    "client_user_id": str(user_id)
                },
                "products": ["transactions"],  # Changed from "auth" to "transactions"
                "country_codes": ["US"],
                "language": "en",
                "redirect_uri": "https://example.com/oauth-redirect"  # Add redirect URI
            }
            
            print(f"🔧 Sending to Plaid: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            print(f"📊 Plaid Response Status: {response.status_code}")
            print(f"📊 Plaid Response: {response.text[:200]}")
            
            if response.status_code == 200:
                data = response.json()
                link_token = data.get('link_token')
                print(f"✅ Link token created successfully")
                return {
                    'success': True, 
                    'link_token': link_token,
                    'environment': 'sandbox'
                }
            else:
                # Get detailed error message
                try:
                    error_data = response.json()
                    error_msg = f"Plaid Error {response.status_code}: {error_data.get('error_message', response.text[:100])}"
                except:
                    error_msg = f"Plaid Error {response.status_code}: {response.text[:100]}"
                
                print(f"❌ {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Connection Error: {str(e)}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}