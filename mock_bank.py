# mock_bank.py
import random
from datetime import datetime, timedelta

class MockBankAPI:
    """Free mock bank API for development"""
    
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
    
    @staticmethod
    def get_bank_list():
        """Get list of available banks"""
        return [
            {'id': code, 'name': info['name'], 'code': info['code']}
            for code, info in MockBankAPI.BANKS.items()
        ]
    
    @staticmethod
    def connect_bank(bank_id, account_number):
        """Simulate connecting a bank account"""
        bank_info = MockBankAPI.BANKS.get(bank_id, {'name': 'Unknown Bank', 'code': 'UNKN'})
        
        # Generate fake connection
        connection_id = f"mock_{bank_id}_{int(datetime.now().timestamp())}"
        
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
            'account_holder': 'Demo Account Holder'
        }
    
    @staticmethod
    def get_transactions(connection_id, days=30):
        """Get mock transactions"""
        transactions = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Generate between 15-40 transactions
        for i in range(random.randint(15, 40)):
            date = start_date + timedelta(days=random.randint(0, days))
            
            # More likely to have recent transactions
            if random.random() > 0.7:
                date = end_date - timedelta(days=random.randint(0, 7))
            
            # Determine if deposit or withdrawal
            is_deposit = random.random() > 0.6
            if is_deposit:
                amount = round(random.uniform(1000, 50000), 2)
                trans_type = 'deposit'
            else:
                amount = -round(random.uniform(100, 20000), 2)
                trans_type = 'withdrawal'
            
            # Transaction categories
            categories = {
                'deposit': ['Salary', 'Business Income', 'Transfer In', 'Refund', 'Dividend'],
                'withdrawal': ['Shopping', 'Utilities', 'Transport', 'Entertainment', 'Food', 'Rent', 'Airtime']
            }
            
            descriptions = {
                'Salary': ['Monthly Salary', 'Bonus Payment', 'Commission'],
                'Business Income': ['Client Payment', 'Sales Revenue', 'Consulting Fee'],
                'Shopping': ['Nakumatt Supermarket', 'Carrefour', 'Quickmart'],
                'Utilities': ['KPLC Bill', 'Nairobi Water', 'Internet Bill'],
                'Transport': ['Fuel - Shell', 'Uber/Taxi', 'Matatu Fare'],
                'Food': ['Restaurant', 'Java House', 'KFC'],
                'Rent': ['Monthly Rent', 'House Payment'],
                'Airtime': ['Safaricom Airtime', 'Airtel Top-up']
            }
            
            category = random.choice(categories[trans_type])
            description = random.choice(descriptions.get(category, [category]))
            
            # Generate reference
            ref_prefix = 'DEP' if is_deposit else 'WDL'
            reference = f"{ref_prefix}{date.strftime('%m%d')}{random.randint(1000, 9999)}"
            
            transactions.append({
                'id': f"txn_{int(date.timestamp())}_{i}",
                'date': date.strftime('%Y-%m-%d'),
                'time': date.strftime('%H:%M:%S'),
                'description': description,
                'category': category,
                'type': trans_type,
                'amount': amount,
                'balance': round(random.uniform(5000, 300000), 2),
                'reference': reference,
                'status': 'completed'
            })
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return {
            'success': True,
            'connection_id': connection_id,
            'transactions': transactions[:50],  # Limit to 50 transactions
            'total': len(transactions),
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        }
    
    @staticmethod
    def get_account_summary(connection_id):
        """Get account summary"""
        current_date = datetime.now()
        
        return {
            'success': True,
            'summary': {
                'current_balance': round(random.uniform(15000, 250000), 2),
                'available_balance': round(random.uniform(14000, 240000), 2),
                'ledger_balance': round(random.uniform(16000, 260000), 2),
                'currency': 'KES',
                'account_status': 'Active',
                'last_updated': current_date.isoformat()
            },
            'stats': {
                'month_deposits': round(random.uniform(50000, 200000), 2),
                'month_withdrawals': round(random.uniform(45000, 180000), 2),
                'average_monthly_balance': round(random.uniform(80000, 150000), 2),
                'transactions_this_month': random.randint(20, 60)
            }
        }