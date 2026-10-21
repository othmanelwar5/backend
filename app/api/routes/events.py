from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.core.config import settings
from app.db.session import get_db
from app.models import AnalyticsEvent
from app.schemas.analytics import AnalyticsEventIn, AnalyticsEventOut
from app.services.geocheck import check_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

BOT_KEYWORDS = ("bot", "crawler", "spider", "headless", "phantom", "selenium")

# ─── Geo skip reasons ──────────────────────────────────────────────────────────
# When geo check is SKIPPED (not actively blocked), we fail open for metrics —
# same behaviour as the order flow. This prevents infra issues (missing MaxMind
# credentials, API timeouts, etc.) from zeroing out all dashboard metrics.
# When MaxMind IS configured and working, real country/VPN data is used instead.
_GEO_SKIP_REASONS: frozenset[str] = frozenset(
    {
        "no_credentials",       # MaxMind creds not set yet
        "maxmind_disabled",     # MAXMIND_ENABLED=false
        "maxmind_api_error",    # MaxMind HTTP error
        "maxmind_timeout",      # MaxMind timed out
        "maxmind_exception",    # unexpected exception in geo client
        "whitelisted_phone",    # phone bypass (orders route only, but guard here too)
    }
)


@router.post("", response_model=AnalyticsEventOut, status_code=status.HTTP_201_CREATED)
async def track_event(
    body: AnalyticsEventIn,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    user_agent = body.user_agent or request.headers.get("User-Agent") or ""
    bot_score = score_bot(user_agent)
    is_bot = bot_score > 0

    geo = await check_ip(client_ip)

    # ── Country validation ──────────────────────────────────────────────────
    # Three distinct situations:
    #   1. Geo check ran and returned a country  → enforce KSA allowlist strictly
    #   2. Geo check was SKIPPED (infra issue)   → fail open (don't zero metrics)
    #   3. Geo check explicitly BLOCKED          → invalid
    geo_skipped    = geo.reason in _GEO_SKIP_REASONS
    geo_conclusive = bool(geo.country_iso)          # MaxMind actually verified country

    if geo_conclusive:
        # Country verified — apply KSA-only rule
        valid_country = geo.country_iso in settings.GEO_ALLOWED_COUNTRIES
    elif geo_skipped:
        # Geo was not performed (credentials missing, API down, etc.) → fail open
        # Log a warning so operators know they should configure MaxMind
        if geo.reason == "no_credentials":
            logger.warning(
                "MaxMind credentials not configured — event counted without geo verification. "
                "Set MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY to enable KSA-only filtering."
            )
        valid_country = True
    else:
        # Unknown state — fail closed
        valid_country = False

    # An event is valid for dashboard metrics when:
    #   • geo.allowed is True (not blocked by MaxMind/VPN provider)
    #   • country is valid (KSA confirmed, or geo was inconclusive → fail open)
    #   • not a known bot
    valid_for_metrics = geo.allowed and valid_country and not is_bot

    rejected = None if valid_for_metrics else _rejected_reason(geo, valid_country, is_bot)

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
        rejected_reason=rejected,
    )
    db.add(event)
    db.commit()

    return AnalyticsEventOut(valid_for_metrics=valid_for_metrics)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def score_bot(user_agent: str) -> int:
    normalized = user_agent.lower()
    return sum(1 for keyword in BOT_KEYWORDS if keyword in normalized)


def _rejected_reason(geo, valid_country: bool, is_bot: bool) -> str:
    if is_bot:
        return "bot_detected"
    if not geo.allowed:
        return geo.reason or "geo_blocked"
    if not valid_country:
        return geo.reason or "country_not_ksa"
    return geo.reason or "not_valid_for_metrics"
