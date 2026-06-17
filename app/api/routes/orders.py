from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, verify_order_geo
from app.db.session import get_db
from app.schemas.order import OrderCreateIn, OrderCreateOut, OrderOut
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreateOut, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreateIn, request: Request, db: Session = Depends(get_db)):
    print(
        "[ORDER-DEBUG] step-10 backend route received request",
        {
            "customer_name": body.customer_name,
            "phone": body.phone,
            "city": body.city,
            "subtotal": body.subtotal,
            "total": body.total,
            "items": [item.model_dump() for item in body.items],
        },
    )
    client_ip = get_client_ip(request)
    print("[ORDER-DEBUG] step-11 client IP resolved", {"client_ip": client_ip})
    await verify_order_geo(ip=client_ip, phone=body.phone)
    print("[ORDER-DEBUG] step-12 geo check passed")

    order = order_service.create_order(db, body)
    print(
        "[ORDER-DEBUG] step-18 route returning created order",
        {"order_number": order.order_number, "order_id": str(order.id)},
    )
    return OrderCreateOut(order_number=order.order_number, order_id=order.id)


@router.get("", response_model=list[OrderOut])
def list_orders(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return order_service.list_orders(db, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "order_not_found"})
    return order
