"""Initial tables: orders, order_items, event_logs

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
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("customer_name", sa.String(100), nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("phone_digits", sa.String(15), nullable=False),
        sa.Column("subtotal_sar", sa.Integer, nullable=False),
        sa.Column("discount_sar", sa.Integer, server_default="0"),
        sa.Column("total_sar", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(5), server_default="SAR"),
        sa.Column("payment_method", sa.String(20), server_default="cod"),
        sa.Column("status", sa.String(20), server_default="new", index=True),
        sa.Column("upsell_offered_product_id", sa.String(50), nullable=True),
        sa.Column("upsell_accepted", sa.Boolean, server_default="false"),
        sa.Column("event_id_purchase", sa.String(100), nullable=True),
        sa.Column("event_ids", JSONB, server_default="{}"),
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
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.String(50), nullable=False),
        sa.Column("product_name_ar", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("offer_price_sar", sa.Integer, nullable=False),
        sa.Column("unit_original_price_sar", sa.Integer, server_default="199"),
        sa.Column("is_upsell", sa.Boolean, server_default="false"),
    )

    op.create_table(
        "event_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("event_name", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=True),
        sa.Column("request_payload", JSONB, nullable=True),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("order_items")
    op.drop_table("orders")
