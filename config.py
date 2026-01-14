import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'reaganx12x#'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///pos.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_PASSWORD = os.environ.get('SECRET_PASSWORD') or 'reaganx12x#'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'transactionsfinance355@gmail.com'
    MAIL_PASSWORD = 'rvzxngpossphfgzm'
    # Add to your existing Config class in config.py

# Payment Gateway Configurations
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')

# ✅ CORRECT - Pass the VARIABLE NAME
PLAID_CLIENT_ID = os.environ.get('PLAID_CLIENT_ID', '5e8f4c4b5a3b3a0014d4d3a7')  # Default value if env var not set
PLAID_SECRET = os.environ.get('PLAID_SECRET', 'ab5c2e1234567890abcdef123456')  # Default value if env var not set
PLAID_ENVIRONMENT = os.environ.get('PLAID_ENVIRONMENT', 'sandbox')

# Teller API
TELLER_APPLICATION_ID = os.environ.get('TELLER_APPLICATION_ID')
TELLER_PRIVATE_KEY = os.environ.get('TELLER_PRIVATE_KEY')

# Encryption key for sensitive data (use Fernet encryption)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')