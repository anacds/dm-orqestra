"""Add rejection_reason to piece_review (optional human feedback on reject/manually_reject).

Revision ID: 004
Revises: 003
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "piece_review",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("piece_review", "rejection_reason")
