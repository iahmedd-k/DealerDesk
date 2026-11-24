"""Add vehicle image metadata.

Revision ID: c34d11aa8f62
Revises: eb80591937f2
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c34d11aa8f62"
down_revision: Union[str, None] = "eb80591937f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicle_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dealership_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("public_url", sa.String(length=1024), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dealership_id"], ["dealerships.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path", name="uq_vehicle_images_storage_path"),
    )
    op.create_index("ix_vehicle_images_id", "vehicle_images", ["id"], unique=False)
    op.create_index(
        "ix_vehicle_images_dealership_id",
        "vehicle_images",
        ["dealership_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_images_vehicle_id",
        "vehicle_images",
        ["vehicle_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_images_vehicle_id", table_name="vehicle_images")
    op.drop_index("ix_vehicle_images_dealership_id", table_name="vehicle_images")
    op.drop_index("ix_vehicle_images_id", table_name="vehicle_images")
    op.drop_table("vehicle_images")
