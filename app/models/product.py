import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True)
    price_1: Mapped[int] = mapped_column(Integer, nullable=False, default=199)
    price_2: Mapped[int] = mapped_column(Integer, nullable=False, default=279)
    price_3: Mapped[int] = mapped_column(Integer, nullable=False, default=349)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")  # noqa: F821
    upsell_offers: Mapped[list["UpsellOffer"]] = relationship(back_populates="product")  # noqa: F821
