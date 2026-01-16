from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session,logging
from flask_mail import Mail, Message
from models import db,  User, Product, Sale, SaleItem, InventoryMovement, AccountingEntry,PurchaseOrder,Supplier,Expense,Dealer,PurchaseOrderItem,Financier,FinancierCredit,FinancierDebit,Location,OTP, SupplierQuotation, SupplierQuotationItem, Item, Category,BankTransaction,BankAccount,PaymentGateway,BankAPIConnection
from datetime import datetime,timedelta
from kenya_bank_service import KenyaBankService
import random
import json
from sqlalchemy.orm import joinedload
import string
from config import Config
from sqlalchemy import func, or_
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
import os  

app = Flask(__name__)
application = app  

app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Create tables and default admin user
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()

# Helper functions
def generate_barcode():
    return ''.join(random.choices(string.digits, k=12))

def calculate_tax(amount, tax_rate=0.16):
    return amount * tax_rate

# Authentication decorator
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Determine if this is an API request (JSON) or web form submission
    is_api_request = request.is_json
    
    # Allow registration if no users exist (initial setup)
    if not User.query.first():
        if request.method == 'POST':
            try:
                # Get data based on content type
                if is_api_request:
                    data = request.get_json()
                    username = data.get('username')
                    email = data.get('email')
                    password = data.get('password')
                else:
                    username = request.form['username']
                    email = request.form['email']
                    password = request.form['password']
                
                # Validate required fields
                if not all([username, email, password]):
                    if is_api_request:
                        return jsonify({'message': 'Missing required fields', 'status': 'error'}), 400
                    flash('Missing required fields', 'danger')
                    return redirect(url_for('register'))
                
                admin = User(
                    username=username,
                    email=email,
                    role='admin'
                )
                admin.set_password(password)
                
                db.session.add(admin)
                db.session.commit()
                
                if is_api_request:
                    return jsonify({
                        'message': 'Admin account created successfully! Please login.',
                        'status': 'success'
                    }), 201
                
                flash('Admin account created successfully! Please login.', 'success')
                return redirect(url_for('login'))
            
            except Exception as e:
                if is_api_request:
                    return jsonify({'message': str(e), 'status': 'error'}), 400
                flash(str(e), 'danger')
                return redirect(url_for('register'))
        
        # GET request - show registration form
        if is_api_request:
            return jsonify({'message': 'Registration available', 'status': 'success'}), 200
        return render_template('register.html')
    
    
    if request.method == 'POST':
        try:
            # Get data based on content type
            if is_api_request:
                data = request.get_json()
                username = data.get('username')
                email = data.get('email')
                password = data.get('password')
                role = data.get('role', 'cashier')  # Default to cashier
            else:
                username = request.form['username']
                email = request.form['email']
                password = request.form['password']
                role = request.form['role']
            
            secret_password = request.form.get('secret_password')
            if role in ['admin', 'manager'] and secret_password != app.config['SECRET_PASSWORD']:
                flash('Invalid secret password.', 'danger')
                return redirect(url_for('register'))

            # Validate required fields
            if not all([username, email, password, role]):
                if is_api_request:
                    return jsonify({'message': 'Missing required fields', 'status': 'error'}), 400
                flash('Missing required fields', 'danger')
                return redirect(url_for('register'))
            
            # Check for existing user
            if User.query.filter_by(username=username).first():
                if is_api_request:
                    return jsonify({'message': 'Username already exists', 'status': 'error'}), 400
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))
            
            if User.query.filter_by(email=email).first():
                if is_api_request:
                    return jsonify({'message': 'Email already exists', 'status': 'error'}), 400
                flash('Email already exists', 'danger')
                return redirect(url_for('register'))
            
            new_user = User(
                username=username,
                email=email,
                role=role
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            if is_api_request:
                return jsonify({
                    'message': 'User registered successfully!',
                    'user_id': new_user.id,
                    'status': 'success'
                }), 201
            
            flash('User registered successfully!', 'success')
            return redirect(url_for('manage_users'))
        
        except Exception as e:
            if is_api_request:
                return jsonify({'message': str(e), 'status': 'error'}), 400
            flash(str(e), 'danger')
            return redirect(url_for('register'))
    
    # GET request - show registration form
    if is_api_request:
        return jsonify({
            'message': 'Registration available for admins',
            'status': 'success'
        }), 200
    return render_template('register.html', is_admin_registration=True)
def login_required(roles=['cashier']):
    def decorator(f):
        from functools import wraps

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('You need to be logged in to access this page', 'danger')
                return redirect(url_for('login'))

            user = User.query.get(session['user_id'])
            if user is None:
                flash('User not found. Please log in again.', 'danger')
                return redirect(url_for('login'))

            if user.role not in roles and user.role != 'admin':
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)

        return decorated_function
    return decorator

# Update the dashboard route
@app.route('/dashboard')
@login_required(roles=['cashier', 'manager', 'admin'])
def dashboard():
    # Base query for sales
    base_sales_query = Sale.query
    if session['role'] == 'cashier':
        base_sales_query = base_sales_query.filter(Sale.user_id == session['user_id'])

    # Get basic stats for dashboard
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.current_stock < Product.min_stock_level).count()
    today = datetime.today().date()

    today_sales_query = base_sales_query.filter(func.date(Sale.sale_date) == today)
    today_sales = today_sales_query.count()

    # Get sales for the last 7 days
    sales_this_week = []
    max_sales = 0
    for i in range(7):
        day = today - timedelta(days=i)
        sales = base_sales_query.with_entities(func.sum(Sale.total_amount)).filter(func.date(Sale.sale_date) == day).scalar() or 0
        sales_this_week.append({'date': day.strftime('%a'), 'total_sales': sales})
        if sales > max_sales:
            max_sales = sales
    sales_this_week.reverse()

    # Get sales by payment method
    sales_by_payment_method = base_sales_query.with_entities(Sale.payment_method, func.sum(Sale.total_amount).label('total')).group_by(Sale.payment_method).all()

    return render_template('dashboard.html',
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         today_sales=today_sales,
                         sales_this_week=sales_this_week,
                         max_sales=max_sales,
                         sales_by_payment_method=sales_by_payment_method)
# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        try:
            if user and user.check_password(password) and user.is_active:
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session['location_id'] = user.location_id
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
        except ValueError as e:
            if "unsupported hash type scrypt" in str(e):
                flash('Password encryption needs update. Please contact admin to reset your password.', 'danger')
            else:
                flash('Login error occurred', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))



@app.route('/products')
@login_required(roles=['manager', 'admin'])
def products():
    page = request.args.get('page', 1, type=int)
    dealer_id = request.args.get('dealer_id', type=int)
    product_search = request.args.get('product_search')

    # Create a base query with joined loads for supplier and dealer
    query = Product.query.options(joinedload(Product.supplier), joinedload(Product.dealer)).order_by(Product.name.asc())

    # Apply dealer filter if dealer_id is provided
    if dealer_id:
        query = query.filter(Product.dealer_id == dealer_id)

    if product_search:
        query = query.filter(
            or_(
                Product.name.ilike(f'%{product_search}%'),
                Product.barcode == product_search
            )
        )

    # Paginate the results
    products = query.paginate(page=page, per_page=10)

    # Fetch all dealers and suppliers for the filter dropdowns
    dealers = Dealer.query.all()
    suppliers = Supplier.query.all()

    # Render the template with the fetched data
    return render_template('products.html',
                           products=products.items,
                           pagination=products,
                           dealers=dealers,
                           suppliers=suppliers)


@app.route('/products/<int:product_id>', methods=['DELETE'])
@login_required(roles=['admin'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    # Delete related inventory movements
    InventoryMovement.query.filter_by(product_id=product.id).delete()

    # Delete related sale_items first
    SaleItem.query.filter_by(product_id=product.id).delete()

    # Now delete the product
    db.session.delete(product)
    db.session.commit()

    return jsonify({'message': 'Product deleted successfully!'})

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    suppliers = Supplier.query.all()
    dealers = Dealer.query.all()
    items = Item.query.all()
    categories = Category.query.all()

    if request.method == 'POST':
        product.name = request.form['name']
        product.category = request.form['category']
        product.buying_price = float(request.form['buying_price'])
        product.selling_price = float(request.form['selling_price'])
        product.current_stock = int(request.form['stock'])
        product.min_stock_level = int(request.form['min_stock'])
        
        # Get the submitted barcode
        submitted_barcode = request.form['barcode'].strip()
        
        # Only update barcode if it's different from current barcode
        if submitted_barcode != product.barcode:
            # Check if new barcode already exists for another product
            existing_product = Product.query.filter(
                Product.barcode == submitted_barcode,
                Product.id != product_id  # Exclude current product
            ).first()
            
            if existing_product:
                flash(f'Barcode "{submitted_barcode}" already exists for product "{existing_product.name}".', 'danger')
                return redirect(url_for('edit_product', product_id=product_id))
            
            product.barcode = submitted_barcode
        
        product.supplier_id = request.form['supplier_id']
        product.dealer_id = request.form['dealer_id']
        product.vatable = 'vatable' in request.form

        if not product.name or not product.category or not product.buying_price or not product.selling_price or not product.current_stock or not product.min_stock_level or not product.barcode or not product.supplier_id or not product.dealer_id:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_product', product_id=product_id))
        
        try:
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('products'))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('edit_product', product_id=product_id))

    return render_template('edit_product.html', product=product, suppliers=suppliers, dealers=dealers, items=items, categories=categories)
