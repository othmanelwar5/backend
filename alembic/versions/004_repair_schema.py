"""Repair schema: ensure sku column and analytics_events table exist

This is a catch-all repair migration that is safe to run on any DB state.
It uses IF NOT EXISTS / DO blocks so it is fully idempotent.

Revision ID: 004_repair_schema
Revises: 003_admin_dashboard_analytics
Create Date: 2026-07-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_repair_schema"
down_revision: Union[str, None] = "003_admin_dashboard_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Ensure products.sku column exists (migration 002 may not have run) ---
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'products' AND column_name = 'sku'
            ) THEN
                ALTER TABLE products ADD COLUMN sku VARCHAR(30);
            END IF;
        END $$;
    """))

    # Fill sku from slug where still NULL
    op.execute(sa.text("UPDATE products SET sku = slug WHERE sku IS NULL"))

    # Add unique index if it doesn't exist
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'products' AND indexname = 'ix_products_sku'
            ) THEN
                CREATE UNIQUE INDEX ix_products_sku ON products (sku);
            END IF;
        END $$;
    """))

    # --- 2. Ensure analytics_events table exists (migration 003 may have failed) ---
    # pgcrypto extension — suppress permission errors on managed hosts
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        WHEN others THEN NULL;
        END $$;
    """))

    # Create analytics_events if missing
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_name VARCHAR(60) NOT NULL,
            session_id VARCHAR(120) NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            path TEXT,
            url TEXT,
            referrer TEXT,
            user_agent TEXT,
            product_slug VARCHAR(100),
            order_number VARCHAR(30),
            properties JSONB NOT NULL DEFAULT '{}',
            ip_address INET,
            country_code VARCHAR(2),
            is_vpn BOOLEAN NOT NULL DEFAULT false,
            is_proxy BOOLEAN NOT NULL DEFAULT false,
            is_tor BOOLEAN NOT NULL DEFAULT false,
            is_hosting BOOLEAN NOT NULL DEFAULT false,
            is_bot BOOLEAN NOT NULL DEFAULT false,
            risk_score FLOAT NOT NULL DEFAULT 0.0,
            vpn_provider VARCHAR(80),
            vpn_provider_payload JSONB NOT NULL DEFAULT '{}',
            maxmind_payload JSONB NOT NULL DEFAULT '{}',
            valid_for_metrics BOOLEAN NOT NULL DEFAULT false,
            rejected_reason VARCHAR(200),
            bot_score INTEGER NOT NULL DEFAULT 0
        );
    """))

    # Indexes for analytics_events (IF NOT EXISTS)
    op.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename='analytics_events' AND indexname='ix_analytics_events_occurred_at')
            THEN CREATE INDEX ix_analytics_events_occurred_at ON analytics_events (occurred_at); END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename='analytics_events' AND indexname='ix_analytics_events_valid_name_date')
            THEN CREATE INDEX ix_analytics_events_valid_name_date ON analytics_events (valid_for_metrics, event_name, occurred_at); END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename='analytics_events' AND indexname='ix_analytics_events_session')
            THEN CREATE INDEX ix_analytics_events_session ON analytics_events (session_id); END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename='analytics_events' AND indexname='ix_analytics_events_product')
            THEN CREATE INDEX ix_analytics_events_product ON analytics_events (product_slug); END IF;
        END $$;
    """))


def downgrade() -> None:
    # This repair migration is intentionally not reversible
    pass
