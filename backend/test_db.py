
from database import get_connection

try:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, unit_price, stock FROM products;")
            products = cur.fetchall()

            print("Connected to PostgreSQL successfully!")
            for product in products:
                print(product)

except Exception as error:
    print("Database connection failed:")
    print(error)
