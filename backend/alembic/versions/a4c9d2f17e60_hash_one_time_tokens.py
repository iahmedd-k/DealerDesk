"""Hash stored refresh, reset, and invitation tokens.

Revision ID: a4c9d2f17e60
Revises: f871c43b2a19
Create Date: 2026-11-21
"""

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c9d2f17e60"
down_revision: Union[str, None] = "f871c43b2a19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    token_columns = (
        ("refresh_tokens", "token"),
        ("password_reset_tokens", "token"),
        ("staff_invitations", "activation_token"),
    )
    for table, column in token_columns:
        rows = connection.execute(
            sa.text(f"SELECT id, {column} FROM {table}")
        ).all()
        for row_id, raw_token in rows:
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            connection.execute(
                sa.text(f"UPDATE {table} SET {column} = :token_hash WHERE id = :id"),
                {"token_hash": token_hash, "id": row_id},
            )


def downgrade() -> None:
    raise RuntimeError("One-time token hashing is an irreversible data migration")
