from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from models import db,  User, Product, Customer, Sale, SaleItem, InventoryMovement, AccountingEntry,PurchaseOrder,Supplier,Expense,Dealer,PurchaseOrderItem,Financier,FinancierCredit,FinancierDebit
from datetime import datetime,timedelta
import random
from sqlalchemy.orm import joinedload
import string
from config import Config
from sqlalchemy import func
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


# Create tables before first request
with app.app_context():
    db.create_all()

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
    
    # For subsequent registrations, only allow admins
    if 'user_id' not in session or session.get('role') != 'admin':
        if is_api_request:
            return jsonify({
                'message': 'Only administrators can register new users',
                'status': 'error'
            }), 403
        flash('Only administrators can register new users', 'danger')
        return redirect(url_for('login'))
    
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
def login_required(role='cashier'):
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

            if user.role not in [role, 'admin']:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)

        return decorated_function
    return decorator

# Update the dashboard route
@app.route('/dashboard')
@login_required()
def dashboard():
    # Get basic stats for dashboard
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.current_stock < Product.min_stock_level).count()
    today_sales = Sale.query.filter(func.date(Sale.sale_date) == datetime.today().date()).count()
    
    # Get recent sales
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    
    # Get low stock items
    low_stock_items = Product.query.filter(Product.current_stock < Product.min_stock_level).order_by(Product.current_stock.asc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         today_sales=today_sales,
                         recent_sales=recent_sales,
                         low_stock_items=low_stock_items)
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

        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            print(f"Session set: {session['user_id']}, {session['username']}, {session['role']}")  # Debug print
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))



@app.route('/products')
@login_required('manager'and 'admin')
def products():
    page = request.args.get('page', 1, type=int)
    dealer_id = request.args.get('dealer_id', type=int)

    # Create a base query with joined loads for supplier and dealer
    query = Product.query.options(joinedload(Product.supplier), joinedload(Product.dealer)).order_by(Product.name.asc())

    # Apply dealer filter if dealer_id is provided
    if dealer_id:
        query = query.filter(Product.dealer_id == dealer_id)

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
@login_required('admin')
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
@login_required('manager' and 'admin')
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    suppliers = Supplier.query.all()
    dealers = Dealer.query.all()

    if request.method == 'POST':
        product.name = request.form['name']
        product.category = request.form['category']
        product.buying_price = float(request.form['buying_price'])
        product.selling_price = float(request.form['selling_price'])
        product.current_stock = int(request.form['stock'])
        product.min_stock_level = int(request.form['min_stock'])
        product.barcode = request.form['barcode'].strip()
        product.supplier_id = request.form['supplier_id']
        product.dealer_id = request.form['dealer_id']
        product.vatable = 'vatable' in request.form

        if not product.name or not product.category or not product.buying_price or not product.selling_price or not product.current_stock or not product.min_stock_level or not product.barcode or not product.supplier_id or not product.dealer_id:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_product', product_id=product_id))

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('products'))

    return render_template('edit_product.html', product=product, suppliers=suppliers, dealers=dealers)

@app.route('/admin/users')
@login_required('admin')
def manage_users():
    users = User.query.order_by(User.username.asc()).all()
    return render_template('users.html', users=users)

@app.route('/admin/reports/sales')
@login_required('manager')
def sales_report():
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    payment_method = request.args.get('payment_method')
    
    # Build query
    query = Sale.query
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Sale.sale_date >= start_date)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Sale.sale_date < end_date)
    
    if payment_method:
        query = query.filter_by(payment_method=payment_method)
    
    # Get sales data
    sales = query.order_by(Sale.sale_date.desc()).limit(50).all()
    
    # Calculate totals
    total_sales = sum(sale.total_amount for sale in sales) if sales else 0
    total_transactions = len(sales)
    average_sale = total_sales / total_transactions if total_transactions > 0 else 0
    
    # Sales by payment method
    sales_by_method = db.session.query(
        Sale.payment_method,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('total')
    ).group_by(Sale.payment_method).all()
    
    # Prepare data for chart
    payment_method_labels = [method[0].capitalize() for method in sales_by_method]
    payment_method_data = [float(method[2]) for method in sales_by_method]
    
    return render_template('sales_report.html',
                        sales=sales,
                        total_sales=total_sales,
                        total_transactions=total_transactions,
                        average_sale=average_sale,
                        sales_by_method=sales_by_method,
                        payment_method_labels=payment_method_labels,
                        payment_method_data=payment_method_data)

