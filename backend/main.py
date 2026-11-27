from pdf_service import generate_quote_pdf
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from uuid import uuid4
import requests
from notification_service import log_notification

from models import QuoteRequest, QuoteMessageRequest
from ai_service import extract_quote_information
from database import get_connection
from services import calculate_quote

app = FastAPI(
    title="AutoPilot AI",
    description="Intelligent automation of commercial processes",
    version="0.5.0"
)


@app.get("/")
def home():
    return {"message": "AutoPilot AI API is running", "status": "success"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }



@app.post("/quotes")
def create_quote(request: QuoteRequest):
    try:
        calculation = calculate_quote(request.items)
        quote_uuid = uuid4()
        customer_name = request.customer_name

        with get_connection() as conn:
            with conn.cursor() as cur:
                customer_id = None

                if request.customer_email:
                    cur.execute(
                        """
                        SELECT id, name FROM customers
                        WHERE LOWER(email) = LOWER(%s)
                        LIMIT 1;
                        """,
                        (request.customer_email,)
                    )
                    customer = cur.fetchone()

                    if customer:
                        customer_id = customer[0]
                        customer_name = request.customer_name or customer[1]

                        if request.customer_name:
                            cur.execute(
                                """
                                UPDATE customers
                                SET name = %s
                                WHERE id = %s;
                                """,
                                (customer_name, customer_id)
                            )

                if customer_id is None:
                    cur.execute(
                        """
                        INSERT INTO customers (name, email, phone)
                        VALUES (%s, %s, %s)
                        RETURNING id, name;
                        """,
                        (
                            request.customer_name,
                            request.customer_email,
                            request.customer_phone
                        )
                    )
                    customer = cur.fetchone()
                    customer_id = customer[0]
                    customer_name = customer[1]

                cur.execute(
                    """
                    INSERT INTO quotations
                        (quote_id, customer_id, status, total, currency)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        str(quote_uuid),
                        customer_id,
                        "calculated",
                        calculation["total"],
                        calculation["currency"]
                    )
                )
                quotation_id = cur.fetchone()[0]

                for item in calculation["items"]:
                    cur.execute(
                        """
                        SELECT id FROM products
                        WHERE LOWER(name) = LOWER(%s);
                        """,
                        (item["product_name"],)
                    )
                    product = cur.fetchone()

                    cur.execute(
                        """
                        INSERT INTO quotation_items
                            (quotation_id, product_id, product_name,
                             quantity, unit_price, subtotal)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            quotation_id,
                            product[0] if product else None,
                            item["product_name"],
                            item["quantity"],
                            item["unit_price"],
                            item["subtotal"]
                        )
                    )

        quote_data = {
            "quote_id": str(quote_uuid),
            "status": "calculated",
            "customer": customer_name,
            "items": calculation["items"],
            "total": calculation["total"],
            "currency": calculation["currency"],
        }

        pdf_path = generate_quote_pdf(quote_data)
        log_notification(
    quote_id=str(quote_uuid),
    recipient=request.customer_email,
    notification_type="quote_created",
    subject="Quotation created",
    message=f"Quotation created for {customer_name}. Total: {calculation['total']} MAD",
    status="created"
)
        return {
            "quote_id": str(quote_uuid),
            "status": "calculated",
            "customer": customer_name,
            "source": request.source,
            "items": calculation["items"],
            "total": calculation["total"],
            "currency": calculation["currency"],
            "pdf_path": pdf_path,
            "message": "Quotation calculated, saved, and PDF generated successfully"
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/quotes/from-message")
def create_quote_from_message(request: QuoteMessageRequest):
    try:
        ai_data = extract_quote_information(request.message)

        customer_name = ai_data.get("customer_name")
        items = ai_data.get("items")

        if not customer_name:
            raise HTTPException(
                status_code=400,
                detail="Customer name was not found in the message."
            )

        if not items:
            raise HTTPException(
                status_code=400,
                detail="No products were found in the message."
            )

        quote_request = QuoteRequest(
            customer_name=customer_name,
            customer_email=request.customer_email,
            customer_phone=request.customer_phone,
            source=request.source,
            items=items,
            message=request.message
        )

        return create_quote(quote_request)

    except requests.RequestException as error:
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(error)}"
        )


@app.post("/quotes/{quote_id}/approve")

