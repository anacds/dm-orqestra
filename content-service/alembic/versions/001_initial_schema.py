"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
import sys
import os

from alembic import op
import sqlalchemy as sa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create creative_piece_analyses table
    op.create_table(
        'creative_piece_analyses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('is_valid', sa.String(), nullable=False),
        sa.Column('analysis_text', sa.Text(), nullable=False),
        sa.Column('analyzed_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_creative_piece_analysis_campaign_channel', 'creative_piece_analyses', ['campaign_id', 'channel'], unique=False)
    op.create_index('ix_creative_piece_analysis_content_hash', 'creative_piece_analyses', ['content_hash'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_creative_piece_analysis_content_hash', table_name='creative_piece_analyses')
    op.drop_index('ix_creative_piece_analysis_campaign_channel', table_name='creative_piece_analyses')
    op.drop_table('creative_piece_analyses')

