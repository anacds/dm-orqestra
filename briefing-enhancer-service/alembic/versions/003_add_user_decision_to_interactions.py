"""Add user_decision and decision_at to AI interactions

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_interactions', sa.Column('user_decision', sa.String(length=20), nullable=True))
    op.add_column('audit_interactions', sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True))
    
    op.create_index('ix_audit_interactions_user_decision', 'audit_interactions', ['user_decision'])


def downgrade() -> None:
    op.drop_index('ix_audit_interactions_user_decision', table_name='audit_interactions')
    op.drop_column('audit_interactions', 'decision_at')
    op.drop_column('audit_interactions', 'user_decision')

