"""Initial ecommerce schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name_ar", sa.String(length=150), nullable=False),
        sa.Column("name_en", sa.String(length=150), nullable=True),
        sa.Column("price_1", sa.Integer(), nullable=False, server_default="199"),
        sa.Column("price_2", sa.Integer(), nullable=False, server_default="279"),
        sa.Column("price_3", sa.Integer(), nullable=False, server_default="349"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_order_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"], unique=True)

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(length=30), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"], unique=False)
    op.create_index("ix_orders_phone", "orders", ["phone"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"], unique=False)

    op.create_table(
        "upsell_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("offer_price", sa.Integer(), nullable=False, server_default="99"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upsell_offers_product_id", "upsell_offers", ["product_id"], unique=False)

    op.create_table(
        "order_upsells",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("upsell_offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upsell_offer_id"], ["upsell_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_upsells_order_id", "order_upsells", ["order_id"], unique=False)
    op.create_index("ix_order_upsells_upsell_offer_id", "order_upsells", ["upsell_offer_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_name", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_order_id", "events", ["order_id"], unique=False)
    op.create_index("ix_events_platform", "events", ["platform"], unique=False)
    op.create_index("ix_events_created_at", "events", ["created_at"], unique=False)
    op.create_index("ix_events_event_id", "events", ["event_id"], unique=False)

    op.create_table(
        "pixel_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_name", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pixel_events_event_name", "pixel_events", ["event_name"], unique=False)
    op.create_index("ix_pixel_events_platform", "pixel_events", ["platform"], unique=False)
    op.create_index("ix_pixel_events_order_id", "pixel_events", ["order_id"], unique=False)
    op.create_index("ix_pixel_events_created_at", "pixel_events", ["created_at"], unique=False)
    op.create_index("ix_pixel_events_event_id", "pixel_events", ["event_id"], unique=False)

    op.create_table(
        "webhook_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_logs_created_at", "webhook_logs", ["created_at"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO products (id, slug, name_ar, name_en, price_1, price_2, price_3, active)
            VALUES
                (gen_random_uuid(), 'd3-k2-gummies', 'علكة D3+K2', 'D3+K2 Gummies', 199, 279, 349, true),
                (gen_random_uuid(), 'sleep-tea', 'شاي النوم', 'Sleep Tea', 199, 279, 349, true),
                (gen_random_uuid(), 'probiotic-fiber-gummies', 'علكة البروبيوتيك والألياف', 'Probiotic Fiber Gummies', 199, 279, 349, true)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_logs_created_at", table_name="webhook_logs")
    op.drop_table("webhook_logs")

    op.drop_index("ix_pixel_events_event_id", table_name="pixel_events")
    op.drop_index("ix_pixel_events_created_at", table_name="pixel_events")
    op.drop_index("ix_pixel_events_order_id", table_name="pixel_events")
    op.drop_index("ix_pixel_events_platform", table_name="pixel_events")
    op.drop_index("ix_pixel_events_event_name", table_name="pixel_events")
    op.drop_table("pixel_events")

    op.drop_index("ix_events_event_id", table_name="events")
    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_platform", table_name="events")
    op.drop_index("ix_events_order_id", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_order_upsells_upsell_offer_id", table_name="order_upsells")
    op.drop_index("ix_order_upsells_order_id", table_name="order_upsells")
    op.drop_table("order_upsells")

    op.drop_index("ix_upsell_offers_product_id", table_name="upsell_offers")
    op.drop_table("upsell_offers")

    op.drop_index("ix_order_items_product_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_phone", table_name="orders")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_order_number", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_table("customers")

    op.drop_index("ix_products_slug", table_name="products")
    op.drop_table("products")
