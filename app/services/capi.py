from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Order, OrderItem, PixelEvent

logger = logging.getLogger(__name__)

META_API_VERSION = "v21.0"
TIKTOK_EVENTS_URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_phone_for_hash(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("966"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 9 and digits.startswith("5"):
        return "966" + digits
    return digits


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0].lower(), ""
    return parts[0].lower(), parts[-1].lower()


def _contents_from_order(order: Order) -> list[dict]:
    contents: list[dict] = []
    for item in order.items:
        product = item.product
        content_id = product.sku if product else str(item.product_id)
        contents.append(
            {
                "id": content_id,
                "quantity": item.quantity,
                "item_price": item.total_price,
            }
        )
    return contents


def _num_items(order: Order) -> int:
    return sum(item.quantity for item in order.items)


async def _send_meta_purchase(
    *,
    order: Order,
    tracking: dict,
    client_ip: str,
    user_agent: str,
) -> bool:
    if not settings.META_PIXEL_ID or not settings.META_ACCESS_TOKEN:
        return False

    first_name, last_name = _split_name(order.customer_name)
    phone_hash = _sha256(_normalize_phone_for_hash(order.phone))
    contents = _contents_from_order(order)

    user_data: dict = {
        "ph": [phone_hash],
        "client_ip_address": client_ip,
        "client_user_agent": user_agent or tracking.get("user_agent") or "",
    }
    if first_name:
        user_data["fn"] = [_sha256(first_name)]
    if last_name:
        user_data["ln"] = [_sha256(last_name)]
    if tracking.get("fbp"):
        user_data["fbp"] = tracking["fbp"]
    if tracking.get("fbc"):
        user_data["fbc"] = tracking["fbc"]

    payload = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(datetime.now(timezone.utc).timestamp()),
                "event_id": tracking.get("event_id") or order.order_number,
                "event_source_url": tracking.get("page_url") or settings.FRONTEND_ORIGIN,
                "action_source": "website",
                "user_data": user_data,
                "custom_data": {
                    "currency": "SAR",
                    "value": float(order.total),
                    "content_type": "product",
                    "content_ids": [item["id"] for item in contents],
                    "contents": contents,
                    "order_id": order.order_number,
                    "num_items": _num_items(order),
                },
            }
        ],
        "access_token": settings.META_ACCESS_TOKEN,
    }
    if settings.META_TEST_EVENT_CODE:
        payload["test_event_code"] = settings.META_TEST_EVENT_CODE

    url = f"https://graph.facebook.com/{META_API_VERSION}/{settings.META_PIXEL_ID}/events"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        body = response.json()
        logger.info("Meta CAPI Purchase sent for %s: %s", order.order_number, body)
        return bool(body.get("events_received"))


