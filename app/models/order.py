import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)

    subtotal_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_sar: Mapped[int] = mapped_column(Integer, default=0)
    total_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(5), default="SAR")
    payment_method: Mapped[str] = mapped_column(String(20), default="cod")

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)

    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    landing_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(200), nullable=True)

    fbp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fbc: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ttp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ttclid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snap_click_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    event_id_purchase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer: Mapped["Customer"] = relationship(back_populates="orders")  # noqa: F821
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    upsells: Mapped[list["Upsell"]] = relationship(back_populates="order", cascade="all, delete-orphan")  # noqa: F821
    events: Mapped[list["Event"]] = relationship(back_populates="order", cascade="all, delete-orphan")  # noqa: F821
    pixel_events: Mapped[list["PixelEvent"]] = relationship(back_populates="order")  # noqa: F821


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    is_upsell: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821
