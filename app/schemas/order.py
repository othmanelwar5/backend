from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemIn(BaseModel):
    product_slug: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., ge=1, le=3)


class OrderCreateIn(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., pattern=r"^(\+966|966|05|5)\d{8}$")
    city: str = Field(..., min_length=2, max_length=100)
    items: list[OrderItemIn] = Field(..., min_length=1)
    subtotal: int = Field(..., ge=0)
    total: int = Field(..., ge=0)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: int
    total_price: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    customer_name: str
    phone: str
    city: str
    status: str
    subtotal: int
    total: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)


class OrderCreateOut(BaseModel):
    success: bool = True
    order_number: str
    order_id: uuid.UUID
    message_ar: str = "تم استلام طلبك بنجاح"


class HealthOut(BaseModel):
    ok: bool
    database: str
    tables: list[str]
