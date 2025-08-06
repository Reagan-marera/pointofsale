document.addEventListener('DOMContentLoaded', function() {
    const addToCartForm = document.getElementById('add-to-cart-form');
    const barcodeInput = document.getElementById('barcode-input');
    const cartItems = document.getElementById('cart-items');
    const totalEl = document.getElementById('total');
    const checkoutBtn = document.getElementById('checkout-btn');

    let cart = [];

    addToCartForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const barcode = barcodeInput.value.trim();
        if (barcode) {
            addToCart(barcode);
        }
    });

    checkoutBtn.addEventListener('click', function() {
        fetch('/api/checkout_simple', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({cart: cart})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Checkout successful!');
                cart = [];
                updateCartDisplay();
            } else {
                alert('Checkout failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Checkout failed');
        });
    });

    function addToCart(barcode) {
        fetch('/api/add_to_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({barcode: barcode})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                cart = data.cart;
                updateCartDisplay();
                barcodeInput.value = '';
                barcodeInput.focus();
            } else {
                alert(data.error);
            }
        });
    }

    function updateCartDisplay() {
        cartItems.innerHTML = '';
        let total = 0;
        cart.forEach(item => {
            const row = document.createElement('tr');
            const itemTotal = item.price * item.quantity;
            total += itemTotal;
            row.innerHTML = `
                <td>${item.name}</td>
                <td>${item.quantity}</td>
                <td>KSh ${item.price.toFixed(2)}</td>
                <td>KSh ${itemTotal.toFixed(2)}</td>
            `;
            cartItems.appendChild(row);
        });
        totalEl.textContent = `KSh ${total.toFixed(2)}`;
    }
});