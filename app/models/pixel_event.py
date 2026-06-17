import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PixelEvent(Base):
    __tablename__ = "pixel_events"
    __table_args__ = (
        Index("ix_pixel_events_event_name", "event_name"),
        Index("ix_pixel_events_platform", "platform"),
        Index("ix_pixel_events_order_id", "order_id"),
        Index("ix_pixel_events_created_at", "created_at"),
        Index("ix_pixel_events_event_id", "event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    event_name: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    order: Mapped["Order | None"] = relationship(back_populates="pixel_events")  # noqa: F821
