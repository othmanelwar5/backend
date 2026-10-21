from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ─── Auth probe ──────────────────────────────────────────────────────────────

@router.get("/session")
def admin_session(admin_username: str = Depends(require_admin)):
    return {"ok": True, "username": admin_username}


# ─── Analytics health diagnostic ─────────────────────────────────────────────

@router.get("/analytics/health")
def analytics_health(db: Session = Depends(get_db)):
    """
    Diagnostic endpoint — shows why dashboard metrics may be zero.
    Inspects the analytics_events table and MaxMind configuration.
    """
    from app.core.config import settings as cfg

    # Total event counts
    totals = db.execute(
        text(
            """
            SELECT
                COUNT(*)::int                                                              AS total_events,
                COUNT(*) FILTER (WHERE valid_for_metrics)::int                            AS valid_events,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics)::int                        AS invalid_events,
                MIN(occurred_at)                                                           AS earliest_event,
                MAX(occurred_at)                                                           AS latest_event
            FROM analytics_events
            """
        )
    ).mappings().one()

    # Breakdown by rejected_reason
    reasons = db.execute(
        text(
            """
            SELECT
                COALESCE(rejected_reason, 'none (valid)') AS reason,
                COUNT(*)::int                              AS count
            FROM analytics_events
            GROUP BY rejected_reason
            ORDER BY count DESC
            LIMIT 20
            """
        )
    ).mappings().all()

    # Breakdown by event_name (valid only)
    event_names = db.execute(
        text(
            """
            SELECT
                event_name,
                COUNT(*) FILTER (WHERE valid_for_metrics)::int     AS valid,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics)::int AS invalid
            FROM analytics_events
            GROUP BY event_name
            ORDER BY (COUNT(*) FILTER (WHERE valid_for_metrics)) DESC
            LIMIT 15
            """
        )
    ).mappings().all()

    maxmind_configured = bool(cfg.MAXMIND_ACCOUNT_ID and cfg.MAXMIND_LICENSE_KEY)
    vpn_provider_configured = bool(cfg.VPN_DETECTION_API_URL and cfg.VPN_DETECTION_API_KEY)

    return {
        "analytics_events": {
            "total":          totals["total_events"],
            "valid":          totals["valid_events"],
            "invalid":        totals["invalid_events"],
            "earliest":       totals["earliest_event"].isoformat() if totals["earliest_event"] else None,
            "latest":         totals["latest_event"].isoformat()   if totals["latest_event"]   else None,
        },
        "rejected_reasons":  [dict(r) for r in reasons],
        "by_event_name":     [dict(e) for e in event_names],
        "geo_config": {
            "maxmind_enabled":          cfg.MAXMIND_ENABLED,
            "maxmind_configured":       maxmind_configured,
            "vpn_provider_configured":  vpn_provider_configured,
            "allowed_countries":        cfg.GEO_ALLOWED_COUNTRIES,
            "block_vpn":                cfg.GEO_BLOCK_VPN,
            "block_high_risk":          cfg.GEO_BLOCK_HIGH_RISK,
        },
        "diagnosis": _analytics_diagnosis(totals, maxmind_configured),
    }


def _analytics_diagnosis(totals: dict, maxmind_configured: bool) -> str:
    total   = totals["total_events"] or 0
    valid   = totals["valid_events"]  or 0
    invalid = totals["invalid_events"] or 0

    if total == 0:
        return (
            "NO_EVENTS — No analytics events recorded yet. "
            "Verify that the frontend is sending events to POST /events "
            "and that CORS is not blocking requests."
        )
    if valid == 0 and invalid > 0:
        if not maxmind_configured:
            return (
                "ALL_INVALID_NO_MAXMIND — MaxMind credentials (MAXMIND_ACCOUNT_ID / "
                "MAXMIND_LICENSE_KEY) are not configured. After the fix in events.py, "
                "new events will be marked valid. Existing events in the DB still have "
                "valid_for_metrics=false — run migrations/003_fix_valid_for_metrics.sql "
                "to retroactively fix historical data."
            )
        return (
            "ALL_INVALID — Events exist but none are valid. "
            "Check rejected_reasons above: likely country_not_ksa (non-SA IP) "
            "or MaxMind is blocking traffic."
        )
    if valid < invalid:
        return (
            f"MOSTLY_INVALID — {valid}/{total} events are valid ({round(valid/total*100)}%). "
            "Normal for a KSA-only store if some traffic is non-SA / VPN."
        )
    return f"OK — {valid}/{total} events are valid ({round(valid/total*100)}%)."


