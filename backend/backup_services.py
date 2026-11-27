
# Temporary product catalogue for development.
# Later, products and prices will come from PostgreSQL.

PRODUCTS = {
    "laptop": {
        "name": "Laptop",
        "unit_price": 6500.00,
        "stock": 20
    },
    "monitor": {
        "name": "Monitor",
        "unit_price": 1200.00,
        "stock": 15
    },
}


def calculate_quote(items):
    quote_items = []
    total = 0.0

    for item in items:
        product_key = item.product_name.strip().lower()
        product = PRODUCTS.get(product_key)

        if product is None:
            raise ValueError(
                f"Product not found: {item.product_name}"
            )

        if item.quantity > product["stock"]:
            raise ValueError(
                f"Insufficient stock for {product['name']}"
            )

        subtotal = product["unit_price"] * item.quantity
        total += subtotal

        quote_items.append({
            "product_name": product["name"],
            "quantity": item.quantity,
            "unit_price": product["unit_price"],
            "subtotal": round(subtotal, 2)
        })

    return {
        "items": quote_items,
        "total": round(total, 2),
        "currency": "MAD"
    }
