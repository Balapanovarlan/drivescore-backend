"""add role column to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22 01:22:20.162418
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable with default, backfill the seeded admin, enforce NOT NULL.
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), nullable=True, server_default="manager"),
    )
    op.execute("UPDATE users SET role = 'admin' WHERE email = 'info@adam.ua'")
    op.alter_column("users", "role", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "role")