# ─── Dashboard overview ───────────────────────────────────────────────────────

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
                COUNT(*) FILTER (WHERE event_name = 'page_view'       AND valid_for_metrics)::int AS page_views,
                COUNT(*) FILTER (WHERE event_name = 'product_view'    AND valid_for_metrics)::int AS product_views,
                COUNT(*) FILTER (WHERE event_name = 'click'           AND valid_for_metrics)::int AS valid_clicks,
                COUNT(*) FILTER (WHERE event_name = 'checkout_open'   AND valid_for_metrics)::int AS checkout_opens,
                COUNT(DISTINCT session_id) FILTER (WHERE valid_for_metrics)::int                   AS valid_sessions,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND country_code IS DISTINCT FROM 'SA')::int AS rejected_non_ksa,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND (is_vpn OR is_proxy OR is_tor OR is_hosting))::int AS rejected_vpn,
                COUNT(*) FILTER (WHERE NOT valid_for_metrics AND is_bot)::int                      AS rejected_bot
            FROM analytics_events
            WHERE occurred_at >= :start AND occurred_at < :end
            """
        ),
        {"start": start, "end": end},
    ).mappings().one()

    orders        = int(order_metrics["orders"] or 0)
    clicks        = int(traffic_metrics["valid_clicks"] or 0)
    revenue       = int(order_metrics["revenue"] or 0)
    checkout_opens= int(traffic_metrics["checkout_opens"] or 0)

    # Status breakdown
    status_rows = db.execute(
        text(
            """
            SELECT status, COUNT(*)::int AS cnt
            FROM orders
            WHERE created_at >= :start AND created_at < :end
            GROUP BY status
            ORDER BY cnt DESC
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    status_breakdown = {row["status"]: row["cnt"] for row in status_rows}

    page_views     = int(traffic_metrics["page_views"]    or 0)
    product_views  = int(traffic_metrics["product_views"] or 0)
    valid_sessions = int(traffic_metrics["valid_sessions"] or 0)
    rejected_non_ksa = int(traffic_metrics["rejected_non_ksa"] or 0)
    rejected_vpn   = int(traffic_metrics["rejected_vpn"]   or 0)
    rejected_bot   = int(traffic_metrics["rejected_bot"]   or 0)

    # Conversion rate: orders ÷ valid_clicks (undefined → 0)
    conversion_rate = orders / clicks if clicks > 0 else 0
    # Checkout → order rate
    checkout_cvr    = orders / checkout_opens if checkout_opens > 0 else 0

    return {
        "metrics": {
            # traffic (all from analytics_events WHERE valid_for_metrics)
            "page_views":       page_views,
            "product_views":    product_views,
            "valid_clicks":     clicks,
            "checkout_opens":   checkout_opens,
            "valid_sessions":   valid_sessions,
            "rejected_non_ksa": rejected_non_ksa,
            "rejected_vpn":     rejected_vpn,
            "rejected_bot":     rejected_bot,
            # orders (from orders table — independent of analytics_events)
            "orders":           orders,
            "revenue":          revenue,
            "aov":              float(order_metrics["aov"] or 0),
            # computed
            "conversion_rate":  conversion_rate,
            "checkout_cvr":     checkout_cvr,
        },
        "series":           daily_series(db, start, end),
        "products":         product_breakdown(db, start, end),
        "funnel": {
            "page_views":    page_views,
            "product_views": product_views,
            "valid_clicks":  clicks,
            "checkout_opens":checkout_opens,
            "orders":        orders,
        },
        "status_breakdown": status_breakdown,
    }


