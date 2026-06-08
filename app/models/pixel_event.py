import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PixelEvent(Base):
    __tablename__ = "pixel_events"
    __table_args__ = (
        Index("ix_pixel_events_event_name", "event_name"),
        Index("ix_pixel_events_platform", "platform"),
        Index("ix_pixel_events_order_id", "order_id"),
        Index("ix_pixel_events_customer_id", "customer_id"),
        Index("ix_pixel_events_created_at", "created_at"),
        Index("ix_pixel_events_event_id", "event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_name: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)

    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)

    fbp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fbc: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ttp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ttclid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snap_click_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    event_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    order: Mapped["Order | None"] = relationship(back_populates="pixel_events")  # noqa: F821
    customer: Mapped["Customer | None"] = relationship()  # noqa: F821
