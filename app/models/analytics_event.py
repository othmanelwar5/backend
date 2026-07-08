import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_events_occurred_at", "occurred_at"),
        Index("ix_analytics_events_valid_name_date", "valid_for_metrics", "event_name", "occurred_at"),
        Index("ix_analytics_events_session", "session_id"),
        Index("ix_analytics_events_product", "product_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_name: Mapped[str] = mapped_column(String(60), nullable=False)
    session_id: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_tor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hosting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vpn_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vpn_provider_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    maxmind_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    valid_for_metrics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rejected_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bot_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
