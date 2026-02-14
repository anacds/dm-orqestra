"""Add AI interactions table

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_interactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=True),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('input_text', sa.Text(), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_audit_interactions_user_id', 'audit_interactions', ['user_id'])
    op.create_index('ix_audit_interactions_campaign_id', 'audit_interactions', ['campaign_id'])
    op.create_index('ix_audit_interactions_field_name', 'audit_interactions', ['field_name'])
    op.create_index('ix_audit_interactions_session_id', 'audit_interactions', ['session_id'])
    op.create_index('ix_audit_interactions_user_campaign', 'audit_interactions', ['user_id', 'campaign_id'])
    op.create_index('ix_audit_interactions_session', 'audit_interactions', ['session_id'])
    op.create_index('ix_audit_interactions_created_at', 'audit_interactions', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_interactions_created_at', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_session', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_user_campaign', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_session_id', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_field_name', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_campaign_id', table_name='audit_interactions')
    op.drop_index('ix_audit_interactions_user_id', table_name='audit_interactions')
    op.drop_table('audit_interactions')

