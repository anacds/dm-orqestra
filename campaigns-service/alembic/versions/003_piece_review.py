"""Add piece_review table for CONTENT_REVIEW workflow (IA verdict + human verdict per piece).

Revision ID: 003
Revises: 002
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece_review",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(), nullable=False),
        sa.Column("commercial_space", sa.String(), nullable=False, server_default=""),
        sa.Column("ia_verdict", sa.String(), nullable=False),
        sa.Column("human_verdict", sa.String(), nullable=False, server_default="pending"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_piece_review_campaign_id", "piece_review", ["campaign_id"], unique=False)
    op.create_index("ix_piece_review_channel", "piece_review", ["channel"], unique=False)
    op.create_index("ix_piece_review_piece_id", "piece_review", ["piece_id"], unique=False)
    op.create_index(
        "ix_piece_review_lookup",
        "piece_review",
        ["campaign_id", "channel", "piece_id", "commercial_space"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_piece_review_lookup", table_name="piece_review")
    op.drop_index("ix_piece_review_piece_id", table_name="piece_review")
    op.drop_index("ix_piece_review_channel", table_name="piece_review")
    op.drop_index("ix_piece_review_campaign_id", table_name="piece_review")
    op.drop_table("piece_review")
