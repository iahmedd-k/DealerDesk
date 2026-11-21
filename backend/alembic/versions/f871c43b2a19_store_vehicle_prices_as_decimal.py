"""Store vehicle prices with fixed precision.

Revision ID: f871c43b2a19
Revises: d45e22bb9a73
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f871c43b2a19"
down_revision: Union[str, None] = "d45e22bb9a73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "vehicles",
        "price",
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        postgresql_using="round(price::numeric, 2)",
    )


def downgrade() -> None:
    op.alter_column(
        "vehicles",
        "price",
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="price::double precision",
    )
