document.addEventListener('DOMContentLoaded', function() {
    // Initialize variables
    let cart = [];
    const taxRate = 0.16; // 16% VAT

    // Scanner functionality
    const barcodeScannerModal = new bootstrap.Modal(document.getElementById('barcodeScannerModal'));
    let scannerActive = false;
    let scannerInitialized = false;

    // Initialize scanner when modal is shown
    document.getElementById('barcodeScannerModal').addEventListener('shown.bs.modal', function() {
        if (!scannerInitialized) {
            initBarcodeScanner();
            scannerInitialized = true;
        } else {
            startScanner();
        }
    });

    // Clean up scanner when modal is hidden
    document.getElementById('barcodeScannerModal').addEventListener('hidden.bs.modal', function() {
        stopScanner();
    });

    // Scan button click handler
    document.getElementById('scan-btn').addEventListener('click', function() {
        barcodeScannerModal.show();
    });

    // Manual barcode confirmation
    document.getElementById('manual-scan-confirm-btn').addEventListener('click', function() {
        const barcode = document.getElementById('manual-barcode-input').value.trim();
        if (barcode) {
            document.getElementById('barcode-input').value = barcode;
            addProductToCart(barcode);
            barcodeScannerModal.hide();
        }
    });

    // Handle manual barcode input
    document.getElementById('barcode-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const barcode = this.value.trim();
            if (barcode) {
                addProductToCart(barcode);
                this.value = '';
            }
        }
    });

    function initBarcodeScanner() {
        Quagga.init({
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: document.querySelector('#interactive'),
                constraints: {
                    width: 640,
                    height: 480,
                    facingMode: "environment"
                },
            },
            decoder: {
                readers: ["ean_reader", "ean_8_reader", "code_128_reader", "code_39_reader"],
                multiple: false
            },
            locate: true,
            debug: {
                drawBoundingBox: true,
                showFrequency: true,
                drawScanline: true,
                showPattern: true
            }
        }, function(err) {
            if (err) {
                console.error("Scanner initialization error:", err);
                alert("Failed to initialize barcode scanner. Please use manual entry.");
                return;
            }
            console.log("Scanner initialized successfully");
            startScanner();
        });

        Quagga.onProcessed(function(result) {
            const drawingCtx = Quagga.canvas.ctx.overlay;
            const drawingCanvas = Quagga.canvas.dom.overlay;

            if (result) {
                if (result.boxes) {
                    drawingCtx.clearRect(0, 0, parseInt(drawingCanvas.getAttribute("width")), parseInt(drawingCanvas.getAttribute("height")));
                    result.boxes.filter(function(box) {
                        return box !== result.box;
                    }).forEach(function(box) {
                        Quagga.ImageDebug.drawPath(box, {x: 0, y: 1}, drawingCtx, {color: "green", lineWidth: 2});
                    });
                }

                if (result.box) {
                    Quagga.ImageDebug.drawPath(result.box, {x: 0, y: 1}, drawingCtx, {color: "#00F", lineWidth: 2});
                }

                if (result.codeResult && result.codeResult.code) {
                    Quagga.ImageDebug.drawPath(result.line, {x: 'x', y: 'y'}, drawingCtx, {color: 'red', lineWidth: 3});
                }
            }
        });

        Quagga.onDetected(function(result) {
            const code = result.codeResult.code;
            console.log("Barcode detected:", code);
            document.getElementById('barcode-input').value = code;
            addProductToCart(code);
            stopScanner();
            barcodeScannerModal.hide();
        });
    }

    function startScanner() {
        if (!scannerActive && scannerInitialized) {
            Quagga.start();
            scannerActive = true;
            console.log("Scanner started");
        }
    }

    function stopScanner() {
        if (scannerActive) {
            Quagga.stop();
            scannerActive = false;
            console.log("Scanner stopped");
        }
    }

    // Product search functionality
    document.getElementById('product-search').addEventListener('input', function() {
        const searchTerm = this.value.trim();
        if (searchTerm.length > 2) {
            fetch(`/api/products/search?q=${encodeURIComponent(searchTerm)}`)
                .then(response => response.json())
                .then(products => {
                    const productList = document.getElementById('product-list');
                    productList.innerHTML = '';

                    if (products.length > 0) {
                        products.forEach(product => {
                            const item = document.createElement('button');
                            item.type = 'button';
                            item.className = 'list-group-item list-group-item-action';
                            item.textContent = `${product.name} (${product.barcode}) - KSh ${product.price.toFixed(2)}`;
                            item.addEventListener('click', function() {
                                addProductToCart(product.barcode);
                                document.getElementById('product-search').value = '';
                                productList.innerHTML = '';
                            });
                            productList.appendChild(item);
                        });
                    } else {
                        const item = document.createElement('div');
                        item.className = 'list-group-item';
                        item.textContent = 'No products found';
                        productList.appendChild(item);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        } else {
            document.getElementById('product-list').innerHTML = '';
        }
    });

    // Add product to cart
    function addProductToCart(barcode) {
        // Check if product already exists in cart
        const existingItem = cart.find(item => item.barcode === barcode);
        if (existingItem) {
            existingItem.quantity += 1;
            updateCartItem(existingItem);
            updateCartTotals();
            return;
        }

        // Fetch product details from API
        fetch(`/api/products/${barcode}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Product not found');
                }
                return response.json();
            })
            .then(product => {
                const cartItem = {
                    id: product.id,
                    barcode: product.barcode,
                    name: product.name,
                    price: product.price,
                    quantity: 1,
                    vatable: product.vatable
                };

                cart.push(cartItem);
                renderCartItem(cartItem);
                updateCartTotals();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Product not found! Please try another barcode.');
            });
    }

    // Render cart item in the table
    function renderCartItem(item) {
        const cartItems = document.getElementById('cart-items');
        const row = document.createElement('tr');
        row.dataset.id = item.id;
        row.innerHTML = `
            <td>${item.name}</td>
            <td class="price">KSh ${item.price.toFixed(2)}</td>
            <td><input type="number" class="form-control form-control-sm qty-input" value="${item.quantity}" min="1"></td>
            <td class="item-total">KSh ${(item.price * item.quantity).toFixed(2)}</td>
            <td><button class="btn btn-sm btn-danger remove-item"><i class="fas fa-trash"></i></button></td>
        `;
        cartItems.appendChild(row);

        // Add event listeners
        row.querySelector('.qty-input').addEventListener('change', function() {
            const newQty = parseInt(this.value);
            if (newQty > 0) {
                item.quantity = newQty;
                updateCartItem(item);
                updateCartTotals();
            }
        });

        row.querySelector('.remove-item').addEventListener('click', function() {
            cart = cart.filter(cartItem => cartItem.id !== item.id);
            row.remove();
            updateCartTotals();
        });
    }

    // Update existing cart item
    function updateCartItem(item) {
        const row = document.querySelector(`tr[data-id="${item.id}"]`);
        if (row) {
            row.querySelector('.qty-input').value = item.quantity;
            row.querySelector('.item-total').textContent = `KSh ${(item.price * item.quantity).toFixed(2)}`;
        }
    }

    // Update cart totals
    function updateCartTotals() {
        const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const taxableItems = cart.filter(item => item.vatable);
        const tax = taxableItems.reduce((sum, item) => sum + (item.price * item.quantity * taxRate), 0);
        const total = subtotal + tax;

        document.getElementById('subtotal').textContent = `KSh ${subtotal.toFixed(2)}`;
        document.getElementById('tax').textContent = `KSh ${tax.toFixed(2)}`;
        document.getElementById('total').textContent = `KSh ${total.toFixed(2)}`;
    }

    // New sale button
    document.getElementById('new-sale-btn').addEventListener('click', function() {
        if (cart.length > 0 && confirm('Are you sure you want to start a new sale? Current cart will be cleared.')) {
            cart = [];
            document.getElementById('cart-items').innerHTML = '';
            updateCartTotals();
            document.getElementById('customer-select').value = '';
            document.getElementById('barcode-input').value = '';
            document.getElementById('barcode-input').focus();
        }
    });

    let lastReceiptNumber = null;

    // Checkout button
    document.getElementById('checkout-btn').addEventListener('click', function() {
        if (cart.length === 0) {
            alert('Cart is empty! Please add products before checkout.');
            return;
        }

        const paymentMethod = document.querySelector('input[name="payment-method"]:checked').value;
        const customerId = document.getElementById('customer-select').value || null;
        const splitPayment = document.getElementById('split-payment').checked;

        const saleData = {
            items: cart,
            customer_id: customerId,
            payment_method: paymentMethod,
            split_payment: splitPayment
        };

        fetch('/api/sales', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(saleData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                lastReceiptNumber = data.receipt_number;
                alert('Sale completed successfully!');
                // Print receipt or clear cart as needed
                cart = [];
                document.getElementById('cart-items').innerHTML = '';
                updateCartTotals();
                document.getElementById('barcode-input').focus();
            } else {
                alert('Checkout failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error completing sale. Please try again.');
        });
    });

    // Print receipt button
    document.getElementById('print-receipt-btn').addEventListener('click', function() {
        if (lastReceiptNumber) {
            window.open(`/receipt/print/${lastReceiptNumber}`, '_blank');
        } else {
            alert('No receipt to print. Please complete a sale first.');
        }
    });
});
