import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UpsellOffer(Base):
    __tablename__ = "upsell_offers"
    __table_args__ = (Index("ix_upsell_offers_product_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    offer_price: Mapped[int] = mapped_column(Integer, nullable=False, default=99)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    product: Mapped["Product"] = relationship(back_populates="upsell_offers")  # noqa: F821
    order_upsells: Mapped[list["OrderUpsell"]] = relationship(back_populates="upsell_offer")


class OrderUpsell(Base):
    __tablename__ = "order_upsells"
    __table_args__ = (
        Index("ix_order_upsells_order_id", "order_id"),
        Index("ix_order_upsells_upsell_offer_id", "upsell_offer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    upsell_offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upsell_offers.id"), nullable=False
    )
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    order: Mapped["Order"] = relationship(back_populates="order_upsells")  # noqa: F821
    upsell_offer: Mapped["UpsellOffer"] = relationship(back_populates="order_upsells")
