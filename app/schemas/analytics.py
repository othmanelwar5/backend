from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsEventIn(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=60)
    session_id: str = Field(..., min_length=1, max_length=120)
    occurred_at: datetime | None = None
    path: str | None = None
    url: str | None = None
    referrer: str | None = None
    user_agent: str | None = None
    product_slug: str | None = None
    order_number: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class AnalyticsEventOut(BaseModel):
    success: bool = True
    valid_for_metrics: bool
