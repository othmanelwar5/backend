"""Full schema: products, customers, orders, order_items, upsells, events, pixel_events

Revision ID: 001
Revises: None
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── products ──
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name_ar", sa.String(150), nullable=False),
        sa.Column("name_en", sa.String(150), nullable=True),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description_ar", sa.Text, nullable=True),
        sa.Column("price_1_sar", sa.Integer, nullable=False, server_default="199"),
        sa.Column("price_2_sar", sa.Integer, nullable=False, server_default="279"),
        sa.Column("price_3_sar", sa.Integer, nullable=False, server_default="349"),
        sa.Column("upsell_price_sar", sa.Integer, nullable=False, server_default="99"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_products_product_id", "products", ["product_id"])
    op.create_index("ix_products_slug", "products", ["slug"])

    # ── customers ──
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone_e164", sa.String(20), unique=True, nullable=False),
        sa.Column("phone_digits", sa.String(15), nullable=False),
        sa.Column("total_orders", sa.Integer, server_default="0"),
        sa.Column("total_spent_sar", sa.Integer, server_default="0"),
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_phone_e164", "customers", ["phone_e164"])

    # ── orders ──
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_number", sa.String(30), unique=True, nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("subtotal_sar", sa.Integer, nullable=False),
        sa.Column("discount_sar", sa.Integer, server_default="0"),
        sa.Column("total_sar", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(5), server_default="SAR"),
        sa.Column("payment_method", sa.String(20), server_default="cod"),
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("landing_page_url", sa.Text, nullable=True),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column("utm_source", sa.String(100), nullable=True),
        sa.Column("utm_medium", sa.String(100), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("utm_content", sa.String(200), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("fbp", sa.String(200), nullable=True),
        sa.Column("fbc", sa.String(200), nullable=True),
        sa.Column("ttp", sa.String(200), nullable=True),
        sa.Column("ttclid", sa.String(200), nullable=True),
        sa.Column("snap_click_id", sa.String(200), nullable=True),
        sa.Column("event_id_purchase", sa.String(100), nullable=True),
        sa.Column("event_ids", JSONB, server_default="{}"),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])

    # ── order_items ──
    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_sar", sa.Integer, nullable=False),
        sa.Column("total_price_sar", sa.Integer, nullable=False),
        sa.Column("is_upsell", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    # ── upsells ──
    op.create_table(
        "upsells",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("offered_price_sar", sa.Integer, nullable=False, server_default="99"),
        sa.Column("accepted", sa.Boolean, server_default="false"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_upsells_order_id", "upsells", ["order_id"])
    op.create_index("ix_upsells_product_id", "upsells", ["product_id"])

    # ── events (CAPI / webhook delivery log) ──
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("event_name", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=True),
        sa.Column("request_payload", JSONB, nullable=True),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_order_id", "events", ["order_id"])
    op.create_index("ix_events_platform", "events", ["platform"])
    op.create_index("ix_events_created_at", "events", ["created_at"])

    # ── pixel_events (browser-side pixel tracking) ──
    op.create_table(
        "pixel_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(100), unique=True, nullable=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("page_url", sa.Text, nullable=True),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column("fbp", sa.String(200), nullable=True),
        sa.Column("fbc", sa.String(200), nullable=True),
        sa.Column("ttp", sa.String(200), nullable=True),
        sa.Column("ttclid", sa.String(200), nullable=True),
        sa.Column("snap_click_id", sa.String(200), nullable=True),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean, server_default="false"),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pixel_events_event_name", "pixel_events", ["event_name"])
    op.create_index("ix_pixel_events_platform", "pixel_events", ["platform"])
    op.create_index("ix_pixel_events_order_id", "pixel_events", ["order_id"])
    op.create_index("ix_pixel_events_customer_id", "pixel_events", ["customer_id"])
    op.create_index("ix_pixel_events_created_at", "pixel_events", ["created_at"])
    op.create_index("ix_pixel_events_event_id", "pixel_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("pixel_events")
    op.drop_table("events")
    op.drop_table("upsells")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("customers")
    op.drop_table("products")
