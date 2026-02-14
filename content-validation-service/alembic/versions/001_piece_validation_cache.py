"""Create piece_validation_audit table

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
        "piece_validation_audit",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("llm_model", sa.String(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_piece_validation_audit_campaign_id", "piece_validation_audit", ["campaign_id"])
    op.create_index("ix_piece_validation_audit_channel", "piece_validation_audit", ["channel"])
    op.create_index("ix_piece_validation_audit_content_hash", "piece_validation_audit", ["content_hash"])
    op.create_index(
        "ix_piece_validation_audit_lookup",
        "piece_validation_audit",
        ["campaign_id", "channel", "content_hash"],
    )
    op.create_index(
        "ix_piece_validation_audit_created_at",
        "piece_validation_audit",
        ["created_at"],
    )

    # Drop old cache table if it exists (migrating from PG cache to Redis)
    op.execute("DROP TABLE IF EXISTS piece_validation_cache CASCADE")


def downgrade() -> None:
    op.drop_index("ix_piece_validation_audit_created_at", table_name="piece_validation_audit")
    op.drop_index("ix_piece_validation_audit_lookup", table_name="piece_validation_audit")
    op.drop_index("ix_piece_validation_audit_content_hash", table_name="piece_validation_audit")
    op.drop_index("ix_piece_validation_audit_channel", table_name="piece_validation_audit")
    op.drop_index("ix_piece_validation_audit_campaign_id", table_name="piece_validation_audit")
    op.drop_table("piece_validation_audit")
