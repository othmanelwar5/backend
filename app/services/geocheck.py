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
    provider: Optional[str] = None
    provider_payload: Optional[dict] = None


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
    print("[ORDER-DEBUG] step-11a geo check started", {"ip": ip_address, "has_phone": bool(phone)})
    if phone and is_phone_whitelisted(phone):
        logger.info("Phone %s is whitelisted, bypassing geo check", phone[-4:])
        print("[ORDER-DEBUG] step-11b geo check bypassed by whitelisted phone")
        return GeoCheckResult(allowed=True, reason="whitelisted_phone")

    if not settings.MAXMIND_ENABLED:
        print("[ORDER-DEBUG] step-11b geo check skipped: maxmind disabled")
        return GeoCheckResult(allowed=True, reason="maxmind_disabled")

    if not settings.MAXMIND_ACCOUNT_ID or not settings.MAXMIND_LICENSE_KEY:
        logger.warning("MaxMind credentials not configured, skipping geo check")
        print("[ORDER-DEBUG] step-11b geo check skipped: missing MaxMind credentials")
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
        result = _evaluate_response(data)
        if result.allowed:
            result = await _apply_secondary_vpn_check(ip_address, result)
        return result

    except httpx.TimeoutException:
        logger.error("MaxMind API timeout for IP %s", ip_address)
        return GeoCheckResult(allowed=True, reason="maxmind_timeout")
    except Exception as e:
        logger.exception("MaxMind unexpected error: %s", str(e))
        return GeoCheckResult(allowed=True, reason="maxmind_exception")


async def _apply_secondary_vpn_check(ip_address: str, result: GeoCheckResult) -> GeoCheckResult:
    if not settings.VPN_DETECTION_API_URL or not settings.VPN_DETECTION_API_KEY:
        return result

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                settings.VPN_DETECTION_API_URL,
                params={"ip": ip_address},
                headers={"Authorization": f"Bearer {settings.VPN_DETECTION_API_KEY}"},
            )

        if response.status_code >= 400:
            logger.error("VPN provider error: status=%d body=%s", response.status_code, response.text[:200])
            return result

        payload = response.json()
        verdict = _evaluate_secondary_vpn_payload(payload)
        result.provider = "secondary_vpn_provider"
        result.provider_payload = payload
        result.is_vpn = result.is_vpn or verdict["is_vpn"]
        result.is_proxy = result.is_proxy or verdict["is_proxy"]
        result.is_tor = result.is_tor or verdict["is_tor"]
        result.is_hosting = result.is_hosting or verdict["is_hosting"]
        result.risk_score = max(result.risk_score, verdict["risk_score"])

        if settings.GEO_BLOCK_VPN and (verdict["is_vpn"] or verdict["is_proxy"] or verdict["is_tor"]):
            result.allowed = False
            result.reason = "secondary_provider_anonymous_ip"
        elif settings.GEO_BLOCK_HIGH_RISK and verdict["is_hosting"]:
            result.allowed = False
            result.reason = "secondary_provider_hosting"
        elif settings.GEO_BLOCK_HIGH_RISK and verdict["risk_score"] >= settings.GEO_RISK_SCORE_THRESHOLD:
            result.allowed = False
            result.reason = f"secondary_provider_high_risk:{verdict['risk_score']}"

        return result
    except httpx.TimeoutException:
        logger.error("VPN provider timeout for IP %s", ip_address)
        return result
    except Exception as exc:
        logger.exception("VPN provider unexpected error: %s", str(exc))
        return result


def _truthy_from_payload(data: dict, *keys: str) -> bool:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return False
        current = current.get(key)
    return bool(current)


def _evaluate_secondary_vpn_payload(data: dict) -> dict:
    security = data.get("security") if isinstance(data.get("security"), dict) else {}
    risk = data.get("risk") if isinstance(data.get("risk"), dict) else {}
    fraud_score = data.get("fraud_score", data.get("risk_score", risk.get("score", 0.0)))

    try:
        risk_score = float(fraud_score or 0.0)
    except (TypeError, ValueError):
        risk_score = 0.0

    return {
        "is_vpn": bool(data.get("vpn") or security.get("vpn") or _truthy_from_payload(data, "privacy", "vpn")),
        "is_proxy": bool(data.get("proxy") or security.get("proxy") or _truthy_from_payload(data, "privacy", "proxy")),
        "is_tor": bool(data.get("tor") or security.get("tor") or _truthy_from_payload(data, "privacy", "tor")),
        "is_hosting": bool(data.get("hosting") or security.get("hosting") or data.get("datacenter")),
        "risk_score": risk_score,
    }


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
