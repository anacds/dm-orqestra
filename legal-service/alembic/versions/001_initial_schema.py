"""Create legal validation audits table

Revision ID: 001
Revises: 
Create Date: 2025-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'legal_validation_audits',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('content_preview', sa.String(length=500), nullable=True),
        sa.Column('decision', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('sources', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('num_chunks_retrieved', sa.Integer(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('search_query', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_legal_validation_audits_task', 'legal_validation_audits', ['task'])
    op.create_index('ix_legal_validation_audits_channel', 'legal_validation_audits', ['channel'])
    op.create_index('ix_legal_validation_audits_decision', 'legal_validation_audits', ['decision'])
    op.create_index('ix_legal_validation_audits_severity', 'legal_validation_audits', ['severity'])
    op.create_index('ix_legal_validation_audits_requires_human_review', 'legal_validation_audits', ['requires_human_review'])
    op.create_index('ix_legal_validation_audits_content_hash', 'legal_validation_audits', ['content_hash'])
    op.create_index('ix_legal_validation_audits_channel_decision', 'legal_validation_audits', ['channel', 'decision'])
    op.create_index('ix_legal_validation_audits_created_at', 'legal_validation_audits', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_legal_validation_audits_created_at', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_channel_decision', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_content_hash', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_requires_human_review', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_severity', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_decision', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_channel', table_name='legal_validation_audits')
    op.drop_index('ix_legal_validation_audits_task', table_name='legal_validation_audits')
    op.drop_table('legal_validation_audits')

