"""Add product SKU and refresh Arabic product names

Revision ID: 002_product_sku
Revises: 001_initial_schema
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_product_sku"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sku", sa.String(length=30), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE products
            SET sku = 'MZN-D3K2-8417',
                name_ar = 'حلوى فيتامين D3 و K2'
            WHERE slug = 'd3-k2-gummies'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE products
            SET sku = 'MZN-SLP-2935',
                name_ar = 'شاي الأشواغاندا والمغنيسيوم'
            WHERE slug = 'sleep-tea'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE products
            SET sku = 'MZN-PRB-6102',
                name_ar = 'حلوى البروبيوتيك والألياف'
            WHERE slug = 'probiotic-fiber-gummies'
            """
        )
    )
    op.execute(sa.text("UPDATE products SET sku = slug WHERE sku IS NULL"))

    op.alter_column("products", "sku", nullable=False)
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_column("products", "sku")
