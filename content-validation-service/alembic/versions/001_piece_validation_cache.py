"""Create piece_validation_cache table

Revision ID: 001
Revises:
Create Date: 2025-01-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "piece_validation_cache",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_piece_validation_cache_campaign_id", "piece_validation_cache", ["campaign_id"])
    op.create_index("ix_piece_validation_cache_channel", "piece_validation_cache", ["channel"])
    op.create_index("ix_piece_validation_cache_content_hash", "piece_validation_cache", ["content_hash"])
    op.create_index(
        "ix_piece_validation_cache_lookup",
        "piece_validation_cache",
        ["campaign_id", "channel", "content_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_piece_validation_cache_lookup", table_name="piece_validation_cache")
    op.drop_index("ix_piece_validation_cache_content_hash", table_name="piece_validation_cache")
    op.drop_index("ix_piece_validation_cache_channel", table_name="piece_validation_cache")
    op.drop_index("ix_piece_validation_cache_campaign_id", table_name="piece_validation_cache")
    op.drop_table("piece_validation_cache")
