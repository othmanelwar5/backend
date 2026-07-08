from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/session")
def admin_session(admin_username: str = Depends(require_admin)):
    return {"ok": True, "username": admin_username}


@router.get("/dashboard")
def dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    start, end = date_window(from_date, to_date)
    order_metrics = db.execute(
        text(
            """
            SELECT
                COUNT(*)::int AS orders,
                COALESCE(SUM(total), 0)::int AS revenue,
                COALESCE(AVG(total), 0)::float AS aov
            FROM orders
            WHERE created_at >= :start AND created_at < :end
            """
        ),
        {"start": start, "end": end},
    ).mappings().one()

    traffic_metrics = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_name = 'page_view' AND valid_for_metrics)::int AS page_views,
                COUNT(*) FILTER (WHERE event_name = 'product_view' AND valid_for_metrics)::int AS product_views,
                COUNT(*) FILTER (WHERE event_name = 'click' AND valid_for_metrics)::int AS valid_clicks,
                COUNT(*) FILTER (WHERE event_name = 'checkout_open' AND valid_for_metrics)::int AS checkout_opens,
                COUNT(DISTINCT session_id) FILTER (WHERE valid_for_metrics)::int AS valid_sessions,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND country_code IS DISTINCT FROM 'SA')::int AS rejected_non_ksa,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND (is_vpn OR is_proxy OR is_tor OR is_hosting))::int AS rejected_vpn,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND is_bot)::int AS rejected_bot
            FROM analytics_events
            WHERE occurred_at >= :start AND occurred_at < :end
            """
        ),
        {"start": start, "end": end},
    ).mappings().one()

    orders = int(order_metrics["orders"] or 0)
    clicks = int(traffic_metrics["valid_clicks"] or 0)
    revenue = int(order_metrics["revenue"] or 0)

    return {
        "metrics": {
            **dict(traffic_metrics),
            "orders": orders,
            "revenue": revenue,
            "aov": float(order_metrics["aov"] or 0),
            "conversion_rate": orders / clicks if clicks else 0,
        },
        "series": daily_series(db, start, end),
        "products": product_breakdown(db, start, end),
        "funnel": {
            "page_views": traffic_metrics["page_views"] or 0,
            "product_views": traffic_metrics["product_views"] or 0,
            "valid_clicks": clicks,
            "checkout_opens": traffic_metrics["checkout_opens"] or 0,
            "orders": orders,
        },
    }


@router.get("/metrics")
def metrics(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    return dashboard(from_date=from_date, to_date=to_date, db=db)


@router.get("/orders")
def admin_orders(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    start, end = date_window(from_date, to_date)
    where = ["o.created_at >= :start", "o.created_at < :end"]
    params: dict[str, object] = {"start": start, "end": end, "limit": limit}

    if status_filter:
        where.append("o.status = :status")
        params["status"] = status_filter

    if search:
        where.append("(o.order_number ILIKE :search OR o.customer_name ILIKE :search OR o.phone ILIKE :search)")
        params["search"] = f"%{search}%"

    rows = db.execute(
        text(
            f"""
            SELECT
                o.id,
                o.order_number,
                o.customer_name,
                o.phone,
                o.city,
                o.status,
                o.subtotal,
                o.total,
                o.created_at,
                o.updated_at,
                COALESCE(json_agg(
                    json_build_object(
                        'id', oi.id,
                        'product_id', oi.product_id,
                        'product_slug', p.slug,
                        'sku', p.sku,
                        'name', COALESCE(p.name_en, p.name_ar),
                        'quantity', oi.quantity,
                        'price', oi.total_price,
                        'unit_price', oi.unit_price,
                        'total', oi.total_price
                    )
                ) FILTER (WHERE oi.id IS NOT NULL), '[]'::json) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE {" AND ".join(where)}
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    return {"orders": [serialize_order(row) for row in rows]}


