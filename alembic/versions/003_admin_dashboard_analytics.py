"""Add admin dashboard analytics events

Revision ID: 003_admin_dashboard_analytics
Revises: 002_product_sku
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_admin_dashboard_analytics"
down_revision: Union[str, None] = "002_product_sku"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_name", sa.String(length=60), nullable=False),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("product_slug", sa.String(length=100), nullable=True),
        sa.Column("order_number", sa.String(length=30), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("is_vpn", sa.Boolean(), nullable=False),
        sa.Column("is_proxy", sa.Boolean(), nullable=False),
        sa.Column("is_tor", sa.Boolean(), nullable=False),
        sa.Column("is_hosting", sa.Boolean(), nullable=False),
        sa.Column("is_bot", sa.Boolean(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("vpn_provider", sa.String(length=80), nullable=True),
        sa.Column("vpn_provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("maxmind_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("valid_for_metrics", sa.Boolean(), nullable=False),
        sa.Column("rejected_reason", sa.String(length=200), nullable=True),
        sa.Column("bot_score", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_occurred_at", "analytics_events", ["occurred_at"])
    op.create_index(
        "ix_analytics_events_valid_name_date",
        "analytics_events",
        ["valid_for_metrics", "event_name", "occurred_at"],
    )
    op.create_index("ix_analytics_events_session", "analytics_events", ["session_id"])
    op.create_index("ix_analytics_events_product", "analytics_events", ["product_slug"])


def downgrade() -> None:
    op.drop_index("ix_analytics_events_product", table_name="analytics_events")
    op.drop_index("ix_analytics_events_session", table_name="analytics_events")
    op.drop_index("ix_analytics_events_valid_name_date", table_name="analytics_events")
    op.drop_index("ix_analytics_events_occurred_at", table_name="analytics_events")
    op.drop_table("analytics_events")
