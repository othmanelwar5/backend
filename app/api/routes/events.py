from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.core.config import settings
from app.db.session import get_db
from app.models import AnalyticsEvent
from app.schemas.analytics import AnalyticsEventIn, AnalyticsEventOut
from app.services.geocheck import check_ip

router = APIRouter(prefix="/events", tags=["events"])

BOT_KEYWORDS = ("bot", "crawler", "spider", "headless", "phantom", "selenium")


@router.post("", response_model=AnalyticsEventOut, status_code=status.HTTP_201_CREATED)
async def track_event(
    body: AnalyticsEventIn,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    user_agent = body.user_agent or request.headers.get("User-Agent") or ""
    bot_score = score_bot(user_agent)
    geo = await check_ip(client_ip)
    is_bot = bot_score > 0
    valid_country = bool(geo.country_iso and geo.country_iso in settings.GEO_ALLOWED_COUNTRIES)
    valid_for_metrics = geo.allowed and valid_country and not is_bot

    event = AnalyticsEvent(
        event_name=body.event_name,
        session_id=body.session_id,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
        path=body.path,
        url=body.url,
        referrer=body.referrer,
        user_agent=user_agent,
        product_slug=body.product_slug or body.properties.get("product_slug"),
        order_number=body.order_number or body.properties.get("order_number"),
        properties=body.properties,
        ip_address=client_ip,
        country_code=geo.country_iso,
        is_vpn=geo.is_vpn,
        is_proxy=geo.is_proxy,
        is_tor=geo.is_tor,
        is_hosting=geo.is_hosting,
        is_bot=is_bot,
        bot_score=bot_score,
        risk_score=geo.risk_score,
        vpn_provider=geo.provider,
        vpn_provider_payload=geo.provider_payload or {},
        valid_for_metrics=valid_for_metrics,
        rejected_reason=None if valid_for_metrics else rejected_reason(geo.reason, valid_country, is_bot),
    )
    db.add(event)
    db.commit()

    return AnalyticsEventOut(valid_for_metrics=valid_for_metrics)


def score_bot(user_agent: str) -> int:
    normalized = user_agent.lower()
    return sum(1 for keyword in BOT_KEYWORDS if keyword in normalized)


def rejected_reason(geo_reason: str | None, valid_country: bool, is_bot: bool) -> str:
    if is_bot:
        return "bot_detected"
    if not valid_country:
        return geo_reason or "country_not_verified"
    return geo_reason or "not_valid_for_metrics"
