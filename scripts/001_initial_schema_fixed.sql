-- =============================================================================
-- Mizan Ecommerce — PostgreSQL initial schema (regenerated from SQLAlchemy/Alembic)
-- File: 001_initial_schema_fixed.sql
-- Revision: 001_initial_schema (matches Alembic migration)
--
-- Usage: paste and run in EasyPanel PostgreSQL Query tab.
-- Requires: PostgreSQL 13+ (pgcrypto for gen_random_uuid)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- products
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(100)  NOT NULL,
    sku         VARCHAR(30)   NOT NULL,
    name_ar     VARCHAR(150)  NOT NULL,
    name_en     VARCHAR(150),
    price_1     INTEGER       NOT NULL DEFAULT 199,
    price_2     INTEGER       NOT NULL DEFAULT 279,
    price_3     INTEGER       NOT NULL DEFAULT 349,
    active      BOOLEAN       NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_products_slug ON products (slug);
CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);

-- -----------------------------------------------------------------------------
-- customers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(100) NOT NULL,
    phone            VARCHAR(20)  NOT NULL,
    total_orders     INTEGER      NOT NULL DEFAULT 0,
    first_order_date TIMESTAMPTZ,
    last_order_date  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_phone ON customers (phone);

-- -----------------------------------------------------------------------------
-- orders
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number  VARCHAR(30)  NOT NULL,
    customer_id   UUID,
    customer_name VARCHAR(100) NOT NULL,
    phone         VARCHAR(20)  NOT NULL,
    city          VARCHAR(100) NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
    subtotal      INTEGER      NOT NULL,
    total         INTEGER      NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_orders_customer_id
        FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_order_number ON orders (order_number);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS ix_orders_status_created ON orders (status, created_at);
CREATE INDEX IF NOT EXISTS ix_orders_phone ON orders (phone);

-- -----------------------------------------------------------------------------
-- order_items
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID        NOT NULL,
    product_id  UUID        NOT NULL,
    quantity    INTEGER     NOT NULL,
    unit_price  INTEGER     NOT NULL,
    total_price INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_order_items_order_id
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product_id
        FOREIGN KEY (product_id) REFERENCES products (id)
);

CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_order_items_product_id ON order_items (product_id);

-- -----------------------------------------------------------------------------
-- upsell_offers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS upsell_offers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id  UUID         NOT NULL,
    name        VARCHAR(150) NOT NULL,
    offer_price INTEGER      NOT NULL DEFAULT 99,
    active      BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_upsell_offers_product_id
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_upsell_offers_product_id ON upsell_offers (product_id);

-- -----------------------------------------------------------------------------
-- order_upsells
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_upsells (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID        NOT NULL,
    upsell_offer_id UUID        NOT NULL,
    accepted        BOOLEAN     NOT NULL DEFAULT false,
    price           INTEGER     NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_order_upsells_order_id
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_order_upsells_upsell_offer_id
        FOREIGN KEY (upsell_offer_id) REFERENCES upsell_offers (id)
);

CREATE INDEX IF NOT EXISTS ix_order_upsells_order_id ON order_upsells (order_id);
CREATE INDEX IF NOT EXISTS ix_order_upsells_upsell_offer_id ON order_upsells (upsell_offer_id);

-- -----------------------------------------------------------------------------
-- events
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id   UUID,
    event_name VARCHAR(50)  NOT NULL,
    event_id   VARCHAR(100),
    platform   VARCHAR(20)  NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_events_order_id
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_events_order_id ON events (order_id);
CREATE INDEX IF NOT EXISTS ix_events_platform ON events (platform);
CREATE INDEX IF NOT EXISTS ix_events_created_at ON events (created_at);
CREATE INDEX IF NOT EXISTS ix_events_event_id ON events (event_id);

-- -----------------------------------------------------------------------------
-- pixel_events
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pixel_events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id   UUID,
    event_name VARCHAR(50)  NOT NULL,
    event_id   VARCHAR(100),
    platform   VARCHAR(20)  NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_pixel_events_order_id
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_pixel_events_event_name ON pixel_events (event_name);
CREATE INDEX IF NOT EXISTS ix_pixel_events_platform ON pixel_events (platform);
CREATE INDEX IF NOT EXISTS ix_pixel_events_order_id ON pixel_events (order_id);
CREATE INDEX IF NOT EXISTS ix_pixel_events_created_at ON pixel_events (created_at);
CREATE INDEX IF NOT EXISTS ix_pixel_events_event_id ON pixel_events (event_id);

-- -----------------------------------------------------------------------------
-- webhook_logs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webhook_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payload    JSONB       NOT NULL,
    response   JSONB,
    success    BOOLEAN     NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_webhook_logs_created_at ON webhook_logs (created_at);

-- -----------------------------------------------------------------------------
-- alembic_version (keeps manual SQL in sync with Alembic)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- -----------------------------------------------------------------------------
-- seed data: default products
-- -----------------------------------------------------------------------------
INSERT INTO products (slug, sku, name_ar, name_en, price_1, price_2, price_3, active)
SELECT 'd3-k2-gummies', 'MZN-D3K2-8417', 'حلوى فيتامين D3 و K2', 'D3+K2 Gummies', 199, 279, 349, true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE slug = 'd3-k2-gummies');

INSERT INTO products (slug, sku, name_ar, name_en, price_1, price_2, price_3, active)
SELECT 'sleep-tea', 'MZN-SLP-2935', 'شاي الأشواغاندا والمغنيسيوم', 'Sleep Tea', 199, 279, 349, true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE slug = 'sleep-tea');

INSERT INTO products (slug, sku, name_ar, name_en, price_1, price_2, price_3, active)
SELECT 'probiotic-fiber-gummies', 'MZN-PRB-6102', 'حلوى البروبيوتيك والألياف', 'Probiotic Fiber Gummies', 199, 279, 349, true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE slug = 'probiotic-fiber-gummies');

INSERT INTO alembic_version (version_num)
SELECT '001_initial_schema'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);

-- -----------------------------------------------------------------------------
-- verification (optional — comment out if your client runs one statement at a time)
-- -----------------------------------------------------------------------------
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
      'products',
      'customers',
      'orders',
      'order_items',
      'upsell_offers',
      'order_upsells',
      'events',
      'pixel_events',
      'webhook_logs',
      'alembic_version'
  )
ORDER BY tablename;
