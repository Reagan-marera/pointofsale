document.addEventListener('DOMContentLoaded', function() {
    const cart = [];
    let customerId = null;
    
    // DOM Elements
    const barcodeInput = document.getElementById('barcode-input');
    const scanBtn = document.getElementById('scan-btn');
    const cartItems = document.getElementById('cart-items');
    const subtotalEl = document.getElementById('subtotal');
    const taxEl = document.getElementById('tax');
    const totalEl = document.getElementById('total');
    const checkoutBtn = document.getElementById('checkout-btn');
    const newSaleBtn = document.getElementById('new-sale-btn');
    const printReceiptBtn = document.getElementById('print-receipt-btn');
    const productSearch = document.getElementById('product-search');
    const productList = document.getElementById('product-list');
    
    // Event Listeners
    barcodeInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            scanProduct();
        }
    });
    
    scanBtn.addEventListener('click', scanProduct);
    checkoutBtn.addEventListener('click', processCheckout);
    newSaleBtn.addEventListener('click', resetSale);
    printReceiptBtn.addEventListener('click', printReceipt);

    productSearchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const searchTerm = productSearch.value.toLowerCase();
        if (searchTerm.length < 2) {
            productList.innerHTML = '';
            return;
        }

        fetch(`/api/products?search=${searchTerm}`)
            .then(response => response.json())
            .then(products => {
                productList.innerHTML = '';
                if (products.length > 0) {
                    const table = document.createElement('table');
                    table.className = 'table table-striped table-hover';
                    const thead = document.createElement('thead');
                    thead.innerHTML = `
                        <tr>
                            <th>Name</th>
                            <th>Barcode</th>
                            <th>Price</th>
                            <th>Action</th>
                        </tr>
                    `;
                    table.appendChild(thead);
                    const tbody = document.createElement('tbody');
                    products.forEach(product => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${product.name}</td>
                            <td>${product.barcode}</td>
                            <td>KSh ${product.selling_price.toFixed(2)}</td>
                            <td>
                                <button class="btn btn-sm btn-primary select-product-btn" data-barcode="${product.barcode}">Select</button>
                            </td>
                        `;
                        tbody.appendChild(row);
                    });
                    table.appendChild(tbody);
                    productList.appendChild(table);

                    document.querySelectorAll('.select-product-btn').forEach(btn => {
                        btn.addEventListener('click', function() {
                            barcodeInput.value = this.dataset.barcode;
                            scanProduct();
                            productList.innerHTML = '';
                            productSearch.value = '';
                        });
                    });
                } else {
                    productList.innerHTML = '<p class="text-muted">No products found.</p>';
                }
            });
    });
    
    // Functions
    function scanProduct() {
        const barcode = barcodeInput.value.trim();
        if (!barcode) {
            alert('Please enter a barcode');
            return;
        }
        
        fetch(`/api/products/${encodeURIComponent(barcode)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Product not found');
                }
                return response.json();
            })
            .then(product => {
                if (product.error) {
                    alert(product.error);
                    return;
                }
                
                // Check stock
                if (product.stock < 1) {
                    alert('Product out of stock');
                    return;
                }
                
                addToCart(product);
                barcodeInput.value = '';
                barcodeInput.focus();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Product not found. Please try another barcode.');
            });
    }
    
    function addToCart(product) {
        const existingItem = cart.find(item => item.id === product.id);
    
        if (existingItem) {
            if (existingItem.quantity >= product.stock) {
                alert(`Only ${product.stock} item(s) available in stock`);
                return;
            }
            existingItem.quantity += 1;
        } else {
            if (product.stock < 1) {
                alert('Product out of stock');
                return;
            }
            cart.push({
                id: product.id,
                name: product.name,
                price: product.price,
                quantity: 1,
                stock: product.stock, // 👈 Store the stock with the cart item
                vatable: product.vatable
            });
        }
    
        updateCartDisplay();
    }
    
    function updateQuantity(productId, change) {
        const item = cart.find(item => item.id === productId);
        if (!item) return;
    
        const newQuantity = item.quantity + change;
    
        if (newQuantity < 1) {
            removeItem(productId);
            return;
        }
    
        // ✅ Check against item.stock before increasing
        if (newQuantity > item.stock) {
            alert(`Only ${item.stock} item(s) available in stock`);
            return;
        }
    
        item.quantity = newQuantity;
        updateCartDisplay();
    }
    
    
    function updateCartDisplay() {
        cartItems.innerHTML = '';
        let subtotal = 0;
        
        cart.forEach(item => {
            const row = document.createElement('tr');
            const total = item.price * item.quantity;
            subtotal += total;
            
            row.innerHTML = `
                <td>${item.name}</td>
                <td>KSh ${item.price.toFixed(2)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <button class="btn btn-outline-secondary minus-btn" data-id="${item.id}">-</button>
                        <input type="text" class="form-control text-center" value="${item.quantity}" readonly>
                        <button class="btn btn-outline-secondary plus-btn" data-id="${item.id}">+</button>
                    </div>
                </td>
                <td>KSh ${total.toFixed(2)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger remove-btn" data-id="${item.id}">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            
            cartItems.appendChild(row);
        });
        
        // Add event listeners to buttons in the new rows
        document.querySelectorAll('.minus-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const productId = parseInt(this.dataset.id);
                updateQuantity(productId, -1);
            });
        });
        
        document.querySelectorAll('.plus-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const productId = parseInt(this.dataset.id);
                updateQuantity(productId, 1);
            });
        });
        
        document.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const productId = parseInt(this.dataset.id);
                removeItem(productId);
            });
        });
        
        // Update totals
        let tax = 0;
        cart.forEach(item => {
            if (item.vatable) {
                tax += item.price * item.quantity * 0.16;
            }
        });
        const total = subtotal + tax;
        
        subtotalEl.textContent = `KSh ${subtotal.toFixed(2)}`;
        taxEl.textContent = `KSh ${tax.toFixed(2)}`;
        totalEl.textContent = `KSh ${total.toFixed(2)}`;
        
        // Enable/disable checkout button
        checkoutBtn.disabled = cart.length === 0;
    }
    
    function updateQuantity(productId, change) {
        const item = cart.find(item => item.id === productId);
        if (!item) return;
        
        const newQuantity = item.quantity + change;
        
        if (newQuantity < 1) {
            removeItem(productId);
            return;
        }
        
        // Check stock (would need to fetch current stock from server in real app)
        item.quantity = newQuantity;
        updateCartDisplay();
    }
    
    function removeItem(productId) {
        const index = cart.findIndex(item => item.id === productId);
        if (index !== -1) {
            cart.splice(index, 1);
            updateCartDisplay();
        }
    }
    
    function processCheckout() {
        if (cart.length === 0) {
            alert('Cart is empty');
            return;
        }
        
        const paymentMethod = document.querySelector('input[name="payment-method"]:checked').value;
        const splitPayment = document.getElementById('split-payment').checked;
        
        const checkoutData = {
            items: cart,
            payment_method: paymentMethod,
            customer_id: customerId,
            split_payment: splitPayment
        };
        
        fetch('/api/checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(checkoutData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Sale completed! Receipt #${data.receipt_number}`);
                window.location.href = `/receipt/${data.receipt_number}`;
            } else {
                alert('Checkout failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Checkout failed');
        });
    }
    
    function resetSale() {
        if (cart.length > 0 && !confirm('Are you sure you want to start a new sale? Current cart will be cleared.')) {
            return;
        }
        
        cart.length = 0;
        customerId = null;
        document.getElementById('customer-search').value = '';
        document.getElementById('cash').checked = true;
        updateCartDisplay();
        barcodeInput.focus();
    }
});