import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    __table_args__ = (Index("ix_webhook_logs_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
