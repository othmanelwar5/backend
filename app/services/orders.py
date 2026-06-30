from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer, Order, OrderItem, OrderStatus, Product
from app.schemas.order import OrderCreateIn
from app.services.phone import normalize_phone

PRICE_BY_QUANTITY = {1: "price_1", 2: "price_2", 3: "price_3"}


def _generate_order_number(db: Session) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"mizan{today}"
    count = db.scalar(
        select(func.count()).select_from(Order).where(Order.order_number.like(f"{prefix}%"))
    )
    return f"{prefix}{(count or 0) + 1:04d}"


def _get_or_create_customer(db: Session, name: str, phone_e164: str) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.phone == phone_e164))
    now = datetime.now(timezone.utc)

    if customer is None:
        customer = Customer(
            name=name,
            phone=phone_e164,
            total_orders=0,
            first_order_date=None,
            last_order_date=None,
        )
        db.add(customer)
        db.flush()

    return customer


def _resolve_line_items(db: Session, payload: OrderCreateIn) -> tuple[list[dict], int]:
    lines: list[dict] = []
    computed_subtotal = 0

    for item in payload.items:
        print("[ORDER-DEBUG] step-14 resolving product", item.model_dump())
        product = db.scalar(select(Product).where(Product.slug == item.product_slug, Product.active.is_(True)))
        if product is None:
            print("[ORDER-DEBUG] stop-8 invalid product", {"slug": item.product_slug})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_product", "slug": item.product_slug},
            )

        if item.quantity not in PRICE_BY_QUANTITY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_quantity", "slug": item.product_slug},
            )

        offer_price = getattr(product, PRICE_BY_QUANTITY[item.quantity])
        # price_1/price_2/price_3 are bundle offer totals, not per-unit prices.
        unit_price = offer_price
        total_price = offer_price
        computed_subtotal += total_price
        print(
            "[ORDER-DEBUG] step-15 line priced",
            {
                "slug": item.product_slug,
                "quantity": item.quantity,
                "offer_price": offer_price,
                "line_total": total_price,
                "running_subtotal": computed_subtotal,
            },
        )

        lines.append(
            {
                "product": product,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "total_price": total_price,
            }
        )

    if computed_subtotal != payload.subtotal or computed_subtotal != payload.total:
        print(
            "[ORDER-DEBUG] stop-9 total mismatch before insert",
            {
                "computed_subtotal": computed_subtotal,
                "payload_subtotal": payload.subtotal,
                "payload_total": payload.total,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "total_mismatch",
                "expected_subtotal": computed_subtotal,
                "expected_total": computed_subtotal,
            },
        )

    return lines, computed_subtotal


def create_order(db: Session, payload: OrderCreateIn) -> Order:
    print("[ORDER-DEBUG] step-13 order service started")
    try:
        phone_e164 = normalize_phone(payload.phone)
    except ValueError as exc:
        print("[ORDER-DEBUG] stop-6 phone normalization failed", {"phone": payload.phone})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc)},
        ) from exc

    print("[ORDER-DEBUG] step-13a phone normalized", {"phone_e164": phone_e164})
    lines, subtotal = _resolve_line_items(db, payload)
    customer = _get_or_create_customer(db, payload.customer_name, phone_e164)
    now = datetime.now(timezone.utc)

    order = Order(
        order_number=_generate_order_number(db),
        customer_id=customer.id,
        customer_name=payload.customer_name,
        phone=phone_e164,
        city=payload.city,
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        total=subtotal,
    )
    db.add(order)
    print("[ORDER-DEBUG] step-16 order added, flushing")
    db.flush()
    print("[ORDER-DEBUG] step-16a order flushed", {"order_id": str(order.id), "order_number": order.order_number})

    for line in lines:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=line["product"].id,
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                total_price=line["total_price"],
            )
        )

    customer.total_orders += 1
    customer.name = payload.customer_name
    customer.last_order_date = now
    if customer.first_order_date is None:
        customer.first_order_date = now

    print("[ORDER-DEBUG] step-17 committing transaction")
    db.commit()
    print("[ORDER-DEBUG] step-17a transaction committed")
    db.refresh(order)
    return order


def list_orders(db: Session, *, limit: int = 50, offset: int = 0) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def get_order(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
