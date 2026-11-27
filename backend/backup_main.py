
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from uuid import uuid4

from models import QuoteRequest
from services import calculate_quote

app = FastAPI(
    title="AutoPilot AI",
    description="Intelligent automation of commercial processes",
    version="0.3.0"
)


@app.get("/")
def home():
    return {
        "message": "AutoPilot AI API is running",
        "status": "success"
    }


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
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "quote_id": str(uuid4()),
        "status": "calculated",
        "customer": request.customer_name,
        "source": request.source,
        "items": calculation["items"],
        "total": calculation["total"],
        "currency": calculation["currency"],
        "message": "Quotation calculated successfully"
    }
