import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)

    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_digits: Mapped[str] = mapped_column(String(15), nullable=False)

    subtotal_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_sar: Mapped[int] = mapped_column(Integer, default=0)
    total_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(5), default="SAR")
    payment_method: Mapped[str] = mapped_column(String(20), default="cod")

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)

    upsell_offered_product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    upsell_accepted: Mapped[bool] = mapped_column(Boolean, default=False)

    event_id_purchase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_ids: Mapped[dict] = mapped_column(JSONB, default=dict)

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

    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)

    product_id: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_price_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_original_price_sar: Mapped[int] = mapped_column(Integer, default=199)
    is_upsell: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["Order"] = relationship(back_populates="items")
