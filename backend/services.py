
from database import get_connection


def calculate_quote(items):
    quote_items = []
    total = 0.0

    with get_connection() as conn:
        with conn.cursor() as cur:

            for item in items:
                product_key = item.product_name.strip()

                # Search for the product in the database
                cur.execute(
                    """
                    SELECT name, unit_price, stock
                    FROM products
                    WHERE LOWER(name) = LOWER(%s);
                    """,
                    (product_key,)
                )

                product = cur.fetchone()

                # Check whether the product exists
                if product is None:
                    raise ValueError(
                        f"Product not found: {item.product_name}"
                    )

                name, unit_price, stock = product

                # Check product availability
                if item.quantity > stock:
                    raise ValueError(
                        f"Insufficient stock for {name}. "
                        f"Requested: {item.quantity}, "
                        f"Available: {stock}."
                    )

                # Calculate subtotal
                subtotal = float(unit_price) * item.quantity
                total += subtotal

                # Add product to quotation
                quote_items.append({
                    "product_name": name,
                    "quantity": item.quantity,
                    "unit_price": float(unit_price),
                    "subtotal": round(subtotal, 2)
                })

    return {
        "items": quote_items,
        "total": round(total, 2),
        "currency": "MAD"
    }
