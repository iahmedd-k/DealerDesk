"""Add persistent dealership leads.

Revision ID: b3d5e8a1c420
Revises: a4c9d2f17e60
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d5e8a1c420"
down_revision: Union[str, None] = "a4c9d2f17e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dealership_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("requested_vehicle_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("test_drive_booking_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=24),
            server_default="website",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "consent_to_contact",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'test_drive_scheduled', "
            "'won', 'lost', 'follow_up')",
            name="ck_customer_leads_status",
        ),
        sa.CheckConstraint(
            "NOT consent_to_contact OR consented_at IS NOT NULL",
            name="ck_customer_leads_consent_timestamp",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["dealership_id"], ["dealerships.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["test_drive_booking_id"],
            ["test_drive_bookings.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "test_drive_booking_id",
            name="uq_customer_leads_test_drive_booking",
        ),
    )
    op.create_index("ix_customer_leads_id", "customer_leads", ["id"], unique=False)
    op.create_index(
        "ix_customer_leads_dealership_id",
        "customer_leads",
        ["dealership_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_customer_id",
        "customer_leads",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_requested_vehicle_id",
        "customer_leads",
        ["requested_vehicle_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_assigned_to_user_id",
        "customer_leads",
        ["assigned_to_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_email",
        "customer_leads",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_next_follow_up_at",
        "customer_leads",
        ["next_follow_up_at"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_dealership_status",
        "customer_leads",
        ["dealership_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_customer_leads_dealership_assignee",
        "customer_leads",
        ["dealership_id", "assigned_to_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_customer_leads_dealership_assignee", table_name="customer_leads")
    op.drop_index("ix_customer_leads_dealership_status", table_name="customer_leads")
    op.drop_index("ix_customer_leads_next_follow_up_at", table_name="customer_leads")
    op.drop_index("ix_customer_leads_email", table_name="customer_leads")
    op.drop_index("ix_customer_leads_assigned_to_user_id", table_name="customer_leads")
    op.drop_index(
        "ix_customer_leads_requested_vehicle_id", table_name="customer_leads"
    )
    op.drop_index("ix_customer_leads_customer_id", table_name="customer_leads")
    op.drop_index("ix_customer_leads_dealership_id", table_name="customer_leads")
    op.drop_index("ix_customer_leads_id", table_name="customer_leads")
    op.drop_table("customer_leads")
