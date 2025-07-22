from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='cashier')  # cashier, manager, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))

    location = db.relationship('Location', backref='users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), unique=True, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(50), index=True)
    buying_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    current_stock = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=5)
    tax_rate = db.Column(db.Float, default=0.16)
    vatable = db.Column(db.Boolean, default=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    dealer_id = db.Column(db.Integer, db.ForeignKey('dealers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier = db.relationship('Supplier', backref=db.backref('supplier_products', lazy=True))
    dealer = db.relationship('Dealer', backref='products')

    def update_stock(self, quantity):
        new_stock = self.current_stock + quantity
        if new_stock < 0:
            raise ValueError("Stock cannot be negative")
        self.current_stock = new_stock
        db.session.commit()

    def check_stock(self, quantity):
        if quantity > self.current_stock:
            return False, f"Only {self.current_stock} items available in stock"
        return True, ""

class Dealer(db.Model):
    __tablename__ = 'dealers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    email = db.Column(db.String(100), unique=True)
    loyalty_points = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def add_loyalty_points(self, points):
        self.loyalty_points += points
        db.session.commit()

class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(20), unique=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, index=True)
    payment_status = db.Column(db.String(20), default='completed')
    sale_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    channel = db.Column(db.String(20), default='offline')
    points_earned = db.Column(db.Integer, default=0)
    split_payment = db.Column(db.Boolean, default=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))

    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')
    location = db.relationship('Location', backref='sales')
    customer = db.relationship('Customer', backref='purchases')
    user = db.relationship('User', backref='sales')

    @classmethod
    def generate_receipt_number(cls):
        today = datetime.now().strftime('%Y%m%d')
        last_receipt = cls.query.filter(cls.receipt_number.like(f'IMO-{today}-%')).order_by(cls.id.desc()).first()
        if last_receipt:
            last_num = int(last_receipt.receipt_number.split('-')[-1])
            return f'IMO-{today}-{last_num + 1:04d}'
        return f'IMO-{today}-0001'

class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='sale_items')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.product and self.quantity:
            success, message = self.product.check_stock(self.quantity)
            if not success:
                raise ValueError(message)
            self.product.update_stock(-self.quantity)

class InventoryMovement(db.Model):
    __tablename__ = 'inventory_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    movement_type = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reference_id = db.Column(db.Integer)
    movement_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    unit_price = db.Column(db.Float, nullable=True)
    total_amount = db.Column(db.Float, nullable=True)

    product = db.relationship('Product', backref='movements')

class AccountingEntry(db.Model):
    __tablename__ = 'accounting_entries'

    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    account_type = db.Column(db.String(50), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    debit_amount = db.Column(db.Float, default=0.0)
    credit_amount = db.Column(db.Float, default=0.0)
    reference_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    reconciled = db.Column(db.Boolean, default=False)

class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    KRA_pin = db.Column(db.String(20))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    total_amount = db.Column(db.Float, nullable=False)

    items = db.relationship('PurchaseOrderItem', backref='purchase_order', cascade='all, delete-orphan')
    supplier = db.relationship('Supplier', backref='purchase_orders')
    user = db.relationship('User', backref='purchase_orders')

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='purchase_order_items')

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    payee_name = db.Column(db.String(100), nullable=False)
    transaction_details = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Expense {self.payee_name}>'

class Financier(db.Model):
    __tablename__ = 'financiers'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    financier_id = db.Column(db.String(50), nullable=False, unique=True)
    financier_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    email = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    kra_pin = db.Column(db.String(20))
    description = db.Column(db.Text)
    credit_amount = db.Column(db.Float, default=0.0)
    debit_amount = db.Column(db.Float, default=0.0)
    credits = db.relationship('FinancierCredit', backref='financier', lazy=True)
    debits = db.relationship('FinancierDebit', backref='financier', lazy=True)

    def __repr__(self):
        return f'<Financier {self.financier_name}>'

class FinancierCredit(db.Model):
    __tablename__ = 'financier_credits'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    financier_id = db.Column(db.String(50), db.ForeignKey('financiers.financier_id'), nullable=False)
    financier_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount_credited = db.Column(db.Float, nullable=False)
    transaction_ref = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<FinancierCredit {self.transaction_ref}>'

class FinancierDebit(db.Model):
    __tablename__ = 'financier_debits'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    financier_id = db.Column(db.String(50), db.ForeignKey('financiers.financier_id'), nullable=False)
    financier_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    principal_amount = db.Column(db.Float, nullable=False)
    interest_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_ref = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<FinancierDebit {self.transaction_ref}>'

class OTP(db.Model):
    __tablename__ = 'otps'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    expiry = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<OTP {self.email}>'