@router.get("/orders/{order_id}")
def admin_order_detail(order_id: str, db: Session = Depends(get_db)):
    where = "o.id = :order_id"
    params: dict[str, object] = {"order_id": order_id}
    try:
        params["order_uuid"] = uuid.UUID(order_id)
        where = "o.id = :order_uuid"
    except ValueError:
        where = "o.order_number = :order_id"

    row = db.execute(
        text(
            f"""
            SELECT
                o.id,
                o.order_number,
                o.customer_name,
                o.phone,
                o.city,
                o.status,
                o.subtotal,
                o.total,
                o.created_at,
                o.updated_at,
                COALESCE(json_agg(
                    json_build_object(
                        'id', oi.id,
                        'product_id', oi.product_id,
                        'product_slug', p.slug,
                        'sku', p.sku,
                        'name', COALESCE(p.name_en, p.name_ar),
                        'quantity', oi.quantity,
                        'price', oi.total_price,
                        'unit_price', oi.unit_price,
                        'total', oi.total_price
                    )
                ) FILTER (WHERE oi.id IS NOT NULL), '[]'::json) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE {where}
            GROUP BY o.id
            """
        ),
        params,
    ).mappings().first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "order_not_found"})

    return {"order": serialize_order(row)}


def daily_series(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(
        text(
            """
            WITH days AS (
                SELECT generate_series(
                    date_trunc('day', CAST(:start AS timestamptz)),
                    date_trunc('day', (CAST(:end AS timestamptz) - interval '1 day')),
                    interval '1 day'
                )::date AS day
            ),
            traffic AS (
                SELECT occurred_at::date AS day, COUNT(*) FILTER (WHERE event_name = 'click' AND valid_for_metrics)::int AS valid_clicks
                FROM analytics_events
                WHERE occurred_at >= :start AND occurred_at < :end
                GROUP BY occurred_at::date
            ),
            order_daily AS (
                SELECT created_at::date AS day, COUNT(*)::int AS orders, COALESCE(SUM(total), 0)::int AS revenue
                FROM orders
                WHERE created_at >= :start AND created_at < :end
                GROUP BY created_at::date
            )
            SELECT
                days.day::text AS date,
                COALESCE(traffic.valid_clicks, 0)::int AS valid_clicks,
                COALESCE(order_daily.orders, 0)::int AS orders,
                COALESCE(order_daily.revenue, 0)::int AS revenue
            FROM days
            LEFT JOIN traffic ON traffic.day = days.day
            LEFT JOIN order_daily ON order_daily.day = days.day
            ORDER BY days.day
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    return [dict(row) for row in rows]


def product_breakdown(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(
        text(
            """
            WITH traffic AS (
                SELECT
                    product_slug,
                    COUNT(*) FILTER (WHERE event_name = 'click' AND valid_for_metrics)::int AS valid_clicks
                FROM analytics_events
                WHERE occurred_at >= :start AND occurred_at < :end AND product_slug IS NOT NULL
                GROUP BY product_slug
            ),
            ordered AS (
                SELECT
                    p.slug AS product_slug,
                    COALESCE(p.name_en, p.name_ar) AS name,
                    p.sku,
                    COUNT(DISTINCT o.id)::int AS orders,
                    COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN oi.total_price ELSE 0 END), 0)::int AS revenue
                FROM products p
                LEFT JOIN order_items oi ON oi.product_id = p.id
                LEFT JOIN orders o ON o.id = oi.order_id AND o.created_at >= :start AND o.created_at < :end
                GROUP BY p.slug, p.name_en, p.name_ar, p.sku
            )
            SELECT
                ordered.product_slug,
                ordered.name,
                ordered.sku,
                COALESCE(traffic.valid_clicks, 0)::int AS valid_clicks,
                ordered.orders,
                ordered.revenue,
                CASE WHEN COALESCE(traffic.valid_clicks, 0) > 0
                    THEN ordered.orders::float / traffic.valid_clicks
                    ELSE 0
                END AS conversion_rate
            FROM ordered
            LEFT JOIN traffic ON traffic.product_slug = ordered.product_slug
            ORDER BY ordered.revenue DESC, ordered.orders DESC
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    return [dict(row) for row in rows]


def date_window(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def serialize_order(row) -> dict:
    return {
        "id": str(row["id"]),
        "order_number": row["order_number"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "city": row["city"],
        "status": row["status"],
        "subtotal": row["subtotal"],
        "total": row["total"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "items": row["items"] or [],
        "currency": "SAR",
        "source": "storefront",
        "traffic_validated": None,
        "ip_country": None,
        "vpn_detected": None,
    }