@app.route('/items', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def manage_items():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_item = Item(name=name)
            db.session.add(new_item)
            db.session.commit()
            flash('Item added successfully!', 'success')
        return redirect(url_for('manage_items'))

    items = Item.query.all()
    return render_template('items.html', items=items)

@app.route('/items/delete/<int:item_id>', methods=['POST'])
@login_required(roles=['admin'])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    try:
        # First delete all related purchase order items
        PurchaseOrderItem.query.filter_by(item_id=item_id).delete()
        
        # Then delete all related supplier quotation items
        SupplierQuotationItem.query.filter_by(item_id=item_id).delete()
        
        # Now delete the item
        db.session.delete(item)
        db.session.commit()
        
        flash('Item and all related records deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {str(e)}', 'danger')
    
    return redirect(url_for('manage_items'))

@app.route('/categories', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def manage_categories():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash('Category added successfully!', 'success')
        return redirect(url_for('manage_categories'))

    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required(roles=['admin'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('manage_categories'))
@app.route('/admin/users')
@login_required(roles=['admin'])
def manage_users():
    users = User.query.order_by(User.username.asc()).all()
    locations = Location.query.all()
    return render_template('users.html', users=users, locations=locations)

@app.route('/admin/locations')
@login_required(roles=['admin'])
def manage_locations():
    locations = Location.query.all()
    return render_template('locations.html', locations=locations)

@app.route('/admin/locations/add', methods=['POST'])
@login_required(roles=['admin'])
def add_location():
    name = request.form['name']
    address = request.form['address']
    new_location = Location(name=name, address=address)
    db.session.add(new_location)
    db.session.commit()
    flash('Location added successfully!', 'success')
    return redirect(url_for('manage_locations'))

@app.route('/admin/locations/edit/<int:location_id>', methods=['POST'])
@login_required(roles=['admin'])
def edit_location(location_id):
    location = Location.query.get_or_404(location_id)
    location.name = request.form['name']
    location.address = request.form['address']
    db.session.commit()
    flash('Location updated successfully!', 'success')
    return redirect(url_for('manage_locations'))

@app.route('/admin/locations/delete/<int:location_id>')
@login_required(roles=['admin'])
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    db.session.delete(location)
    db.session.commit()
    flash('Location deleted successfully!', 'success')
    return redirect(url_for('manage_locations'))

@app.route('/admin/reports/employee')
@login_required(roles=['manager'])
def employee_report():
    users = User.query.all()
    user_id = request.args.get('user_id', type=int)
    sales_by_employee = []

    query = db.session.query(
        User.username,
        func.sum(Sale.total_amount).label('total_sales'),
        func.count(Sale.id).label('total_transactions')
    ).join(Sale).group_by(User.username)

    if user_id:
        query = query.filter(User.id == user_id)

    sales_by_employee = query.all()

    return render_template('employee_report.html', users=users, sales_by_employee=sales_by_employee)

@app.route('/admin/reports/daily')
@login_required(roles=['manager', 'cashier', 'admin'])
def daily_report():
    date_str = request.args.get('date')
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        date = datetime.today().date()

    # Base query for sales on the selected date
    sales_query = Sale.query.filter(func.date(Sale.sale_date) == date)
    if session['role'] == 'cashier':
        sales_query = sales_query.filter(Sale.user_id == session['user_id'])

    # Calculate total sales
    total_sales = sales_query.with_entities(func.sum(Sale.total_amount)).scalar() or 0

    # Initialize values for all roles
    total_expenses = 0
    net_profit = 0

    # Managers and admins see expenses and net profit
    if session['role'] in ['manager', 'admin']:
        # Calculate total expenses for the day
        total_expenses_query = db.session.query(func.sum(Expense.amount)).filter(func.date(Expense.date) == date)
        total_expenses = total_expenses_query.scalar() or 0

        # Calculate Cost of Goods Sold (COGS) for the day
        cogs_query = db.session.query(func.sum(SaleItem.quantity * Product.buying_price))\
            .join(Sale, Sale.id == SaleItem.sale_id)\
            .join(Product, Product.id == SaleItem.product_id)\
            .filter(func.date(Sale.sale_date) == date)

        # If a manager is viewing their own report, this will be filtered.
        # This assumes a manager might also be a cashier.
        if session['role'] == 'manager' and 'cashier' in session.get('roles', []):
             cogs_query = cogs_query.filter(Sale.user_id == session['user_id'])

        total_cogs = cogs_query.scalar() or 0

        # Calculate net profit
        net_profit = total_sales - total_cogs - total_expenses

    return render_template('daily_report.html',
                         total_sales=total_sales,
                         total_expenses=total_expenses,
                         net_profit=net_profit,
                         date=date_str if date_str else date.strftime('%Y-%m-%d'))

@app.route('/admin/reports/supplier')
@login_required(roles=['manager'])
def supplier_report():
    suppliers = Supplier.query.all()
    supplier_id = request.args.get('supplier_id', type=int)
    products_data = []

    if supplier_id:
        products_data = db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label('items_sold'),
            func.sum(SaleItem.total_price).label('total_sales'),
            func.sum((SaleItem.unit_price - Product.buying_price) * SaleItem.quantity).label('total_profit')
        ).join(SaleItem, SaleItem.product_id == Product.id)\
         .filter(Product.supplier_id == supplier_id)\
         .group_by(Product.name)\
         .all()

    return render_template('supplier_report.html', suppliers=suppliers, products=products_data)


@app.route('/admin/reports/sales')
@login_required(roles=['manager'])
def sales_report():
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    payment_method = request.args.get('payment_method')
    product_search = request.args.get('product_search')
    
    # Build base query for ALL sales (for totals)
    base_query = Sale.query
    
    # Apply filters to base query
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        base_query = base_query.filter(Sale.sale_date >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        base_query = base_query.filter(Sale.sale_date < end_date_obj)
    
    if payment_method:
        base_query = base_query.filter(Sale.payment_method == payment_method)
    
    # Handle product search separately
    if product_search:
        # For totals: get sale IDs that have the searched product
        sale_ids_with_product = db.session.query(SaleItem.sale_id).join(Product).filter(
            (Product.name.ilike(f'%{product_search}%')) |
            (Product.barcode.ilike(f'%{product_search}%'))
        ).distinct()
        
        base_query = base_query.filter(Sale.id.in_(sale_ids_with_product))
    
    # Calculate totals from ALL matching sales
    total_sales_result = base_query.with_entities(func.sum(Sale.total_amount)).scalar()
    total_sales = total_sales_result if total_sales_result else 0
    
    total_transactions_result = base_query.count()
    total_transactions = total_transactions_result if total_transactions_result else 0
    
    average_sale = total_sales / total_transactions if total_transactions > 0 else 0
    
    # Build display query with joins for showing sales details - NO LIMIT
    display_query = Sale.query.options(
        joinedload(Sale.items).joinedload(SaleItem.product),
        joinedload(Sale.user)
    )
    
    # Apply the same filters to display query
    if start_date:
        display_query = display_query.filter(Sale.sale_date >= start_date_obj)
    
    if end_date:
        display_query = display_query.filter(Sale.sale_date < end_date_obj)
    
    if payment_method:
        display_query = display_query.filter(Sale.payment_method == payment_method)
    
    if product_search:
        display_query = display_query.filter(Sale.id.in_(sale_ids_with_product))
    
    # Get ALL sales data for display (no limit, no pagination)
    sales = display_query.order_by(Sale.sale_date.desc()).all()
    
    # Sales by payment method - use the same base_query for consistency
    sales_by_method_query = base_query.with_entities(
        Sale.payment_method,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('total')
    ).group_by(Sale.payment_method)
    
    sales_by_method = sales_by_method_query.all()
    
    # FIXED: Calculate profit with proper joins
    profit_query = db.session.query(
        func.sum(SaleItem.quantity * (SaleItem.unit_price - Product.buying_price))
    ).select_from(SaleItem)\
     .join(Product, SaleItem.product_id == Product.id)\
     .join(Sale, SaleItem.sale_id == Sale.id)
    
    # Apply the same filters to profit query
    if start_date:
        profit_query = profit_query.filter(Sale.sale_date >= start_date_obj)
    if end_date:
        profit_query = profit_query.filter(Sale.sale_date < end_date_obj)
    if payment_method:
        profit_query = profit_query.filter(Sale.payment_method == payment_method)
    if product_search:
        profit_query = profit_query.filter(Sale.id.in_(sale_ids_with_product))
    
    total_profit_result = profit_query.scalar()
    total_profit = total_profit_result if total_profit_result else 0
    
    # Debug: Check if totals match
    print(f"Total transactions from base_query: {total_transactions}")
    print(f"Total sales displayed: {len(sales)}")
    print(f"Total sales from base_query: {total_sales}")
    print(f"Total profit: {total_profit}")
    
    # Prepare data for chart
    payment_method_labels = [method[0].capitalize() for method in sales_by_method] if sales_by_method else []
    payment_method_data = [float(method[2]) for method in sales_by_method] if sales_by_method else []
    
    return render_template('sales_report.html',
                        sales=sales,
                        total_sales=total_sales,
                        total_transactions=total_transactions,
                        average_sale=average_sale,
                        total_profit=total_profit,
                        sales_by_method=sales_by_method,
                        payment_method_labels=payment_method_labels,
                        payment_method_data=payment_method_data)
    
@app.route('/api/products/id/<int:product_id>')
def get_product_by_id(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'barcode': product.barcode,
        'name': product.name,
        'price': product.selling_price,
        'stock': product.current_stock,
        'tax_rate': product.tax_rate,
        'vatable': product.vatable
    })

@app.route('/api/products/<barcode>', methods=['GET'])
@login_required(roles=['cashier', 'manager', 'admin'])
def get_product_by_barcode(barcode):
    try:
        product = Product.query.filter_by(barcode=barcode).first()
        if not product:
            return jsonify({'error': 'Product not found'}), 404

        return jsonify({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'price': float(product.selling_price),
            'stock': product.current_stock,
            'vatable': product.vatable,
            'tax_rate': float(product.tax_rate) if product.tax_rate else 0.0
        })
    except Exception as e:
        app.logger.error(f"Error fetching product: {e}")
        return jsonify({'error': 'Failed to fetch product'}), 500
# Add user management routes
@app.route('/admin/users/add', methods=['POST'])
@login_required(roles=['admin'])
def add_user():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    location_id = request.form.get('location_id')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('manage_users'))
    
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('manage_users'))
    
    new_user = User(
        username=username,
        email=email,
        role=role,
        location_id=location_id if location_id else None
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('User added successfully', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required(roles=['admin'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    user.username = request.form['username']
    user.email = request.form['email']
    user.role = request.form['role']
    user.location_id = request.form.get('location_id') if request.form.get('location_id') else None
    user.is_active = 'is_active' in request.form
    
    if request.form['password']:
        user.set_password(request.form['password'])
    
    db.session.commit()
    
    flash('User updated successfully', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required(roles=['admin'])
def toggle_user_status(user_id):
    if user_id == session['user_id']:
        flash('You cannot deactivate yourself', 'danger')
        return redirect(url_for('manage_users'))
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    flash(f'User {"activated" if user.is_active else "deactivated"} successfully', 'success')
    return redirect(url_for('manage_users'))


@app.route('/products/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def add_product():
    suppliers = Supplier.query.all()
    dealers = Dealer.query.all()  # Fetch all dealers
    items = Item.query.all()
    categories = Category.query.all()

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        buying_price = float(request.form['buying_price'])
        selling_price = float(request.form['selling_price'])
        stock = int(request.form['stock'])
        min_stock_level = int(request.form['min_stock'])
        barcode = request.form['barcode'].strip()
        supplier_id = request.form['supplier_id']
        dealer_id = request.form['dealer_id']  # Get dealer_id from form
        vatable = 'vatable' in request.form
        redirect_url = request.form.get('redirect_url')

        if not barcode:
            flash('Barcode is required.', 'danger')
            return redirect(url_for('add_product'))

        # Check for existing barcode
        existing = Product.query.filter_by(barcode=barcode).first()
        if existing:
            flash(f'A product with barcode "{barcode}" already exists.', 'danger')
            return redirect(url_for('add_product'))

        if not name or not category or not buying_price or not selling_price or not stock or not barcode or not supplier_id or not dealer_id:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_product'))
        
        try:
            new_product = Product(
                barcode=barcode,
                name=name,
                category=category,
                buying_price=buying_price,
                selling_price=selling_price,
                current_stock=stock,
                min_stock_level=min_stock_level,
                supplier_id=supplier_id,
                dealer_id=dealer_id,
                vatable=vatable
            )

            db.session.add(new_product)
            db.session.commit()

            flash('Product added successfully!', 'success')
            # Redirect to the edit page of the newly created product
            return redirect(url_for('edit_product', product_id=new_product.id))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('add_product'))

    name = request.args.get('name')
    redirect_url = request.args.get('redirect_url')
    return render_template('add_product.html', suppliers=suppliers, dealers=dealers, items=items, categories=categories, name=name, redirect_url=redirect_url)

@app.route('/pos')
@login_required(roles=['cashier', 'manager', 'admin'])
def pos():
    return render_template('pos.html')

@app.route('/api/products/search', methods=['GET'])
@login_required(roles=['cashier', 'manager', 'admin'])
def search_products():
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify([])

        # Search by name or barcode
        products = Product.query.filter(
            db.or_(
                Product.name.ilike(f'%{query}%'),
                Product.barcode.ilike(f'%{query}%')
            )
        ).limit(10).all()

        result = []
        for product in products:
            result.append({
                'id': product.id,
                'name': product.name,
                'barcode': product.barcode,
                'price': float(product.selling_price),
                'stock': product.current_stock
            })

        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error searching products: {e}")
        return jsonify([])
@app.route('/api/sales', methods=['POST'])
@login_required(roles=['cashier', 'manager', 'admin'])
def create_sale():
    app.logger.info("Received request to create a new sale")
    try:
        data = request.get_json()
        app.logger.info(f"Request data: {data}")
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        split_payment = data.get('split_payment', False)

        if not items:
            app.logger.warning("Checkout failed: No items in cart")
            return jsonify({'error': 'No items in cart.'}), 400

        subtotal = 0
        tax = 0
        for item in items:
            product = Product.query.get(item['id'])
            if not product or product.current_stock < item['quantity']:
                app.logger.warning(f"Checkout failed: Insufficient stock for product {item['id']}")
                return jsonify({'error': f"Insufficient stock for {product.name}. Only {product.current_stock} left."}), 400

            item_total = product.selling_price * item['quantity']
            subtotal += item_total
            if product.vatable and product.tax_rate:
                tax += item_total * product.tax_rate

        total = subtotal + tax
        app.logger.info(f"Calculated totals: subtotal={subtotal}, tax={tax}, total={total}")

        sale = Sale(
            receipt_number=Sale.generate_receipt_number(),
            user_id=session['user_id'],
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            payment_method=payment_method,
            channel='offline',
            customer_email=data.get('customer_email'),
            split_payment=split_payment,
            location_id=session.get('location_id')
        )
        db.session.add(sale)
        app.logger.info(f"Created new sale with receipt number: {sale.receipt_number}")

        db.session.commit()
        app.logger.info("Committed sale to database")

        for item in items:
            product = Product.query.get(item['id'])
            if product:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=item['price'],
                    total_price=item['price'] * item['quantity']
                )
                db.session.add(sale_item)

                product.current_stock -= item['quantity']

                movement = InventoryMovement(
                    product_id=product.id,
                    movement_type='sale',
                    quantity=-item['quantity'],
                    reference_id=sale.id
                )
                db.session.add(movement)

        db.session.commit()
        app.logger.info("Committed sale items and inventory movements to database")

        return jsonify({'success': True, 'receipt_number': sale.receipt_number})
    except Exception as e:
        app.logger.error(f"Error creating sale: {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/receipt/<receipt_number>')
@login_required(roles=['cashier', 'manager', 'admin'])
def view_receipt(receipt_number):
    sale = Sale.query.filter_by(receipt_number=receipt_number).first_or_404()
    return render_template('receipt.html', sale=sale)

@app.route('/receipt/print/<receipt_number>')
@login_required(roles=['cashier', 'manager', 'admin'])
def print_receipt(receipt_number):
    sale = Sale.query.filter_by(receipt_number=receipt_number).first_or_404()
    return render_template('receipt_print.html', sale=sale)

@app.route('/sales/delete/<int:sale_id>', methods=['POST'])
@login_required(roles=['admin'])
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    # Reverse the stock for each item in the sale
    for item in sale.items:
        product = item.product
        product.current_stock += item.quantity

        # Create a reversal inventory movement
        movement = InventoryMovement(
            product_id=product.id,
            movement_type='sale_reversal',
            quantity=item.quantity,  # Positive quantity
            reference_id=sale.id,
            notes=f"Reversal for deleted sale #{sale.receipt_number}"
        )
        db.session.add(movement)

    # Delete the sale. Items and movements will be handled by cascades/relationships.
    db.session.delete(sale)
    db.session.commit()

    flash(f'Sale #{sale.receipt_number} has been deleted and stock reversed.', 'success')
    return redirect(url_for('sales_report'))

@app.route('/purchase_orders')
@login_required(roles=['manager', 'admin'])
def manage_purchase_orders():
    purchase_orders = PurchaseOrder.query.options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.user)
    ).order_by(PurchaseOrder.order_date.desc()).all()
    return render_template('purchase_orders/list.html', purchase_orders=purchase_orders)

@app.route('/purchase_orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def edit_purchase_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    suppliers = Supplier.query.all()
    products = Product.query.all()
    items = Item.query.all()

    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        if not supplier_id:
            flash('Supplier is required.', 'danger')
            return redirect(url_for('edit_purchase_order', order_id=order_id))

        order.supplier_id = supplier_id

        # Clear existing items
        PurchaseOrderItem.query.filter_by(purchase_order_id=order_id).delete()

        # Add new items
        total_amount = 0
        i = 0
        while f'product_{i}' in request.form:
            item_id = request.form.get(f'product_{i}')
            quantity = int(request.form.get(f'quantity_{i}', 0))
            unit_price = float(request.form.get(f'unit_price_{i}', 0))
            if item_id and quantity > 0:
                item = Item.query.get(item_id)
                if item:
                    total_price = unit_price * quantity
                    total_amount += total_price
                    order_item = PurchaseOrderItem(
                        purchase_order_id=order.id,
                        item_id=item_id,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price
                    )
                    db.session.add(order_item)
            i += 1

        order.total_amount = total_amount
        db.session.commit()
        flash('Purchase order updated successfully!', 'success')
        return redirect(url_for('view_purchase_order', order_id=order_id))

    return render_template('purchase_orders/edit.html', order=order, suppliers=suppliers, products=products, items=items)

@app.route('/purchase_orders/<int:order_id>')
@login_required(roles=['manager', 'admin'])
def view_purchase_order(order_id):
    order = PurchaseOrder.query.options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.item)
    ).get_or_404(order_id)
    return render_template('purchase_orders/view.html', order=order)

@app.route('/purchase_orders/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def add_purchase_order():
    suppliers = Supplier.query.all()
    products = Product.query.all()
    items = Item.query.all()
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        items_data = []
        total_order_amount = 0
        i = 0
        while f'product_{i}' in request.form:
            item_id = request.form.get(f'product_{i}')
            quantity = int(request.form.get(f'quantity_{i}', 0))
            unit_price = float(request.form.get(f'unit_price_{i}', 0))
            if item_id and quantity > 0:
                item = Item.query.get(item_id)
                if item:
                    total_price = unit_price * quantity
                    items_data.append({
                        'item_id': item.id,
                        'quantity': quantity,
                        'unit_price': unit_price,
                        'total_price': total_price
                    })
                    total_order_amount += total_price
            i += 1
        if not supplier_id or not items_data:
            flash('Please select a supplier and add at least one product.', 'danger')
            return redirect(url_for('add_purchase_order'))
        new_order = PurchaseOrder(
            order_number=f'PO-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            supplier_id=supplier_id,
            user_id=session['user_id'],
            total_amount=total_order_amount,
            status='pending'
        )
        db.session.add(new_order)
        db.session.commit()
        for item_data in items_data:
            order_item = PurchaseOrderItem(
                purchase_order_id=new_order.id,
                item_id=item_data['item_id'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                total_price=item_data['total_price']
            )
            db.session.add(order_item)
        db.session.commit()
        flash('Purchase order created successfully!', 'success')
        return redirect(url_for('manage_purchase_orders'))
    return render_template('purchase_orders/add.html', suppliers=suppliers, products=products, items=items)

@app.route('/purchase_orders/<int:order_id>/receive', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def receive_purchase_order(order_id):
    purchase_order = PurchaseOrder.query.get_or_404(order_id)
    if purchase_order.status != 'pending':
        flash('Only pending orders can be received.', 'danger')
        return redirect(url_for('manage_purchase_orders'))
    total_purchase_amount = 0
    for item in purchase_order.items:
        product = Product.query.filter_by(name=item.item.name).first()
        if not product:
            flash(f'Product {item.item.name} not found in inventory.', 'danger')
            return redirect(url_for('view_purchase_order', order_id=order_id))
        product.current_stock += item.quantity
        item_total = item.unit_price * item.quantity
        total_purchase_amount += item_total
        movement = InventoryMovement(
            product_id=product.id,
            movement_type='purchase',
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_amount=item_total,
            reference_id=purchase_order.id,
            notes=f'Received from PO {purchase_order.order_number}'
        )
        db.session.add(movement)
    purchase_order.status = 'received'
    purchase_order.total_amount = total_purchase_amount
    db.session.commit()
    flash('Purchase order received and stock updated successfully!', 'success')
    return redirect(url_for('manage_purchase_orders'))

@app.route('/purchase_orders/<int:order_id>/delete', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def delete_purchase_order(order_id):
    try:
        order = PurchaseOrder.query.get_or_404(order_id)
        PurchaseOrderItem.query.filter_by(purchase_order_id=order_id).delete()
        db.session.delete(order)
        db.session.commit()
        flash('Purchase order deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the purchase order.', 'danger')
        app.logger.error(f"Error deleting purchase order {order_id}: {e}")

    return redirect(url_for('manage_purchase_orders'))

@app.route('/supplier_quotations/<int:quotation_id>/delete', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def delete_supplier_quotation(quotation_id):
    quotation = SupplierQuotation.query.get_or_404(quotation_id)

    # Delete associated quotation items
    SupplierQuotationItem.query.filter_by(quotation_id=quotation_id).delete()

    # Delete the quotation
    db.session.delete(quotation)
    db.session.commit()

    flash('Supplier quotation deleted successfully!', 'success')
    return redirect(url_for('supplier_quotations'))
@app.route('/supplier_quotations/<int:quotation_id>/edit', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def edit_supplier_quotation(quotation_id):
    quotation = SupplierQuotation.query.get_or_404(quotation_id)
    suppliers = Supplier.query.all()
    products = Product.query.all()
    items = Item.query.all()

    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        items = []
        total_amount = 0

        for key, value in request.form.items():
            if key.startswith('product_'):
                index = key.split('_')[1]
                item_id = value
                quantity = int(request.form[f'quantity_{index}'])
                unit_price = float(request.form[f'unit_price_{index}'])
                total_price = quantity * unit_price
                total_amount += total_price
                items.append({
                    'item_id': item_id,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_price': total_price
                })

        if not supplier_id or not items:
            flash('Please select a supplier and add at least one item.', 'danger')
            return redirect(url_for('edit_supplier_quotation', quotation_id=quotation_id))

        # Update quotation details
        quotation.supplier_id = supplier_id
        quotation.total_amount = total_amount
        quotation.status = request.form.get('status', 'pending')

        # Clear existing quotation items
        SupplierQuotationItem.query.filter_by(quotation_id=quotation_id).delete()

        # Add new quotation items
        for item in items:
            quotation_item = SupplierQuotationItem(
                quotation_id=quotation.id,
                item_id=item['item_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=item['total_price']
            )
            db.session.add(quotation_item)

        db.session.commit()
        flash('Supplier quotation updated successfully!', 'success')
        return redirect(url_for('supplier_quotations'))

    # Pre-fill form with existing data
    quotation_items = SupplierQuotationItem.query.filter_by(quotation_id=quotation_id).all()
    return render_template(
        'supplier_quotations/edit.html',
        quotation=quotation,
        suppliers=suppliers,
        products=products,
        items=items,
        quotation_items=quotation_items
    )

@app.route('/resolve_products/<int:order_id>')
@login_required(roles=['manager'])
def resolve_products(order_id):
    purchase_order = PurchaseOrder.query.get_or_404(order_id)
    missing_products = []
    for item in purchase_order.items:
        product = Product.query.filter_by(name=item.item.name).first()
        if not product:
            missing_products.append(item.item)
    return render_template('resolve_products.html', order_id=order_id, missing_products=missing_products)

@app.route('/purchase_orders/<int:order_id>/finalize', methods=['POST'])
@login_required(roles=['manager'])
def finalize_purchase_order(order_id):
    purchase_order = PurchaseOrder.query.get_or_404(order_id)
    # Create accounting entries for the purchase
    inventory_entry = AccountingEntry(
        account_type='asset',
        account_name='Inventory',
        debit_amount=purchase_order.total_amount,
        reference_id=purchase_order.id,
        description=f'Purchase order #{purchase_order.order_number}'
    )
    accounts_payable_entry = AccountingEntry(
        account_type='liability',
        account_name='Accounts Payable',
        credit_amount=purchase_order.total_amount,
        reference_id=purchase_order.id,
        description=f'Purchase order #{purchase_order.order_number}'
    )
    db.session.add(inventory_entry)
    db.session.add(accounts_payable_entry)
    db.session.commit()
    flash('Purchase order finalized successfully', 'success')
    return redirect(url_for('manage_purchase_orders'))



@app.route('/admin/inventory')
@login_required(roles=['manager', 'admin'])
def inventory_management():
    dealer_id = request.args.get('dealer_id', type=int)
    product_search = request.args.get('product_search')
    dealers = Dealer.query.all()

    # Base queries
    products_query = Product.query
    movements_query = InventoryMovement.query.join(Product)
    purchase_orders_query = PurchaseOrder.query
    sales_items_query = db.session.query(SaleItem).join(Product)

    if dealer_id:
        products_query = products_query.filter(Product.dealer_id == dealer_id)
        movements_query = movements_query.filter(Product.dealer_id == dealer_id)
        purchase_orders_query = purchase_orders_query.join(PurchaseOrderItem).join(Product).filter(Product.dealer_id == dealer_id).distinct()
        sales_items_query = sales_items_query.filter(Product.dealer_id == dealer_id)

    if product_search:
        movements_query = movements_query.filter(
            or_(
                Product.name.ilike(f'%{product_search}%'),
                Product.barcode.ilike(f'%{product_search}%')
            )
        )

    products = products_query.all()
    # REMOVED LIMITS: Show all inventory movements and purchase orders
    inventory_movements = movements_query.order_by(InventoryMovement.movement_date.desc()).all()
    purchase_orders = purchase_orders_query.order_by(PurchaseOrder.order_date.desc()).all()

    # Financials
    total_sales_amount = sales_items_query.with_entities(func.sum(SaleItem.quantity * SaleItem.unit_price)).scalar() or 0
    total_cogs = sales_items_query.with_entities(func.sum(SaleItem.quantity * Product.buying_price)).scalar() or 0
    
    # Calculate total purchase amount (all products ever purchased - both sold and in stock)
    total_products_purchased = 0
    for p in products:
        # Get total quantity sold for this product
        total_sold = sales_items_query.filter(SaleItem.product_id == p.id).with_entities(func.sum(SaleItem.quantity)).scalar() or 0
        # Total purchased = current stock + total sold
        total_purchased = p.current_stock + total_sold
        total_products_purchased += p.buying_price * total_purchased
    
    total_purchase_amount = total_products_purchased
    
    total_expense_amount = db.session.query(func.sum(Expense.amount)).scalar() or 0
    net_profit = total_sales_amount - total_cogs - total_expense_amount

    return render_template('inventory_management.html',
                         products=products,
                         dealers=dealers,
                         selected_dealer_id=dealer_id,
                         inventory_movements=inventory_movements,
                         purchase_orders=purchase_orders,
                         total_sales_amount=total_sales_amount,
                         total_purchase_amount=total_purchase_amount,
                         total_expense_amount=total_expense_amount,
                         net_profit=net_profit)
@app.route('/suppliers')
@login_required(roles=['manager', 'admin'])
def list_suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

# Route to add a new supplier
@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required(roles=['manager'])
def add_supplier():
    if request.method == 'POST':
        name = request.form['name']
        contact_person = request.form['contact_person']
        phone = request.form['phone']
        email = request.form['email']
        address = request.form['address']
        kra_pin = request.form['kra_pin']

        if not name or not contact_person or not phone or not email or not address or not kra_pin:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_supplier'))

        if Supplier.query.filter_by(email=email).first():
            flash('A supplier with this email already exists.', 'danger')
            return redirect(url_for('add_supplier'))

        if Supplier.query.filter_by(phone=phone).first():
            flash('A supplier with this phone number already exists.', 'danger')
            return redirect(url_for('add_supplier'))

        supplier = Supplier(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            KRA_pin=kra_pin
        )

        db.session.add(supplier)
        db.session.commit()

        flash('Supplier added successfully!', 'success')
        return redirect(url_for('list_suppliers'))

    return render_template('suppliers/add.html')

# Route to edit an existing supplier
@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required(roles=['manager'])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == 'POST':
        supplier.name = request.form['name']
        supplier.contact_person = request.form['contact_person']
        supplier.phone = request.form['phone']
        supplier.email = request.form['email']
        supplier.address = request.form['address']
        supplier.KRA_pin = request.form['kra_pin']

        if not supplier.name or not supplier.contact_person or not supplier.phone or not supplier.email or not supplier.address or not supplier.KRA_pin:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))

        db.session.commit()

        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('list_suppliers'))

    return render_template('suppliers/edit.html', supplier=supplier)

# Route to delete a supplier
@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@login_required(roles=['manager'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()

    flash('Supplier deleted successfully!', 'success')
    return redirect(url_for('list_suppliers'))


@app.route('/expenses')
@login_required(roles=['manager', 'cashier'])
def list_expenses():
    query = Expense.query.order_by(Expense.date.desc())
    if session['role'] == 'cashier':
        query = query.filter_by(user_id=session['user_id'])
    expenses = query.all()
    return render_template('expenses/list.html', expenses=expenses)

@app.route('/expenses/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'cashier'])
def add_expense():
    if request.method == 'POST':
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        payee_name = request.form['payee_name']
        transaction_details = request.form['transaction_details']
        description = request.form['description']
        amount = float(request.form['amount'])

        expense = Expense(
            date=date,
            payee_name=payee_name,
            transaction_details=transaction_details,
            description=description,
            amount=amount,
            user_id=session['user_id']
        )

        db.session.add(expense)
        db.session.commit()

        flash('Expense added successfully!', 'success')
        return redirect(url_for('list_expenses'))

    return render_template('expenses/add.html')

@app.route('/expenses/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required('manager')
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if request.method == 'POST':
        expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        expense.payee_name = request.form['payee_name']
        expense.transaction_details = request.form['transaction_details']
        expense.description = request.form['description']
        expense.amount = float(request.form['amount'])

        db.session.commit()

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('list_expenses'))

    return render_template('expenses/edit.html', expense=expense)

@app.route('/expenses/delete/<int:expense_id>', methods=['POST'])
@login_required('manager')
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()

    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('list_expenses'))
@app.route('/dealers')
@login_required(roles=['manager', 'admin'])
def list_dealers():
    dealers = Dealer.query.all()
    return render_template('dealers/list.html', dealers=dealers)

@app.route('/dealers/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def add_dealer():
    if request.method == 'POST':
        name = request.form['name']
        contact_person = request.form['contact_person']
        phone = request.form['phone']
        email = request.form['email']
        address = request.form['address']

        if not name or not contact_person or not phone or not email or not address:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_dealer'))

        if Dealer.query.filter_by(email=email).first():
            flash('A dealer with this email already exists.', 'danger')
            return redirect(url_for('add_dealer'))

        if Dealer.query.filter_by(phone=phone).first():
            flash('A dealer with this phone number already exists.', 'danger')
            return redirect(url_for('add_dealer'))

        dealer = Dealer(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address
        )

        db.session.add(dealer)
        db.session.commit()

        flash('Dealer added successfully!', 'success')
        return redirect(url_for('list_dealers'))

    return render_template('dealers/add.html')

@app.route('/dealers/edit/<int:dealer_id>', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def edit_dealer(dealer_id):
    dealer = Dealer.query.get_or_404(dealer_id)

    if request.method == 'POST':
        dealer.name = request.form['name']
        dealer.contact_person = request.form['contact_person']
        dealer.phone = request.form['phone']
        dealer.email = request.form['email']
        dealer.address = request.form['address']

        if not dealer.name or not dealer.contact_person or not dealer.phone or not dealer.email or not dealer.address:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_dealer', dealer_id=dealer_id))

        db.session.commit()

        flash('Dealer updated successfully!', 'success')
        return redirect(url_for('list_dealers'))

    return render_template('dealers/edit.html', dealer=dealer)

@app.route('/dealers/delete/<int:dealer_id>', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def delete_dealer(dealer_id):
    dealer = Dealer.query.get_or_404(dealer_id)
    db.session.delete(dealer)
    db.session.commit()

    flash('Dealer deleted successfully!', 'success')
    return redirect(url_for('list_dealers'))



# Routes for Financiers
@app.route('/financiers')
@login_required('manager' and 'admin')
def list_financiers():
    financiers = Financier.query.order_by(Financier.date.desc()).all()
    return render_template('financiers/list.html', financiers=financiers)

@app.route('/financiers/add', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def add_financier():
    if request.method == 'POST':
        financier_id = request.form['financier_id']
        financier_name = request.form['financier_name']
        address = request.form['address']
        email = request.form['email']
        phone_number = request.form['phone_number']
        kra_pin = request.form['kra_pin']
        description = request.form['description']

        if not financier_id or not financier_name or not address or not email or not phone_number or not kra_pin:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_financier'))

        if Financier.query.filter_by(financier_id=financier_id).first():
            flash('A financier with this ID already exists.', 'danger')
            return redirect(url_for('add_financier'))

        if Financier.query.filter_by(email=email).first():
            flash('A financier with this email already exists.', 'danger')
            return redirect(url_for('add_financier'))

        if Financier.query.filter_by(phone_number=phone_number).first():
            flash('A financier with this phone number already exists.', 'danger')
            return redirect(url_for('add_financier'))

        financier = Financier(
            financier_id=financier_id,
            financier_name=financier_name,
            address=address,
            email=email,
            phone_number=phone_number,
            kra_pin=kra_pin,
            description=description
        )

        db.session.add(financier)
        db.session.commit()

        flash('Financier added successfully!', 'success')
        return redirect(url_for('list_financiers'))

    return render_template('financiers/add.html')

@app.route('/financiers/edit/<int:financier_id>', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def edit_financier(financier_id):
    financier = Financier.query.get_or_404(financier_id)

    if request.method == 'POST':
        financier.financier_id = request.form['financier_id']
        financier.financier_name = request.form['financier_name']
        financier.address = request.form['address']
        financier.email = request.form['email']
        financier.phone_number = request.form['phone_number']
        financier.kra_pin = request.form['kra_pin']
        financier.description = request.form['description']

        if not financier.financier_id or not financier.financier_name or not financier.address or not financier.email or not financier.phone_number or not financier.kra_pin:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_financier', financier_id=financier_id))

        db.session.commit()

        flash('Financier updated successfully!', 'success')
        return redirect(url_for('list_financiers'))

    return render_template('financiers/edit.html', financier=financier)

@app.route('/financiers/delete/<int:financier_id>', methods=['POST'])
@login_required('manager' and 'admin')
def delete_financier(financier_id):
    financier = Financier.query.get_or_404(financier_id)
    db.session.delete(financier)
    db.session.commit()

    flash('Financier deleted successfully!', 'success')
    return redirect(url_for('list_financiers'))

# Routes for Financier Credits
@app.route('/financiers/credits')
@login_required('manager' and 'admin')
def list_financier_credits():
    credits = FinancierCredit.query.order_by(FinancierCredit.date.desc()).all()
    return render_template('financiers/credits.html', credits=credits)

@app.route('/financiers/credits/add', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def add_financier_credit():
    financiers = Financier.query.all()
    if request.method == 'POST':
        financier_id = request.form['financier_id']
        financier = Financier.query.get(financier_id)
        financier_name = financier.financier_name
        description = request.form['description']
        amount_credited = float(request.form['amount_credited'])
        transaction_ref = request.form['transaction_ref']

        if not financier_id or not description or not amount_credited or not transaction_ref:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_financier_credit'))

        credit = FinancierCredit(
            financier_id=financier_id,
            financier_name=financier_name,
            description=description,
            amount_credited=amount_credited,
            transaction_ref=transaction_ref
        )

        db.session.add(credit)
        db.session.commit()

        flash('Financier credit added successfully!', 'success')
        return redirect(url_for('list_financier_credits'))

    return render_template('financiers/add_credit.html', financiers=financiers)

# Routes for Financier Debits
@app.route('/financiers/debits')
@login_required('manager' and 'admin')
def list_financier_debits():
    debits = FinancierDebit.query.order_by(FinancierDebit.date.desc()).all()
    return render_template('financiers/debits.html', debits=debits)

@app.route('/financiers/debits/add', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def add_financier_debit():
    financiers = Financier.query.all()
    if request.method == 'POST':
        financier_id = request.form['financier_id']
        financier = Financier.query.get(financier_id)
        financier_name = financier.financier_name
        description = request.form['description']
        principal_amount = float(request.form['principal_amount'])
        interest_amount = float(request.form.get('interest_amount', 0.0))
        total_amount = principal_amount + interest_amount
        transaction_ref = request.form['transaction_ref']

        if not financier_id or not description or not principal_amount or not transaction_ref:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_financier_debit'))

        debit = FinancierDebit(
            financier_id=financier_id,
            financier_name=financier_name,
            description=description,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            total_amount=total_amount,
            transaction_ref=transaction_ref
        )

        db.session.add(debit)
        db.session.commit()

        flash('Financier debit added successfully!', 'success')
        return redirect(url_for('list_financier_debits'))

    return render_template('financiers/add_debit.html', financiers=financiers)
# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'transactionsfinance355@gmail.com'
app.config['MAIL_PASSWORD'] = 'rvzxngpossphfgzm'

# --- Password Reset Web Flow ---

@app.route('/request_reset_password', methods=['GET', 'POST'])
def request_reset_password():
    if request.method == 'GET':
        return render_template('request_reset_password.html')

    # Handle POST for both form and JSON
    if request.is_json:
        data = request.get_json()
        email = data.get('email')
    else:
        email = request.form.get('email')

    if not email:
        if request.is_json:
            return jsonify({"error": "Email is required"}), 400
        flash("Email is required", "danger")
        return redirect(url_for('request_reset_password'))

    user = User.query.filter(User.email.ilike(email)).first()
    if not user:
        if request.is_json:
            return jsonify({"error": "User with this email does not exist"}), 404
        # For web, don't reveal user existence. Redirect to a generic page.
        flash("If an account with that email exists, an OTP has been sent.", "info")
        return redirect(url_for('verify_otp_page', email=email))

    otp = generate_otp()
    store_otp(email, otp)
    username = user.username

    msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f"""
    Hello, {username}

    Here's the verification code to reset your password:

    {otp}

    This code will expire in 5 minutes.

    If you did not request this password reset, please ignore this email.
    """

    try:
        mail.send(msg)
        if request.is_json:
            return jsonify({"message": "OTP sent to your email"}), 200
        flash("OTP sent to your email.", "success")
        return redirect(url_for('verify_otp_page', email=email))
    except Exception as e:
        app.logger.error(f"Failed to send OTP email: {e}")
        if request.is_json:
            return jsonify({"error": f"Failed to send OTP email: {str(e)}"}), 500
        flash(f"Failed to send OTP email.", "danger")
        return redirect(url_for('request_reset_password'))

@app.route('/verify_otp_page', methods=['GET', 'POST'])
def verify_otp_page():
    email = request.args.get('email') or request.form.get('email')
    if request.method == 'GET':
        if not email:
            flash("No email provided for OTP verification.", "danger")
            return redirect(url_for('request_reset_password'))
        return render_template('verify_otp.html', email=email)

    # Handle POST
    otp = request.form.get('otp')
    if not email or not otp:
        flash("Email and OTP are required.", "danger")
        return redirect(url_for('verify_otp_page', email=email))

    otp_entry = OTP.query.filter_by(email=email).first()

    if not otp_entry or otp_entry.otp != otp:
        flash("Invalid OTP.", "danger")
        return redirect(url_for('verify_otp_page', email=email))

    if datetime.utcnow() > otp_entry.expiry:
        flash("OTP has expired. Please request a new one.", "warning")
        return redirect(url_for('request_reset_password'))

    # OTP is valid, redirect to reset password page
    flash("OTP verified. Please reset your password.", "success")
    return redirect(url_for('reset_password_page', email=email, otp=otp))

@app.route('/reset_password_page', methods=['GET', 'POST'])
def reset_password_page():
    email = request.args.get('email') or request.form.get('email')
    otp = request.args.get('otp') or request.form.get('otp')

    if request.method == 'GET':
        if not email or not otp:
            flash("Invalid request for password reset.", "danger")
            return redirect(url_for('login'))
        return render_template('reset_password.html', email=email, otp=otp)

    # Handle POST
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not new_password or new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for('reset_password_page', email=email, otp=otp))

    # Re-verify OTP before resetting password
    otp_entry = OTP.query.filter_by(email=email, otp=otp).first()
    if not otp_entry or datetime.utcnow() > otp_entry.expiry:
        flash("Invalid or expired OTP. Please start over.", "danger")
        return redirect(url_for('request_reset_password'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('request_reset_password'))

    user.set_password(new_password)
    db.session.delete(otp_entry)
    db.session.commit()

    flash("Password reset successfully. Please log in.", "success")
    return redirect(url_for('login'))

# --- Password Reset API Endpoints ---

# Helper Functions
def generate_otp():
    """Generate a random 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))


def store_otp(email, otp):
    """Store the OTP in the database or any other storage for verification."""
    expiry = datetime.utcnow() + timedelta(minutes=5)
    otp_entry = OTP.query.filter_by(email=email).first()
    if otp_entry:
        otp_entry.otp = otp
        otp_entry.expiry = expiry
    else:
        otp_entry = OTP(email=email, otp=otp, expiry=expiry)
        db.session.add(otp_entry)
    db.session.commit()

@app.route('/get_user_role_by_email', methods=['POST'])
def get_user_role_by_email():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User with this email does not exist"}), 404

    return jsonify({'role': user.role}), 200

@app.route('/check_email_exists', methods=['POST'])
def check_email_exists():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'message': 'Email exists'}), 200
    else:
        return jsonify({'error': 'Email not found'}), 404

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    otp_entry = OTP.query.filter_by(email=email).first()

    if not otp_entry:
        return jsonify({"error": "OTP not requested or does not exist"}), 404

    if datetime.utcnow() > otp_entry.expiry:
        return jsonify({
            "error": "OTP expired",
            "message": "Did time run out? Request a new OTP.",
            "request_new_otp": True
        }), 400

    if otp_entry.otp != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    return jsonify({"message": "OTP is valid"}), 200

@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    new_password = data.get('new_password')

    if not email or not otp or not new_password:
        return jsonify({"error": "Missing email, OTP or new password"}), 400

    otp_entry = OTP.query.filter_by(email=email).first()
    if not otp_entry:
        return jsonify({"error": "OTP not requested"}), 404

    if datetime.utcnow() > otp_entry.expiry:
        return jsonify({"error": "OTP expired"}), 400

    if otp_entry.otp != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User with this email does not exist"}), 404

    user.set_password(new_password)
    db.session.delete(otp_entry)
    db.session.commit()

    return jsonify({"message": "Password reset successfully"}), 200

@app.route('/request_new_otp', methods=['POST'])
def request_new_otp():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User with this email does not exist"}), 404

    otp = generate_otp()
    store_otp(email, otp)

    username = user.username
    msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f"""
    Hello, {username}

    Here's the verification code to reset your password:

    {otp}

    To reset your password, enter this verification code when prompted.

    This code will expire in 5 minutes.

    If you did not request this password reset, please ignore this email.
    """
    mail.send(msg)

    return jsonify({"message": "New OTP sent to your email"}), 200
# Simplified POS routes
@app.route('/pos_simple')
@login_required(roles=['cashier', 'manager', 'admin'])
def pos_simple():
    return render_template('pos_simple.html')

@app.route('/api/add_to_cart', methods=['POST'])
@login_required(roles=['cashier', 'manager', 'admin'])
def add_to_cart_simple():
    data = request.get_json()
    barcode = data.get('barcode')

    product = Product.query.filter_by(barcode=barcode).first()

    if not product:
        return jsonify({'success': False, 'error': 'Product not found'})

    if product.current_stock < 1:
        return jsonify({'success': False, 'error': 'Product out of stock'})

    cart = session.get('cart', [])

    existing_item = next((item for item in cart if item['id'] == product.id), None)

    if existing_item:
        if existing_item['quantity'] >= product.current_stock:
            return jsonify({'success': False, 'error': 'Not enough stock'})
        existing_item['quantity'] += 1
    else:
        cart.append({
            'id': product.id,
            'name': product.name,
            'price': product.selling_price,
            'quantity': 1
        })

    session['cart'] = cart

    return jsonify({'success': True, 'cart': cart})

@app.route('/supplier_quotations')
@login_required(roles=['manager', 'admin'])
def supplier_quotations():
    quotations = SupplierQuotation.query.options(joinedload(SupplierQuotation.supplier)).order_by(SupplierQuotation.quotation_date.desc()).all()
    return render_template('supplier_quotations/list.html', quotations=quotations)

@app.route('/supplier_quotations/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def add_supplier_quotation():
    suppliers = Supplier.query.all()
    products = Product.query.all()
    items = Item.query.all()

    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        items = []
        total_amount = 0

        for key, value in request.form.items():
            if key.startswith('product_'):
                index = key.split('_')[1]
                item_id = value
                quantity = int(request.form[f'quantity_{index}'])
                unit_price = float(request.form[f'unit_price_{index}'])
                total_price = quantity * unit_price
                total_amount += total_price
                item = Item.query.get(item_id)
                items.append({
                    'item_id': item_id,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_price': total_price
                })

        if not supplier_id or not items:
            flash('Please select a supplier and add at least one item.', 'danger')
            return redirect(url_for('add_supplier_quotation'))

        quotation = SupplierQuotation(
            supplier_id=supplier_id,
            total_amount=total_amount,
            status='pending'
        )
        db.session.add(quotation)
        db.session.commit()

        for item in items:
            quotation_item = SupplierQuotationItem(
                quotation_id=quotation.id,
                item_id=item['item_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=item['total_price']
            )
            db.session.add(quotation_item)

        db.session.commit()
        flash('Supplier quotation added successfully!', 'success')
        return redirect(url_for('supplier_quotations'))

    return render_template('supplier_quotations/add.html', suppliers=suppliers, products=products, items=items)

@app.route('/supplier_quotations/<int:quotation_id>')
@login_required(roles=['manager', 'admin'])
def view_supplier_quotation(quotation_id):
    quotation = SupplierQuotation.query.get_or_404(quotation_id)
    return render_template('supplier_quotations/view.html', quotation=quotation)

@app.route('/supplier_quotations/<int:quotation_id>/award', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def award_supplier_quotation(quotation_id):
    quotation = SupplierQuotation.query.get_or_404(quotation_id)

    # Decline all other quotations for the same products
    item_ids = [item.item_id for item in quotation.items]
    other_quotations = SupplierQuotation.query.filter(
        SupplierQuotation.id != quotation_id,
        SupplierQuotation.items.any(SupplierQuotationItem.item_id.in_(item_ids))
    ).all()

    for other_quotation in other_quotations:
        other_quotation.status = 'declined'

    # Award the selected quotation
    quotation.status = 'awarded'
    db.session.commit()

    flash(f'Quotation from {quotation.supplier.name} has been awarded.', 'success')
    return redirect(url_for('supplier_quotations'))
@app.route('/admin/reports/profit_loss')
@login_required(roles=['manager', 'admin'])
def profit_loss_report():
    try:
        # Get date range from request or default to current month
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        else:
            # Default to current month
            today = datetime.today()
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1)
        
        # Get custom tax amount from request
        custom_tax_amount = request.args.get('custom_tax_amount', type=float)
        use_custom_tax = request.args.get('use_custom_tax') == 'true'
        
        # REVENUE SECTION
        # Total Sales Revenue
        sales_query = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date < end_date)
        if session['role'] == 'cashier':
            sales_query = sales_query.filter(Sale.user_id == session['user_id'])
        
        total_sales_revenue = sales_query.with_entities(func.sum(Sale.total_amount)).scalar() or 0
        
        # COST OF GOODS SOLD (COGS)
        cogs_query = db.session.query(func.sum(SaleItem.quantity * Product.buying_price))\
            .join(Sale, Sale.id == SaleItem.sale_id)\
            .join(Product, Product.id == SaleItem.product_id)\
            .filter(Sale.sale_date >= start_date, Sale.sale_date < end_date)
        
        if session['role'] == 'cashier':
            cogs_query = cogs_query.filter(Sale.user_id == session['user_id'])
        
        total_cogs = cogs_query.scalar() or 0
        
        # GROSS PROFIT
        gross_profit = total_sales_revenue - total_cogs
        gross_profit_margin = (gross_profit / total_sales_revenue * 100) if total_sales_revenue > 0 else 0
        
        # OPERATING EXPENSES
        expenses_query = Expense.query.filter(Expense.date >= start_date, Expense.date < end_date)
        if session['role'] == 'cashier':
            expenses_query = expenses_query.filter(Expense.user_id == session['user_id'])
        
        total_expenses = expenses_query.with_entities(func.sum(Expense.amount)).scalar() or 0
        
        # Categorize expenses
        expense_categories = {
            'Salaries & Wages': 0,
            'Rent & Utilities': 0,
            'Marketing & Advertising': 0,
            'Supplies & Materials': 0,
            'Transport & Delivery': 0,
            'Other Expenses': 0
        }
        
        all_expenses = expenses_query.all()
        for expense in all_expenses:
            description_lower = expense.description.lower()
            if any(word in description_lower for word in ['salary', 'wage', 'payroll']):
                expense_categories['Salaries & Wages'] += float(expense.amount)
            elif any(word in description_lower for word in ['rent', 'utility', 'electric', 'water']):
                expense_categories['Rent & Utilities'] += float(expense.amount)
            elif any(word in description_lower for word in ['marketing', 'advert', 'promo']):
                expense_categories['Marketing & Advertising'] += float(expense.amount)
            elif any(word in description_lower for word in ['supply', 'material', 'stationery']):
                expense_categories['Supplies & Materials'] += float(expense.amount)
            elif any(word in description_lower for word in ['transport', 'delivery', 'fuel']):
                expense_categories['Transport & Delivery'] += float(expense.amount)
            else:
                expense_categories['Other Expenses'] += float(expense.amount)
        
        # OPERATING INCOME
        operating_income = gross_profit - total_expenses
        
        # NON-OPERATING ITEMS
        interest_income = FinancierCredit.query.filter(
            FinancierCredit.date >= start_date, 
            FinancierCredit.date < end_date
        ).with_entities(func.sum(FinancierCredit.amount_credited)).scalar() or 0
        
        interest_expense = FinancierDebit.query.filter(
            FinancierDebit.date >= start_date, 
            FinancierDebit.date < end_date
        ).with_entities(func.sum(FinancierDebit.interest_amount)).scalar() or 0
        
        # NET INCOME BEFORE TAXES
        net_income_before_taxes = operating_income + interest_income - interest_expense
        
        # TAX CALCULATION - Editable
        tax_rate = 0.30  # Default 30%
        
        if use_custom_tax and custom_tax_amount is not None:
            income_tax_expense = custom_tax_amount
            tax_percentage = (custom_tax_amount / net_income_before_taxes * 100) if net_income_before_taxes > 0 else 0
        else:
            income_tax_expense = net_income_before_taxes * tax_rate if net_income_before_taxes > 0 else 0
            tax_percentage = tax_rate * 100
        
        # NET INCOME AFTER TAXES
        net_income = net_income_before_taxes - income_tax_expense
        
        # KEY PERFORMANCE INDICATORS
        total_transactions = sales_query.count()
        average_transaction_value = total_sales_revenue / total_transactions if total_transactions > 0 else 0
        
        # Format dates for display
        start_date_display = start_date.strftime('%Y-%m-%d')
        end_date_display = (end_date - timedelta(days=1)).strftime('%Y-%m-%d')
        
        return render_template('reports/profit_loss.html',
                            start_date=start_date_display,
                            end_date=end_date_display,
                            total_sales_revenue=total_sales_revenue,
                            total_cogs=total_cogs,
                            gross_profit=gross_profit,
                            gross_profit_margin=gross_profit_margin,
                            total_expenses=total_expenses,
                            expense_categories=expense_categories,
                            operating_income=operating_income,
                            interest_income=interest_income,
                            interest_expense=interest_expense,
                            net_income_before_taxes=net_income_before_taxes,
                            income_tax_expense=income_tax_expense,
                            tax_percentage=tax_percentage,
                            net_income=net_income,
                            total_transactions=total_transactions,
                            average_transaction_value=average_transaction_value,
                            custom_tax_amount=custom_tax_amount,
                            use_custom_tax=use_custom_tax)
    
    except Exception as e:
        app.logger.error(f"Error generating profit loss report: {e}")
        flash('Error generating profit loss report', 'danger')
        return redirect(url_for('dashboard'))
    
    
@app.route('/bank/accounts')
@login_required(roles=['manager', 'admin'])
def manage_bank_accounts():
    """View all bank accounts"""
    bank_accounts = BankAccount.query.order_by(BankAccount.is_primary.desc(), BankAccount.bank_name).all()
    return render_template('bank/accounts.html', bank_accounts=bank_accounts)

@app.route('/bank/accounts/add', methods=['GET', 'POST'])
@login_required(roles=['manager', 'admin'])
def add_bank_account():
    """Add a new bank account"""
    if request.method == 'POST':
        try:
            bank_account = BankAccount(
                account_name=request.form['account_name'],
                account_number=request.form['account_number'],
                bank_name=request.form['bank_name'],
                branch_code=request.form.get('branch_code'),
                account_type=request.form.get('account_type', 'checking'),
                currency=request.form.get('currency', 'KES'),
                is_primary=request.form.get('is_primary') == 'on'
            )
            
            # If setting as primary, unset others
            if bank_account.is_primary:
                BankAccount.query.update({'is_primary': False})
            
            db.session.add(bank_account)
            db.session.commit()
            
            flash('Bank account added successfully!', 'success')
            return redirect(url_for('manage_bank_accounts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding bank account: {str(e)}', 'danger')
    
    return render_template('bank/add_account.html')

# ======================
# MPESA INTEGRATION
# ======================

@app.route('/api/mpesa/stk_push', methods=['POST'])
@login_required(roles=['cashier', 'manager', 'admin'])
def mpesa_stk_push():
    """Initiate M-Pesa STK Push"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        sale_id = data.get('sale_id')

        # Format phone number to 254...
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            phone_number = phone_number[1:]

        gateway = PaymentGateway.query.filter_by(name='mpesa', is_active=True).first()
        config = {}
        if gateway:
            config = {
                'api_key': gateway.api_key,
                'api_secret': gateway.api_secret,
                'webhook_secret': gateway.webhook_secret,
                'merchant_id': gateway.merchant_id,
                'test_mode': gateway.test_mode,
                'callback_url': f"{request.url_root.rstrip('/')}/api/mpesa/callback"
            }
        else:
            # Default to simulation if not configured
            config = {'test_mode': True}

        service = KenyaBankService(config)
        result = service.initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            account_ref=f"Sale-{sale_id}" if sale_id else "POS-Sale",
            description="Payment for POS Sale"
        )

        if result.get('ResponseCode') == '0' or result.get('success'):
            return jsonify({'success': True, 'checkout_id': result.get('CheckoutRequestID')})
        else:
            return jsonify({'success': False, 'error': result.get('ResponseDescription', 'Unknown error')}), 400

    except Exception as e:
        app.logger.error(f"M-Pesa STK Push error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa STK Push Callback"""
    data = request.get_json()
    app.logger.info(f"M-Pesa Callback received: {json.dumps(data)}")

    # Process the callback data
    # Real logic would update transaction status in DB
    return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})

@app.route('/api/bank/transfer', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def bank_transfer():
    """Initiate a bank transfer (B2C or inter-bank)"""
    try:
        data = request.get_json()
        target = data.get('target') # phone or account number
        amount = data.get('amount')
        transfer_type = data.get('type', 'mpesa') # mpesa or bank

        # Real implementation would use KenyaBankService
        service = KenyaBankService({'test_mode': True})

        if transfer_type == 'mpesa':
            result = service.initiate_b2c_transfer(target, amount, "Payment")
        else:
            # Generic bank transfer logic
            result = {'success': True, 'simulation': True}

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bank/reconcile', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def reconcile_transaction():
    """Manually reconcile a bank transaction with system record"""
    try:
        data = request.get_json()
        transaction_id = data['transaction_id']
        system_record_id = data.get('system_record_id')
        
        if system_record_id:
            # Link to existing system record
            bank_txn = BankTransaction.query.get(system_record_id)
            if bank_txn:
                bank_txn.status = 'reconciled'
                bank_txn.posted_date = datetime.utcnow()
                db.session.commit()
        else:
            # Create new system record from bank transaction
            bank_txn = BankTransaction(
                transaction_ref=f"BANK-{transaction_id}",
                amount=data['amount'],
                transaction_type='deposit' if data['amount'] > 0 else 'withdrawal',
                description=data['description'],
                status='reconciled',
                transaction_date=datetime.strptime(data['date'], '%Y-%m-%d'),
                posted_date=datetime.utcnow(),
                transaction_data={'bank_reconciled': True, 'original_data': data}
            )
            db.session.add(bank_txn)
            db.session.commit()
        
        return jsonify({'success': True, 'transaction_id': bank_txn.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# ======================
# ENHANCED POS WITH PAYMENT OPTIONS
# ======================

@app.route('/pos_advanced')
@login_required(roles=['cashier', 'manager', 'admin'])
def pos_advanced():
    """POS with integrated payment options"""
    payment_gateways = PaymentGateway.query.filter_by(is_active=True).all()
    bank_accounts = BankAccount.query.filter_by(is_active=True).all()
    
    return render_template('pos_advanced.html',
                         payment_gateways=payment_gateways,
                         bank_accounts=bank_accounts)

@app.route('/api/sale/create_with_payment', methods=['POST'])
@login_required(roles=['cashier', 'manager', 'admin'])
def create_sale_with_payment():
    """Create sale with integrated payment processing"""
    try:
        data = request.get_json()
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        gateway_name = data.get('gateway')
        
        if not items:
            return jsonify({'error': 'No items in cart.'}), 400
        
        # Calculate totals
        subtotal = 0
        tax = 0
        for item in items:
            product = Product.query.get(item['id'])
            if not product or product.current_stock < item['quantity']:
                return jsonify({'error': f"Insufficient stock for {product.name}. Only {product.current_stock} left."}), 400
            
            item_total = product.selling_price * item['quantity']
            subtotal += item_total
            if product.vatable and product.tax_rate:
                tax += item_total * product.tax_rate
        
        total = subtotal + tax
        
        # Create sale record
        sale = Sale(
            receipt_number=Sale.generate_receipt_number(),
            user_id=session['user_id'],
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            payment_method=payment_method,
            channel='offline',
            customer_email=data.get('customer_email'),
            split_payment=False,
            location_id=session.get('location_id')
        )
        db.session.add(sale)
        db.session.commit()
        
        # Add sale items and update inventory
        for item in items:
            product = Product.query.get(item['id'])
            if product:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=item['quantity'],
                    unit_price=item['price'],
                    total_price=item['price'] * item['quantity']
                )
                db.session.add(sale_item)
                
                product.current_stock -= item['quantity']
                
                movement = InventoryMovement(
                    product_id=product.id,
                    movement_type='sale',
                    quantity=-item['quantity'],
                    reference_id=sale.id
                )
                db.session.add(movement)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'receipt_number': sale.receipt_number,
            'sale_id': sale.id
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating sale with payment: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

# ======================
# FINANCIAL REPORTS WITH BANK DATA
# ======================

@app.route('/admin/reports/bank_reconciliation')
@login_required(roles=['manager', 'admin'])
def bank_reconciliation_report():
    """Bank reconciliation report"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # System transactions
    system_transactions = BankTransaction.query.filter(
        BankTransaction.transaction_date.between(start_date, end_date)
    ).order_by(BankTransaction.transaction_date.desc()).all()
    
    # Bank API connections
    connections = BankAPIConnection.query.filter_by(is_active=True).all()
    
    # Totals
    total_deposits = db.session.query(func.sum(BankTransaction.amount)).filter(
        BankTransaction.transaction_type == 'deposit',
        BankTransaction.status == 'completed',
        BankTransaction.transaction_date.between(start_date, end_date)
    ).scalar() or 0
    
    total_withdrawals = db.session.query(func.sum(BankTransaction.amount)).filter(
        BankTransaction.transaction_type == 'withdrawal',
        BankTransaction.status == 'completed',
        BankTransaction.transaction_date.between(start_date, end_date)
    ).scalar() or 0
    
    unreconciled = BankTransaction.query.filter(
        BankTransaction.status != 'reconciled',
        BankTransaction.transaction_date.between(start_date, end_date)
    ).count()
    
    return render_template('reports/bank_reconciliation.html',
                         system_transactions=system_transactions,
                         connections=connections,
                         total_deposits=total_deposits,
                         total_withdrawals=total_withdrawals,
                         unreconciled=unreconciled,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

# ======================
# BULK PAYMENT PROCESSING
# ======================

@app.route('/bank/payments/bulk', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def process_bulk_payments():
    """Process bulk payments to suppliers/expenses"""
    try:
        data = request.get_json()
        payment_ids = data.get('payment_ids', [])  # Could be expense_ids, supplier_invoice_ids
        bank_account_id = data['bank_account_id']
        payment_method = data.get('payment_method', 'bank_transfer')
        
        bank_account = BankAccount.query.get(bank_account_id)
        if not bank_account:
            return jsonify({'error': 'Bank account not found'}), 400
        
        total_amount = 0
        processed_payments = []
        
        # Process each payment
        for payment_id in payment_ids:
            # This would fetch the actual payable amount
            # For now, using placeholder logic
            amount = 1000  # Would be fetched from expense/supplier record
            
            # Create withdrawal transaction
            transaction = BankTransaction(
                transaction_ref=f"BULK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{payment_id}",
                bank_account_id=bank_account_id,
                amount=-amount,  # Negative for withdrawal
                transaction_type='withdrawal',
                description=f'Bulk payment for ID: {payment_id}',
                status='pending',
                payment_method=payment_method,
                transaction_date=datetime.utcnow()
            )
            
            db.session.add(transaction)
            total_amount += amount
            processed_payments.append({
                'payment_id': payment_id,
                'amount': amount,
                'transaction_id': transaction.id
            })
        
        # In real implementation, you would:
        # 1. Generate payment file (ACH, SEPA, SWIFT)
        # 2. Send to bank via API
        # 3. Update status based on response
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(processed_payments)} payments totaling {total_amount:.2f}',
            'total_amount': total_amount,
            'processed_payments': processed_payments
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500   
    
# ======================
# MOCK BANK INTEGRATION
# ======================

@app.route('/bank/connect', methods=['GET'])
@login_required(roles=['manager', 'admin'])
def mock_bank_connect():
    """Bank connection page"""
    try:
        from mock_bank import MockBankAPI
        banks = MockBankAPI.get_bank_list()
        return render_template('bank/connect.html',
                             banks=banks,
                             title="Connect Bank Account")
    except ImportError:
        flash('Mock bank module not found', 'warning')
        return redirect(url_for('dashboard'))

@app.route('/api/bank/connect', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def api_mock_bank_connect():
    """API to connect mock bank"""
    try:
        data = request.get_json()
        bank_id = data.get('bank_id')
        account_number = data.get('account_number')
        
        if not bank_id or not account_number:
            return jsonify({'success': False, 'error': 'Bank and account number required'})
        
        if len(str(account_number).strip()) < 3:
            return jsonify({'success': False, 'error': 'Account number too short'})
        
        from mock_bank import MockBankAPI
        result = MockBankAPI.connect_bank(bank_id, account_number)
        
        # Save to database
        from models import BankAPIConnection
        connection = BankAPIConnection(
            bank_name=result['bank_name'],
            account_number=result['account_number'],
            connection_type='mock',
            connection_data=result,
            is_active=True,
            user_id=session['user_id']
        )
        db.session.add(connection)
        db.session.commit()
        
        result['db_id'] = connection.id
        return jsonify(result)
        
    except Exception as e:
        print(f"Error connecting bank: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/bank/transactions/<int:connection_id>')
@login_required(roles=['manager', 'admin'])
def mock_bank_transactions(connection_id):
    """View mock transactions"""
    from models import BankAPIConnection
    
    connection = BankAPIConnection.query.get_or_404(connection_id)
    
    # Verify ownership
    if connection.user_id != session['user_id'] and session['role'] not in ['admin', 'manager']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    from mock_bank import MockBankAPI
    transactions = MockBankAPI.get_transactions(f"mock_{connection_id}")
    summary = MockBankAPI.get_account_summary(f"mock_{connection_id}")
    
    return render_template('bank/mock_transactions.html',
                         connection=connection,
                         transactions=transactions['transactions'],
                         summary=summary['summary'],
                         stats=summary['stats'])

@app.route('/api/bank/transactions/<int:connection_id>')
@login_required(roles=['manager', 'admin'])
def api_mock_transactions(connection_id):
    """API to get mock transactions"""
    from mock_bank import MockBankAPI
    days = request.args.get('days', 30, type=int)
    
    result = MockBankAPI.get_transactions(f"mock_{connection_id}", days)
    return jsonify(result)

@app.route('/bank/connections')
@login_required(roles=['manager', 'admin'])
def list_bank_connections():
    """List all bank connections"""
    from models import BankAPIConnection
    
    if session['role'] in ['admin', 'manager']:
        connections = BankAPIConnection.query.filter_by(is_active=True).all()
    else:
        connections = BankAPIConnection.query.filter_by(
            user_id=session['user_id'], 
            is_active=True
        ).all()
    
    return render_template('bank/connections.html', connections=connections)

@app.route('/bank/disconnect/<int:connection_id>', methods=['POST'])
@login_required(roles=['manager', 'admin'])
def disconnect_bank(connection_id):
    """Disconnect a bank account"""
    from models import BankAPIConnection
    
    connection = BankAPIConnection.query.get_or_404(connection_id)
    
    # Verify ownership
    if connection.user_id != session['user_id'] and session['role'] not in ['admin', 'manager']:
        flash('Access denied', 'danger')
        return redirect(url_for('list_bank_connections'))
    
    connection.is_active = False
    db.session.commit()
    
    flash(f'Disconnected from {connection.bank_name}', 'success')
    return redirect(url_for('list_bank_connections'))
if __name__ == '__main__':
    app.run(debug=True)