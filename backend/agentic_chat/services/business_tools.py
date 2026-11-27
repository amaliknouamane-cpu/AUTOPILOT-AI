"""Read-only business functions shared by LangGraph and the MCP server."""
from backend.database import get_connection


def list_catalogue(search: str = "", limit: int = 30) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    search_term = f"%{search.strip()}%"
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, unit_price, stock
                FROM products
                WHERE (%s = '' OR name ILIKE %s)
                ORDER BY name
                LIMIT %s;
                """,
                (search.strip(), search_term, limit),
            )
            rows = cursor.fetchall()
    return [
        {"product_name": row[0], "unit_price": float(row[1]), "available_stock": int(row[2])}
        for row in rows
    ]


def get_product_stock(product_name: str) -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, unit_price, stock
                FROM products
                WHERE LOWER(name) = LOWER(%s)
                LIMIT 1;
                """,
                (product_name.strip(),),
            )
            row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Product not found: {product_name}")
    return {"product_name": row[0], "unit_price": float(row[1]), "available_stock": int(row[2])}


def forecast_product_demand(product_name: str, days: int = 30) -> dict:
    """Simple, transparent baseline; the production Chronos forecast remains intact."""
    days = max(7, min(int(days), 90))
    product = get_product_stock(product_name)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(target), 0), COUNT(DISTINCT timestamp::date)
                FROM sales_history
                WHERE LOWER(item_id) = LOWER(%s)
                  AND timestamp >= CURRENT_DATE - (%s * INTERVAL '1 day')
                  AND timestamp < CURRENT_DATE;
                """,
                (product["product_name"], days),
            )
            total_quantity, active_days = cursor.fetchone()
    observed_days = int(active_days or 0)
    total_quantity = float(total_quantity or 0)
    if observed_days == 0:
        return {
            **product,
            "period_days": days,
            "observed_days": 0,
            "estimated_daily_demand": None,
            "estimated_next_7_day_demand": None,
            "message": "No recent approved sales; there is not enough evidence for an estimate.",
        }
    daily_average = total_quantity / days
    next_week = daily_average * 7
    return {
        **product,
        "period_days": days,
        "observed_days": observed_days,
        "estimated_daily_demand": round(daily_average, 3),
        "estimated_next_7_day_demand": round(next_week, 2),
        "estimated_stock_after_7_days": round(product["available_stock"] - next_week, 2),
        "method": "total sales in selected period divided by calendar days",
        "warning": "Baseline estimate for discussion, not the Chronos forecast.",
    }
