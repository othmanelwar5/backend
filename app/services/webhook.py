from __future__ import annotations

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import Order, OrderItem, WebhookLog
from app.services.phone import phone_to_sheet_digits

logger = logging.getLogger(__name__)

RIYADH_TZ = ZoneInfo("Asia/Riyadh")


def format_sheet_date(created_at: datetime) -> str:
    local = created_at.astimezone(RIYADH_TZ)
    return local.strftime("%d/%m/%Y")


def build_sheet_payload(order: Order) -> dict[str, str]:
    items = sorted(order.items, key=lambda row: row.created_at)
    product_names: list[str] = []
    skus: list[str] = []
    quantities: list[str] = []

    for item in items:
        product = item.product
        product_names.append(product.name_ar if product else "")
        skus.append(product.sku if product and product.sku else "")
        quantities.append(str(item.quantity))

    return {
        "date": format_sheet_date(order.created_at),
        "order_id": order.order_number,
        "country": "KSA",
        "name": order.customer_name,
        "phone": phone_to_sheet_digits(order.phone),
        "product": "/".join(product_names),
        "sku": "/".join(skus),
        "quantity": "/".join(quantities),
        "total": str(order.total),
        "currency": "SAR",
        "status": "",
    }


def send_order_to_sheet(db: Session, order_id: uuid.UUID) -> bool:
    webhook_url = settings.ORDER_WEBHOOK_URL.strip()
    if not webhook_url:
        logger.info("ORDER_WEBHOOK_URL not configured; skipping sheet webhook for %s", order_id)
        return False

    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(Order.id == order_id)
    )
    if order is None:
        logger.warning("Order %s not found for webhook dispatch", order_id)
        return False

    payload = build_sheet_payload(order)
    response_data: dict | None = None
    success = False

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.post(webhook_url, json=payload)
            success = response.is_success
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"status_code": response.status_code, "body": response.text[:500]}
    except httpx.HTTPError as exc:
        logger.exception("Sheet webhook request failed for order %s", order.order_number)
        response_data = {"error": str(exc)}

    db.add(
        WebhookLog(
            payload=payload,
            response=response_data,
            success=success,
        )
    )
    db.commit()

    if success:
        logger.info("Sheet webhook delivered for order %s", order.order_number)
    else:
        logger.warning("Sheet webhook failed for order %s: %s", order.order_number, response_data)

    return success


def dispatch_order_webhook(order_id: uuid.UUID) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        send_order_to_sheet(db, order_id)
    except Exception:
        logger.exception("Unexpected error dispatching sheet webhook for %s", order_id)
        db.rollback()
    finally:
        db.close()
