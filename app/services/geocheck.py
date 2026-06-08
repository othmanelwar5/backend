"""
MaxMind GeoIP2 Precision Insights integration for fraud/geo-blocking.

Checks:
1. Country must be SA (Saudi Arabia)
2. IP must not be a VPN / proxy / Tor
3. Risk score must be below threshold

Whitelisted phone numbers bypass all checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAXMIND_INSIGHTS_URL = "https://geoip.maxmind.com/geoip/v2.1/insights/{ip}"


@dataclass
class GeoCheckResult:
    allowed: bool
    country_iso: Optional[str] = None
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    is_hosting: bool = False
    risk_score: float = 0.0
    reason: Optional[str] = None


def normalize_phone_for_whitelist(phone: str) -> str:
    """Strip to digits-only for whitelist comparison."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("966"):
        digits = "0" + digits[3:]
    if not digits.startswith("0") and len(digits) == 9:
        digits = "0" + digits
    return digits


def is_phone_whitelisted(phone: str) -> bool:
    normalized = normalize_phone_for_whitelist(phone)
    whitelist = [normalize_phone_for_whitelist(p) for p in settings.WHITELISTED_PHONES]
    return normalized in whitelist


async def check_ip(ip_address: str, phone: Optional[str] = None) -> GeoCheckResult:
    """
    Query MaxMind GeoIP2 Insights for the given IP.
    Returns GeoCheckResult indicating whether the order should be allowed.

    If phone is whitelisted, bypasses all checks.
    If MaxMind is disabled or credentials are missing, allows by default.
    """
    if phone and is_phone_whitelisted(phone):
        logger.info("Phone %s is whitelisted, bypassing geo check", phone[-4:])
        return GeoCheckResult(allowed=True, reason="whitelisted_phone")

    if not settings.MAXMIND_ENABLED:
        return GeoCheckResult(allowed=True, reason="maxmind_disabled")

    if not settings.MAXMIND_ACCOUNT_ID or not settings.MAXMIND_LICENSE_KEY:
        logger.warning("MaxMind credentials not configured, skipping geo check")
        return GeoCheckResult(allowed=True, reason="no_credentials")

    url = MAXMIND_INSIGHTS_URL.format(ip=ip_address)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY),
            )

        if response.status_code != 200:
            logger.error(
                "MaxMind API error: status=%d body=%s",
                response.status_code,
                response.text[:200],
            )
            # Fail open: don't block legitimate orders if MaxMind is down
            return GeoCheckResult(allowed=True, reason="maxmind_api_error")

        data = response.json()
        return _evaluate_response(data)

    except httpx.TimeoutException:
        logger.error("MaxMind API timeout for IP %s", ip_address)
        return GeoCheckResult(allowed=True, reason="maxmind_timeout")
    except Exception as e:
        logger.exception("MaxMind unexpected error: %s", str(e))
        return GeoCheckResult(allowed=True, reason="maxmind_exception")


def _evaluate_response(data: dict) -> GeoCheckResult:
    """Parse MaxMind Insights response and decide."""
    country_iso = data.get("country", {}).get("iso_code", "").upper()

    traits = data.get("traits", {})
    is_vpn = traits.get("is_anonymous_vpn", False)
    is_proxy = traits.get("is_anonymous_proxy", False) or traits.get("is_public_proxy", False)
    is_tor = traits.get("is_tor_exit_node", False)
    is_hosting = traits.get("is_hosting_provider", False)

    risk_score = data.get("risk", {}).get("risk_score", 0.0)
    # Fallback: some responses put it under traits
    if risk_score == 0.0:
        risk_score = traits.get("ip_risk", 0.0)

    result = GeoCheckResult(
        allowed=True,
        country_iso=country_iso,
        is_vpn=is_vpn,
        is_proxy=is_proxy,
        is_tor=is_tor,
        is_hosting=is_hosting,
        risk_score=risk_score,
    )

    # Check 1: Country must be SA
    if country_iso not in settings.GEO_ALLOWED_COUNTRIES:
        result.allowed = False
        result.reason = f"country_blocked:{country_iso}"
        logger.info("Order blocked: country %s not in allowed list", country_iso)
        return result

    # Check 2: VPN / Proxy / Tor
    if settings.GEO_BLOCK_VPN and (is_vpn or is_proxy or is_tor):
        result.allowed = False
        reason_parts = []
        if is_vpn:
            reason_parts.append("vpn")
        if is_proxy:
            reason_parts.append("proxy")
        if is_tor:
            reason_parts.append("tor")
        result.reason = f"anonymous_ip:{'+'.join(reason_parts)}"
        logger.info("Order blocked: anonymous IP detected (%s)", result.reason)
        return result

    # Check 3: Hosting provider (datacenter IPs)
    if settings.GEO_BLOCK_HIGH_RISK and is_hosting:
        result.allowed = False
        result.reason = "hosting_provider"
        logger.info("Order blocked: hosting/datacenter IP")
        return result

    # Check 4: Risk score
    if settings.GEO_BLOCK_HIGH_RISK and risk_score >= settings.GEO_RISK_SCORE_THRESHOLD:
        result.allowed = False
        result.reason = f"high_risk_score:{risk_score}"
        logger.info("Order blocked: risk score %.1f >= threshold %.1f", risk_score, settings.GEO_RISK_SCORE_THRESHOLD)
        return result

    result.reason = "allowed"
    return result