@app.route('/api/products/<barcode>')
def get_product_by_barcode(barcode):
    product = Product.query.filter_by(barcode=barcode).first()
    if product:
        return jsonify({
            'id': product.id,
            'barcode': product.barcode,
            'name': product.name,
            'price': product.selling_price,
            'stock': product.current_stock,
            'tax_rate': product.tax_rate,
            'vatable': product.vatable
        })
    return jsonify({'error': 'Product not found'}), 404
# Add user management routes
@app.route('/admin/users/add', methods=['POST'])
@login_required('admin')
def add_user():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('manage_users'))
    
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('manage_users'))
    
    new_user = User(
        username=username,
        email=email,
        role=role
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('User added successfully', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required('admin')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    user.username = request.form['username']
    user.email = request.form['email']
    user.role = request.form['role']
    user.is_active = 'is_active' in request.form
    
    if request.form['password']:
        user.set_password(request.form['password'])
    
    db.session.commit()
    
    flash('User updated successfully', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required('admin')
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
@login_required('manager'and 'admin')
def add_product():
    suppliers = Supplier.query.all()
    dealers = Dealer.query.all()  # Fetch all dealers

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        buying_price = float(request.form['buying_price'])
        selling_price = float(request.form['selling_price'])
        stock = int(request.form['stock'])
        barcode = request.form['barcode'].strip()
        supplier_id = request.form['supplier_id']
        dealer_id = request.form['dealer_id']  # Get dealer_id from form
        vatable = 'vatable' in request.form

        if not barcode:
            flash('Barcode is required.', 'danger')
            return redirect(url_for('add_product'))

        existing = Product.query.filter_by(barcode=barcode).first()
        if existing:
            flash('A product with this barcode already exists.', 'danger')
            return redirect(url_for('add_product'))

        if not name or not category or not buying_price or not selling_price or not stock or not barcode or not supplier_id or not dealer_id:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_product'))

        new_product = Product(
            barcode=barcode,
            name=name,
            category=category,
            buying_price=buying_price,
            selling_price=selling_price,
            current_stock=stock,
            supplier_id=supplier_id,
            dealer_id=dealer_id,  # Assign dealer_id to the product
            vatable=vatable
        )

        db.session.add(new_product)
        db.session.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))

    return render_template('add_product.html', suppliers=suppliers, dealers=dealers)


@app.route('/pos')
@login_required()
def pos():
    products = Product.query.filter(Product.current_stock > 0).all()
    customers = Customer.query.all()
    return render_template('pos.html', products=products, customers=customers)

@app.route('/api/products/<barcode>')
def get_product(barcode):
    product = Product.query.filter_by(barcode=barcode).first()
    if product:
        return jsonify({
            'id': product.id,
            'name': product.name,
            'price': product.selling_price,
            'stock': product.current_stock
        })
    return jsonify({'error': 'Product not found'}), 404

@app.route('/api/checkout', methods=['POST'])
@login_required()
def checkout():
    data = request.get_json()
    items = data.get('items', [])
    customer_id = data.get('customer_id')
    payment_method = data.get('payment_method', 'cash')

    if not items:
        return jsonify({'error': 'No items in cart'}), 400

    # Calculate totals
    subtotal = 0
    tax = 0
    for item in items:
        product = Product.query.get(item['id'])
        if product:
            item_total = product.selling_price * item['quantity']
            subtotal += item_total
            if product.vatable:
                tax += item_total * product.tax_rate

    total = subtotal + tax

    # Create sale
    sale = Sale(
        receipt_number=Sale.generate_receipt_number(),
        customer_id=customer_id,
        user_id=session['user_id'],
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=total,
        payment_method=payment_method
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

            # Update product stock
            product.current_stock -= item['quantity']

            # Record inventory movement
            movement = InventoryMovement(
                product_id=product.id,
                movement_type='sale',
                quantity=-item['quantity'],
                reference_id=sale.id
            )
            db.session.add(movement)

    # Create accounting entries
    revenue_entry = AccountingEntry(
        account_type='revenue',
        account_name='Sales Revenue',
        credit_amount=subtotal,
        reference_id=sale.id,
        description=f'Sale #{sale.receipt_number}'
    )

    tax_entry = AccountingEntry(
        account_type='liability',
        account_name='VAT Payable',
        credit_amount=tax,
        reference_id=sale.id,
        description=f'VAT for sale #{sale.receipt_number}'
    )

    db.session.add(revenue_entry)
    db.session.add(tax_entry)
    db.session.commit()

    return jsonify({
        'success': True,
        'receipt_number': sale.receipt_number,
        'total': total
    })

@app.route('/receipt/<receipt_number>')
@login_required()
def view_receipt(receipt_number):
    sale = Sale.query.filter_by(receipt_number=receipt_number).first_or_404()
    return render_template('receipt.html', sale=sale)

@app.route('/receipt/<receipt_number>/delete', methods=['POST'])
@login_required('admin')  # or 'manager', depending on your roles
def delete_receipt(receipt_number):
    sale = Sale.query.filter_by(receipt_number=receipt_number).first_or_404()

    # Optional: delete related sale_items if your model requires it
    SaleItem.query.filter_by(sale_id=sale.id).delete()

    db.session.delete(sale)
    db.session.commit()

    flash(f'Receipt #{receipt_number} deleted successfully.', 'success')
    return redirect(url_for('dashboard'))
@app.route('/purchase_orders/<int:order_id>/receive', methods=['POST'])
@login_required('manager')
def receive_purchase_order(order_id):
    purchase_order = PurchaseOrder.query.get_or_404(order_id)

    total_purchase_amount = 0
    for item in purchase_order.items:
        product = Product.query.get(item.product_id)
        product.current_stock += item.quantity

        # Calculate total purchase amount for this item
        item_total = product.buying_price * item.quantity
        total_purchase_amount += item_total

        # Record inventory movement with the total purchase amount
        movement = InventoryMovement(
            product_id=product.id,
            movement_type='purchase',
            quantity=item.quantity,
            unit_price=product.buying_price,
            total_amount=item_total,
            reference_id=purchase_order.id,
            notes='Received from purchase order'
        )
        db.session.add(movement)

    # Update the total purchase amount for the purchase order
    purchase_order.total_amount = total_purchase_amount
    db.session.commit()

    flash('Purchase order received successfully', 'success')
    return redirect(url_for('manage_purchase_orders'))

@app.route('/purchase_orders/<int:order_id>/finalize', methods=['POST'])
@login_required('manager')
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
@login_required('manager')
def inventory_management():
    # Get the selected dealer_id from the request arguments
    dealer_id = request.args.get('dealer_id', type=int)

    # Fetch all dealers for the filter dropdown
    dealers = Dealer.query.all()

    # Base queries with dealer filtering
    products_query = Product.query
    movements_query = InventoryMovement.query
    purchase_orders_query = PurchaseOrder.query
    sale_items_query = SaleItem.query

    if dealer_id:
        # Apply dealer filter to all queries
        products_query = products_query.filter(Product.dealer_id == dealer_id)
        
        movements_query = movements_query.join(Product).filter(Product.dealer_id == dealer_id)
        
        purchase_orders_query = purchase_orders_query.join(
            PurchaseOrderItem
        ).join(
            Product
        ).filter(
            Product.dealer_id == dealer_id
        ).distinct()
        
        sale_items_query = sale_items_query.join(Product).filter(Product.dealer_id == dealer_id)

    # Execute queries
    products = products_query.all()
    inventory_movements = movements_query.order_by(InventoryMovement.movement_date.desc()).limit(50).all()
    purchase_orders = purchase_orders_query.order_by(PurchaseOrder.order_date.desc()).limit(50).all()

    # Calculate financials with proper filtering
    total_sales_amount = db.session.query(
        func.sum(SaleItem.total_price)
    ).join(
        Product
    ).filter(
        Product.dealer_id == dealer_id if dealer_id else True
    ).scalar() or 0

    total_purchase_amount = db.session.query(
        func.sum(InventoryMovement.total_amount)
    ).join(
        Product
    ).filter(
        InventoryMovement.movement_type == 'purchase',
        Product.dealer_id == dealer_id if dealer_id else True
    ).scalar() or 0

    # Expenses remain global (not dealer-specific)
    total_expense_amount = db.session.query(func.sum(Expense.amount)).scalar() or 0

    net_amount = total_sales_amount - total_purchase_amount - total_expense_amount

    return render_template('inventory_management.html',
                         products=products,
                         dealers=dealers,
                         selected_dealer_id=dealer_id,
                         inventory_movements=inventory_movements,
                         purchase_orders=purchase_orders,
                         total_sales_amount=total_sales_amount,
                         total_purchase_amount=total_purchase_amount,
                         total_expense_amount=total_expense_amount,
                         net_amount=net_amount)

@app.route('/suppliers')
@login_required('manager 'and 'admin')
def list_suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

# Route to add a new supplier
@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required('manager')
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
@login_required('manager')
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
@login_required('manager')
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()

    flash('Supplier deleted successfully!', 'success')
    return redirect(url_for('list_suppliers'))


@app.route('/expenses')
@login_required('manager')
def list_expenses():
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('expenses/list.html', expenses=expenses)

@app.route('/expenses/add', methods=['GET', 'POST'])
@login_required('manager')
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
            amount=amount
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
@login_required('manager')
def list_dealers():
    dealers = Dealer.query.all()
    return render_template('dealers/list.html', dealers=dealers)

@app.route('/dealers/add', methods=['GET', 'POST'])
@login_required('manager')
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
@login_required('manager')
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
@login_required('manager')
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

# Add a new route for customers
@app.route('/customers')
@login_required('manager' and 'admin')
def list_customers():
    customers = Customer.query.all()
    return render_template('customers/list.html', customers=customers)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        if not name or not email or not phone:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('add_customer'))

        if Customer.query.filter_by(email=email).first():
            flash('A customer with this email already exists.', 'danger')
            return redirect(url_for('add_customer'))

        if Customer.query.filter_by(phone=phone).first():
            flash('A customer with this phone number already exists.', 'danger')
            return redirect(url_for('add_customer'))

        new_customer = Customer(
            name=name,
            email=email,
            phone=phone
        )

        db.session.add(new_customer)
        db.session.commit()

        flash('Customer added successfully!', 'success')
        return redirect(url_for('list_customers'))

    return render_template('customers/add.html')

@app.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required('manager' and 'admin')
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        customer.name = request.form['name']
        customer.email = request.form['email']
        customer.phone = request.form['phone']

        if not customer.name or not customer.email or not customer.phone:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('edit_customer', customer_id=customer_id))

        db.session.commit()

        flash('Customer updated successfully!', 'success')
        return redirect(url_for('list_customers'))

    return render_template('customers/edit.html', customer=customer)

@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required('manager' and 'admin')
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()

    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('list_customers'))

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
if __name__ == '__main__':
    app.run(debug=True)