async def _send_tiktok_complete_payment(
    *,
    order: Order,
    tracking: dict,
    client_ip: str,
    user_agent: str,
) -> bool:
    if not settings.TIKTOK_PIXEL_ID or not settings.TIKTOK_ACCESS_TOKEN:
        return False

    phone_hash = _sha256(_normalize_phone_for_hash(order.phone))
    contents = _contents_from_order(order)

    payload = {
        "event_source": "web",
        "event_source_id": settings.TIKTOK_PIXEL_ID,
        "data": [
            {
                "event": "CompletePayment",
                "event_time": int(datetime.now(timezone.utc).timestamp()),
                "event_id": tracking.get("event_id") or order.order_number,
                "user": {
                    "phone": phone_hash,
                    "ip": client_ip,
                    "user_agent": user_agent or tracking.get("user_agent") or "",
                },
                "page": {
                    "url": tracking.get("page_url") or settings.FRONTEND_ORIGIN,
                    "referrer": tracking.get("referrer") or "",
                },
                "properties": {
                    "currency": "SAR",
                    "value": float(order.total),
                    "order_id": order.order_number,
                    "content_type": "product",
                    "contents": [
                        {
                            "content_id": item["id"],
                            "content_type": "product",
                            "quantity": item["quantity"],
                            "price": float(item["item_price"]),
                        }
                        for item in contents
                    ],
                },
            }
        ],
    }

    user = payload["data"][0]["user"]
    if tracking.get("ttclid"):
        user["ttclid"] = tracking["ttclid"]
    if tracking.get("ttp"):
        user["ttp"] = tracking["ttp"]

    headers = {
        "Access-Token": settings.TIKTOK_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }
    if settings.TIKTOK_TEST_EVENT_CODE:
        payload["test_event_code"] = settings.TIKTOK_TEST_EVENT_CODE

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(TIKTOK_EVENTS_URL, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        logger.info("TikTok CAPI CompletePayment sent for %s: %s", order.order_number, body)
        return body.get("code", 1) == 0


async def _send_snap_purchase(
    *,
    order: Order,
    tracking: dict,
    client_ip: str,
    user_agent: str,
) -> bool:
    if not settings.SNAP_PIXEL_ID or not settings.SNAP_ACCESS_TOKEN:
        return False

    phone_hash = _sha256(_normalize_phone_for_hash(order.phone))
    contents = _contents_from_order(order)
    event_id = tracking.get("event_id") or order.order_number

    payload = {
        "data": [
            {
                "event_name": "PURCHASE",
                "event_time": int(datetime.now(timezone.utc).timestamp()),
                "event_id": event_id,
                "action_source": "WEB",
                "event_source_url": tracking.get("page_url") or settings.FRONTEND_ORIGIN,
                "user_data": {
                    "ph": [phone_hash],
                    "client_ip_address": client_ip,
                    "client_user_agent": user_agent or tracking.get("user_agent") or "",
                },
                "custom_data": {
                    "currency": "SAR",
                    "value": str(float(order.total)),
                    "order_id": order.order_number,
                    "content_ids": [item["id"] for item in contents],
                    "num_items": _num_items(order),
                    "contents": [
                        {
                            "id": item["id"],
                            "quantity": str(item["quantity"]),
                            "item_price": str(float(item["item_price"])),
                        }
                        for item in contents
                    ],
                },
            }
        ]
    }

    if tracking.get("sc_click_id"):
        payload["data"][0]["user_data"]["sc_click_id"] = tracking["sc_click_id"]
    if tracking.get("sc_cookie1"):
        payload["data"][0]["user_data"]["sc_cookie1"] = tracking["sc_cookie1"]

    url = f"https://tr.snapchat.com/v3/{settings.SNAP_PIXEL_ID}/events"
    params = {"access_token": settings.SNAP_ACCESS_TOKEN}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, params=params, json=payload)
        response.raise_for_status()
        body = response.json()
        logger.info("Snap CAPI PURCHASE sent for %s: %s", order.order_number, body)
        return response.status_code == 200


def _log_pixel_event(
    db: Session,
    *,
    order_id: uuid.UUID,
    event_name: str,
    platform: str,
    event_id: str | None,
) -> None:
    db.add(
        PixelEvent(
            order_id=order_id,
            event_name=event_name,
            event_id=event_id,
            platform=platform,
        )
    )
    db.commit()


async def dispatch_purchase_capi(
    order_id: uuid.UUID,
    tracking: dict | None,
    client_ip: str,
    user_agent: str,
) -> None:
    if not settings.CAPI_ENABLED:
        logger.info("CAPI disabled; skipping purchase dispatch for %s", order_id)
        return

    tracking = tracking or {}
    db = SessionLocal()
    try:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.id == order_id)
        )
        if order is None:
            logger.warning("CAPI skipped: order %s not found", order_id)
            return

        event_id = tracking.get("event_id") or order.order_number
        results: list[tuple[str, str, bool]] = []

        for platform, sender in (
            ("meta", _send_meta_purchase),
            ("tiktok", _send_tiktok_complete_payment),
            ("snap", _send_snap_purchase),
        ):
            try:
                ok = await sender(
                    order=order,
                    tracking=tracking,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
                if ok:
                    _log_pixel_event(
                        db,
                        order_id=order.id,
                        event_name="Purchase",
                        platform=platform,
                        event_id=event_id,
                    )
                results.append((platform, event_id, ok))
            except Exception:
                logger.exception("CAPI %s Purchase failed for order %s", platform, order.order_number)

        logger.info("CAPI purchase dispatch for %s: %s", order.order_number, results)
    finally:
        db.close()