# Keep /metrics as alias for backward compat
@router.get("/metrics")
def metrics(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    return dashboard(from_date=from_date, to_date=to_date, db=db)


# ─── Orders list ─────────────────────────────────────────────────────────────

@router.get("/orders")
def admin_orders(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    start, end = date_window(from_date, to_date)
    where = ["o.created_at >= :start", "o.created_at < :end"]
    params: dict[str, object] = {"start": start, "end": end, "limit": limit}

    if status_filter:
        where.append("o.status = :status")
        params["status"] = status_filter

    if search:
        where.append(
            "(o.order_number ILIKE :search OR o.customer_name ILIKE :search OR o.phone ILIKE :search)"
        )
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
                -- optional columns that may or may not exist in the DB
                (o.source)::text              AS source,
                (o.utm_campaign)::text        AS utm_campaign,
                (o.utm_source)::text          AS utm_source,
                (o.utm_medium)::text          AS utm_medium,
                (o.admin_note)::text          AS admin_note,
                (o.ip_country)::text          AS ip_country,
                (o.traffic_validated)::boolean AS traffic_validated,
                (o.vpn_detected)::boolean     AS vpn_detected,
                COALESCE(json_agg(
                    json_build_object(
                        'id',           oi.id,
                        'product_id',   oi.product_id,
                        'product_slug', p.slug,
                        'sku',          p.sku,
                        'name',         COALESCE(p.name_en, p.name_ar),
                        'quantity',     oi.quantity,
                        'unit_price',   oi.unit_price,
                        'price',        oi.total_price,
                        'total',        oi.total_price
                    )
                ) FILTER (WHERE oi.id IS NOT NULL), '[]'::json) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products    p  ON p.id = oi.product_id
            WHERE {" AND ".join(where)}
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    return {"orders": [serialize_order(row) for row in rows]}


# ─── Orders export CSV ────────────────────────────────────────────────────────

@router.get("/orders/export.csv")
def export_orders_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    start, end = date_window(from_date, to_date)
    where = ["o.created_at >= :start", "o.created_at < :end"]
    params: dict[str, object] = {"start": start, "end": end}

    if status_filter:
        where.append("o.status = :status")
        params["status"] = status_filter

    rows = db.execute(
        text(
            f"""
            SELECT
                o.order_number,
                o.customer_name,
                o.phone,
                o.city,
                o.status,
                o.subtotal,
                o.total,
                o.created_at,
                (o.source)::text       AS source,
                (o.utm_campaign)::text AS utm_campaign,
                (o.admin_note)::text   AS admin_note,
                (o.ip_country)::text   AS ip_country,
                string_agg(
                    COALESCE(p.name_en, p.name_ar, '') || ' x' || oi.quantity::text,
                    ' | '
                ) AS items_summary
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products    p  ON p.id = oi.product_id
            WHERE {" AND ".join(where)}
            GROUP BY o.id
            ORDER BY o.created_at DESC
            """
        ),
        params,
    ).mappings().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order #", "Customer", "Phone", "City", "Status",
        "Subtotal (SAR)", "Total (SAR)", "Date", "Source",
        "Campaign", "Admin Note", "Country", "Items",
    ])
    for row in rows:
        writer.writerow([
            row["order_number"],
            row["customer_name"],
            row["phone"],
            row["city"],
            row["status"],
            row["subtotal"],
            row["total"],
            row["created_at"].strftime("%Y-%m-%d %H:%M") if row["created_at"] else "",
            row["source"] or "",
            row["utm_campaign"] or "",
            row["admin_note"] or "",
            row["ip_country"] or "",
            row["items_summary"] or "",
        ])

    filename = f"orders_{from_date}_{to_date}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Single order detail ──────────────────────────────────────────────────────

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
                (o.source)::text              AS source,
                (o.utm_campaign)::text        AS utm_campaign,
                (o.utm_source)::text          AS utm_source,
                (o.utm_medium)::text          AS utm_medium,
                (o.admin_note)::text          AS admin_note,
                (o.ip_country)::text          AS ip_country,
                (o.traffic_validated)::boolean AS traffic_validated,
                (o.vpn_detected)::boolean     AS vpn_detected,
                COALESCE(json_agg(
                    json_build_object(
                        'id',           oi.id,
                        'product_id',   oi.product_id,
                        'product_slug', p.slug,
                        'sku',          p.sku,
                        'name',         COALESCE(p.name_en, p.name_ar),
                        'quantity',     oi.quantity,
                        'unit_price',   oi.unit_price,
                        'price',        oi.total_price,
                        'total',        oi.total_price
                    )
                ) FILTER (WHERE oi.id IS NOT NULL), '[]'::json) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products    p  ON p.id = oi.product_id
            WHERE {where}
            GROUP BY o.id
            """
        ),
        params,
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "order_not_found"},
        )

    return {"order": serialize_order(row)}


# ─── Update order status ──────────────────────────────────────────────────────

VALID_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled", "returned"}


class StatusUpdateBody(BaseModel):
    status: str
    note: Optional[str] = None


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: str,
    body: StatusUpdateBody,
    db: Session = Depends(get_db),
    admin_username: str = Depends(require_admin),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_status", "allowed": sorted(VALID_STATUSES)},
        )

    # Resolve order
    where = "id = :oid"
    params: dict[str, object] = {"oid": order_id, "new_status": body.status}
    try:
        params["oid"] = uuid.UUID(order_id)
    except ValueError:
        where = "order_number = :oid"

    result = db.execute(
        text(
            f"""
            UPDATE orders
            SET status = :new_status,
                updated_at = NOW()
            WHERE {where}
            RETURNING id, order_number, status, updated_at
            """
        ),
        params,
    ).mappings().first()

    if result is None:
        raise HTTPException(status_code=404, detail={"error": "order_not_found"})

    # Log to history table if it exists
    try:
        log_params: dict[str, object] = {
            "order_id":   str(result["id"]),
            "order_num":  result["order_number"],
            "new_status": body.status,
            "note":       body.note or "",
            "by":         admin_username,
        }
        db.execute(
            text(
                """
                INSERT INTO order_status_history
                    (order_id, order_number, new_status, note, changed_by)
                VALUES
                    (:order_id::uuid, :order_num, :new_status, :note, :by)
                """
            ),
            log_params,
        )
    except Exception:
        pass  # history table may not exist yet – don't fail the update

    db.commit()

    return {
        "ok": True,
        "order_number": result["order_number"],
        "status": result["status"],
        "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
    }


# ─── Update admin note ────────────────────────────────────────────────────────

class NoteBody(BaseModel):
    note: str


@router.patch("/orders/{order_id}/note")
def update_order_note(
    order_id: str,
    body: NoteBody,
    db: Session = Depends(get_db),
    admin_username: str = Depends(require_admin),
):
    where = "id = :oid"
    params: dict[str, object] = {"oid": order_id, "note": body.note}
    try:
        params["oid"] = uuid.UUID(order_id)
    except ValueError:
        where = "order_number = :oid"

    result = db.execute(
        text(f"UPDATE orders SET admin_note = :note, updated_at = NOW() WHERE {where} RETURNING id, order_number"),
        params,
    ).mappings().first()

    if result is None:
        raise HTTPException(status_code=404, detail={"error": "order_not_found"})

    db.commit()
    return {"ok": True, "order_number": result["order_number"]}


# ─── Helpers ──────────────────────────────────────────────────────────────────

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
                SELECT
                    occurred_at::date AS day,
                    COUNT(*) FILTER (WHERE event_name = 'page_view'     AND valid_for_metrics)::int AS page_views,
                    COUNT(*) FILTER (WHERE event_name = 'click'         AND valid_for_metrics)::int AS valid_clicks,
                    COUNT(*) FILTER (WHERE event_name = 'checkout_open' AND valid_for_metrics)::int AS checkout_opens
                FROM analytics_events
                WHERE occurred_at >= :start AND occurred_at < :end
                GROUP BY occurred_at::date
            ),
            order_daily AS (
                SELECT
                    created_at::date AS day,
                    COUNT(*)::int    AS orders,
                    COALESCE(SUM(total), 0)::int AS revenue
                FROM orders
                WHERE created_at >= :start AND created_at < :end
                GROUP BY created_at::date
            )
            SELECT
                days.day::text AS date,
                COALESCE(traffic.page_views,    0)::int AS page_views,
                COALESCE(traffic.valid_clicks,  0)::int AS valid_clicks,
                COALESCE(traffic.checkout_opens,0)::int AS checkout_opens,
                COALESCE(order_daily.orders,    0)::int AS orders,
                COALESCE(order_daily.revenue,   0)::int AS revenue
            FROM days
            LEFT JOIN traffic     ON traffic.day     = days.day
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
                    COUNT(*) FILTER (WHERE event_name = 'click'      AND valid_for_metrics)::int AS valid_clicks,
                    COUNT(*) FILTER (WHERE event_name = 'product_view' AND valid_for_metrics)::int AS product_views
                FROM analytics_events
                WHERE occurred_at >= :start AND occurred_at < :end AND product_slug IS NOT NULL
                GROUP BY product_slug
            ),
            ordered AS (
                SELECT
                    p.slug          AS product_slug,
                    COALESCE(p.name_en, p.name_ar) AS name,
                    p.sku,
                    COUNT(DISTINCT o.id)::int                                                   AS orders,
                    COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN oi.total_price ELSE 0 END), 0)::int AS revenue
                FROM products p
                LEFT JOIN order_items oi ON oi.product_id = p.id
                LEFT JOIN orders      o  ON o.id = oi.order_id
                    AND o.created_at >= :start AND o.created_at < :end
                GROUP BY p.slug, p.name_en, p.name_ar, p.sku
            )
            SELECT
                ordered.product_slug,
                ordered.name,
                ordered.sku,
                COALESCE(traffic.valid_clicks,  0)::int AS valid_clicks,
                COALESCE(traffic.product_views, 0)::int AS product_views,
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
    end   = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _safe_bool(value) -> bool | None:
    if value is None:
        return None
    return bool(value)


def serialize_order(row) -> dict:
    return {
        "id":               str(row["id"]),
        "order_number":     row["order_number"],
        "customer_name":    row["customer_name"],
        "phone":            row["phone"],
        "city":             row["city"],
        "status":           row["status"],
        "subtotal":         row["subtotal"],
        "total":            row["total"],
        "currency":         "SAR",
        "created_at":       row["created_at"].isoformat()  if row["created_at"]  else None,
        "updated_at":       row["updated_at"].isoformat()  if row.get("updated_at") else None,
        "source":           row.get("source")       or "storefront",
        "utm_campaign":     row.get("utm_campaign") or "",
        "utm_source":       row.get("utm_source")   or "",
        "utm_medium":       row.get("utm_medium")   or "",
        "admin_note":       row.get("admin_note")   or "",
        "ip_country":       row.get("ip_country")   or "SA",
        "traffic_validated":_safe_bool(row.get("traffic_validated")),
        "vpn_detected":     _safe_bool(row.get("vpn_detected")),
        "items":            row["items"] or [],
    }
