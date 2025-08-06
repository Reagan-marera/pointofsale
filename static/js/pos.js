document.addEventListener('DOMContentLoaded', function() {
    const cart = [];
    let customerId = null;

    const selectedProduct = sessionStorage.getItem('selectedProduct');
    if (selectedProduct) {
        addToCart(JSON.parse(selectedProduct));
        sessionStorage.removeItem('selectedProduct');
    }
    
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
    scanBtn.addEventListener('click', function() {
        const barcode = barcodeInput.value.trim();
        if (barcode) {
            scanProduct(barcode);
        } else {
            if (Quagga.isExecuting) {
                Quagga.stop();
            } else {
                startScanner();
            }
        }
    });

    productSearch.addEventListener('keyup', function() {
        const searchTerm = this.value.toLowerCase();
        console.log('Searching for:', searchTerm);
        if (searchTerm.length < 2) {
            productList.innerHTML = '';
            return;
        }

        fetch(`/api/products?search=${searchTerm}`)
            .then(response => {
                console.log('Received response from /api/products:', response);
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(products => {
                console.log('Received products:', products);
                productList.innerHTML = '';
                if (products.length === 0) {
                    const item = document.createElement('div');
                    item.className = 'list-group-item';
                    item.textContent = 'No products found';
                    productList.appendChild(item);
                    return;
                }
                products.forEach(product => {
                    const item = document.createElement('a');
                    item.href = '#';
                    item.className = 'list-group-item list-group-item-action';
                    item.textContent = `${product.name} (${product.barcode})`;
                    item.addEventListener('click', function(e) {
                        e.preventDefault();
                        addToCart(product);
                        productList.innerHTML = '';
                        productSearch.value = '';
                    });
                    productList.appendChild(item);
                });
            })
            .catch(error => {
                console.error('Error fetching products:', error);
                productList.innerHTML = '<div class="list-group-item text-danger">Error searching for products.</div>';
            });
    });

    barcodeInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            scanProduct(barcodeInput.value);
        }
    });
    checkoutBtn.addEventListener('click', processCheckout);
    newSaleBtn.addEventListener('click', resetSale);
    printReceiptBtn.addEventListener('click', printReceipt);

    // Functions
    function startScanner() {
        Quagga.init({
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: document.querySelector('#barcode-scanner'),
                constraints: {
                    width: 480,
                    height: 320,
                    facingMode: "environment"
                },
            },
            decoder: {
                readers: [
                    "ean_reader",
                    "upc_reader",
                    "code_128_reader"
                ],
                debug: {
                    showCanvas: false,
                    showPatches: false,
                    showFoundPatches: false,
                    showSkeleton: false,
                    showLabels: false,
                    showFoundLabels: false,
                    showImage: false,
                    drawBoundingBox: false,
                    drawScanline: false,
                    showPattern: false
                }
            },
        }, function (err) {
            if (err) {
                console.error(err);
                alert('Error initializing scanner: ' + err);
                return;
            }
            console.log("Initialization finished. Ready to start");
            Quagga.start();
        });

        Quagga.onDetected(function (result) {
            scanProduct(result.codeResult.code);
            Quagga.stop();
            // Hide the scanner after a successful scan
            document.querySelector('#barcode-scanner').style.display = 'none';
        });
    }

    function scanProduct(barcode) {
        console.log('Scanning for barcode:', barcode);
        if (!barcode) {
            alert('Please enter a barcode');
            return;
        }
        
        fetch(`/api/products/${barcode}`)
            .then(response => {
                console.log('Received response from /api/products/<barcode>:', response);
                if (response.status === 404) {
                    throw new Error('Product with this barcode not found.');
                }
                if (!response.ok) {
                    throw new Error('An error occurred while fetching the product.');
                }
                return response.json();
            })
            .then(product => {
                console.log('Received product data:', product);
                if (product.error) {
                    alert(product.error);
                    return;
                }
                
                if (product.stock < 1) {
                    alert('Product is out of stock.');
                    return;
                }
                
                addToCart(product);
                barcodeInput.value = '';
                barcodeInput.focus();
            })
            .catch(error => {
                console.error('Error scanning product:', error);
                alert(error.message);
            });
    }
    
    function addToCart(product) {
        if (typeof product.price === 'undefined') {
            console.error('Product is missing price:', product);
            alert('Error: Product information is incomplete.');
            return;
        }

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
                stock: product.stock,
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
        document.getElementById('customer-select').value = '';
        document.getElementById('cash').checked = true;
        updateCartDisplay();
        barcodeInput.focus();
    }
});