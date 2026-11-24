"""initial_schema

Revision ID: eb80591937f2
Revises:
Create Date: 2026-11-20 23:32:40.984952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb80591937f2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Dealerships
    op.create_table(
        'dealerships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dealerships_id', 'dealerships', ['id'], unique=False)

    # 2. Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), server_default='customer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_dealership_id', 'users', ['dealership_id'], unique=False)
    op.create_index('ix_users_role', 'users', ['role'], unique=False)

    # 3. Refresh Tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_id', 'refresh_tokens', ['id'], unique=False)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)

    # 4. Revoked Access Tokens
    op.create_table(
        'revoked_access_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_revoked_access_tokens_id', 'revoked_access_tokens', ['id'], unique=False)
    op.create_index('ix_revoked_access_tokens_user_id', 'revoked_access_tokens', ['user_id'], unique=False)
    op.create_index('ix_revoked_access_tokens_token_hash', 'revoked_access_tokens', ['token_hash'], unique=True)
    op.create_index('ix_revoked_access_tokens_expires_at', 'revoked_access_tokens', ['expires_at'], unique=False)

    # 5. User Token Versions
    op.create_table(
        'user_token_versions',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # 6. Password Reset Tokens
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_password_reset_tokens_id', 'password_reset_tokens', ['id'], unique=False)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('ix_password_reset_tokens_token', 'password_reset_tokens', ['token'], unique=True)

    # 7. Staff Invitations
    op.create_table(
        'staff_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('activation_token', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_status', sa.String(length=32), server_default='email_provider_pending', nullable=False),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_staff_invitations_id', 'staff_invitations', ['id'], unique=False)
    op.create_index('ix_staff_invitations_user_id', 'staff_invitations', ['user_id'], unique=True)
    op.create_index('ix_staff_invitations_dealership_id', 'staff_invitations', ['dealership_id'], unique=False)
    op.create_index('ix_staff_invitations_activation_token', 'staff_invitations', ['activation_token'], unique=True)

    # 8. Brands
    op.create_table(
        'brands',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('logo_url', sa.String(length=1024), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_brands_id', 'brands', ['id'], unique=False)
    op.create_index('ix_brands_dealership_id', 'brands', ['dealership_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_brand_dealership_name_active
        ON brands (dealership_id, lower(name))
        WHERE is_deleted = FALSE
        """
    )

    # 9. Vehicles
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('make', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('model_year', sa.Integer(), nullable=False),
        sa.Column('variant', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('stock_number', sa.String(length=64), nullable=False),
        sa.Column('is_available', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('test_drive_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealership_id', 'stock_number', name='uq_vehicle_dealership_stock'),
    )
    op.create_index('ix_vehicles_id', 'vehicles', ['id'], unique=False)
    op.create_index('ix_vehicles_dealership_id', 'vehicles', ['dealership_id'], unique=False)
    op.create_index('ix_vehicles_brand_id', 'vehicles', ['brand_id'], unique=False)

    # 10. Test Drive Settings
    op.create_table(
        'test_drive_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('opening_time', sa.String(length=5), server_default='09:00', nullable=False),
        sa.Column('closing_time', sa.String(length=5), server_default='17:00', nullable=False),
        sa.Column('slot_duration_minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('capacity_per_slot', sa.Integer(), server_default='1', nullable=False),
        sa.Column('days_open', sa.String(length=32), server_default='0,1,2,3,4', nullable=False),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealership_id'),
    )
    op.create_index('ix_test_drive_settings_id', 'test_drive_settings', ['id'], unique=False)
    op.create_index('ix_test_drive_settings_dealership_id', 'test_drive_settings', ['dealership_id'], unique=False)

    # 11. Test Drive Slots
    op.create_table(
        'test_drive_slots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('booked_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealership_id', 'vehicle_id', 'starts_at', name='uq_test_drive_slot'),
    )
    op.create_index('ix_test_drive_slots_id', 'test_drive_slots', ['id'], unique=False)
    op.create_index('ix_test_drive_slots_dealership_id', 'test_drive_slots', ['dealership_id'], unique=False)
    op.create_index('ix_test_drive_slots_vehicle_id', 'test_drive_slots', ['vehicle_id'], unique=False)
    op.create_index('ix_test_drive_slots_starts_at', 'test_drive_slots', ['starts_at'], unique=False)

    # 12. Test Drive Bookings
    op.create_table(
        'test_drive_bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='booked', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.ForeignKeyConstraint(['slot_id'], ['test_drive_slots.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_test_drive_bookings_id', 'test_drive_bookings', ['id'], unique=False)
    op.create_index('ix_test_drive_bookings_dealership_id', 'test_drive_bookings', ['dealership_id'], unique=False)
    op.create_index('ix_test_drive_bookings_slot_id', 'test_drive_bookings', ['slot_id'], unique=False)
    op.create_index('ix_test_drive_bookings_vehicle_id', 'test_drive_bookings', ['vehicle_id'], unique=False)
    op.create_index('ix_test_drive_bookings_customer_id', 'test_drive_bookings', ['customer_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_test_drive_booking_active_customer
        ON test_drive_bookings (slot_id, customer_id)
        WHERE status = 'booked'
        """
    )

    # 13. Knowledge Documents
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dealership_id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('media_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=24), server_default='ready', nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('embedding_model', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ),
        sa.ForeignKeyConstraint(['dealership_id'], ['dealerships.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_knowledge_documents_id', 'knowledge_documents', ['id'], unique=False)
    op.create_index('ix_knowledge_documents_dealership_id', 'knowledge_documents', ['dealership_id'], unique=False)
    op.create_index('ix_knowledge_documents_brand_id', 'knowledge_documents', ['brand_id'], unique=False)

    # 14. Knowledge Chunks
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_knowledge_chunks_id', 'knowledge_chunks', ['id'], unique=False)
    op.create_index('ix_knowledge_chunks_document_id', 'knowledge_chunks', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
    op.execute("DROP INDEX IF EXISTS uq_test_drive_booking_active_customer")
    op.drop_table('test_drive_bookings')
    op.drop_table('test_drive_slots')
    op.drop_table('test_drive_settings')
    op.drop_table('vehicles')
    op.execute("DROP INDEX IF EXISTS uq_brand_dealership_name_active")
    op.drop_table('brands')
    op.drop_table('staff_invitations')
    op.drop_table('password_reset_tokens')
    op.drop_table('user_token_versions')
    op.drop_table('revoked_access_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    op.drop_table('dealerships')
