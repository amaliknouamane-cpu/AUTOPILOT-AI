from typing import Literal

from pydantic import BaseModel, Field


class QuoteItem(BaseModel):
    product_name: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class QuoteRequest(BaseModel):
    customer_name: str = Field(min_length=1)
    customer_email: str | None = None
    customer_phone: str | None = None
    source: Literal["gmail", "whatsapp", "manual", "client_portal"]
    items: list[QuoteItem] = Field(min_length=1)
    message: str | None = None

class QuoteMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    customer_email: str | None = None
    customer_phone: str | None = None
    source: Literal["gmail", "manual"] = "manual"
