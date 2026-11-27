"""Database-backed queries used by the Business Intelligence dashboard."""

from datetime import date, timedelta

import pandas as pd

from database import read_query


LOW_STOCK_THRESHOLD = 5
NEW_CUSTOMER_DAYS = 30
AT_RISK_DAYS = 60
LOYAL_MIN_APPROVED_QUOTES = 3
BEST_CUSTOMER_PERCENTILE = 0.80


def get_business_kpis():
    """Return one row of quotation, revenue, and inventory KPIs."""
    return read_query(
        """
        SELECT
            COUNT(*)::integer AS total_quotations,
            COUNT(*) FILTER (WHERE status = 'approved')::integer
                AS approved_quotations,
            COUNT(*) FILTER (WHERE status = 'rejected')::integer
                AS rejected_quotations,
            COUNT(*) FILTER (WHERE status = 'calculated')::integer
                AS pending_quotations,
            COALESCE(
                SUM(total) FILTER (WHERE status = 'approved'), 0
            ) AS approved_revenue,
            COALESCE(ROUND(AVG(total), 2), 0) AS average_quotation_value,
            COALESCE(
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE status = 'approved')
                    / NULLIF(COUNT(*), 0),
                    2
                ),
                0
            ) AS approval_rate,
            COALESCE(
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE status = 'rejected')
                    / NULLIF(COUNT(*), 0),
                    2
                ),
                0
            ) AS rejection_rate,
            (SELECT COUNT(*)::integer FROM products) AS total_products,
            (
                SELECT COUNT(*)::integer
                FROM products
                WHERE stock <= %s
            ) AS low_stock_products
        FROM quotations;
        """,
        (LOW_STOCK_THRESHOLD,),
    )


def get_quotation_status_counts():
    return read_query(
        """
        SELECT status, COUNT(*)::integer AS total_quotations
        FROM quotations
        GROUP BY status
        ORDER BY status;
        """
    )


def get_monthly_quotation_metrics():
    """Monthly counts by status and approved-only revenue."""
    return read_query(
        """
        SELECT
            DATE_TRUNC('month', created_at)::date AS month,
            COUNT(*)::integer AS total_quotations,
            COUNT(*) FILTER (WHERE status = 'approved')::integer
                AS approved_quotations,
            COUNT(*) FILTER (WHERE status = 'rejected')::integer
                AS rejected_quotations,
            COUNT(*) FILTER (WHERE status = 'calculated')::integer
                AS pending_quotations,
            COALESCE(
                SUM(total) FILTER (WHERE status = 'approved'), 0
            ) AS approved_revenue
        FROM quotations
        WHERE created_at IS NOT NULL
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month;
        """
    )


def get_approved_sales_lines():
    """One row per approved quotation item; pending/rejected items excluded."""
    return read_query(
        """
        SELECT
            q.created_at::date AS sale_date,
            COALESCE(p.name, qi.product_name) AS product,
            qi.quantity,
            qi.subtotal AS revenue
        FROM quotations AS q
        JOIN quotation_items AS qi
            ON qi.quotation_id = q.id
        LEFT JOIN products AS p
            ON p.id = qi.product_id
        WHERE q.status = 'approved'
        ORDER BY sale_date, product;
        """
    )


def get_inventory():
    return read_query(
        """
        SELECT
            name AS product,
            unit_price,
            stock AS available_stock,
            unit_price * stock AS stock_value
        FROM products
        ORDER BY name;
        """
    )


def get_customer_purchase_summary():
    """One row per customer, with approved-quotation purchase history."""
    return read_query(
        """
        SELECT
            c.id AS customer_id,
            c.name AS customer,
            c.created_at AS customer_since,
            COUNT(q.id) FILTER (WHERE q.status = 'approved')::integer
                AS approved_order_count,
            COALESCE(
                SUM(q.total) FILTER (WHERE q.status = 'approved'), 0
            ) AS approved_revenue,
            MIN(q.created_at) FILTER (WHERE q.status = 'approved')
                AS first_purchase_at,
            MAX(q.created_at) FILTER (WHERE q.status = 'approved')
                AS last_purchase_at
        FROM customers AS c
        LEFT JOIN quotations AS q
            ON q.customer_id = c.id
        GROUP BY c.id, c.name, c.created_at
        ORDER BY c.name;
        """
    )


def segment_customers(customers, as_of=None):
    """Assign each customer one explainable segment from approved purchases."""
    result = customers.copy()
    if result.empty:
        result["segment"] = pd.Series(dtype="object")
        result["days_since_last_purchase"] = pd.Series(dtype="Int64")
        return result

    as_of = as_of or date.today()
    for column in ("customer_since", "first_purchase_at", "last_purchase_at"):
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.date

    result["approved_order_count"] = pd.to_numeric(
        result["approved_order_count"], errors="coerce"
    ).fillna(0).astype(int)
    result["approved_revenue"] = pd.to_numeric(
        result["approved_revenue"], errors="coerce"
    ).fillna(0.0)
    result["days_since_last_purchase"] = result["last_purchase_at"].apply(
        lambda last_purchase: (as_of - last_purchase).days
        if pd.notna(last_purchase)
        else pd.NA
    ).astype("Int64")

    has_purchase = result["approved_order_count"] > 0
    recent_first_purchase = result["first_purchase_at"].apply(
        lambda first: pd.notna(first)
        and first >= as_of - timedelta(days=NEW_CUSTOMER_DAYS)
    )
    is_new = recent_first_purchase & (
        result["approved_order_count"] == 1
    )

    at_risk = (
        has_purchase
        & result["days_since_last_purchase"].notna()
        & (result["days_since_last_purchase"] > AT_RISK_DAYS)
    )
    active = (
        has_purchase
        & result["days_since_last_purchase"].notna()
        & (result["days_since_last_purchase"] <= AT_RISK_DAYS)
    )
    best_eligible = active & (
        result["approved_order_count"] >= 2
    )
    best_customers = pd.Series(False, index=result.index)
    if best_eligible.any():
        revenue_cutoff = result.loc[
            best_eligible, "approved_revenue"
        ].quantile(BEST_CUSTOMER_PERCENTILE)
        best_customers = best_eligible & (
            result["approved_revenue"] >= revenue_cutoff
        )

    loyal = (
        active
        & (result["approved_order_count"] >= LOYAL_MIN_APPROVED_QUOTES)
        & ~best_customers
    )

    result["segment"] = "Occasional"
    result.loc[~has_purchase, "segment"] = "Prospect"
    result.loc[at_risk, "segment"] = "At Risk"
    result.loc[loyal, "segment"] = "Loyal"
    result.loc[best_customers, "segment"] = "Best Customers"
    result.loc[is_new, "segment"] = "New"
    return result
