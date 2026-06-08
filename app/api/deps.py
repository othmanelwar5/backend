"""
FastAPI dependencies for geo-fraud checking on order endpoints.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.services.geocheck import GeoCheckResult, check_ip


def get_client_ip(request: Request) -> str:
    """
    Extract real client IP, respecting reverse proxy headers.
    Priority: X-Real-IP > X-Forwarded-For (first entry) > request.client.host
    """
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()

    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "0.0.0.0"


async def enforce_geo_check(
    request: Request,
) -> GeoCheckResult:
    """
    Dependency to be used on order creation routes.
    Phone must be passed separately after body parsing.
    This runs only the IP check without phone whitelist awareness.
    Use `verify_order_geo` for full check with phone whitelist.
    """
    ip = get_client_ip(request)
    result = await check_ip(ip)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "order_blocked",
                "reason": result.reason,
                "message_ar": "عذراً، لا يمكن إتمام الطلب من موقعك الحالي. الخدمة متاحة فقط داخل المملكة العربية السعودية.",
            },
        )

    return result


async def verify_order_geo(ip: str, phone: str) -> GeoCheckResult:
    """
    Full geo verification with phone whitelist support.
    Call this from the order creation handler after parsing the body.
    """
    result = await check_ip(ip, phone=phone)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "order_blocked",
                "reason": result.reason,
                "message_ar": "عذراً، لا يمكن إتمام الطلب من موقعك الحالي. الخدمة متاحة فقط داخل المملكة العربية السعودية.",
            },
        )

    return result