def approve_quote(quote_id: str):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                # 1. Vérifier le devis et verrouiller son enregistrement
                cur.execute(
                    """
                    SELECT id, status
                    FROM quotations
                    WHERE quote_id = %s
                    FOR UPDATE;
                    """,
                    (quote_id,)
                )

                quotation = cur.fetchone()

                if quotation is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Quotation not found."
                    )

                quotation_id, status = quotation

                # 2. Empêcher une double approbation
                if status != "calculated":
                    raise HTTPException(
                        status_code=409,
                        detail=f"Quotation cannot be approved. Current status: {status}"
                    )

                # 3. Récupérer les produits du devis
                cur.execute(
                    """
                    SELECT product_id, product_name, quantity
                    FROM quotation_items
                    WHERE quotation_id = %s;
                    """,
                    (quotation_id,)
                )

                items = cur.fetchall()

                if not items:
                    raise HTTPException(
                        status_code=400,
                        detail="Quotation contains no items."
                    )

                # 4. Vérifier et déduire le stock
                for product_id, product_name, quantity in items:
                    cur.execute(
                        """
                        UPDATE products
                        SET stock = stock - %s
                        WHERE id = %s AND stock >= %s
                        RETURNING stock;
                        """,
                        (quantity, product_id, quantity)
                    )

                    updated_product = cur.fetchone()

                    if updated_product is None:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Insufficient stock for {product_name}."
                        )

                # 5. Enregistrer automatiquement les ventes
                # dans sales_history
                for product_id, product_name, quantity in items:

                    # Vérifier si une vente existe déjà aujourd'hui
                    cur.execute(
                        """
                        UPDATE sales_history
                        SET target = target + %s
                        WHERE item_id = %s
                        AND timestamp = CURRENT_DATE;
                        """,
                        (quantity, product_name)
                    )

                    # Sinon, créer un nouvel enregistrement
                    if cur.rowcount == 0:
                        cur.execute(
                            """
                            INSERT INTO sales_history
                            (item_id, timestamp, target)
                            VALUES (%s, CURRENT_DATE, %s);
                            """,
                            (product_name, quantity)
                        )

                # 6. Mettre à jour le statut du devis
                cur.execute(
                    """
                    UPDATE quotations
                    SET status = 'approved'
                    WHERE id = %s;
                    """,
                    (quotation_id,)
                )

                # 7. Récupérer les informations du devis
                cur.execute(
                    """
                    SELECT
                        q.quote_id::text,
                        c.name,
                        c.email,
                        q.status,
                        q.total,
                        q.currency
                    FROM quotations q
                    JOIN customers c ON q.customer_id = c.id
                    WHERE q.id = %s;
                    """,
                    (quotation_id,)
                )

                quote = cur.fetchone()

                # 8. Récupérer les détails des produits
                cur.execute(
                    """
                    SELECT product_name, quantity, unit_price, subtotal
                    FROM quotation_items
                    WHERE quotation_id = %s
                    ORDER BY id;
                    """,
                    (quotation_id,)
                )

                quote_items = cur.fetchall()

                quote_data = {
                    "quote_id": quote[0],
                    "customer": quote[1],
                    "customer_email": quote[2],
                    "status": quote[3],
                    "total": quote[4],
                    "currency": quote[5],
                    "items": [
                        {
                            "product_name": item[0],
                            "quantity": item[1],
                            "unit_price": item[2],
                            "subtotal": item[3]
                        }
                        for item in quote_items
                    ]
                }

        # 9. Régénérer le PDF après validation
        pdf_path = generate_quote_pdf(quote_data)

        return {
            "quote_id": quote_id,
            "status": "approved",
            "pdf_path": pdf_path,
            "message": "Quotation approved, stock updated, sales history updated and PDF regenerated successfully."
        }

    except HTTPException:
        raise

@app.post("/quotes/{quote_id}/reject")
def reject_quote(quote_id: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
    """
    SELECT q.id, q.status, c.email
    FROM quotations q
    JOIN customers c ON q.customer_id = c.id
    WHERE q.quote_id = %s
    FOR UPDATE OF q;
    """,
    (quote_id,)
)
            

            quotation = cur.fetchone()

            if quotation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Quotation not found."
                )

            quotation_id, status, customer_email = quotation

            if status != "calculated":
                raise HTTPException(
                    status_code=409,
                    detail=f"Quotation cannot be rejected. Current status: {status}"
                )

            cur.execute(
                """
                UPDATE quotations
                SET status = 'rejected'
                WHERE id = %s;
                """,
                (quotation_id,)
            )
    log_notification(
    quote_id=quote_id,
    recipient=customer_email,
    notification_type="quote_rejected",
    subject="Quotation rejected",
    message=f"Your quotation {quote_id} has been rejected.",
    status="rejected"
)
    
    return {
        "quote_id": quote_id,
        "status": "rejected",
        "message": "Quotation rejected successfully. Stock unchanged."
    }
